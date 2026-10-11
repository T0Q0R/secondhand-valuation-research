"""Full-field one-query regression ACO adaptation on frozen parent estimators."""
from __future__ import annotations

import argparse
import hashlib
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from threadpoolctl import threadpool_limits

from analyze_nested import close, id_hash, read, require, sha
from benchmark_public_pipeline import current_quote
from conditional_neighbor_head import ConditionalNeighborHead, encoder_groups
from run_all import evaluate_method, load_source, write_json
from run_crossfit import inner_split
from savval import ACTIONS, FEATURES, price_features

PRICES = {"masking": "masking_suppression", "robust": "robust_no_feedback"}
NEIGHBORS = [25, 10, 50]


def prepare_bank(model, guidance, fields, folder):
    public = price_features(guidance, fields)
    encoded = model.encoder.transform(public)
    available = guidance.loc[:, list(ACTIONS)].notna().to_numpy()
    predictions = np.empty((len(guidance), 16))
    for pattern in range(16):
        masked = public.copy()
        for a, field in enumerate(ACTIONS):
            if pattern & (1 << a):
                masked[field] = np.nan
        predictions[:, pattern], _ = current_quote(model, masked)
    targets = guidance.target_log.to_numpy()
    losses = (predictions - targets[:, None]) ** 2
    groups, weights = encoder_groups(model.encoder)
    folder.mkdir()
    for name, array in [("bank_encoded", encoded), ("bank_available", available),
                        ("bank_predictions", predictions), ("bank_log_targets", targets),
                        ("bank_loss_patterns", losses), ("coordinate_weights", weights)]:
        np.save(folder / f"{name}.npy", array)
    pd.DataFrame({"listing_id": guidance.listing_id}).to_csv(folder / "bank_ids.csv", index=False)
    write_json(folder / "field_groups.json", groups)
    return encoded, available, losses, groups, weights


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--partial", action="store_true")
    args = parser.parse_args()
    parent, output = args.run.resolve(), args.output.resolve()
    manifest = read(parent / "run_manifest.json")
    config, binding = manifest["config"], manifest["binding"]
    parent_complete = (parent / "completion.json").exists()
    if parent_complete:
        done = read(parent / "completion.json")
        require(done["status"] == "completed" and done["binding"] == binding, "Parent completion")
        require(sha(parent / "all_summary.csv") == done["summary_sha256"], "Parent aggregate hash")
    require(parent_complete or args.partial, "Incomplete parent requires explicit partial execution")
    for name in ["run_all.py", "run_crossfit.py", "savval.py"]:
        require(sha(Path(__file__).with_name(name)) == manifest["source_hashes"][name], "Parent core generation")
    pairs = [(d, s) for d in config["datasets"] for s in config["seeds"]
             if (parent / d / f"seed-{s}" / "evaluation_completion.json").exists()]
    require(bool(pairs), "No completed parent pairs")
    require(not parent_complete or len(pairs) == len(config["datasets"]) * len(config["seeds"]), "Incomplete completed parent")
    require(not output.exists(), "Immutable ACO outputs")
    output.mkdir(parents=True)
    snapshot = output / "source_snapshot"; snapshot.mkdir()
    files = [Path(__file__), *[Path(__file__).with_name(name) for name in
        ["conditional_neighbor_head.py", "benchmark_public_pipeline.py", "run_all.py", "run_crossfit.py", "savval.py", "analyze_nested.py"]],
        Path(__file__).parents[1] / "plan/aco-regression-comparator-v2.md",
        Path(__file__).parents[1] / "tests/test_conditional_neighbor_head.py"]
    hashes = {p.name: sha(p) for p in files}
    for source in files:
        (snapshot / source.name).write_bytes(source.read_bytes())
    write_json(output / "manifest.json", {"parent_binding": binding, "parent_config": config,
        "parent_complete_at_start": parent_complete, "frozen_parent_pairs": pairs,
        "source_hashes": hashes, "neighbors": NEIGHBORS, "prices": PRICES,
        "scope": "retrospective full-field ACO-1 regression/group/hard-cap adaptation; partial status explicit; no author code executed"})
    summaries, finished = [], []
    started = time.time()
    torch.set_num_threads(4)
    with threadpool_limits(limits=4):
        for dataset in config["datasets"]:
            selected = [seed for d, seed in pairs if d == dataset]
            if not selected:
                continue
            first, old_guidance, evaluation, provenance = load_source(dataset, config)
            training = pd.concat([first, old_guidance], ignore_index=True)
            estimator, guidance = inner_split(training, config["head_fitting_fraction"])
            require(not set(guidance.listing_id) & set(evaluation.listing_id), "Validation record in neighbor bank")
            folder = output / dataset;folder.mkdir()
            write_json(folder / "data_audit.json", {**provenance, "neighbor_bank_ids_sha256": id_hash(guidance.listing_id),
                "neighbor_bank_count": len(guidance), "estimator_ids_sha256": id_hash(estimator.listing_id)})
            for seed in selected:
                print(f"ACO-1 {dataset} seed {seed}", flush=True)
                saved = parent / dataset / f"seed-{seed}"
                receipt = read(saved / "evaluation_completion.json")
                require(receipt["binding"] == binding, "Parent pair binding")
                for key, name in [("outcomes_sha256", "per_listing_outcomes.csv.gz"), ("summary_sha256", "summary.csv")]:
                    require(sha(saved / name) == receipt[key], "Parent pair artifacts")
                fit = read(saved / "deployment_fit/fit_completion.json")
                require(fit["inputs"]["estimator_ids"] == id_hash(estimator.listing_id), "Exact parent estimator sample")
                require(fit["inputs"]["guidance_ids"] == id_hash(guidance.listing_id), "Exact parent guidance bank")
                parent_outcomes = pd.read_csv(saved / "per_listing_outcomes.csv.gz")
                own = folder / f"seed-{seed}";own.mkdir()
                model_hashes, rows, cell_summary = {}, [], []
                for price_name, price_key in PRICES.items():
                    model_path = saved / "deployment_models" / f"{price_key}.joblib"
                    model_hashes[price_key] = sha(model_path)
                    model, _, _ = joblib.load(model_path)
                    check_method = "masking_benefit" if price_name == "masking" else "robust_no_feedback"
                    clean = parent_outcomes[(parent_outcomes.method == check_method) & (parent_outcomes.budget == .1)].set_index("listing_id").loc[evaluation.listing_id].clean_prediction_log.to_numpy()
                    actual, _ = current_quote(model, price_features(evaluation, FEATURES[dataset]))
                    require(np.allclose(actual, clean, atol=2e-6, rtol=0), "Frozen price reproduction")
                    bank_folder = own / f"bank-{price_name}"
                    tick = time.time()
                    arrays = prepare_bank(model, guidance, FEATURES[dataset], bank_folder)
                    construction_seconds = time.time() - tick
                    reference_head = ConditionalNeighborHead(*arrays, k=25)
                    write_json(bank_folder / "construction.json", {"model_sha256": model_hashes[price_key],
                        "parent_binding": binding, "bank_count": len(guidance), "construction_seconds": construction_seconds,
                        "pattern_eligible_counts": reference_head.pattern_eligible_counts,
                        "bank_ood_new_hiding_counts": reference_head.bank_ood_new_hiding_counts,
                        "files": {p.name: sha(p) for p in bank_folder.iterdir() if p.is_file()}})
                    for neighbors in NEIGHBORS:
                        head = ConditionalNeighborHead(*arrays, k=neighbors)
                        budgets = config["budgets"] if neighbors == 25 else [.1]
                        method = f"{price_name}_aco1_k{neighbors}"
                        for budget in budgets:
                            tick = time.time()
                            outcomes, row = evaluate_method(method, model, head, "benefit", evaluation,
                                FEATURES[dataset], config, seed, budget)
                            outcomes["neighbor_count"] = neighbors;outcomes["price_key"] = price_key
                            rows.append(outcomes)
                            cell_summary.append({**row, "dataset": dataset, "neighbor_count": neighbors, "price_key": price_key,
                                "evaluation_seconds": time.time() - tick, **head.last_coverage})
                        del head
                    require(sha(model_path) == model_hashes[price_key], "Parent model changed during comparator execution")
                    del model, reference_head, arrays
                pd.concat(rows, ignore_index=True).to_csv(own / "outcomes.csv.gz", index=False)
                pd.DataFrame(cell_summary).to_csv(own / "summary.csv", index=False)
                write_json(own / "completion.json", {"status": "completed", "parent_binding": binding,
                    "parent_evaluation_receipt_sha256": sha(saved / "evaluation_completion.json"),
                    "source_model_hashes": model_hashes, "outcomes_sha256": sha(own / "outcomes.csv.gz"),
                    "summary_sha256": sha(own / "summary.csv"),
                    "bank_construction_hashes": {name: sha(own / f"bank-{name}/construction.json") for name in PRICES}})
                summaries.extend(cell_summary);finished.append([dataset, seed])
                pd.DataFrame(summaries).to_csv(output / "summary.csv", index=False)
                print(f"COMPLETED PAIR {dataset}/{seed}: {len(cell_summary)} cells", flush=True)
    require(hashes == {p.name: sha(p) for p in files}, "Frozen comparator generation changed")
    write_json(output / "completion.json", {"status": "completed", "parent_binding": binding,
        "full_parent_matrix": len(finished) == len(config["datasets"]) * len(config["seeds"]),
        "completed_source_seed_pairs": finished, "cells": len(summaries),
        "elapsed_seconds": time.time() - started, "summary_sha256": sha(output / "summary.csv")})
    print(f"COMPLETED ACO-1 adaptation {output}", flush=True)


if __name__ == "__main__":
    main()
