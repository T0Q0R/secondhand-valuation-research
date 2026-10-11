"""Independent arithmetic and receipt audit of completed saved-model diagnostics.

Training seeds share evaluation listings: average paired contrasts over seeds
before resampling their common batches. No incomplete source seed is promoted.
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analyze_nested import close, conditional_cluster_interval, read, require, sha
from run_all import load_source
from savval import ACTIONS

METHODS = {"masking_benefit", "robust_no_feedback", "sav_val", "sav_benefit_head"}


def masks(maximum):
    return np.array([[j in group for j in range(4)]
                     for k in range(maximum + 1)
                     for group in itertools.combinations(range(4), k)], dtype=bool)


def audit_cell(rows, reported, maximum, batch_size):
    """Recompute metrics without executing the price model or response search."""
    require(len(rows) == reported.n, "Listing count differs")
    require(rows.listing_id.is_unique, "Duplicated listing in a diagnostic cell")
    y, honest, attacked = (rows[k].to_numpy() for k in
                          ["target_log", "clean_prediction_log", "attacked_prediction_log"])
    for field, value in {
        "clean_sq_log_loss": (honest - y) ** 2,
        "attack_sq_log_loss": (attacked - y) ** 2,
        "clean_absolute_error": np.abs(np.expm1(honest) - np.expm1(y)),
        "attack_absolute_error": np.abs(np.expm1(attacked) - np.expm1(y)),
        "positive_log_inflation": np.maximum(attacked - honest, 0),
        "positive_price_inflation": np.maximum(np.expm1(attacked) - np.expm1(honest), 0),
        "clean_signed_log_error": honest - y,
        "attack_signed_log_error": attacked - y,
        "clean_underprediction_log": np.maximum(y - honest, 0),
    }.items():
        close(rows[field], value, f"Saved diagnostic {field} differs")
    lattice = masks(maximum)
    state, final, action = (rows[k].to_numpy(int) for k in ["state", "final_state", "action"])
    require(((state >= 0) & (state < len(lattice)) & (final >= 0) & (final < len(lattice))).all(), "Invalid diagnostic state")
    require(((action >= -1) & (action < 4)).all(), "Invalid diagnostic query")
    close(rows.hidden_count, lattice[state].sum(axis=1), "Diagnostic concealment count differs")
    succeeded = rows.query_succeeded.to_numpy(bool)
    require(((action >= 0) | ~succeeded).all(), "Replay without a request")
    changed = lattice[state].copy()
    for i in np.flatnonzero(action >= 0):
        require(succeeded[i] == lattice[state[i], action[i]], "Replay success contradicts state")
        if succeeded[i]:
            changed[i, action[i]] = False
    require(np.array_equal(changed, lattice[final]), "Replay state differs")
    batches = rows.groupby("batch")
    for _, group in batches:
        require(len(group) <= batch_size, "Oversized batch")
        require((group.action >= 0).sum() <= int(np.floor(reported.budget * len(group))), "Diagnostic capacity exceeded")
        for field in ["batch_converged", "batch_cycle_detected", "batch_sweeps"]:
            require(group[field].nunique() == 1, "Inconsistent search flags")
    require((rows.best_response_regret_log >= -1e-9).all(), "Negative regret")
    require((rows.unilateral_inflation_envelope_log >= rows.positive_log_inflation - 1e-9).all(), "Quote envelope below realized inflation")
    actual = {
        "clean_rmsle": np.sqrt(rows.clean_sq_log_loss.mean()),
        "attack_rmsle": np.sqrt(rows.attack_sq_log_loss.mean()),
        "clean_mae": rows.clean_absolute_error.mean(), "attack_mae": rows.attack_absolute_error.mean(),
        "mean_positive_log_inflation": rows.positive_log_inflation.mean(),
        "mean_positive_price_inflation": rows.positive_price_inflation.mean(),
        "clean_signed_log_bias": rows.clean_signed_log_error.mean(),
        "attack_signed_log_bias": rows.attack_signed_log_error.mean(),
        "clean_underprediction_log": rows.clean_underprediction_log.mean(),
        "actual_audit_fraction": (rows.action >= 0).mean(),
        "hiding_fraction": (rows.hidden_count > 0).mean(),
        "max_remaining_response_regret": rows.best_response_regret_log.max(),
        "mean_remaining_response_regret": rows.best_response_regret_log.mean(),
        "mean_unilateral_inflation_envelope_log": rows.unilateral_inflation_envelope_log.mean(),
        "failed_query_fraction": ((rows.action >= 0) & ~rows.query_succeeded).mean(),
        "nonconverged_batch_fraction": 1 - batches.batch_converged.first().mean(),
    }
    for key, value in actual.items():
        close(value, reported[key], f"Reported diagnostic {key} differs")
    return len(actual)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, parent, output = (p.resolve() for p in [args.run, args.parent, args.output])
    manifest, completion = read(root / "manifest.json"), read(root / "completion.json")
    parent_manifest, parent_completion = read(parent / "run_manifest.json"), read(parent / "completion.json")
    require(completion["status"] == parent_completion["status"] == "completed", "Only completed runs can be analyzed")
    binding = parent_manifest["binding"]
    require(binding == completion["parent_binding"] == manifest["parent_binding"] == parent_completion["binding"], "Parent generation differs")
    require(manifest["parent_config"] == parent_manifest["config"], "Parent configuration differs")
    require(sha(parent / "all_summary.csv") == parent_completion["summary_sha256"], "Parent aggregate changed")
    for name in ["run_all.py", "savval.py"]:
        require(sha(Path(__file__).with_name(name)) == parent_manifest["source_hashes"][name], "Source reader generation differs")
    require(sha(root / "summary.csv") == completion["summary_sha256"], "Diagnostic summary changed")
    require(sha(root / "source_missing_groups.csv") == completion["group_sha256"], "Stratum table changed")
    for name, digest in manifest["source_hashes"].items():
        require(sha(root / "source_snapshot" / name) == digest, "Diagnostic source snapshot changed")
    config = manifest["parent_config"]
    scheduled = {(d, s) for d in config["datasets"] for s in config["seeds"]}
    require(set(map(tuple, completion["completed_source_seed_pairs"])) == scheduled, "Incomplete diagnostic seed matrix")
    summary, strata = pd.read_csv(root / "summary.csv"), pd.read_csv(root / "source_missing_groups.csv")
    require(not summary.duplicated(["dataset", "seed", "scenario", "method"]).any(), "Repeated diagnostic cell")
    scenarios = {s["name"]: s for s in manifest["scenarios"]}
    require(len(scenarios) == 6 and set(manifest["methods"]) == METHODS, "Unexpected diagnostic matrix")
    expected_cells = {(scenario, method) for scenario in scenarios for method in METHODS}
    expected_cells.add(("generic-order-closure", "disclosure_envelope"))
    checks, all_outcomes, parents = [], [], []
    source_membership = {}
    for dataset in config["datasets"]:
        _, _, original, _ = load_source(dataset, config)
        source_membership[dataset] = pd.Series(
            original[list(ACTIONS)].isna().sum(axis=1).clip(upper=2).map({0: "0", 1: "1", 2: "2+"}).to_numpy(),
            index=original.listing_id)
    for dataset, seed in sorted(scheduled):
        folder, old_folder = root / dataset / f"seed-{seed}", parent / dataset / f"seed-{seed}"
        receipt, old_receipt = read(folder / "completion.json"), read(old_folder / "evaluation_completion.json")
        require(receipt["parent_binding"] == binding, "Diagnostic source/seed parent differs")
        require(old_receipt["binding"] == binding, "Parent source/seed generation differs")
        require(sha(folder / "outcomes.csv.gz") == receipt["outcomes_sha256"], "Diagnostic listing file changed")
        require(sha(old_folder / "per_listing_outcomes.csv.gz") == old_receipt["outcomes_sha256"], "Parent listing file changed")
        for key, digest in receipt["source_model_hashes"].items():
            require(sha(old_folder / "deployment_models" / f"{key}.joblib") == digest, "Saved source model changed")
        outcomes = pd.read_csv(folder / "outcomes.csv.gz")
        require((outcomes.seed == seed).all(), "Wrong diagnostic seed labels")
        old = pd.read_csv(old_folder / "per_listing_outcomes.csv.gz")
        main = old[(old.budget == .1) & old.method.isin(METHODS)].copy()
        main["scenario"] = "main-cost0-h2"
        main["dataset"] = dataset
        parents.append(main)
        values = main[main.method == "sav_val"].set_index("listing_id")
        ids = set(values.index)
        require(ids == set(source_membership[dataset].index), "Source cohort differs")
        selected = summary[(summary.dataset == dataset) & (summary.seed == seed)]
        require(set(zip(selected.scenario, selected.method)) == expected_cells, "Missing or extra diagnostic cells")
        require(set(zip(outcomes.scenario, outcomes.method)) == expected_cells, "Listing matrix differs")
        for (scenario, method), rows in outcomes.groupby(["scenario", "method"], sort=True):
            require(set(rows.listing_id) == ids, "Diagnostic cohort differs")
            close(rows.set_index("listing_id").target_log.sort_index(), values.target_log.sort_index(), "Diagnostic targets differ from parent")
            row = selected[(selected.scenario == scenario) & (selected.method == method)].iloc[0]
            is_closure = scenario == "generic-order-closure"
            maximum = config["maximum_hidden"] if is_closure else scenarios[scenario].get("hidden", config["maximum_hidden"])
            close(row.budget, 0 if is_closure else .1, "Diagnostic budget differs")
            count = audit_cell(rows, row, maximum, config["batch_size"])
            if not is_closure:
                spec = scenarios[scenario]
                close(row.evaluated_maximum_hidden, maximum, "Attack extent metadata differs")
                close(row.fitted_maximum_hidden, config["maximum_hidden"], "Fit extent metadata differs")
                close(row.concealment_cost_log, spec.get("cost", config["concealment_cost_log"]), "Cost metadata differs")
                close(row.additional_natural_missing_probability, spec.get("missing", 0), "Missingness metadata differs")
                # Cost/extent changes leave honest reports and quotes intact.
                if "missing" not in spec:
                    baseline = main[main.method == method].set_index("listing_id").clean_prediction_log
                    close(rows.set_index("listing_id").clean_prediction_log.sort_index(), baseline.sort_index(), "Unchanged honest quotes differ")
            else:
                require(rows.positive_log_inflation.max() <= 1e-8 and (rows.action == -1).all(), "Generic envelope property failed")
                baseline = main[main.method == "masking_benefit"].set_index("listing_id").clean_prediction_log
                difference = rows.set_index("listing_id").clean_prediction_log.sort_index() - baseline.sort_index()
                require(difference.min() >= -1e-8, "Closure lowered a backbone honest quote")
            checks.append({"dataset": dataset, "seed": seed, "scenario": scenario, "method": method,
                           "rows": len(rows), "recomputed_metrics": count, "capacity_and_transitions": True})
        # Reconstruct source strata using the exact bound source reader;
        # recompute every subgroup metric from independent parent outcomes.
        groups = strata[(strata.dataset == dataset) & (strata.seed == seed)]
        require(set(groups.method) == METHODS, "Incomplete source/seed stratum methods")
        require(not groups.duplicated(["method", "source_missing_group"]).any(), "Repeated source stratum")
        for method, subset in groups.groupby("method"):
            require(subset.n.sum() == len(ids), "Stratum counts do not cover the cohort")
            original = main[main.method == method].copy()
            original["source_missing_group"] = original.listing_id.map(source_membership[dataset])
            require(set(subset.source_missing_group.astype(str)) == set(original.source_missing_group), "Stratum membership labels differ")
            for label, members in original.groupby("source_missing_group"):
                row = subset[subset.source_missing_group.astype(str) == label].iloc[0]
                require(row.n == len(members), "Stratum member count differs")
                for field, source in {"honest_mae": "clean_absolute_error", "attacked_mae": "attack_absolute_error",
                                      "honest_signed_log_bias": "clean_signed_log_error",
                                      "mean_positive_log_inflation": "positive_log_inflation"}.items():
                    close(row[field], members[source].mean(), "Recomputed stratum metric differs")
                close(row.query_fraction, (members.action >= 0).mean(), "Stratum query rate differs")
                close(row.failed_query_fraction, ((members.action >= 0) & ~members.query_succeeded).mean(), "Stratum failure rate differs")
        all_outcomes.append(outcomes.assign(dataset=dataset))
    require(set(strata.method) == METHODS, "Incomplete stratum methods")
    outcomes = pd.concat(all_outcomes + parents, ignore_index=True)
    closure_rows = []
    for dataset in config["datasets"]:
        selected = outcomes[outcomes.dataset == dataset]
        closure = selected[selected.method == "disclosure_envelope"].set_index(["seed", "listing_id"])
        baseline = selected[(selected.method == "masking_benefit") & (selected.scenario == "main-cost0-h2")].set_index(["seed", "listing_id"])
        require(set(closure.index) == set(baseline.index), "Closure cohort differs")
        joined = pd.DataFrame({"delta": closure.clean_absolute_error - baseline.clean_absolute_error,
                               "batch": baseline.batch}).reset_index()
        require((joined.groupby("listing_id").batch.nunique() == 1).all(), "Closure batches differ across seeds")
        averaged = joined.groupby(["listing_id", "batch"], as_index=False).delta.mean()
        interval = conditional_cluster_interval(averaged, config["bootstrap_repetitions"], 55102)
        closure_rows.append({"dataset": dataset, "backbone_honest_mae": baseline.clean_absolute_error.mean(),
                             "closure_honest_mae": closure.clean_absolute_error.mean(),
                             "mae_change": interval["difference"], "mae_change_lower": interval["lower"],
                             "mae_change_upper": interval["upper"], "clusters": interval["clusters"],
                             "mean_honest_log_quote_lift": (closure.clean_prediction_log - baseline.clean_prediction_log).mean(),
                             "closure_signed_log_bias": closure.clean_signed_log_error.mean(),
                             "backbone_signed_log_bias": baseline.clean_signed_log_error.mean(),
                             "closure_inflation": closure.positive_log_inflation.mean(),
                             "scope": "generic monotone control; full-lattice inference; conditional evaluation interval"})
    comparisons = []
    for (dataset, scenario), group in outcomes[outcomes.method.isin(METHODS)].groupby(["dataset", "scenario"]):
        for reference in ["sav_benefit_head", "robust_no_feedback", "masking_benefit"]:
            pivot = group[group.method.isin([reference, "sav_val"])].pivot(index=["seed", "listing_id"], columns="method", values="positive_log_inflation")
            require(not pivot.isna().any().any(), "Unpaired sensitivity comparison")
            batches = group.drop_duplicates(["seed", "listing_id"]).set_index(["seed", "listing_id"]).batch
            paired = pd.DataFrame({"delta": pivot[reference] - pivot.sav_val, "batch": batches}).reset_index()
            require((paired.groupby("listing_id").batch.nunique() == 1).all(), "Seed batches differ")
            averaged = paired.groupby(["listing_id", "batch"], as_index=False).delta.mean()
            interval = conditional_cluster_interval(averaged, config["bootstrap_repetitions"], 55101)
            ref_mean = group[group.method == reference].positive_log_inflation.mean()
            our_mean = group[group.method == "sav_val"].positive_log_inflation.mean()
            comparisons.append({"dataset": dataset, "scenario": scenario, "reference": reference, **interval,
                                "reference_inflation": ref_mean, "sav_inflation": our_mean,
                                "relative_reduction_percent": 100 * (ref_mean - our_mean) / ref_mean if ref_mean > 0 else np.nan,
                                "training_seeds": len(config["seeds"]), "scope": "conditional shared-batch interval; retrospective frozen-model follow-up"})
    require(not output.exists(), "Analysis is immutable; choose a new directory")
    output.mkdir(parents=True)
    pd.DataFrame(checks).to_csv(output / "recomputed_cells.csv", index=False)
    pd.DataFrame(comparisons).to_csv(output / "paired_sensitivity_comparisons.csv", index=False)
    pd.DataFrame(closure_rows).to_csv(output / "closure_tradeoffs.csv", index=False)
    report = ["# Saved-model diagnostic audit", "",
              "Retrospective frozen-model sensitivities. A smoke parent supports software execution only.", "",
              "Intervals resample shared evaluation batches after averaging paired listing contrasts across training seeds.",
              "They condition on fitted models and omit training-data uncertainty.", "",
              "| Source | Setting | Reference | SAV inflation | Reference inflation | Reduction (%) | Paired 95% interval |",
              "|---|---|---|---:|---:|---:|---|"]
    for row in comparisons:
        report.append(f"| {row['dataset']} | {row['scenario']} | {row['reference']} | {row['sav_inflation']:.5f} | {row['reference_inflation']:.5f} | {row['relative_reduction_percent']:.2f} | [{row['lower']:.5f}, {row['upper']:.5f}] |")
    report += ["", "## Generic disclosure-monotone control", "",
               "Zero strategic uplift is not sufficient evidence of good valuation. Honest error and quote lift are retained.", "",
               "| Source | Backbone honest MAE | Closure honest MAE | Honest log-quote lift | Closure uplift |",
               "|---|---:|---:|---:|---:|"]
    for row in closure_rows:
        report.append(f"| {row['dataset']} | {row['backbone_honest_mae']:.2f} | {row['closure_honest_mae']:.2f} | {row['mean_honest_log_quote_lift']:.5f} | {row['closure_inflation']:.8f} |")
    report += ["", "Source-missingness subgroup membership and each subgroup metric were reconstructed and checked.",
               "These are technical strata, not protected-demographic groups.",
               "The three-hidden setting and added natural missingness are distribution shifts without retraining."]
    (output / "report.md").write_text("\n".join(report) + "\n")
    # Save the exact analyzer and helper used by this audit.
    snapshot = output / "analyzer_snapshot"; snapshot.mkdir()
    for path in [Path(__file__), *[Path(__file__).with_name(name) for name in
                                 ["analyze_nested.py", "run_all.py", "savval.py"]]]:
        (snapshot / path.name).write_bytes(path.read_bytes())
    receipt = {"status": "completed", "parent_binding": binding, "audited_cells": len(checks),
               "source_seed_pairs": sorted(scheduled), "diagnostic_completion_sha256": sha(root / "completion.json"),
               "analyzers": {p.name: sha(p) for p in snapshot.iterdir()},
               "outputs": {p.name: sha(p) for p in output.iterdir() if p.is_file()},
               "limits": "Source reader shared only for bound dataset reconstruction; metric/transition/stratum arithmetic independent. No model fitting or deployment recommendation. Smoke parent yields software evidence only."}
    (output / "analysis_completion.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"Audited {len(checks)} diagnostic cells; {output}")


if __name__ == "__main__":
    main()
