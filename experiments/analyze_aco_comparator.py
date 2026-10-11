"""Audit full-field ACO-1 adaptations and retain their declared scope."""
from __future__ import annotations

import argparse
import itertools
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import torch

from analyze_nested import close, conditional_cluster_interval, id_hash, read, require, sha
from analyze_saved_diagnostics import audit_cell, masks
from benchmark_public_pipeline import current_quote
from conditional_neighbor_head import ConditionalNeighborHead
from run_all import load_source, write_json
from run_crossfit import inner_split
from savval import ACTIONS, FEATURES, price_features

PRICES = {"masking": "masking_suppression", "robust": "robust_no_feedback"}


def independent_scores(bank, available, losses, groups, weights, query, missing, k):
    unseen = {ACTIONS[j] for j in np.flatnonzero(missing)}
    blocks = sorted([block for field, block in groups.items() if field not in unseen], key=min)
    eligible = np.flatnonzero(available[:, ~missing].all(1))
    scores = np.full(4, -np.inf)
    if not len(eligible):
        return scores
    # Direct coordinate differences, independently of the head's Gram formula.
    bank, query = np.asarray(bank, float), np.asarray(query, float)
    distance = np.zeros(len(eligible))
    for block in blocks:
        for j in block:
            distance += weights[j] * np.square(bank[eligible, j] - query[j])
    nearest = eligible[np.argsort(distance, kind="stable")[:min(k, len(eligible))]]
    pattern = int(missing.astype(int) @ (1 << np.arange(4)))
    for a in np.flatnonzero(missing):
        scores[a] = (losses[nearest, pattern] - losses[nearest, pattern & ~(1 << a)]).mean()
    return scores


def independent_allocation(pred, scores, states, lattice, capacity):
    chosen_scores = scores[np.arange(len(states)), states]
    field = chosen_scores.argmax(1)
    merit = chosen_scores[np.arange(len(states)), field]
    order = sorted(range(len(states)), key=lambda i: (-merit[i], i))
    selected = [i for i in order if np.isfinite(merit[i]) and merit[i] > 0][:capacity]
    final = states.copy()
    chosen = np.full(len(states), -1, int)
    lookup = {tuple(mask): i for i, mask in enumerate(lattice)}
    for i in selected:
        chosen[i] = field[i]
        after = lattice[states[i]].copy()
        after[field[i]] = False
        final[i] = lookup[tuple(after)]
    return pred[np.arange(len(states)), final], chosen, final


def first_batch_unilateral(outcomes, pred, scores, available, lattice, cost):
    rows = outcomes[outcomes.batch == outcomes.batch.min()].copy()
    n = len(rows)
    states = rows.state.to_numpy(int)
    pred, scores, available = pred[:n], scores[:n], available[:n]
    capacity = int(np.floor(.1 * n))
    quote, chosen, final = independent_allocation(pred, scores, states, lattice, capacity)
    require(np.array_equal(chosen, rows.action), "Independent allocation differs")
    require(np.array_equal(final, rows.final_state), "Independent replay differs")
    close(quote, rows.attacked_prediction_log, "Independent primary quotes differ")
    net = quote - cost * lattice[states].sum(1)
    regret, envelope = np.zeros(n), quote.copy()
    for i in range(n):
        for state in range(len(lattice)):
            if (lattice[state] & ~available[i]).any():
                continue
            trial = states.copy();trial[i] = state
            candidate, _, _ = independent_allocation(pred, scores, trial, lattice, capacity)
            regret[i] = max(regret[i], candidate[i] - cost * lattice[state].sum() - net[i])
            envelope[i] = max(envelope[i], candidate[i])
    close(regret, rows.best_response_regret_log, "Independent unilateral regret differs")
    close(np.maximum(envelope - pred[:, 0], 0), rows.unilateral_inflation_envelope_log, "Independent unilateral envelope differs")
    return {"n": n, "candidate_moves_checked": int(sum((~(lattice & ~a).any(1)).sum() for a in available)),
            "maximum_regret": float(regret.max()), "allocation_and_envelope_match": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, parent, output = (p.resolve() for p in [args.run, args.parent, args.output])
    manifest, done = read(root / "manifest.json"), read(root / "completion.json")
    old_manifest = read(parent / "run_manifest.json")
    config, binding = old_manifest["config"], old_manifest["binding"]
    require(done["status"] == "completed" and done["parent_binding"] == manifest["parent_binding"] == binding, "Completed adaptation/binding")
    require(config == manifest["parent_config"], "Parent configuration")
    pairs = list(map(tuple, manifest["frozen_parent_pairs"]))
    require(pairs == list(map(tuple, done["completed_source_seed_pairs"])), "Frozen pair schedule")
    require(set(pairs) <= {(d, s) for d in config["datasets"] for s in config["seeds"]}, "Extra source/seed")
    require(len(set(pairs)) == len(pairs), "Duplicate pair")
    require(done["full_parent_matrix"] == (len(pairs) == len(config["datasets"]) * len(config["seeds"])), "Partial/full scope metadata")
    require(manifest["neighbors"] == [25, 10, 50] and manifest["prices"] == PRICES, "Prespecified adaptation")
    require(sha(root / "summary.csv") == done["summary_sha256"], "Aggregate summary")
    for name, digest in manifest["source_hashes"].items():
        require(sha(root / "source_snapshot" / name) == digest, "Comparator snapshot " + name)
    for name in ["run_all.py", "run_crossfit.py", "savval.py"]:
        require(sha(Path(__file__).with_name(name)) == old_manifest["source_hashes"][name], "Source reconstruction generation")
    require(sha(Path(__file__).with_name("conditional_neighbor_head.py")) == manifest["source_hashes"]["conditional_neighbor_head.py"], "Scoring generation")
    require(not output.exists(), "Immutable analysis output")
    aggregate = pd.read_csv(root / "summary.csv")
    torch.set_num_threads(4)
    checks, bank_checks, unilateral, listings, parents, summaries = [], [], [], [], [], []
    lattice = masks(config["maximum_hidden"])
    with threadpool_limits(limits=4):
        for dataset in config["datasets"]:
            seeds = [s for d, s in pairs if d == dataset]
            if not seeds:
                continue
            first, old_guidance, evaluation, _ = load_source(dataset, config)
            estimator, guidance = inner_split(pd.concat([first, old_guidance], ignore_index=True), config["head_fitting_fraction"])
            require(not set(guidance.listing_id) & set(evaluation.listing_id), "Evaluation item in bank")
            for seed in seeds:
                folder, old_folder = root / dataset / f"seed-{seed}", parent / dataset / f"seed-{seed}"
                receipt, old_receipt = read(folder / "completion.json"), read(old_folder / "evaluation_completion.json")
                require(sha(old_folder / "evaluation_completion.json") == receipt["parent_evaluation_receipt_sha256"], "Parent receipt")
                require(sha(old_folder / "per_listing_outcomes.csv.gz") == old_receipt["outcomes_sha256"], "Parent outcomes")
                require(sha(folder / "outcomes.csv.gz") == receipt["outcomes_sha256"], "Comparator outcomes")
                require(sha(folder / "summary.csv") == receipt["summary_sha256"], "Comparator summary")
                old = pd.read_csv(old_folder / "per_listing_outcomes.csv.gz")
                outcomes, reported = pd.read_csv(folder / "outcomes.csv.gz"), pd.read_csv(folder / "summary.csv")
                require(not reported.duplicated(["method", "budget"]).any(), "Duplicate cells")
                expected = {(f"{price}_aco1_k{k}", b) for price, k in itertools.product(PRICES, [25, 10, 50])
                            for b in (config["budgets"] if k == 25 else [.1])}
                require(set(zip(reported.method, reported.budget)) == expected == set(zip(outcomes.method, outcomes.budget)), "Incomplete adaptation matrix")
                for (method, budget), rows in outcomes.groupby(["method", "budget"], sort=True):
                    require(set(rows.listing_id) == set(evaluation.listing_id), "Complete source cohort")
                    rows = rows.set_index("listing_id").loc[evaluation.listing_id].reset_index()
                    close(rows.target_log, evaluation.target_log, "Source outcome alignment")
                    close(rows.batch, np.arange(len(evaluation)) // config["batch_size"], "Shared batch alignment")
                    require((rows.seed == seed).all(), "Seed labels")
                    available = evaluation[list(ACTIONS)].notna().to_numpy()
                    require(not (lattice[rows.state.to_numpy(int)] & ~available).any(), "Withholding originally unavailable data")
                    missing = ~available | lattice[rows.state.to_numpy(int)]
                    for i in np.flatnonzero(rows.action.to_numpy() >= 0):
                        require(missing[i, int(rows.action.iloc[i])], "Query nonmissing public field")
                    row = reported[(reported.method == method) & (reported.budget == budget)].iloc[0]
                    count = audit_cell(rows, row, config["maximum_hidden"], config["batch_size"])
                    checks.append({"dataset": dataset, "seed": seed, "method": method, "budget": budget, "metrics_recomputed": count})
                for price, price_key in PRICES.items():
                    model_path = old_folder / "deployment_models" / f"{price_key}.joblib"
                    require(sha(model_path) == receipt["source_model_hashes"][price_key], "Frozen price model")
                    model, _, _ = joblib.load(model_path)
                    bank_folder = folder / f"bank-{price}"
                    construction = read(bank_folder / "construction.json")
                    require(sha(bank_folder / "construction.json") == receipt["bank_construction_hashes"][price], "Construction receipt")
                    require(construction["model_sha256"] == sha(model_path) and construction["parent_binding"] == binding, "Bank/model binding")
                    for name, digest in construction["files"].items():
                        require(sha(bank_folder / name) == digest, "Bank artifact hash")
                    ids = pd.read_csv(bank_folder / "bank_ids.csv")
                    require(ids.listing_id.tolist() == guidance.listing_id.tolist(), "Exact guidance bank")
                    fit = read(old_folder / "deployment_fit/fit_completion.json")
                    require(fit["inputs"]["estimator_ids"] == id_hash(estimator.listing_id) and fit["inputs"]["guidance_ids"] == id_hash(guidance.listing_id), "No bank/estimator overlap")
                    bank, available, targets, predictions, losses, weights = [np.load(bank_folder / f"{name}.npy") for name in
                        ["bank_encoded", "bank_available", "bank_log_targets", "bank_predictions", "bank_loss_patterns", "coordinate_weights"]]
                    groups = read(bank_folder / "field_groups.json")
                    require(bank.shape[0] == len(guidance) and predictions.shape == losses.shape == (len(guidance), 16), "Bank dimensions")
                    close(targets, guidance.target_log, "Training-only bank labels")
                    require(np.array_equal(available, guidance[list(ACTIONS)].notna().to_numpy()), "Recorded bank availability")
                    close(bank, model.encoder.transform(price_features(guidance, FEATURES[dataset])), "Original bank encoding")
                    close(losses, np.square(predictions - targets[:, None]), "Neighbor squared loss")
                    require(sorted(j for g in groups.values() for j in g) == list(range(bank.shape[1])), "Group coordinate partition")
                    for field, indices in groups.items():
                        base = price_features(guidance.iloc[:1], FEATURES[dataset])
                        altered = base.copy()
                        altered[field] = 54321. if field in model.encoder.numeric else "<AUDIT-NEW-CATEGORY>"
                        changed = np.flatnonzero((model.encoder.transform(base) != model.encoder.transform(altered)).ravel())
                        require(set(changed) <= set(indices), "Cross-field geometry leak")
                        if field in model.encoder.categorical:
                            require(np.all(weights[indices] == .5), "Category distance weight")
                        else:
                            require(weights[indices[0]] == 1 and np.all(weights[indices[1:]] == .5), "Numeric/indicator distance weights")
                    sample = np.linspace(0, len(guidance) - 1, min(32, len(guidance)), dtype=int)
                    for pattern in range(16):
                        public = price_features(guidance.iloc[sample], FEATURES[dataset])
                        for a, field in enumerate(ACTIONS):
                            if pattern & (1 << a):
                                public[field] = np.nan
                        reproduced, _ = current_quote(model, public)
                        require(np.allclose(reproduced, predictions[sample, pattern], atol=2e-6, rtol=0), "Bank prediction sample")
                        for a in range(4):
                            if pattern & (1 << a):
                                missing_bank = ~available[:, a]
                                close(predictions[missing_bank, pattern], predictions[missing_bank, pattern & ~(1 << a)], "Failed bank replay must not alter prediction")
                    prices_all, encoded_all, _ = model.predict(price_features(evaluation, FEATURES[dataset]))
                    missing_all = model.space.reported_missing(evaluation)
                    for k in [25, 10, 50]:
                        head = ConditionalNeighborHead(bank, available, losses, groups, weights, k=k)
                        close(head.pattern_eligible_counts, construction["pattern_eligible_counts"], "Conditional coverage count")
                        close(head.bank_ood_new_hiding_counts, construction["bank_ood_new_hiding_counts"], "Bank extrapolation count")
                        method = f"{price}_aco1_k{k}"
                        primary = outcomes[(outcomes.method == method) & (outcomes.budget == .1)].set_index("listing_id").loc[evaluation.listing_id].reset_index()
                        primary_x = encoded_all[np.arange(len(evaluation)), primary.state.to_numpy(int)]
                        primary_missing = missing_all[np.arange(len(evaluation)), primary.state.to_numpy(int)]
                        patterns = primary_missing.astype(int) @ (1 << np.arange(4))
                        sample_queries = np.unique(np.r_[np.arange(min(4, len(primary))), [np.flatnonzero(patterns == p)[0] for p in np.unique(patterns)]])
                        for i in sample_queries:
                            direct = independent_scores(bank, available, losses, groups, weights, primary_x[i], primary_missing[i], k)
                            actual = head.score(primary_x[i][None, None], np.zeros((1, 1)), model.space, "benefit", reported_missing=primary_missing[i][None, None])[0, 0]
                            close(actual, direct, "Independent conditional neighbor gain")
                        if k == 25:
                            scores_all = head.score(encoded_all, prices_all, model.space, "benefit", reported_missing=missing_all)
                            audit = first_batch_unilateral(primary, prices_all, scores_all, evaluation[list(ACTIONS)].notna().to_numpy(), lattice, config["concealment_cost_log"])
                            unilateral.append({"dataset": dataset, "seed": seed, "method": method, **audit})
                        reference = "masking_benefit" if price == "masking" else "robust_no_feedback"
                        honest_reference = old[(old.method == reference) & (old.budget == .1)].set_index("listing_id").loc[evaluation.listing_id].clean_prediction_log
                        close(primary.clean_prediction_log, honest_reference, "Same frozen honest valuation")
                        bank_checks.append({"dataset": dataset, "seed": seed, "method": method, "bank_n": len(bank),
                            "independent_neighbor_query_samples": len(sample_queries), "sample_bank_predictions": len(sample) * 16,
                            "bank_and_evaluation_disjoint": True, "all_input_groups_checked": True})
                    del model, head, prices_all, encoded_all
                listings.append(outcomes.assign(dataset=dataset));parents.append(old.assign(dataset=dataset));summaries.append(reported)
    full = pd.concat(listings, ignore_index=True);old = pd.concat(parents, ignore_index=True)
    combined = pd.concat([full, old], ignore_index=True)
    source_summary = pd.concat(summaries, ignore_index=True)
    require(len(source_summary) == done["cells"] == len(aggregate), "Aggregate cell counts")
    keys = ["dataset", "seed", "method", "budget"]
    left, right = source_summary.sort_values(keys).reset_index(drop=True), aggregate.sort_values(keys).reset_index(drop=True)
    require(left[keys].equals(right[keys]), "Aggregate cell keys")
    close(left.select_dtypes("number"), right.select_dtypes("number"), "Aggregate metric mapping")
    contrasts = []
    for dataset in config["datasets"]:
        source = combined[combined.dataset == dataset]
        if source.empty:
            continue
        seeds = source.seed.nunique()
        for price, k in itertools.product(PRICES, [25, 10, 50]):
            method = f"{price}_aco1_k{k}"
            matched = "masking_benefit" if price == "masking" else "robust_no_feedback"
            for reference, metric in itertools.product([matched, "sav_val"],
                    ["positive_log_inflation", "clean_absolute_error", "attack_absolute_error"]):
                selected = source[(source.budget == .1) & source.method.isin([reference, method])]
                pivot = selected.pivot(index=["seed", "listing_id", "batch"], columns="method", values=metric)
                require(not pivot.isna().any().any(), "Unpaired price-policy comparison")
                require((pivot.reset_index().groupby("listing_id").seed.nunique() == seeds).all(), "Seed cohort alignment")
                paired = (pivot[reference] - pivot[method]).rename("delta").reset_index().groupby(["listing_id", "batch"], as_index=False).delta.mean()
                interval = conditional_cluster_interval(paired, config["bootstrap_repetitions"], 61741)
                contrasts.append({"dataset": dataset, "method": method, "reference": reference, "metric": metric, **interval,
                    "aco_mean": float(selected[selected.method == method][metric].mean()),
                    "reference_mean": float(selected[selected.method == reference][metric].mean()),
                    "completed_training_seeds": int(seeds), "all_scheduled_seeds_complete": seeds == len(config["seeds"]),
                    "scope": "declared ACO-1 adaptation; unadjusted seed-averaged paired shared-batch intervals conditional on fitted prices/banks"})
    output.mkdir(parents=True)
    for name, data in [("metric_recomputation", checks), ("bank_boundary_checks", bank_checks),
                       ("primary_first_batch_unilateral_audit", unilateral), ("paired_primary_comparisons", contrasts)]:
        pd.DataFrame(data).to_csv(output / f"{name}.csv", index=False)
    source_summary.to_csv(output / "rechecked_summary.csv", index=False)
    report = f"# ACO-1 comparator audit\n\nAudited {len(checks)} cells and {len(pairs)} completed source/seed pairs. Full scheduled matrix: {done['full_parent_matrix']}.\n\n"
    report += "This is the declared regression/group/hard-cap adaptation, not the author's classification execution. Training-only conditional neighbor banks, field boundaries, failed replay, source cohorts, 16 metrics and primary first-batch exact unilateral moves were checked. Conditional score samples use direct coordinate distances independently of the scoring implementation. All k settings are retained; no winning setting is selected.\n\n"
    report += "Paired intervals average fitted-seed contrasts before resampling shared batches. They omit training-sample and real seller-behavior uncertainty.\n\n```text\n"
    report += pd.DataFrame(contrasts).to_string(index=False) + "\n```\n"
    (output / "report.md").write_text(report)
    snapshot = output / "source_snapshot";snapshot.mkdir()
    files = [Path(__file__), *[Path(__file__).with_name(n) for n in ["analyze_nested.py", "analyze_saved_diagnostics.py", "conditional_neighbor_head.py", "benchmark_public_pipeline.py", "run_all.py", "run_crossfit.py", "savval.py"]]]
    for file in files:
        (snapshot / file.name).write_bytes(file.read_bytes())
    write_json(output / "analysis_completion.json", {"status": "completed", "parent_binding": binding,
        "run_manifest_sha256": sha(root / "manifest.json"), "run_completion_sha256": sha(root / "completion.json"),
        "audited_cells": len(checks), "completed_pairs": pairs, "full_parent_matrix": done["full_parent_matrix"],
        "source_hashes": {p.name: sha(p) for p in files}, "outputs": {p.name: sha(p) for p in output.iterdir() if p.is_file()}})
    print(f"Audited {len(checks)} full-field adaptation cells: {output}")


if __name__ == "__main__":
    main()
