"""Execute SAV-Val development or frozen research configurations."""
from __future__ import annotations

import argparse
import copy
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

from savval import ACTIONS, FEATURES, ActionHeads, StateSpace, allocate, audit_deviations, fit_backbone, price_features, simulate_market, stable_rank, strategic_response

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")


def rank_subset(frame, count, salt):
    order = frame["listing_id"].map(lambda x: stable_rank(str(x), salt))
    return frame.loc[order.sort_values(kind="stable").index[:count]].reset_index(drop=True)


def load_source(name, config):
    if name == "synthetic":
        train = simulate_market(config["synthetic_train"], config["synthetic_generation_seed"])
        evaluation = simulate_market(config["synthetic_evaluation"], config["synthetic_evaluation_seed"])
        provenance = {"source": "stipulated synthetic generator", "generation_seed": config["synthetic_generation_seed"],
            "evaluation_generation_seed": config["synthetic_evaluation_seed"], "status": "development"}
    else:
        directory = PARENT / "experiments" / "data" / "processed" / f"{name}_bvival_v1" / "splits"
        train_path, evaluation_path = directory / "train.csv", directory / "validation.csv"
        train, evaluation = pd.read_csv(train_path), pd.read_csv(evaluation_path)
        provenance = {"source_train": str(train_path), "source_validation": str(evaluation_path),
            "train_sha256": sha(train_path), "validation_sha256": sha(evaluation_path),
            "status": "retrospective source / development validation", "original_test_labels_read": False}
    train = rank_subset(train, config["max_train"], "sav-val-train-v1")
    evaluation = rank_subset(evaluation, config["max_evaluation"], "sav-val-evaluation-order-v1")
    ids = set(train["listing_id"])
    if len(ids) != len(train) or len(set(evaluation["listing_id"])) != len(evaluation) or ids.intersection(evaluation["listing_id"]):
        raise ValueError("Non-unique or overlapping record identifiers")
    n_head = int(np.floor(config["head_fitting_fraction"] * len(train)))
    # This ordering is independent of labels. Keep action-target fitting rows
    # disjoint from every estimator's supervised-fitting rows.
    ordered = rank_subset(train, len(train), "sav-val-head-fitting-v1")
    head_frame, estimator_frame = ordered.iloc[:n_head].copy(), ordered.iloc[n_head:].copy()
    features = FEATURES[name]
    provenance.update({"source_train_count": len(train), "estimator_count": len(estimator_frame),
        "head_count": len(head_frame), "evaluation_count": len(evaluation), "features": features,
        "action_target_fit": "disjoint estimator/head sample split; not full multi-fold cross-fitting",
        "estimator_ids_sha256": hashlib.sha256("\n".join(estimator_frame["listing_id"]).encode()).hexdigest(),
        "head_ids_sha256": hashlib.sha256("\n".join(head_frame["listing_id"]).encode()).hexdigest(),
        "evaluation_ids_sha256": hashlib.sha256("\n".join(evaluation["listing_id"]).encode()).hexdigest()})
    return estimator_frame, head_frame, evaluation, provenance


def fit_heads(model, frame, columns, config, seed):
    pred, encoded, valid = model.predict(price_features(frame, columns))
    return ActionHeads(config["head_trees"], seed).fit(encoded, pred, valid,
        frame["target_log"].to_numpy(), model.space,
        reported_missing=model.space.reported_missing(frame))


def fit_methods(estimator_frame, head_frame, columns, config, seed, directory):
    x = price_features(estimator_frame, columns)
    y = estimator_frame["target_log"].to_numpy()
    space = StateSpace.build(config["maximum_hidden"])
    masked = fit_backbone(x, y, space, config, seed, augment=True)
    native = fit_backbone(x, y, space, config, seed, augment=False)
    head = fit_heads(masked, head_frame, columns, config, seed)
    methods = {
        "native_no_audit": (native, head, "none"),
        "masking_no_audit": (masked, head, "none"),
        "masking_random": (masked, head, "random"),
        "masking_fixed": (masked, head, "fixed"),
        "masking_risk": (masked, head, "risk"),
        "masking_benefit": (masked, head, "benefit"),
        "masking_suppression": (masked, head, "suppression"),
    }
    trace = {}
    static = copy.deepcopy(masked)
    print("  fitting robust without feedback", flush=True)
    trace["robust_no_feedback"] = static.train_residual(x, y, config, seed, policy=None)
    static_head = fit_heads(static, head_frame, columns, config, seed)
    methods["robust_no_feedback"] = (static, static_head, "suppression")
    for variant, beta, kind, adaptive in [
        ("sav_val", config["gap_penalty_weight"], "suppression", True),
        ("sav_no_gap", 0.0, "suppression", True),
        ("sav_benefit_head", config["gap_penalty_weight"], "benefit", True),
        ("sav_preaudit_attacker", config["gap_penalty_weight"], "suppression", False),
    ]:
        print(f"  fitting {variant}", flush=True)
        model, current_head = copy.deepcopy(masked), head
        trace[variant] = []
        rounds = config["feedback_rounds"]
        for iteration in range(rounds):
            epochs = config["residual_epochs"] // rounds + int(iteration < config["residual_epochs"] % rounds)
            logs = model.train_residual(x, y, config, seed + iteration, current_head,
                gap_weight=beta, policy_kind=kind, policy_aware=adaptive, epochs=epochs)
            current_head = fit_heads(model, head_frame, columns, config, seed)
            trace[variant].append({"round": iteration + 1, "training": logs,
                "head_targets": current_head.target_summary})
        methods[variant] = (model, current_head, kind)
    model_dir = directory / "models"
    model_dir.mkdir()
    for name, fitted in methods.items():
        if name in {"native_no_audit", "masking_suppression", "robust_no_feedback", "sav_val", "sav_no_gap", "sav_benefit_head", "sav_preaudit_attacker"}:
            joblib.dump(fitted, model_dir / f"{name}.joblib", compress=3)
    write_json(directory / "training_trace.json", trace)
    return methods


def random_scores(ids, space, reported_missing):
    # Reproducible random-priority control. The adversary knows this realized
    # table: no claim of hidden-randomness deterrence is made.
    values = np.array([int(stable_rank(str(x), "sav-val-random")[:16], 16) % (2**32) for x in ids])
    priorities = np.stack([np.random.default_rng(int(k)).random(len(ACTIONS)) for k in values])
    score = np.broadcast_to(priorities[:, None, :], reported_missing.shape)
    return np.where(reported_missing, score, -np.inf)


def evaluate_method(name, model, head, kind, frame, columns, config, seed, budget, *, fixed_states=None):
    target = frame["target_log"].to_numpy()
    pred, x, valid = model.predict(price_features(frame, columns))
    missing = model.space.reported_missing(frame)
    scores = random_scores(frame["listing_id"], model.space, missing) if kind == "random" else head.score(x, pred, model.space, kind, reported_missing=missing)
    rows = []
    for batch, start in enumerate(range(0, len(frame), config["batch_size"])):
        end = min(start + config["batch_size"], len(frame))
        batchpred, batchscore, batchvalid = pred[start:end], scores[start:end], valid[start:end]
        if fixed_states is None:
            response = strategic_response(batchpred, batchscore, batchvalid, model.space,
                budget=budget, sweeps=config["attacker_sweeps"], restarts=config["attacker_restarts"], cost=config["concealment_cost_log"])
        else:
            states = fixed_states[start:end].copy()
            final, chosen, _ = allocate(batchscore, states, model.space, int(np.floor(budget * (end - start))))
            response = {"states": states, "final_state": final, "action": chosen,
                "regret": np.zeros(end - start), "sweeps": 0,
                "best_response_converged": False, "cycle_detected": False,
                "capacity": int(np.floor(budget * (end - start)))}
        honest = batchpred[:, 0]
        final = batchpred[np.arange(end - start), response["final_state"]]
        y = target[start:end]
        if fixed_states is None:
            audit = audit_deviations(batchpred, batchscore, batchvalid, response["states"], model.space,
                response["capacity"], config["concealment_cost_log"])
            if not np.allclose(audit["regret"], response["regret"], atol=1e-8):
                raise AssertionError("Search regret differs from exhaustive allocator check")
            envelope = np.maximum(audit["maximum_quote"] - honest, 0)
        else:
            envelope = np.full(len(y), np.nan)
        true_price, clean_price, attacked_price = np.expm1(y), np.expm1(honest), np.expm1(final)
        for k in range(end - start):
            rows.append({"listing_id": frame.iloc[start + k]["listing_id"], "batch": batch,
                "method": name, "seed": seed, "budget": budget,
                "state": int(response["states"][k]), "final_state": int(response["final_state"][k]),
                "action": int(response["action"][k]), "hidden_count": int(model.space.masks[response["states"][k]].sum()),
                "query_succeeded": bool(response["action"][k] >= 0 and model.space.masks[response["states"][k], response["action"][k]]),
                "clean_prediction_log": float(honest[k]), "attacked_prediction_log": float(final[k]), "target_log": float(y[k]),
                "clean_sq_log_loss": float((honest[k] - y[k]) ** 2), "attack_sq_log_loss": float((final[k] - y[k]) ** 2),
                "clean_absolute_error": float(abs(clean_price[k] - true_price[k])), "attack_absolute_error": float(abs(attacked_price[k] - true_price[k])),
                "positive_log_inflation": float(max(final[k] - honest[k], 0)),
                "positive_price_inflation": float(max(attacked_price[k] - clean_price[k], 0)),
                "attack_signed_log_error": float(final[k] - y[k]),
                "clean_signed_log_error": float(honest[k] - y[k]),
                "clean_underprediction_log": float(max(y[k] - honest[k], 0)),
                "best_response_regret_log": float(response["regret"][k]),
                "unilateral_inflation_envelope_log": float(envelope[k]),
                "batch_cycle_detected": response.get("cycle_detected", False),
                "batch_converged": response["best_response_converged"], "batch_sweeps": response["sweeps"]})
        if sum(response["action"] >= 0) > response["capacity"]:
            raise AssertionError("Evaluation exceeded batch budget")
    outcomes = pd.DataFrame(rows)
    summary = {"method": name, "seed": seed, "budget": budget, "n": len(outcomes),
        "clean_rmsle": float(np.sqrt(outcomes.clean_sq_log_loss.mean())),
        "attack_rmsle": float(np.sqrt(outcomes.attack_sq_log_loss.mean())),
        "clean_mae": float(outcomes.clean_absolute_error.mean()), "attack_mae": float(outcomes.attack_absolute_error.mean()),
        "mean_positive_log_inflation": float(outcomes.positive_log_inflation.mean()),
        "mean_positive_price_inflation": float(outcomes.positive_price_inflation.mean()),
        "clean_signed_log_bias": float(outcomes.clean_signed_log_error.mean()),
        "attack_signed_log_bias": float(outcomes.attack_signed_log_error.mean()),
        "clean_underprediction_log": float(outcomes.clean_underprediction_log.mean()),
        "actual_audit_fraction": float((outcomes.action >= 0).mean()), "hiding_fraction": float((outcomes.hidden_count > 0).mean()),
        "max_remaining_response_regret": float(outcomes.best_response_regret_log.max()),
        "mean_remaining_response_regret": float(outcomes.best_response_regret_log.mean()),
        "mean_unilateral_inflation_envelope_log": float(outcomes.unilateral_inflation_envelope_log.mean()),
        "failed_query_fraction": float(((outcomes.action >= 0) & ~outcomes.query_succeeded).mean()),
        "nonconverged_batch_fraction": float(1 - outcomes.groupby("batch").batch_converged.first().mean()) if fixed_states is None else None}
    return outcomes, summary


def cluster_intervals(outcomes, repetitions, seed):
    primary = outcomes[outcomes.budget == 0.1]
    comparison = primary[primary.method.isin(["sav_val", "sav_benefit_head"])]
    if comparison.empty:
        return {}
    table = comparison.pivot(index="listing_id", columns="method", values="positive_log_inflation")
    batches = comparison.drop_duplicates("listing_id").set_index("listing_id")["batch"]
    delta = table["sav_benefit_head"] - table["sav_val"]
    totals = pd.DataFrame({"delta": delta, "batch": batches}).groupby("batch").delta.agg(["sum", "count"])
    rng = np.random.default_rng(seed)
    sampled = rng.integers(0, len(totals), (repetitions, len(totals)))
    distribution = totals["sum"].to_numpy()[sampled].sum(axis=1) / totals["count"].to_numpy()[sampled].sum(axis=1)
    return {"comparison": "sav_benefit_head minus sav_val", "metric": "mean positive log-price inflation",
        "difference": float(delta.mean()), "conditional_batch_cluster_95_interval": np.quantile(distribution, [0.025, 0.975]).tolist(),
        "clusters": len(totals), "repetitions": repetitions, "status": "development conditional on fitted estimators and realized attack searches"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text())
    output = ROOT / config["output"]
    if output.exists():
        raise FileExistsError(f"Refuse to overwrite experiment evidence: {output}")
    output.mkdir(parents=True)
    torch.set_num_threads(4)
    started = time.time()
    environment = {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
        "device": "CPU", "torch_threads": 4,
        "versions": {m: importlib.metadata.version(m) for m in ["numpy", "pandas", "scikit-learn", "catboost", "torch", "scipy", "joblib"]}}
    source_hashes = {p.name: sha(p) for p in [Path(__file__), ROOT / "experiments/savval.py", config_path, ROOT / "plan/protocol.md"]}
    write_json(output / "run_manifest.json", {"status": "running", "protocol": config, "environment": environment,
        "source_hashes_before_run": source_hashes, "started_unix": started})
    all_summaries = []
    try:
        for dataset in config["datasets"]:
            estimator, head_frame, evaluation, provenance = load_source(dataset, config)
            dataset_dir = output / dataset
            dataset_dir.mkdir()
            write_json(dataset_dir / "data_audit.json", provenance)
            for seed in config["seeds"]:
                seed_dir = dataset_dir / f"seed-{seed}"
                seed_dir.mkdir()
                print(f"DATASET {dataset} seed {seed}: estimator={len(estimator)} head={len(head_frame)} evaluation={len(evaluation)}", flush=True)
                fit_start = time.time()
                methods = fit_methods(estimator, head_frame, FEATURES[dataset], config, seed, seed_dir)
                write_json(seed_dir / "fitting_time.json", {"seconds": time.time() - fit_start})
                combined, summaries = [], []
                for name, (model, heads, kind) in methods.items():
                    print(f"  evaluating {name}", flush=True)
                    for budget in config["budgets"]:
                        if kind == "none" and budget != 0:
                            continue
                        inference_start = time.time()
                        rows, summary = evaluate_method(name, model, heads, kind, evaluation, FEATURES[dataset], config, seed, budget)
                        summary.update({"dataset": dataset, "evaluation_seconds": time.time() - inference_start})
                        combined.append(rows)
                        summaries.append(summary)
                outcomes = pd.concat(combined, ignore_index=True)
                outcomes.to_csv(seed_dir / "per_listing_outcomes.csv.gz", index=False, compression="gzip")
                pd.DataFrame(summaries).to_csv(seed_dir / "summary.csv", index=False)
                write_json(seed_dir / "primary_interval.json", cluster_intervals(outcomes, config["bootstrap_repetitions"], seed))
                # Same disclosed states transferred across methods: a diagnostic,
                # distinguished from each method's own adaptive seller response.
                selected = outcomes[(outcomes.method == "sav_val") & (outcomes.budget == 0.1)]
                if not selected.empty:
                    states = selected.set_index("listing_id").loc[evaluation.listing_id, "state"].to_numpy()
                    transfer = []
                    for name in ["masking_benefit", "robust_no_feedback", "sav_val", "sav_benefit_head"]:
                        model, heads, kind = methods[name]
                        _, summary = evaluate_method(name, model, heads, kind, evaluation, FEATURES[dataset], config, seed, 0.1, fixed_states=states)
                        transfer.append(summary)
                    pd.DataFrame(transfer).to_csv(seed_dir / "common_attack_transfer.csv", index=False)
                all_summaries.extend(summaries)
                pd.DataFrame(all_summaries).to_csv(output / "all_summary.csv", index=False)
                print(pd.DataFrame(summaries).query("budget == 0.1")[["method", "clean_mae", "attack_mae", "mean_positive_log_inflation", "actual_audit_fraction", "nonconverged_batch_fraction"]].to_string(index=False), flush=True)
        current_hashes = {p.name: sha(p) for p in [Path(__file__), ROOT / "experiments/savval.py", config_path, ROOT / "plan/protocol.md"]}
        if current_hashes != source_hashes:
            raise RuntimeError("Experiment source changed during execution")
        write_json(output / "completion.json", {"status": "completed", "elapsed_seconds": time.time() - started,
            "summary_sha256": sha(output / "all_summary.csv"), "source_hashes_after_run": current_hashes,
            "evidence_status": config["status"], "original_test_labels_read": False})
        print(f"COMPLETED {output}", flush=True)
    except BaseException as error:
        write_json(output / "failure.json", {"status": "failed", "type": type(error).__name__, "message": str(error), "elapsed_seconds": time.time() - started})
        raise


if __name__ == "__main__":
    main()
