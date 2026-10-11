"""Independent one-missing-coordinate analytic audit of the numerical diagnostic.

No call to the diagnostic's LP solver: equations (7)/(8) reduce to intervals
for the full-model center when only mileage is missing. This is not a full
categorical strategic-regression benchmark.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analyze_nested import close, conditional_cluster_interval, id_hash, read, require, sha
from run_all import load_source, write_json
from run_crossfit import inner_split

DOMAINS = {"smi_free_with_fallback": (None, None),
           "smi_nonnegative_with_fallback": (0., None),
           "smi_unit_box_with_fallback": (0., 1.)}


def analytic_quote(full_known, reduced, coefficient, epsilon, bounds):
    """Solve both stages via the achievable interval of the full center."""
    lo, hi = bounds
    if coefficient > 0:
        low = -np.inf if lo is None else full_known + coefficient * lo
        high = np.inf if hi is None else full_known + coefficient * hi
    elif coefficient < 0:
        low = -np.inf if hi is None else full_known + coefficient * hi
        high = np.inf if lo is None else full_known + coefficient * lo
    else:
        low = high = full_known
    y_star = max(reduced, low) - epsilon
    left, right = max(y_star, low), min(y_star + epsilon, high)
    feasible = reduced >= y_star - 1e-7 and reduced <= y_star + epsilon + 1e-7
    feasible = feasible and left <= right + 1e-7
    # sign(w)*z minimizes the full center for w != 0. With w=0 the
    # quote is constant and the imputed coordinate is not uniquely identified.
    return (left if coefficient != 0 else full_known), y_star, feasible


def numeric(frame, fields):
    result = frame[fields].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    result[:, 1] = np.log1p(np.maximum(result[:, 1], 0))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run, parent, output = args.run.resolve(), args.parent.resolve(), args.output.resolve()
    manifest, completion = read(run / "manifest.json"), read(run / "completion.json")
    parent_manifest = read(parent / "run_manifest.json")
    require(completion["status"] == "completed", "Numerical run incomplete")
    require(manifest["parent_binding"] == parent_manifest["binding"] == completion["parent_binding"], "Parent binding")
    require(manifest["parent_config"] == parent_manifest["config"], "Parent config")
    require(sha(run / "summary.csv") == completion["summary_sha256"], "Summary hash")
    for name, digest in manifest["source_hashes"].items():
        require(sha(run / "source_snapshot" / name) == digest, f"Snapshot {name}")
    for name in ["run_all.py", "run_crossfit.py", "savval.py"]:
        require(sha(Path(__file__).with_name(name)) == parent_manifest["source_hashes"][name], "Source reconstruction generation")
    require(not output.exists(), "Audit outputs are immutable")
    config = manifest["parent_config"]
    require(completion["sources"] == config["datasets"], "Incomplete source schedule")
    summary = pd.read_csv(run / "summary.csv")
    checked, comparisons, statuses, outcome_bindings = [], [], [], {}
    source_domains, profitable_bounded_reports = [], []
    for dataset in config["datasets"]:
        folder = run / dataset
        receipt, fit = read(folder / "completion.json"), read(folder / "fit_audit.json")
        for name, key in [("outcomes.csv.gz", "outcomes_sha256"), ("fit_audit.json", "fit_audit_sha256")]:
            require(sha(folder / name) == receipt[key], f"{dataset} {name}")
        outcome_bindings[dataset] = receipt
        outcomes = pd.read_csv(folder / "outcomes.csv.gz")
        first, guidance, evaluation, provenance = load_source(dataset, config)
        estimator, _ = inner_split(pd.concat([first, guidance], ignore_index=True), config["head_fitting_fraction"])
        require(id_hash(estimator.listing_id) == fit["estimator_ids_sha256"], "Estimator membership")
        require(id_hash(evaluation.listing_id) == fit["evaluation_ids_sha256"], "Evaluation membership")
        for key in ["train_sha256", "validation_sha256"]:
            if key in provenance:
                require(provenance[key] == fit[key], "Source hash")
        fields = ["year", "mileage_km", "seats" if dataset == "jucars" else "fiscal_power"]
        require(fit["numeric_fields"] == fields, "Restricted feature contract")
        raw_train, raw_eval = numeric(estimator, fields), numeric(evaluation, fields)
        centers = np.nanmedian(raw_train, axis=0)
        centers[~np.isfinite(centers)] = 0.
        eligible = np.isfinite(raw_train[:, 1])
        require(int(eligible.sum()) == fit["full_and_reduced_fit_rows"], "Complete-mileage fit count")
        complete_train = np.where(np.isfinite(raw_train[eligible]), raw_train[eligible], centers)
        lo, width = complete_train.min(0), np.ptp(complete_train, axis=0)
        width[width == 0] = 1.
        close(lo, fit["feature_minima"], "Train-only feature minima")
        close(width, fit["feature_widths"], "Train-only feature widths")
        fit_targets = estimator.target_log.to_numpy()[eligible]
        y_lo, y_width = fit_targets.min(), np.ptp(fit_targets)
        close(y_lo, fit["target_minimum"], "Train-only target minimum")
        close(y_width, fit["target_width"], "Train-only target width")
        x = (raw_eval - lo) / width
        for j in [0, 2]:
            x[~np.isfinite(x[:, j]), j] = (centers[j] - lo[j]) / width[j]
        recorded = np.isfinite(x[:, 1])
        source_domains.append({"dataset": dataset, "n": len(evaluation),
            "recorded_mileage_n": int(recorded.sum()),
            "recorded_mileage_outside_training_range_n": int((recorded & ((x[:, 1] < 0) | (x[:, 1] > 1))).sum())})
        median = (centers[1] - lo[1]) / width[1]
        close(median, fit["normalized_mileage_median"], "Train-only mileage median")
        full, reduced = fit["models"]
        require(full["omitted"] == [] and reduced["omitted"] == [1], "Full/reduced family")
        wf, wr = np.array(full["weights"]), np.array(reduced["weights"])
        require(wr[1] == 0, "Reduced mileage coefficient")
        consistent = np.array_equal(np.sign(wf[[0, 2]]), np.sign(wr[[0, 2]]))
        cf = x[:, [0, 2]] @ wf[[0, 2]] + full["intercept"]
        cr = x[:, [0, 2]] @ wr[[0, 2]] + reduced["intercept"]
        median_missing = cf + wf[1] * median
        recorded_full = cf + wf[1] * np.where(recorded, x[:, 1], median)
        require(set(outcomes.method) == {"linear_svr_median", *DOMAINS}, "Four scheduled methods")
        require(not outcomes.duplicated(["method", "listing_id"]).any(), "Duplicate method/listing")
        for method, frame in outcomes.groupby("method", sort=False):
            require(len(frame) == len(evaluation) and set(frame.listing_id) == set(evaluation.listing_id), "Exact source cohort")
            frame = frame.set_index("listing_id").loc[evaluation.listing_id].reset_index()
            require(len(frame) == len(evaluation), "Complete retained cohort")
            close(frame.target_log, evaluation.target_log, "Source target")
            close(frame.batch, np.arange(len(evaluation)) // config["batch_size"], "Shared batches")
            require(np.array_equal(frame.source_mileage_recorded, recorded), "Recorded mileage availability")
            require(np.isfinite(frame.select_dtypes("number").to_numpy()).all(), "Finite quotes/metrics")
            if method == "linear_svr_median":
                expected = median_missing
                require(not frame.median_fallback.any(), "Ordinary baseline flag")
                require((frame.solver_status == "ordinary_median").all(), "Ordinary baseline status")
                close(frame.normalized_mileage_imputed, median, "Ordinary imputation")
            else:
                expected = np.empty(len(frame))
                bounds = DOMAINS[method]
                for i, row in frame.iterrows():
                    value, y_star, feasible = analytic_quote(cf[i], cr[i], wf[1], manifest["epsilon"], bounds)
                    feasible = feasible and consistent
                    require(bool(row.median_fallback) == (not feasible), "Analytic feasibility/fallback agreement")
                    if not feasible:
                        expected[i] = median_missing[i]
                        require(row.solver_status != "solved", "Failure status disclosure")
                        close(row.normalized_mileage_imputed, median, "Declared same-median fallback")
                    else:
                        expected[i] = value
                        require(row.solver_status == "solved", "Success status")
                        imputed = row.normalized_mileage_imputed
                        require(bounds[0] is None or imputed >= bounds[0] - 1e-7, "Lower domain bound")
                        require(bounds[1] is None or imputed <= bounds[1] + 1e-7, "Upper domain bound")
                        close(cf[i] + wf[1] * imputed, value, "Analytic stage-two optimal quote")
                        require(min(value, cr[i]) >= y_star - 1e-7 and max(value, cr[i]) <= y_star + manifest["epsilon"] + 1e-7, "Two-stage center constraints")
            honest = np.where(recorded, recorded_full, expected) * y_width + y_lo
            hidden = expected * y_width + y_lo
            close(frame.honest_log_quote, honest, "Honest full/imputed quote")
            close(frame.withheld_log_quote, hidden, "Analytic missing quote")
            hide = recorded & (hidden > honest)
            require(np.array_equal(frame.seller_withholds, hide), "Exact two-report maximum and honest ties")
            attacked = np.where(hide, hidden, honest)
            close(frame.attacked_log_quote, attacked, "Exact response quote")
            if method == "smi_unit_box_with_fallback":
                for i in np.flatnonzero(hide):
                    profitable_bounded_reports.append({"dataset": dataset, "listing_id": frame.listing_id.iloc[i],
                        "original_mileage_km": float(evaluation.mileage_km.iloc[i]),
                        "original_normalized_mileage": float(x[i, 1]),
                        "normalized_mileage_imputed": float(frame.normalized_mileage_imputed.iloc[i]),
                        "full_mileage_coefficient": float(wf[1]), "target_normalization_width": float(y_width),
                        "honest_log_quote": float(honest[i]), "withheld_log_quote": float(hidden[i]),
                        "positive_log_quote_gain": float(hidden[i] - honest[i])})
            metrics = {"honest_absolute_error": np.abs(np.expm1(honest) - np.expm1(frame.target_log)),
                       "attacked_absolute_error": np.abs(np.expm1(attacked) - np.expm1(frame.target_log)),
                       "positive_log_inflation": np.maximum(attacked - honest, 0),
                       "honest_signed_log_bias": honest - frame.target_log}
            for metric, values in metrics.items():
                close(frame[metric], values, "Independently recomputed " + metric)
            row = summary[(summary.dataset == dataset) & (summary.method == method)]
            require(len(row) == 1, "Unique summary cell")
            row = row.iloc[0]
            mapping = {"honest_mae": "honest_absolute_error", "attacked_mae": "attacked_absolute_error",
                       "mean_positive_log_inflation": "positive_log_inflation", "honest_signed_log_bias": "honest_signed_log_bias"}
            for key, metric in mapping.items():
                close(row[key], frame[metric].mean(), "Summary " + key)
            close(row.fallback_fraction, frame.median_fallback.mean(), "Fallback count")
            close(row.hiding_fraction, hide.mean(), "Withholding count")
            close(row.imputation_outside_training_range_fraction, ((frame.normalized_mileage_imputed < 0) | (frame.normalized_mileage_imputed > 1)).mean(), "Training-range extrapolation")
            require(row.n == len(frame) and row.fit_rows == eligible.sum() and row.maximum_hidden == 1 and row.queries == 0 and row.deterministic_fit, "Numerical-only cohort/control contract")
            checked.append(row.to_dict())
            for status, count in frame.solver_status.value_counts().items():
                statuses.append({"dataset": dataset, "method": method, "status": status, "n": int(count)})
        baseline = outcomes[outcomes.method == "linear_svr_median"].set_index("listing_id")
        for method in DOMAINS:
            other = outcomes[outcomes.method == method].set_index("listing_id").loc[baseline.index]
            for metric in ["honest_absolute_error", "attacked_absolute_error", "positive_log_inflation"]:
                paired = pd.DataFrame({"batch": baseline.batch, "delta": baseline[metric] - other[metric]})
                interval = conditional_cluster_interval(paired, config["bootstrap_repetitions"], 61731)
                comparisons.append({"dataset": dataset, "method": method, "metric": metric, **interval,
                    "scope": "one deterministic restricted fit; unadjusted conditional shared-batch interval"})
    output.mkdir(parents=True)
    pd.DataFrame(checked).to_csv(output / "rechecked_summary.csv", index=False)
    pd.DataFrame(statuses).to_csv(output / "solver_status_counts.csv", index=False)
    pd.DataFrame(comparisons).to_csv(output / "paired_diagnostic_comparisons.csv", index=False)
    pd.DataFrame(source_domains).to_csv(output / "source_domain_counts.csv", index=False)
    write_json(output / "profitable_bounded_reports.json", profitable_bounded_reports)
    text = "# Numerical SMI diagnostic audit\n\n"
    text += f"Audited {len(checked)} cells using analytic one-coordinate solutions independently of the LP solver.\n\n"
    text += "Restricted numerical inputs, one withholdable mileage field, no queries and one deterministic fit per source. These are not high-dimensional full-market SMI/SAV-Val comparisons. All cohort rows remain; fallback status is checked explicitly. Known validation values are not clipped to the training range.\n\n"
    text += "Mean differences and intervals concern these fitted models and shared evaluation batches. They do not establish official reproduction, general incentive compatibility, observed seller behavior, or a superior full-market algorithm.\n\n"
    text += "```text\n" + pd.DataFrame(checked).to_string(index=False) + "\n```\n"
    (output / "report.md").write_text(text)
    snapshot = output / "source_snapshot"; snapshot.mkdir()
    sources = [Path(__file__), *[Path(__file__).with_name(n) for n in ["analyze_nested.py", "run_all.py", "run_crossfit.py", "savval.py"]]]
    for path in sources:
        (snapshot / path.name).write_bytes(path.read_bytes())
    write_json(output / "analysis_completion.json", {"status": "completed", "audited_cells": len(checked),
        "run_completion_sha256": sha(run / "completion.json"), "run_manifest_sha256": sha(run / "manifest.json"),
        "parent_binding": parent_manifest["binding"], "source_outcome_bindings": outcome_bindings,
        "analyzer_source_hashes": {p.name: sha(p) for p in sources},
        "outputs": {p.name: sha(p) for p in output.iterdir() if p.is_file()}})
    print(f"Audited {len(checked)} numeric-only cells: {output}")


if __name__ == "__main__":
    main()
