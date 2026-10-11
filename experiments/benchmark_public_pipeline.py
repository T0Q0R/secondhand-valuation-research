"""Saved-model public inference diagnostic; excludes private-state enumeration."""
from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch

from analyze_nested import close, read, require, sha
from run_all import load_source, write_json
from savval import ACTIONS, FEATURES, price_features

METHOD_FILES = {"masking_benefit": "masking_suppression", "robust_no_feedback": "robust_no_feedback",
                "sav_benefit_head": "sav_benefit_head", "sav_val": "sav_val"}


def current_quote(model, public):
    x = model.encoder.transform(public)
    base = model.backbone.predict(model.encoder.tree_frame(public), thread_count=4).astype(np.float32)
    quote = model.predict_arrays(x[:, None, :], base[:, None])[:, 0]
    return quote, x


def public_pipeline(model, head, kind, public, replay, budget):
    start = time.perf_counter()
    quote, encoded = current_quote(model, public)
    first = time.perf_counter()
    missing = public.loc[:, list(ACTIONS)].isna().to_numpy()[:, None, :]
    scores = head.score(encoded[:, None, :], quote[:, None], model.space, kind,
                        reported_missing=missing)[:, 0, :]
    second = time.perf_counter()
    field = np.argmax(scores, axis=1)
    merit = scores[np.arange(len(public)), field]
    eligible = np.isfinite(merit) & (merit > 0)
    ranking = np.lexsort((np.arange(len(public)), -merit))
    capacity = int(np.floor(budget * len(public)))
    selected = ranking[eligible[ranking]][:capacity]
    chosen = np.full(len(public), -1, int);chosen[selected] = field[selected]
    third = time.perf_counter()
    after, succeeded = replay(public, chosen)
    fourth = time.perf_counter()
    final_quote, _ = current_quote(model, after)
    end = time.perf_counter()
    timing = {"pre_quote_seconds": first - start, "head_seconds": second - first,
              "allocation_seconds": third - second, "software_replay_seconds": fourth - third,
              "post_quote_seconds": end - fourth, "pipeline_seconds": end - start}
    require((chosen >= 0).sum() <= capacity, "Hard online capacity")
    return final_quote, chosen, succeeded, timing


def environment_replay(source):
    """Only selected fields are read after the publicly determined allocation."""
    def replay(public, chosen):
        after = public.copy()
        succeeded = np.zeros(len(public), bool)
        for i in np.flatnonzero(chosen >= 0):
            field = ACTIONS[chosen[i]]
            require(pd.isna(public.iloc[i][field]), "Query publicly missing field")
            value = source.iloc[i][field]
            if pd.notna(value):
                after.iloc[i, after.columns.get_loc(field)] = value
                succeeded[i] = True
        return after, succeeded
    return replay


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execution-smoke", action="store_true")
    args = parser.parse_args()
    run, output = args.run.resolve(), args.output.resolve()
    manifest, parent_done = read(run / "run_manifest.json"), read(run / "completion.json")
    require(parent_done["status"] == "completed" and parent_done["binding"] == manifest["binding"], "Completed parent required")
    require(sha(run / "all_summary.csv") == parent_done["summary_sha256"], "Parent summary hash")
    config = manifest["config"]
    for name in ["run_all.py", "run_crossfit.py", "savval.py"]:
        require(sha(Path(__file__).with_name(name)) == manifest["source_hashes"][name], "Parent core generation")
    require(not output.exists(), "Immutable benchmark output")
    output.mkdir(parents=True)
    snapshot = output / "source_snapshot"; snapshot.mkdir()
    sources = [Path(__file__), *[Path(__file__).with_name(n) for n in ["analyze_nested.py", "run_all.py", "run_crossfit.py", "savval.py"]],
               Path(__file__).parents[1] / "plan/online-resource-diagnostic-v2.md"]
    for source in sources:
        (snapshot / source.name).write_bytes(source.read_bytes())
    hashes = {p.name: sha(p) for p in sources}
    torch.set_num_threads(4)
    warmups, repeats = (1, 2) if args.execution_smoke else (2, 20)
    write_json(output / "manifest.json", {"parent_binding": manifest["binding"], "parent_completion_sha256": sha(run / "completion.json"),
        "parent_config": config, "source_hashes": hashes, "warmups": warmups, "repetitions": repeats, "cpu_threads": 4,
        "execution_smoke": args.execution_smoke, "platform": platform.platform(), "machine": platform.machine(),
        "package_versions": manifest["versions"], "scope": "shared-workstation CPU inference; excludes loading/search/inspection latency; no individual fit-time attribution"})
    timings, equivalence, fit_stages, model_bindings = [], [], [], []
    started = time.time()
    for dataset in config["datasets"]:
        _, _, evaluation, _ = load_source(dataset, config)
        for seed in config["seeds"]:
            folder = run / dataset / f"seed-{seed}"
            receipt = read(folder / "evaluation_completion.json")
            require(receipt["binding"] == manifest["binding"], "Source/seed binding")
            for key, name in [("outcomes_sha256", "per_listing_outcomes.csv.gz"), ("summary_sha256", "summary.csv")]:
                require(receipt[key] == sha(folder / name), "Source/seed artifact")
            outcomes = pd.read_csv(folder / "per_listing_outcomes.csv.gz")
            for stage in [*[f"outer-{k}" for k in range(config["outer_folds"])], "deployment_fit"]:
                fit_receipt = read(folder / stage / "fit_completion.json")
                require(fit_receipt["inputs"]["binding"] == manifest["binding"], "Fit-stage binding")
                fit_stages.append({"dataset": dataset, "seed": seed, "stage": stage,
                    "seconds_shared_twelve_method_fit": fit_receipt["seconds"], "receipt_sha256": sha(folder / stage / "fit_completion.json")})
            for method, price_key in METHOD_FILES.items():
                model_path = folder / "deployment_models" / f"{price_key}.joblib"
                model_hash = sha(model_path)
                model, head, kind = joblib.load(model_path)
                if method == "masking_benefit":
                    kind = "benefit"
                require(head.model.n_jobs == 4, "Four-thread saved scoring head")
                model_bindings.append({"dataset": dataset, "seed": seed, "method": method, "model_sha256": model_hash,
                                       "serialized_model_and_head_bytes": model_path.stat().st_size})
                expected = outcomes[(outcomes.method == method) & (outcomes.budget == .1)].set_index("listing_id")
                require(set(expected.index) == set(evaluation.listing_id), "Complete 10% cohort")
                expected = expected.loc[evaluation.listing_id]
                for batch, subset in expected.groupby("batch", sort=True):
                    source = price_features(evaluation.set_index("listing_id").loc[subset.index].reset_index(), FEATURES[dataset])
                    public = source.copy()
                    states = subset.state.to_numpy(int)
                    for a, field in enumerate(ACTIONS):
                        public.loc[model.space.masks[states, a], field] = np.nan
                    replay = environment_replay(source)
                    final_quote, chosen, succeeded, _ = public_pipeline(model, head, kind, public, replay, .1)
                    require(np.array_equal(chosen, subset.action.to_numpy()), "Online query disagreement")
                    require(np.array_equal(succeeded, subset.query_succeeded.to_numpy()), "Online success disagreement")
                    require(np.allclose(final_quote, subset.attacked_prediction_log, atol=2e-6, rtol=0), "Online quote disagreement")
                    equivalence.append({"dataset": dataset, "seed": seed, "method": method, "batch": int(batch),
                        "n": len(public), "queries_match": True, "successes_match": True,
                        "max_abs_quote_difference": float(np.max(np.abs(final_quote - subset.attacked_prediction_log.to_numpy())))})
                    for _ in range(warmups):
                        public_pipeline(model, head, kind, public, replay, .1)
                    for repetition in range(repeats):
                        _, _, _, measured = public_pipeline(model, head, kind, public, replay, .1)
                        timings.append({"dataset": dataset, "seed": seed, "method": method, "batch": int(batch),
                            "repetition": repetition, "n": len(public), **measured})
                require(sha(model_path) == model_hash, "Parent model changed")
                del model, head
                print(f"BENCHMARK {dataset} {seed} {method}", flush=True)
    frame = pd.DataFrame(timings)
    frame.to_csv(output / "repetition_timings.csv", index=False)
    pd.DataFrame(equivalence).to_csv(output / "public_path_equivalence.csv", index=False)
    pd.DataFrame(fit_stages).to_csv(output / "shared_matrix_fit_stages.csv", index=False)
    pd.DataFrame(model_bindings).to_csv(output / "model_bindings.csv", index=False)
    summary = frame.groupby(["dataset", "method"]).pipeline_seconds.agg(
        mean="mean", median="median", p90=lambda s: s.quantile(.9), minimum="min", maximum="max", observations="count")
    summary.to_csv(output / "pipeline_summary.csv")
    require(hashes == {p.name: sha(p) for p in sources}, "Benchmark code changed during execution")
    write_json(output / "completion.json", {"status": "completed", "parent_binding": manifest["binding"],
        "elapsed_seconds": time.time() - started, "execution_smoke": args.execution_smoke,
        "source_seed_pairs": len(config["datasets"]) * len(config["seeds"]), "equivalence_batches": len(equivalence),
        "timing_rows": len(frame), "outputs": {p.name: sha(p) for p in output.iterdir() if p.is_file()}})
    print(f"COMPLETED {output}")


if __name__ == "__main__":
    main()
