"""Frozen-model sensitivities and an explicitly generic monotone control.

No new estimator fitting or retrospective tuning occurs here. Three-hidden
and added-natural-missingness settings are distribution-shift diagnostics.
Only a fully completed protocol-v2 run may supply the saved estimators.
"""
from __future__ import annotations

import argparse
import copy
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

import run_all
from disclosure_envelope import disclosure_envelope
from run_all import evaluate_method, load_source, sha, write_json
from savval import ACTIONS, FEATURES, StateSpace, stable_rank

SELECTED = ["masking_benefit", "robust_no_feedback", "sav_val", "sav_benefit_head"]
KEYS = ["masking_suppression", "robust_no_feedback", "sav_val", "sav_benefit_head"]


class NoQueryHead:
    def score(self, x, pred, space, kind, *, reported_missing):
        return np.full(reported_missing.shape, -np.inf)


class EnvelopeValuator:
    def __init__(self, model):
        self.space = model.space
        self.base = copy.deepcopy(model)
        self.base.space = StateSpace.build(4)
        lookup = {tuple(mask): i for i, mask in enumerate(self.base.space.masks)}
        self.indices = [lookup[tuple(mask)] for mask in self.space.masks]

    def predict(self, frame):
        pred, encoded, valid = self.base.predict(frame)
        quote = disclosure_envelope(pred, self.base.space.masks)
        return quote[:, self.indices], encoded[:, self.indices], valid[:, self.indices]


def natural_missingness(frame, fraction):
    altered = frame.copy()
    for j, field in enumerate(ACTIONS):
        draw = np.array([int(stable_rank(str(identifier), f"sav-val-added-natural-{j}")[:16], 16) / 2**64
                         for identifier in frame.listing_id])
        altered.loc[draw < fraction, field] = np.nan
    return altered


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.run.resolve(), args.output.resolve()
    manifest = json.loads((root / "run_manifest.json").read_text())
    completed = json.loads((root / "completion.json").read_text())
    if completed["status"] != "completed" or completed["binding"] != manifest["binding"]:
        raise ValueError("Parent run is not complete")
    if sha(root / "all_summary.csv") != completed["summary_sha256"]:
        raise ValueError("Parent results changed")
    for name in ["savval.py", "run_all.py"]:
        if sha(Path(__file__).parent / name) != manifest["source_hashes"][name]:
            raise ValueError("Use the parent run's exact estimator/evaluation source generation")
    if output.exists():
        raise FileExistsError("Diagnostic outputs are immutable; choose a new directory")
    output.mkdir(parents=True)
    snapshot = output / "source_snapshot"; snapshot.mkdir()
    files = [Path(__file__), Path(__file__).with_name("disclosure_envelope.py"),
             Path(__file__).with_name("savval.py"), Path(__file__).with_name("run_all.py")]
    hashes = {p.name: sha(p) for p in files}
    for p in files:
        (snapshot / p.name).write_bytes(p.read_bytes())
    config = manifest["config"]
    scenarios = [
        {"name": "cost-0.02", "cost": .02}, {"name": "cost-0.05", "cost": .05},
        {"name": "hidden-1", "hidden": 1}, {"name": "hidden-3-ood", "hidden": 3},
        {"name": "added-natural-0.10", "missing": .10}, {"name": "added-natural-0.30", "missing": .30},
    ]
    write_json(output / "manifest.json", {"parent_binding": manifest["binding"], "parent_config": config,
        "source_hashes": hashes, "scenarios": scenarios, "methods": SELECTED, "capacity": .1,
        "scope": "frozen-model retrospective sensitivities; no tuning or estimator refitting"})
    summary_rows, group_rows, finished = [], [], []
    started = time.time()
    for dataset in config["datasets"]:
        _, _, original, provenance = load_source(dataset, config)
        source = output / dataset; source.mkdir()
        write_json(source / "data_audit.json", provenance)
        for seed in config["seeds"]:
            tick = time.time()
            print(f"DIAGNOSTICS {dataset} seed {seed}", flush=True)
            parent = root / dataset / f"seed-{seed}"
            receipt = json.loads((parent / "evaluation_completion.json").read_text())
            if sha(parent / "per_listing_outcomes.csv.gz") != receipt["outcomes_sha256"]:
                raise ValueError("Parent outcome binding changed")
            model_paths = {key: parent / "deployment_models" / f"{key}.joblib" for key in KEYS}
            model_hashes = {key: sha(path) for key, path in model_paths.items()}
            loaded = {key: joblib.load(path) for key, path in model_paths.items()}
            methods = {key: loaded[key] for key in SELECTED if key in loaded}
            backbone, head, _ = loaded["masking_suppression"]
            methods["masking_benefit"] = (backbone, head, "benefit")
            # Reproduce honest quotes from the exact parent outcome records
            # before using saved model bytes in any new scenario.
            old = pd.read_csv(parent / "per_listing_outcomes.csv.gz")
            for name, (model, _, _) in methods.items():
                prediction, _, _ = model.predict(original[FEATURES[dataset]])
                expected = old[(old.method == name) & (old.budget == .1)].set_index("listing_id").loc[original.listing_id, "clean_prediction_log"]
                if not np.allclose(prediction[:, 0], expected.to_numpy(), atol=1e-8, rtol=1e-8):
                    raise ValueError("Saved estimator does not reproduce parent honest quotes")
            folder = source / f"seed-{seed}"; folder.mkdir()
            outcomes = []
            for scenario in scenarios:
                settings = dict(config)
                settings["concealment_cost_log"] = scenario.get("cost", config["concealment_cost_log"])
                frame = natural_missingness(original, scenario["missing"]) if "missing" in scenario else original
                for name, (original_model, policy, kind) in methods.items():
                    model = original_model
                    if "hidden" in scenario:
                        model = copy.deepcopy(original_model)
                        model.space = StateSpace.build(scenario["hidden"])
                    before = time.time()
                    records, metrics = evaluate_method(name, model, policy, kind, frame, FEATURES[dataset], settings, seed, .1)
                    records["scenario"] = scenario["name"]
                    outcomes.append(records)
                    summary_rows.append({**metrics, "dataset": dataset, "scenario": scenario["name"], "seconds": time.time() - before,
                        "fitted_maximum_hidden": config["maximum_hidden"], "evaluated_maximum_hidden": scenario.get("hidden", config["maximum_hidden"]),
                        "concealment_cost_log": settings["concealment_cost_log"], "additional_natural_missing_probability": scenario.get("missing", 0)})
            # No-query generic order closure is a diagnostic control, not a
            # claimed official strategically-withheld regression algorithm.
            closure = EnvelopeValuator(backbone)
            records, metrics = evaluate_method("disclosure_envelope", closure, NoQueryHead(), "none", original,
                FEATURES[dataset], config, seed, 0)
            if records.positive_log_inflation.max() > 1e-8:
                raise AssertionError("Disclosure-monotone closure violated")
            records["scenario"] = "generic-order-closure"
            outcomes.append(records)
            summary_rows.append({**metrics, "dataset": dataset, "scenario": "generic-order-closure"})
            combined = pd.concat(outcomes, ignore_index=True)
            combined.to_csv(folder / "outcomes.csv.gz", index=False)
            # Technical subgroup audit of original main outcomes: natural
            # missingness is an evaluation stratum, never a head input.
            metadata = pd.DataFrame({"listing_id": original.listing_id,
                "source_missing_group": original[list(ACTIONS)].isna().sum(1).clip(upper=2).map({0: "0", 1: "1", 2: "2+"})})
            groups = old[(old.budget == .1) & old.method.isin(SELECTED)].merge(metadata, on="listing_id", validate="many_to_one")
            for (method, stratum), rows in groups.groupby(["method", "source_missing_group"]):
                group_rows.append({"dataset": dataset, "seed": seed, "method": method, "source_missing_group": stratum,
                    "n": len(rows), "honest_mae": rows.clean_absolute_error.mean(), "attacked_mae": rows.attack_absolute_error.mean(),
                    "honest_signed_log_bias": rows.clean_signed_log_error.mean(), "mean_positive_log_inflation": rows.positive_log_inflation.mean(),
                    "query_fraction": (rows.action >= 0).mean(), "failed_query_fraction": ((rows.action >= 0) & ~rows.query_succeeded).mean()})
            if {key: sha(path) for key, path in model_paths.items()} != model_hashes:
                raise ValueError("Saved estimators changed while diagnosing")
            write_json(folder / "completion.json", {"source_model_hashes": model_hashes, "parent_binding": manifest["binding"],
                "outcomes_sha256": sha(folder / "outcomes.csv.gz"), "seconds": time.time() - tick, "scenarios": [s["name"] for s in scenarios] + ["generic-order-closure"]})
            finished.append([dataset, seed])
            pd.DataFrame(summary_rows).to_csv(output / "summary.csv", index=False)
            pd.DataFrame(group_rows).to_csv(output / "source_missing_groups.csv", index=False)
            print(f"  completed {len(outcomes)} method/scenario cells", flush=True)
    if {p.name: sha(p) for p in files} != hashes:
        raise ValueError("Diagnostic source generation changed")
    write_json(output / "completion.json", {"status": "completed", "completed_source_seed_pairs": finished,
        "elapsed_seconds": time.time() - started, "summary_sha256": sha(output / "summary.csv"),
        "group_sha256": sha(output / "source_missing_groups.csv"), "parent_binding": manifest["binding"]})
    print(f"COMPLETED {output}", flush=True)


if __name__ == "__main__":
    main()
