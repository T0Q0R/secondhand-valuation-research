"""Restricted deterministic numerical SMI domain diagnosis, not a full baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.svm import SVR

from run_all import load_source, sha, write_json
from run_crossfit import inner_split
from support_margin import LinearModel, MarginSolveError, sign_consistent, solve_smi

DOMAINS = {"smi_free_with_fallback": None,
           "smi_nonnegative_with_fallback": [(0, None)],
           "smi_unit_box_with_fallback": [(0, 1)]}


def identifiers(frame):
    return hashlib.sha256("\n".join(frame.listing_id).encode()).hexdigest()


def numeric(frame, fields):
    values = frame[fields].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    values[:, 1] = np.log1p(np.maximum(values[:, 1], 0))
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parent, output = args.parent.resolve(), args.output.resolve()
    manifest = json.loads((parent / "run_manifest.json").read_text())
    config = manifest["config"]
    for name in ["run_all.py", "run_crossfit.py", "savval.py"]:
        if sha(Path(__file__).with_name(name)) != manifest["source_hashes"][name]:
            raise ValueError("Parent source generation differs")
    if output.exists():
        raise FileExistsError("Numeric diagnostic outputs are immutable")
    output.mkdir(parents=True)
    snapshot = output / "source_snapshot"; snapshot.mkdir()
    sources = [Path(__file__), *[Path(__file__).with_name(name) for name in
                               ["support_margin.py", "run_all.py", "run_crossfit.py", "savval.py"]],
               Path(__file__).parents[1] / "plan/numeric-smi-diagnostic.md"]
    source_hashes = {p.name: sha(p) for p in sources}
    for path in sources:
        (snapshot / path.name).write_bytes(path.read_bytes())
    write_json(output / "manifest.json", {"parent_binding": manifest["binding"],
        "parent_config": config, "source_hashes": source_hashes, "epsilon": .15, "C": 1,
        "domains": {k: "free" if v is None else str(v) for k, v in DOMAINS.items()},
        "scope": "retrospective one-field numerical domain diagnostic; deterministic SVR; explicit median fallback; not official/full-market SMI"})
    summaries, completed = [], []
    started = time.time()
    for dataset in config["datasets"]:
        first, guidance, evaluation, provenance = load_source(dataset, config)
        all_train = pd.concat([first, guidance], ignore_index=True)
        estimator, _ = inner_split(all_train, config["head_fitting_fraction"])
        fields = ["year", "mileage_km", "seats" if dataset == "jucars" else "fiscal_power"]
        raw_train, raw_eval = numeric(estimator, fields), numeric(evaluation, fields)
        centers = np.nanmedian(raw_train, axis=0)
        centers = np.where(np.isfinite(centers), centers, 0.)
        eligible = np.isfinite(raw_train[:, 1])
        if eligible.sum() < 20:
            raise ValueError("Insufficient complete-mileage estimator rows")
        full_train = np.where(np.isfinite(raw_train[eligible]), raw_train[eligible], centers)
        lo, width = full_train.min(axis=0), np.ptp(full_train, axis=0)
        width[width == 0] = 1.
        x_train = (full_train - lo) / width
        x_eval = (raw_eval - lo) / width
        for j in [0, 2]:
            x_eval[~np.isfinite(x_eval[:, j]), j] = (centers[j] - lo[j]) / width[j]
        targets = estimator.target_log.to_numpy()[eligible]
        y_lo, y_width = targets.min(), np.ptp(targets)
        if y_width <= 0:
            raise ValueError("Constant target")
        normalized_y = (targets - y_lo) / y_width
        models = []
        for columns in [[0, 1, 2], [0, 2]]:
            fitted = SVR(kernel="linear", C=1., epsilon=.15, tol=1e-5,
                         max_iter=20000, cache_size=128)
            fitted.fit(x_train[:, columns], normalized_y)
            if fitted.fit_status_ != 0:
                raise ValueError("SVR did not converge")
            weights = np.zeros(3);weights[columns] = fitted.coef_.ravel()
            weights[np.abs(weights) < 1e-10] = 0
            models.append(LinearModel(weights, float(fitted.intercept_[0]),
                                      frozenset() if len(columns) == 3 else frozenset([1])))
        median = (centers[1] - lo[1]) / width[1]
        fallback = x_eval.copy();fallback[:, 1] = median
        missing_median_quotes = fallback @ models[0].weights + models[0].intercept
        honest_median = np.where(np.isfinite(x_eval), x_eval, np.array([0., median, 0.]))
        honest_median_quotes = honest_median @ models[0].weights + models[0].intercept
        recorded = np.isfinite(x_eval[:, 1])
        methods = {"linear_svr_median": (missing_median_quotes, np.full(len(evaluation), median),
                                         ["ordinary_median"] * len(evaluation), np.zeros(len(evaluation), bool))}
        consistent = sign_consistent(models[0], models[1])
        print(f"NUMERIC SMI {dataset}: {eligible.sum()} estimator rows, {len(evaluation)} evaluation; sign consistency={consistent}", flush=True)
        for name, bounds in DOMAINS.items():
            quotes, imputations, statuses, fell_back = [], [], [], []
            for i, report in enumerate(x_eval):
                missing_report = report.copy();missing_report[1] = np.nan
                try:
                    result = solve_smi(missing_report, models, .15, missing_bounds=bounds)
                    quotes.append(result.prediction);imputations.append(result.imputed_record[1])
                    statuses.append("solved");fell_back.append(False)
                except (MarginSolveError, ValueError) as error:
                    quotes.append(missing_median_quotes[i]);imputations.append(median)
                    statuses.append(str(error));fell_back.append(True)
            methods[name] = (np.array(quotes), np.array(imputations), statuses, np.array(fell_back))
        folder = output / dataset;folder.mkdir()
        data = {**provenance, "estimator_ids_sha256": identifiers(estimator),
                "evaluation_ids_sha256": identifiers(evaluation), "full_and_reduced_fit_rows": int(eligible.sum()),
                "same_complete_mileage_rows_for_both_models": True, "numeric_fields": fields,
                "feature_minima": lo.tolist(), "feature_widths": width.tolist(),
                "target_minimum": float(y_lo), "target_width": float(y_width),
                "normalized_mileage_median": float(median), "sign_zero_tolerance": 1e-10,
                "models": [{"weights": m.weights.tolist(), "intercept": m.intercept, "omitted": sorted(m.omitted)} for m in models]}
        write_json(folder / "fit_audit.json", data)
        outcomes = []
        for method, (hidden_quotes, imputed, statuses, fell_back) in methods.items():
            honest = np.where(recorded, honest_median_quotes, hidden_quotes) * y_width + y_lo
            hidden = hidden_quotes * y_width + y_lo
            # Exactly enumerate the two feasible reports; preserve honest ties.
            hide = recorded & (hidden > honest)
            attacked = np.where(hide, hidden, honest)
            y = evaluation.target_log.to_numpy()
            frame = pd.DataFrame({"dataset": dataset, "method": method, "listing_id": evaluation.listing_id,
                "batch": np.arange(len(evaluation)) // config["batch_size"], "target_log": y,
                "honest_log_quote": honest, "withheld_log_quote": hidden, "attacked_log_quote": attacked,
                "source_mileage_recorded": recorded, "seller_withholds": hide,
                "normalized_mileage_imputed": imputed, "solver_status": statuses, "median_fallback": fell_back,
                "honest_absolute_error": np.abs(np.expm1(honest) - np.expm1(y)),
                "attacked_absolute_error": np.abs(np.expm1(attacked) - np.expm1(y)),
                "positive_log_inflation": np.maximum(attacked - honest, 0), "honest_signed_log_bias": honest - y})
            outcomes.append(frame)
            summaries.append({"dataset": dataset, "method": method, "n": len(frame), "fit_rows": int(eligible.sum()),
                "honest_mae": float(frame.honest_absolute_error.mean()), "attacked_mae": float(frame.attacked_absolute_error.mean()),
                "mean_positive_log_inflation": float(frame.positive_log_inflation.mean()),
                "honest_signed_log_bias": float(frame.honest_signed_log_bias.mean()),
                "hiding_fraction": float(hide.mean()), "fallback_fraction": float(fell_back.mean()),
                "imputation_outside_training_range_fraction": float(((imputed < 0) | (imputed > 1)).mean()),
                "deterministic_fit": True, "maximum_hidden": 1, "queries": 0})
        pd.concat(outcomes).to_csv(folder / "outcomes.csv.gz", index=False)
        write_json(folder / "completion.json", {"status": "completed", "outcomes_sha256": sha(folder / "outcomes.csv.gz"),
                                                "fit_audit_sha256": sha(folder / "fit_audit.json")})
        completed.append(dataset)
    pd.DataFrame(summaries).to_csv(output / "summary.csv", index=False)
    if source_hashes != {p.name: sha(p) for p in sources}:
        raise ValueError("Numeric diagnostic generation changed")
    write_json(output / "completion.json", {"status": "completed", "sources": completed,
        "summary_sha256": sha(output / "summary.csv"), "parent_binding": manifest["binding"],
        "elapsed_seconds": time.time() - started})
    print(f"COMPLETED {output}", flush=True)


if __name__ == "__main__":
    main()
