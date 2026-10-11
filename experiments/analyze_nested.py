"""Audit protocol-v2 evidence, respecting shared listings across training seeds.

Partial mode reads only hash-bound completed source/seed checkpoints. Neither
an intermediate run nor its incomplete seed is promoted to complete evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

METHODS = {
    "native_no_audit", "masking_no_audit", "masking_random", "masking_fixed",
    "masking_risk", "masking_benefit", "masking_suppression", "robust_no_feedback",
    "sav_val", "sav_no_gap", "sav_benefit_head", "sav_preaudit_attacker",
}
PRICE_KEYS = ["native_no_audit", "masking_suppression", "robust_no_feedback",
              "sav_val", "sav_no_gap", "sav_benefit_head", "sav_preaudit_attacker"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(actual, expected, message):
    require(np.allclose(actual, expected, atol=1e-8, rtol=1e-8, equal_nan=True), message)


def id_hash(ids):
    return hashlib.sha256("\n".join(ids).encode()).hexdigest()


def ranked(ids, salt):
    return sorted(ids, key=lambda x: hashlib.sha256(f"{salt}|{x}".encode()).hexdigest())


def conditional_cluster_interval(paired, repeats, seed):
    # Each row is a listing-level paired contrast, averaged over fitted seeds
    # when appropriate. Resample shared batches once, never count repeated
    # copies of the same evaluation items as independent seed-specific clusters.
    totals = paired.groupby("batch").delta.agg(["sum", "count"])
    rng = np.random.default_rng(seed)
    draw = rng.integers(0, len(totals), (repeats, len(totals)))
    values = totals["sum"].to_numpy()[draw].sum(1) / totals["count"].to_numpy()[draw].sum(1)
    return {"difference": float(paired.delta.mean()), "clusters": len(totals),
            "lower": float(np.quantile(values, .025)), "upper": float(np.quantile(values, .975))}


def contrast(outcomes, reference, ours="sav_val", metric="positive_log_inflation", budget=.1):
    selected = outcomes[(outcomes.budget == budget) & outcomes.method.isin([ours, reference])]
    require(not selected.duplicated(["seed", "listing_id", "method"]).any(), "Repeated paired key")
    pivot = selected.pivot(index=["seed", "listing_id"], columns="method", values=metric)
    require(not pivot.isna().any().any(), "Unpaired listings")
    batch = selected.drop_duplicates(["seed", "listing_id"]).set_index(["seed", "listing_id"]).batch
    return pd.DataFrame({"delta": pivot[reference] - pivot[ours], "batch": batch}).reset_index()


def audit_outer(folder, config, binding):
    audit = read(folder / "outer_audit.json")
    require(audit["all_records_predicted_out_of_loop"], "Outer target-generation claim missing")
    require(sha(folder / "outer_assignments.csv") == audit["assignment_sha256"], "Outer assignments changed")
    require(sha(folder / "outer_predictions.npz") == audit["prediction_sha256"], "Outer quotes changed")
    assigned = pd.read_csv(folder / "outer_assignments.csv")
    require(len(assigned) == audit["rows"] and assigned.listing_id.is_unique, "Outer row integrity failed")
    ordered = ranked(assigned.listing_id.tolist(), "sav-val-outer-v2")
    expected = {identifier: j % config["outer_folds"] for j, identifier in enumerate(ordered)}
    require((assigned.outer_fold == assigned.listing_id.map(expected)).all(), "Fold allocation differs")
    states = sum(len(list(itertools.combinations(range(4), k))) for k in range(config["maximum_hidden"] + 1))
    with np.load(folder / "outer_predictions.npz") as values:
        require(set(values.files) == set(PRICE_KEYS), "Missing outer estimator variant")
        for key in values.files:
            require(values[key].shape == (len(assigned), states) and np.isfinite(values[key]).all(), "Invalid outer predictions")
    require(len(audit["folds"]) == config["outer_folds"], "Incomplete outer fold receipts")
    for fold in audit["folds"]:
        number = fold["fold"]
        estimator_plus_guidance = assigned[assigned.outer_fold != number].listing_id.tolist()
        heldout = assigned[assigned.outer_fold == number].listing_id.tolist()
        inner_order = ranked(estimator_plus_guidance, "sav-val-inner-guidance-v2")
        cut = int(np.floor(config["head_fitting_fraction"] * len(inner_order)))
        estimator, guidance = inner_order[cut:], inner_order[:cut]
        require(not (set(heldout) & (set(estimator) | set(guidance))), "Overlapping outer roles")
        for role, identifiers in [("estimator", estimator), ("guidance", guidance), ("holdout", heldout)]:
            require(fold[role + "_ids"] == id_hash(identifiers), f"Outer {role} IDs differ")
        require(not fold["heldout_outcomes_used_for_fitting"], "Held-out outcomes used")
        receipt = read(folder / f"outer-{number}" / "fit_completion.json")
        require(receipt["inputs"]["binding"] == binding, "Outer model generation differs")
        require(receipt["inputs"]["estimator_ids"] == id_hash(estimator), "Estimator receipt differs")
        require(receipt["inputs"]["guidance_ids"] == id_hash(guidance), "Guidance receipt differs")
        for artifact, digest in receipt["files"].items():
            require(sha(folder / f"outer-{number}" / artifact) == digest, "Outer model artifact changed")


def audit_seed(root, dataset, seed, config, binding):
    folder = root / dataset / f"seed-{seed}"
    receipt = read(folder / "evaluation_completion.json")
    require(receipt["binding"] == binding, "Seed generation differs")
    artifacts = {"summary_sha256": folder / "summary.csv", "outcomes_sha256": folder / "per_listing_outcomes.csv.gz",
                 "outer_audit_sha256": folder / "outer_audit.json", "data_audit_sha256": root / dataset / "data_audit.json"}
    for key, artifact in artifacts.items():
        require(sha(artifact) == receipt[key], f"Changed seed artifact: {artifact}")
    audit_outer(folder, config, binding)
    summaries = pd.read_csv(folder / "summary.csv")
    outcomes = pd.read_csv(folder / "per_listing_outcomes.csv.gz")
    require(set(summaries.method) == METHODS and set(outcomes.method) == METHODS, "Incomplete methods")
    require(not summaries.duplicated(["method", "budget"]).any(), "Repeated summary cell")
    require(not outcomes.duplicated(["listing_id", "method", "budget"]).any(), "Repeated outcome key")
    expected_cells = {(m, b) for m in METHODS for b in config["budgets"]
                      if m not in {"native_no_audit", "masking_no_audit"} or b == 0}
    require(set(zip(summaries.method, summaries.budget)) == expected_cells, "Budget cells incomplete")
    masks = np.array([[j in group for j in range(4)] for k in range(config["maximum_hidden"] + 1)
                      for group in itertools.combinations(range(4), k)], dtype=bool)
    checks = []
    evaluation_ids = None
    for (method, budget), group in outcomes.groupby(["method", "budget"], sort=True):
        row = summaries[(summaries.method == method) & (summaries.budget == budget)].iloc[0]
        require(len(group) == row.n, "Incomplete listing cell")
        if evaluation_ids is None:
            evaluation_ids = set(group.listing_id)
        require(set(group.listing_id) == evaluation_ids, "Evaluation cohort varies between methods")
        require((group.seed == seed).all(), "Unexpected seed labels")
        target, honest, attacked = group.target_log.to_numpy(), group.clean_prediction_log.to_numpy(), group.attacked_prediction_log.to_numpy()
        close(group.clean_sq_log_loss, (honest - target) ** 2, "Honest squared log errors differ")
        close(group.attack_sq_log_loss, (attacked - target) ** 2, "Attack squared log errors differ")
        close(group.clean_absolute_error, np.abs(np.expm1(honest) - np.expm1(target)), "Honest price errors differ")
        close(group.attack_absolute_error, np.abs(np.expm1(attacked) - np.expm1(target)), "Attack price errors differ")
        close(group.positive_log_inflation, np.maximum(attacked - honest, 0), "Log inflation differs")
        close(group.positive_price_inflation, np.maximum(np.expm1(attacked) - np.expm1(honest), 0), "Price inflation differs")
        close(group.clean_signed_log_error, honest - target, "Honest bias differs")
        close(group.attack_signed_log_error, attacked - target, "Attack bias differs")
        close(group.clean_underprediction_log, np.maximum(target - honest, 0), "Underprediction differs")
        state, final, action = group.state.to_numpy(int), group.final_state.to_numpy(int), group.action.to_numpy(int)
        require(((state >= 0) & (state < len(masks)) & (final >= 0) & (final < len(masks))).all(), "Invalid mask index")
        require(((action >= -1) & (action < 4)).all(), "Invalid field request")
        close(group.hidden_count, masks[state].sum(1), "Hidden-field counts differ")
        changed = masks[state].copy()
        succeeded = group.query_succeeded.to_numpy(bool)
        require(((action >= 0) | ~succeeded).all(), "Successful query without request")
        for j in np.flatnonzero(action >= 0):
            require(succeeded[j] == masks[state[j], action[j]], "Query-success flag differs from recorded transition")
            if succeeded[j]:
                changed[j, action[j]] = False
        require(np.array_equal(changed, masks[final]), "Query transition differs")
        require((group.best_response_regret_log >= -1e-9).all(), "Negative unilateral regret")
        require((group.unilateral_inflation_envelope_log >= group.positive_log_inflation - 1e-9).all(), "Unilateral quote envelope below realized quote")
        batch_flags = group.groupby("batch")
        for _, rows in batch_flags:
            require((rows.action >= 0).sum() <= int(np.floor(budget * len(rows))), "Hard batch capacity exceeded")
            for field in ["batch_converged", "batch_cycle_detected", "batch_sweeps"]:
                require(rows[field].nunique() == 1, "Inconsistent batch search flags")
        metrics = {
            "clean_rmsle": np.sqrt(group.clean_sq_log_loss.mean()), "attack_rmsle": np.sqrt(group.attack_sq_log_loss.mean()),
            "clean_mae": group.clean_absolute_error.mean(), "attack_mae": group.attack_absolute_error.mean(),
            "mean_positive_log_inflation": group.positive_log_inflation.mean(), "mean_positive_price_inflation": group.positive_price_inflation.mean(),
            "clean_signed_log_bias": group.clean_signed_log_error.mean(), "attack_signed_log_bias": group.attack_signed_log_error.mean(),
            "clean_underprediction_log": group.clean_underprediction_log.mean(), "actual_audit_fraction": (group.action >= 0).mean(),
            "hiding_fraction": (group.hidden_count > 0).mean(), "max_remaining_response_regret": group.best_response_regret_log.max(),
            "mean_remaining_response_regret": group.best_response_regret_log.mean(), "mean_unilateral_inflation_envelope_log": group.unilateral_inflation_envelope_log.mean(),
            "failed_query_fraction": ((group.action >= 0) & ~group.query_succeeded).mean(),
            "nonconverged_batch_fraction": 1 - batch_flags.batch_converged.first().mean(),
        }
        for field, value in metrics.items():
            close(value, row[field], f"Summary metric differs: {dataset}/{seed}/{method}/{budget}/{field}")
        checks.append({"dataset": dataset, "seed": seed, "method": method, "budget": budget,
                       "rows": len(group), "recomputed_summary_metrics": len(metrics), "state_transition_checked": True,
                       "price_space_checked": True, "capacity_checked": True})
    paired = contrast(outcomes, "sav_benefit_head")
    interval = conditional_cluster_interval(paired, config["bootstrap_repetitions"], seed)
    stored = read(folder / "primary_interval.json")
    close(interval["difference"], stored["difference"], "Stored paired difference differs")
    close([interval["lower"], interval["upper"]], stored["conditional_batch_cluster_95_interval"], "Stored cluster interval differs")
    return outcomes.assign(dataset=dataset), summaries, checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--partial", action="store_true")
    args = parser.parse_args()
    root, output = args.run.resolve(), args.output.resolve()
    manifest = read(root / "run_manifest.json")
    config, binding = manifest["config"], manifest["binding"]
    for name, digest in manifest["source_hashes"].items():
        require(sha(root / "source_snapshot" / name) == digest, "Frozen snapshot changed")
    require(hashlib.sha256(json.dumps(manifest["source_hashes"], sort_keys=True).encode()).hexdigest() == binding, "Manifest binding differs")
    complete = (root / "completion.json").exists()
    if complete:
        receipt = read(root / "completion.json")
        require(receipt["status"] == "completed" and receipt["binding"] == binding, "Run completion invalid")
        require(sha(root / "all_summary.csv") == receipt["summary_sha256"], "Aggregate summary changed")
    require(complete or args.partial, "Run still incomplete; only explicit partial analysis permitted")
    outcomes, summaries, checks, completed = [], [], [], []
    for dataset in config["datasets"]:
        for seed in config["seeds"]:
            if not (root / dataset / f"seed-{seed}" / "evaluation_completion.json").exists():
                require(args.partial and not complete, "Scheduled seed missing")
                continue
            listing, summary, audited = audit_seed(root, dataset, seed, config, binding)
            outcomes.append(listing); summaries.append(summary); checks.extend(audited); completed.append([dataset, seed])
    require(bool(completed), "No completed seed to analyze")
    outcomes, summaries = pd.concat(outcomes, ignore_index=True), pd.concat(summaries, ignore_index=True)
    require(not output.exists(), "Analysis outputs are immutable; use a new directory")
    output.mkdir(parents=True)
    pd.DataFrame(checks).to_csv(output / "metric_recomputation.csv", index=False)
    seed_rows, pooled_rows, tradeoffs = [], [], []
    for dataset in config["datasets"]:
        source = outcomes[outcomes.dataset == dataset]
        if source.empty:
            continue
        seeds = sorted(source.seed.unique())
        for reference in ["sav_benefit_head", "robust_no_feedback", "masking_benefit", "sav_no_gap", "sav_preaudit_attacker"]:
            paired = contrast(source, reference)
            require((paired.groupby("listing_id").batch.nunique() == 1).all(), "Shared evaluation batch changed between seeds")
            require((paired.groupby("listing_id").seed.nunique() == len(seeds)).all(), "Seed evaluation cohorts differ")
            for seed in seeds:
                interval = conditional_cluster_interval(paired[paired.seed == seed], config["bootstrap_repetitions"], int(seed))
                subset = summaries[(summaries.dataset == dataset) & (summaries.seed == seed) & (summaries.budget == .1)].set_index("method")
                ours, control = subset.loc["sav_val"], subset.loc[reference]
                relative = 100 * interval["difference"] / control.mean_positive_log_inflation if control.mean_positive_log_inflation > 0 else np.nan
                mae_change = 100 * (ours.clean_mae / control.clean_mae - 1)
                seed_rows.append({"dataset": dataset, "seed": int(seed), "reference": reference, **interval,
                    "relative_inflation_reduction_percent": relative, "honest_mae_change_percent": mae_change,
                    "passes_prespecified_development_threshold": bool(relative >= 10 and mae_change <= 5 and interval["lower"] > 0)})
            averaged = paired.groupby(["listing_id", "batch"], as_index=False).delta.mean()
            interval = conditional_cluster_interval(averaged, config["bootstrap_repetitions"], 61721)
            means = summaries[(summaries.dataset == dataset) & (summaries.budget == .1)].groupby("method").mean(numeric_only=True)
            control, ours = means.loc[reference], means.loc["sav_val"]
            pooled_rows.append({"dataset": dataset, "reference": reference, "completed_training_seeds": len(seeds),
                **interval, "relative_inflation_reduction_percent": 100 * interval["difference"] / control.mean_positive_log_inflation if control.mean_positive_log_inflation > 0 else np.nan,
                "honest_mae_change_percent": 100 * (ours.clean_mae / control.clean_mae - 1),
                "all_scheduled_seeds_complete": len(seeds) == len(config["seeds"]),
                "interval_scope": "evaluation-batch sampling conditional on all fitted models; seed-averaged paired contrast"})
            for metric in ["clean_absolute_error", "attack_absolute_error", "clean_sq_log_loss", "attack_sq_log_loss",
                           "clean_signed_log_error", "positive_price_inflation", "unilateral_inflation_envelope_log"]:
                values = contrast(source, reference, metric=metric)
                require((values.groupby("listing_id").batch.nunique() == 1).all(), "Shared metric batches differ")
                require((values.groupby("listing_id").seed.nunique() == len(seeds)).all(), "Shared metric cohort differs")
                average = values.groupby(["listing_id", "batch"], as_index=False).delta.mean()
                bounds = conditional_cluster_interval(average, config["bootstrap_repetitions"], 61722)
                selected = source[(source.budget == .1) & source.method.isin([reference, "sav_val"])]
                tradeoffs.append({"dataset": dataset, "reference": reference, "metric": metric, **bounds,
                    "reference_mean": selected[selected.method == reference][metric].mean(),
                    "sav_mean": selected[selected.method == "sav_val"][metric].mean(),
                    "completed_training_seeds": len(seeds), "all_scheduled_seeds_complete": len(seeds) == len(config["seeds"]),
                    "interpretation": "reference minus SAV; positive is lower SAV loss, but signed bias is not a loss",
                    "interval_scope": "shared evaluation batches conditional on fitted models; exploratory multiple metrics"})
    seed_frame, pooled_frame = pd.DataFrame(seed_rows), pd.DataFrame(pooled_rows)
    seed_frame.to_csv(output / "per_seed_comparisons.csv", index=False)
    pooled_frame.to_csv(output / "shared_batch_comparisons.csv", index=False)
    pd.DataFrame(tradeoffs).to_csv(output / "paired_metric_tradeoffs.csv", index=False)
    frontier = []
    for dataset in config["datasets"]:
        source = outcomes[outcomes.dataset == dataset]
        if source.empty:
            continue
        count = source.seed.nunique()
        for reference, budget, metric in itertools.product(
            ["sav_benefit_head", "robust_no_feedback", "masking_benefit", "sav_no_gap", "sav_preaudit_attacker"],
            config["budgets"], ["positive_log_inflation", "clean_absolute_error", "attack_absolute_error"]):
            paired = contrast(source, reference, metric=metric, budget=budget)
            require((paired.groupby("listing_id").batch.nunique() == 1).all(), "Frontier batches differ")
            require((paired.groupby("listing_id").seed.nunique() == count).all(), "Frontier cohorts differ")
            averaged = paired.groupby(["listing_id", "batch"], as_index=False).delta.mean()
            bounds = conditional_cluster_interval(averaged, config["bootstrap_repetitions"], 61723)
            selected = source[(source.budget == budget) & source.method.isin([reference, "sav_val"])]
            ref_mean = selected[selected.method == reference][metric].mean()
            our_mean = selected[selected.method == "sav_val"][metric].mean()
            frontier.append({"dataset": dataset, "budget": budget, "reference": reference, "metric": metric, **bounds,
                "reference_mean": ref_mean, "sav_mean": our_mean,
                "relative_reduction_percent": 100 * (ref_mean - our_mean) / ref_mean if ref_mean > 0 else np.nan,
                "completed_training_seeds": int(count), "all_scheduled_seeds_complete": count == len(config["seeds"]),
                "scope": "all preset capacities; unadjusted exploratory conditional shared-batch intervals"})
    pd.DataFrame(frontier).to_csv(output / "paired_capacity_frontiers.csv", index=False)
    summaries.groupby(["dataset", "method", "budget"]).agg(
        mean_inflation=("mean_positive_log_inflation", "mean"), seed_sd_inflation=("mean_positive_log_inflation", "std"),
        mean_clean_mae=("clean_mae", "mean"), mean_attack_mae=("attack_mae", "mean"),
        mean_clean_log_bias=("clean_signed_log_bias", "mean"), mean_regret=("mean_remaining_response_regret", "mean"),
        max_regret=("max_remaining_response_regret", "max"), nonconverged=("nonconverged_batch_fraction", "mean"),
        failed_queries=("failed_query_fraction", "mean")).to_csv(output / "method_seed_summary.csv")
    selected = ["masking_benefit", "robust_no_feedback", "sav_val", "sav_no_gap", "sav_benefit_head"]
    labels = ["Masking + error benefit", "Robust without feedback", "SAV-Val", "No gap penalty", "Ordinary benefit head"]
    fig, axes = plt.subplots(len(config["datasets"]), 2, figsize=(10, 3.2 * len(config["datasets"])), squeeze=False)
    for i, dataset in enumerate(config["datasets"]):
        source = summaries[summaries.dataset == dataset]
        if source.empty:
            for ax in axes[i]:
                ax.text(.5, .5, "No completed seed", ha="center", va="center", transform=ax.transAxes)
        for method, label in zip(selected, labels):
            rows = source[source.method == method].groupby("budget").mean(numeric_only=True).sort_index()
            if rows.empty:
                continue
            axes[i, 0].plot(rows.index * 100, rows.mean_positive_log_inflation, "o-", ms=3, label=label)
            axes[i, 1].plot(rows.index * 100, rows.attack_mae, "o-", ms=3, label=label)
        axes[i, 0].set_ylabel(f"{dataset}\nPositive log-price inflation")
        axes[i, 1].set_ylabel("Attacked MAE (source currency)")
        for ax in axes[i]:
            ax.set_xlabel("Available verification capacity (%)")
            ax.grid(alpha=.2); ax.spines[["top", "right"]].set_visible(False)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle(("Partial" if not complete else "Completed") + " retrospective development; mean over completed training seeds")
    fig.tight_layout(); fig.savefig(output / "budget_frontiers.pdf"); fig.savefig(output / "budget_frontiers.png", dpi=170); plt.close(fig)
    text = ["# Corrected nested-crossfit development audit", "", f"Run complete: **{complete}**. Completed source/seed pairs: {len(completed)} / {len(config['datasets']) * len(config['seeds'])}.", "",
            "These are retrospective development results. Development-v1 deployability conclusions are withdrawn; this audit uses only protocol-v2 public query rules.", "",
            "Training seeds share the same evaluation records. Pooled intervals resample shared batches after averaging paired listing differences across seeds; they do not treat seed-specific copies as independent clusters. These conditional intervals exclude training-data and behavior-model uncertainty. Seed variability is separately reported.", "",
            "Primary contrast: ordinary-benefit counterpart minus SAV-Val at 10% capacity. Positive differences favor SAV-Val. Other direct local comparisons are retained, including the simpler robust/no-feedback control.", "",
            "| Source | Completed seeds | Relative inflation reduction | Honest MAE change | Paired batch interval |", "|---|---:|---:|---:|---|"]
    for row in pooled_rows:
        if row["reference"] == "sav_benefit_head":
            text.append(f"| {row['dataset']} | {row['completed_training_seeds']} | {row['relative_inflation_reduction_percent']:.2f}% | {row['honest_mae_change_percent']:+.2f}% | [{row['lower']:.5f}, {row['upper']:.5f}] |")
    text.extend(["", f"Independently recomputed {len(checks)} method/capacity cells, including price-space errors, signed bias, failed-query capacity, state transitions, regret envelopes and outer-fold checkpoint bindings.", "",
                 "Prespecified per-seed rule: inflation reduction at least 10%, paired batch interval lower bound positive, honest MAE worsening at most 5%. A pooled development result does not establish broad method success or a final confirmatory result.", "",
                 "Data-audit fields inherited from the original loader describe its temporary split: the authoritative outer-loop construction is `target_generation` plus the verified outer assignments/model receipts. The inherited `action_target_fit` field is a legacy provenance description, not the final deployment-head construction.", "",
                 "Remaining work: direct-prior reproduction/adaptation audit, attack-cost/hidden-count/natural-missingness/source-size sensitivities, group and efficiency reporting, final design freeze, and full manuscript/PDF QA."])
    (output / "report.md").write_text("\n".join(text) + "\n")
    files = [p for p in output.iterdir() if p.is_file()]
    snapshot = output / "analyzer_snapshot"; snapshot.mkdir()
    (snapshot / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    (output / "analysis_completion.json").write_text(json.dumps({"run_binding": binding, "run_complete": complete,
        "completed_source_seed_pairs": completed, "analyzer_sha256": sha(__file__),
        "audited_cells": len(checks), "outputs": {p.name: sha(p) for p in files}}, indent=2))
    print(pooled_frame.to_string(index=False))
    print(f"Audited {len(checks)} cells; {output / 'report.md'}")


if __name__ == "__main__":
    main()
