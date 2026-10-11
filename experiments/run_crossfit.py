"""Nested acquisition-target cross-fitting with resumable fold checkpoints.

No outer-held-out outcomes enter estimator fitting or feedback-guidance heads.
The deployment action heads learn from these outer predictions. Evaluation
still uses existing validation sources and is explicitly retrospective.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.metadata
import json
import platform
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch

import run_all
from run_all import ROOT, FEATURES, cluster_intervals, evaluate_method, fit_methods, load_source, rank_subset, sha, write_json
from savval import ActionHeads, price_features, stable_rank

MODEL_FILES = ["native_no_audit", "masking_suppression", "robust_no_feedback", "sav_val", "sav_no_gap", "sav_benefit_head", "sav_preaudit_attacker"]


def identifiers(frame):
    return hashlib.sha256("\n".join(frame.listing_id).encode()).hexdigest()


def fold_assignments(frame, folds):
    if folds < 2 or len(frame) < folds:
        raise ValueError("Need at least two nonempty outer folds")
    hashes = frame.listing_id.map(lambda x: stable_rank(str(x), "sav-val-outer-v2"))
    order = np.argsort(hashes.to_numpy(), kind="stable")
    assigned = np.empty(len(frame), dtype=int)
    assigned[order] = np.arange(len(frame)) % folds
    return assigned


def inner_split(frame, fraction):
    ordered = rank_subset(frame, len(frame), "sav-val-inner-guidance-v2")
    count = int(np.floor(fraction * len(frame)))
    if count < 2 or count >= len(frame) - 2:
        raise ValueError("Insufficient inner-fitting records")
    return ordered.iloc[count:].copy(), ordered.iloc[:count].copy()


def read_methods(directory):
    saved = {name: joblib.load(directory / "models" / f"{name}.joblib") for name in MODEL_FILES}
    masked, head, _ = saved["masking_suppression"]
    for name, kind in [("masking_no_audit", "none"), ("masking_random", "random"),
                       ("masking_fixed", "fixed"), ("masking_risk", "risk"), ("masking_benefit", "benefit")]:
        saved[name] = (masked, head, kind)
    return saved


def checkpoint_fit(estimator, guidance, columns, config, seed, directory, binding):
    expected = {"binding": binding, "seed": seed, "estimator_ids": identifiers(estimator),
                "guidance_ids": identifiers(guidance),
                "estimator_content": hashlib.sha256(estimator.to_csv(index=False).encode()).hexdigest(),
                "guidance_content": hashlib.sha256(guidance.to_csv(index=False).encode()).hexdigest()}
    receipt_path = directory / "fit_completion.json"
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        if receipt["inputs"] != expected:
            raise RuntimeError("Checkpoint input binding changed")
        for name, digest in receipt["files"].items():
            if sha(directory / name) != digest:
                raise RuntimeError(f"Checkpoint artifact changed: {name}")
        print(f"  reusing completed {directory.name}", flush=True)
        return read_methods(directory)
    if directory.exists():
        # Only a confirmed terminal/restart path may reach this. Preserve the
        # incomplete directory instead of replacing historical partial files.
        archived = directory.with_name(directory.name + f"-incomplete-{time.time_ns()}")
        directory.rename(archived)
    directory.mkdir(parents=True)
    start = time.time()
    methods = fit_methods(estimator, guidance, columns, config, seed, directory)
    files = [directory / "models" / f"{name}.joblib" for name in MODEL_FILES]
    files.append(directory / "training_trace.json")
    write_json(receipt_path, {"inputs": expected, "seconds": time.time() - start,
        "files": {str(path.relative_to(directory)): sha(path) for path in files}})
    return methods


def outer_fit(train, columns, config, seed, directory, binding):
    assigned = fold_assignments(train, config["outer_folds"])
    # Derive the width from the declared state space rather than the constant
    # primary-case width when maximum-hidden sensitivity is requested.
    from savval import StateSpace
    states_count = len(StateSpace.build(config["maximum_hidden"]).masks)
    predictions = {name: np.empty((len(train), states_count), dtype=float) for name in MODEL_FILES}
    receipts = []
    for fold in range(config["outer_folds"]):
        training = train.loc[assigned != fold].copy()
        heldout = train.loc[assigned == fold].copy()
        estimator, guidance = inner_split(training, config["head_fitting_fraction"])
        if set(heldout.listing_id) & (set(estimator.listing_id) | set(guidance.listing_id)):
            raise AssertionError("Outer holdout used in the fitted loop")
        print(f"  OUTER {fold}: estimator={len(estimator)} guidance={len(guidance)} holdout={len(heldout)}", flush=True)
        models = checkpoint_fit(estimator, guidance, columns, config, seed,
            directory / f"outer-{fold}", binding)
        for name in MODEL_FILES:
            model, _, _ = models[name]
            # Outcomes are not passed to prediction or preprocessing.
            prediction, _, _ = model.predict(price_features(heldout, columns))
            predictions[name][assigned == fold] = prediction
        receipts.append({"fold": fold, "estimator_ids": identifiers(estimator),
            "guidance_ids": identifiers(guidance), "holdout_ids": identifiers(heldout),
            "estimator_count": len(estimator), "guidance_count": len(guidance),
            "heldout_count": len(heldout), "heldout_outcomes_used_for_fitting": False})
        del models
    np.savez_compressed(directory / "outer_predictions.npz", **predictions)
    pd.DataFrame({"listing_id": train.listing_id, "outer_fold": assigned}).to_csv(directory / "outer_assignments.csv", index=False)
    write_json(directory / "outer_audit.json", {"folds": receipts,
        "rows": len(train), "all_records_predicted_out_of_loop": True,
        "prediction_sha256": sha(directory / "outer_predictions.npz"),
        "assignment_sha256": sha(directory / "outer_assignments.csv")})
    return predictions


def deployable_heads(methods, predictions, train, columns, config, seed):
    updated = {}
    cached = {}
    for name, (model, _, kind) in methods.items():
        price_key = name if name in predictions else "masking_suppression"
        if price_key not in cached:
            _, encoded, valid = model.predict(price_features(train, columns))
            cached[price_key] = ActionHeads(config["head_trees"], seed).fit(encoded, predictions[price_key], valid,
                train.target_log.to_numpy(), model.space,
                reported_missing=model.space.reported_missing(train))
        head = cached[price_key]
        updated[name] = (model, head, kind)
    return updated


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text())
    output = ROOT / config["output"]
    files = [Path(__file__), ROOT / "experiments/run_all.py", ROOT / "experiments/savval.py",
             config_path, ROOT / "plan/protocol-v2.md"]
    hashes = {p.name: sha(p) for p in files}
    binding = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    if output.exists() and not args.resume:
        raise FileExistsError("Use a new output directory, or explicit resume of a terminal run")
    if (output / "completion.json").exists():
        raise RuntimeError("A completed research run is immutable")
    output.mkdir(parents=True, exist_ok=True)
    # A live OS file lock, rather than a stale PID/JSON file, prevents double
    # fitting even if a second invocation mistakenly requests resume.
    lock = (output / "execution.lock").open("a+")
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    started = time.time()
    manifest_path = output / "run_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest["source_hashes"] != hashes:
            raise RuntimeError("Frozen sources changed; do not mix checkpoint generations")
    else:
        write_json(manifest_path, {"config": config, "source_hashes": hashes, "binding": binding,
            "started_unix": started, "status": "running", "python": sys.version,
            "executable": sys.executable, "platform": platform.platform(),
            "versions": {m: importlib.metadata.version(m) for m in ["numpy", "pandas", "scikit-learn", "catboost", "torch"]}})
        snapshot = output / "source_snapshot"
        snapshot.mkdir()
        for path in files:
            (snapshot / path.name).write_bytes(path.read_bytes())
    torch.set_num_threads(4)
    all_summary = []
    for dataset in config["datasets"]:
        original_est, original_head, evaluation, provenance = load_source(dataset, config)
        train = pd.concat([original_est, original_head], ignore_index=True)
        train = rank_subset(train, len(train), "sav-val-cf-training-order-v2")
        dataset_dir = output / dataset
        dataset_dir.mkdir(exist_ok=True)
        data_audit = {**provenance,
            "target_generation": "nested outer cross-fitting of complete feedback loop",
            "evaluation_status": "retrospective/development validation"}
        data_audit_path = dataset_dir / "data_audit.json"
        if data_audit_path.exists() and json.loads(data_audit_path.read_text()) != data_audit:
            raise RuntimeError("Source data/cohort changed during resume")
        if not data_audit_path.exists():
            write_json(data_audit_path, data_audit)
        for seed in config["seeds"]:
            directory = dataset_dir / f"seed-{seed}"
            directory.mkdir(exist_ok=True)
            result_receipt = directory / "evaluation_completion.json"
            if result_receipt.exists():
                receipt = json.loads(result_receipt.read_text())
                if receipt["binding"] != binding or receipt["summary_sha256"] != sha(directory / "summary.csv") or receipt["data_audit_sha256"] != sha(data_audit_path):
                    raise RuntimeError("Evaluation checkpoint changed")
                for file_key, artifact in [("outcomes_sha256", "per_listing_outcomes.csv.gz"), ("outer_audit_sha256", "outer_audit.json")]:
                    if receipt[file_key] != sha(directory / artifact):
                        raise RuntimeError("Evaluation checkpoint artifact changed")
                all_summary.extend(pd.read_csv(directory / "summary.csv").to_dict("records"))
                continue
            print(f"DATASET {dataset} seed {seed}: {len(train)} training / {len(evaluation)} evaluation", flush=True)
            predictions = outer_fit(train, FEATURES[dataset], config, seed, directory, binding)
            estimator, guidance = inner_split(train, config["head_fitting_fraction"])
            methods = checkpoint_fit(estimator, guidance, FEATURES[dataset], config, seed,
                directory / "deployment_fit", binding)
            methods = deployable_heads(methods, predictions, train, FEATURES[dataset], config, seed)
            deployed = directory / "deployment_models"
            deployed.mkdir(exist_ok=True)
            for name in MODEL_FILES:
                joblib.dump(methods[name], deployed / f"{name}.joblib", compress=3)
            combined, summaries = [], []
            for name, (model, head, kind) in methods.items():
                print(f"  EVALUATE {name}", flush=True)
                for budget in config["budgets"]:
                    if kind == "none" and budget != 0:
                        continue
                    tick = time.time()
                    rows, summary = evaluate_method(name, model, head, kind, evaluation,
                        FEATURES[dataset], config, seed, budget)
                    combined.append(rows)
                    summaries.append({**summary, "dataset": dataset, "evaluation_seconds": time.time() - tick})
            outcomes = pd.concat(combined, ignore_index=True)
            outcomes.to_csv(directory / "per_listing_outcomes.csv.gz", index=False)
            pd.DataFrame(summaries).to_csv(directory / "summary.csv", index=False)
            write_json(directory / "primary_interval.json", cluster_intervals(outcomes, config["bootstrap_repetitions"], seed))
            primary = outcomes[(outcomes.method == "sav_val") & (outcomes.budget == .1)]
            if not primary.empty:
                fixed = primary.set_index("listing_id").loc[evaluation.listing_id, "state"].to_numpy()
                transfer = []
                for name in ["masking_benefit", "robust_no_feedback", "sav_val", "sav_benefit_head"]:
                    model, head, kind = methods[name]
                    _, row = evaluate_method(name, model, head, kind, evaluation,
                        FEATURES[dataset], config, seed, .1, fixed_states=fixed)
                    transfer.append(row)
                pd.DataFrame(transfer).to_csv(directory / "common_attack_transfer.csv", index=False)
            write_json(result_receipt, {"binding": binding, "summary_sha256": sha(directory / "summary.csv"),
                "data_audit_sha256": sha(data_audit_path),
                "outcomes_sha256": sha(directory / "per_listing_outcomes.csv.gz"),
                "outer_audit_sha256": sha(directory / "outer_audit.json")})
            all_summary.extend(summaries)
            pd.DataFrame(all_summary).to_csv(output / "all_summary.csv", index=False)
            print(pd.DataFrame(summaries).query("budget == .1")[["method", "clean_mae", "mean_positive_log_inflation", "failed_query_fraction"]].to_string(index=False), flush=True)
    if {p.name: sha(p) for p in files} != hashes:
        raise RuntimeError("Frozen sources changed during execution")
    pd.DataFrame(all_summary).to_csv(output / "all_summary.csv", index=False)
    write_json(output / "completion.json", {"status": "completed", "binding": binding,
        "elapsed_seconds_this_invocation": time.time() - started,
        "summary_sha256": sha(output / "all_summary.csv"), "status_of_evidence": config["status"]})
    print(f"COMPLETED {output}", flush=True)


if __name__ == "__main__":
    main()
