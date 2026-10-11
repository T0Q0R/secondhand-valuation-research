"""Frozen-estimator, disjoint-head/calibration CDM source development.

Outputs include signed payoff matrices, exact restricted LP traces, expected
seller responses, all pure controls and private hard-cap draw outcomes.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from threadpoolctl import threadpool_limits

from analyze_nested import read, require, sha
from cdm_mechanism import Market, POLICIES, policy_scores, solve_mixture
from run_all import fit_heads, load_source, rank_subset, write_json
from run_crossfit import identifiers, inner_split
from savval import FEATURES, price_features


PRICES = {"masking": "masking_suppression", "robust": "robust_no_feedback"}


def capacity(budget, count):
    return int(np.floor(budget * count))


def peer_profiles(market):
    profiles = [np.zeros(market.n, int),
                np.argmax(np.where(market.valid, market.pred, -np.inf), axis=1)]
    rng = np.random.default_rng(603)
    profiles.append(np.array([rng.choice(np.flatnonzero(v)) for v in market.valid]))
    for k in (1, 2):
        alpha = np.eye(market.k)[k]
        profiles.append(market.response(alpha)["states"])
    return profiles


def fit_probabilities(pred, scores, valid, frame, space, config, budget, directory):
    matrices, locators, profiles = [], [], []
    batch_size = config["batch_size"]
    for batch, start in enumerate(range(0, len(frame), batch_size)):
        stop = min(start + batch_size, len(frame))
        market = Market(pred[start:stop], scores[:, start:stop], valid[start:stop],
                        space, capacity(budget, stop - start), config["concealment_cost_log"])
        for scenario, states in enumerate(peer_profiles(market)):
            matrix, where = market.deviation_matrix(states)
            matrices.append(matrix)
            locators.append(np.column_stack((np.full(len(where), batch),
                                             np.full(len(where), scenario),
                                             where[:, 0] + start, where[:, 1])))
            profiles.append({"batch": batch, "scenario": scenario, "start": start,
                             "states": states.tolist()})
    matrix = np.concatenate(matrices)
    locator = np.concatenate(locators)
    truthful_price = np.expm1(pred[:, 0])
    target_price = np.expm1(frame.target_log.to_numpy())
    error = float(np.mean(np.abs(truthful_price - target_price)))
    errors = np.full(len(POLICIES), error)
    solution = solve_mixture(matrix, errors, error * 1.01)
    pure_worst = np.maximum(0.0, matrix.max(axis=0))
    solution.update({"normal_errors": errors.tolist(), "policies": list(POLICIES),
                     "pure_worst_gains": pure_worst.tolist(),
                     "best_training_pure_policy": POLICIES[int(np.argmin(pure_worst))],
                     "payoff_rows": len(matrix), "peer_profiles_per_batch": 5,
                     "honest_error_constraint_explanation": "same frozen estimator; recorded-only replay makes all honest errors equal"})
    directory.mkdir()
    np.savez_compressed(directory / "matrix.npz", matrix=matrix, locator=locator)
    write_json(directory / "profiles.json", profiles)
    write_json(directory / "solution.json", solution)
    return solution


def evaluate(pred, scores, valid, frame, space, config, budget, probabilities,
             method, seed, directory):
    rows, quotes, finals, actions, draw_indices, realized = [], [], [], [], [], []
    probabilities = np.asarray(probabilities, float)
    batch_size = config["batch_size"]
    for batch, start in enumerate(range(0, len(frame), batch_size)):
        stop = min(start + batch_size, len(frame))
        market = Market(pred[start:stop], scores[:, start:stop], valid[start:stop],
                        space, capacity(budget, stop - start), config["concealment_cost_log"])
        response = market.response(probabilities, sweeps=config["attacker_sweeps"],
                                   restarts=config["attacker_restarts"])
        quote, action, final = response["quotes"], response["actions"], response["finals"]
        succeeded = np.zeros_like(action, dtype=bool)
        for k in range(market.k):
            selected = np.flatnonzero(action[:, k] >= 0)
            succeeded[selected, k] = space.masks[response["states"][selected], action[selected, k]]
        clean_log = pred[start:stop, 0]
        target_log = frame.target_log.iloc[start:stop].to_numpy()
        currency = np.expm1(quote)
        target_currency = np.expm1(target_log)
        clean_currency = np.expm1(clean_log)
        expected_log = quote @ probabilities
        expected_currency = currency @ probabilities
        expected_abs = np.abs(currency - target_currency[:, None]) @ probabilities
        expected_sq = (quote - target_log[:, None]) ** 2 @ probabilities
        expected_positive = np.maximum(quote - clean_log[:, None], 0) @ probabilities
        query_probability = (action >= 0) @ probabilities
        failed_probability = ((action >= 0) & ~succeeded) @ probabilities
        expected_signed = (quote - target_log[:, None]) @ probabilities
        for i in range(market.n):
            rows.append({"listing_id": str(frame.listing_id.iloc[start + i]), "batch": batch,
                         "method": method, "seed": seed, "budget": budget,
                         "state": int(response["states"][i]),
                         "hidden_count": int(space.masks[response["states"][i]].sum()),
                         "target_log": float(target_log[i]), "clean_prediction_log": float(clean_log[i]),
                         "expected_prediction_log": float(expected_log[i]),
                         "expected_prediction_currency": float(expected_currency[i]),
                         "clean_absolute_error": float(abs(clean_currency[i] - target_currency[i])),
                         "expected_attack_absolute_error": float(expected_abs[i]),
                         "expected_attack_squared_log_error": float(expected_sq[i]),
                         "positive_expected_log_inflation": float(max(expected_log[i] - clean_log[i], 0)),
                         "expected_realized_positive_log_inflation": float(expected_positive[i]),
                         "expected_query_probability": float(query_probability[i]),
                         "expected_failed_query_probability": float(failed_probability[i]),
                         "expected_signed_log_error": float(expected_signed[i]),
                         "best_response_regret_log": float(response["regret"][i]),
                         "unilateral_deviation_envelope_log": float(response["deviation_envelope"][i]),
                         "batch_converged": response["converged"], "batch_cycle": response["cycle"],
                         "batch_sweeps": response["sweeps"]})
        quotes.append(quote)
        finals.append(final)
        actions.append(action)
        # Common uniforms across methods/prices/capacities, but independent of
        # report choices. One private rule draw serves the entire batch.
        rng = np.random.default_rng(7214000 + seed * 101 + batch)
        uniforms = rng.random(config["private_draw_repetitions"])
        selected_rules = np.searchsorted(np.cumsum(probabilities), uniforms, side="right")
        selected_rules = np.minimum(selected_rules, market.k - 1)
        draw_indices.append(selected_rules)
        for repetition, k in enumerate(selected_rules):
            selected = action[:, k] >= 0
            require(int(selected.sum()) <= market.capacity, "Draw exceeds capacity")
            realized.append({"batch": batch, "repetition": repetition, "policy_index": int(k),
                             "queries": int(selected.sum()), "failed_queries": int((selected & ~succeeded[:, k]).sum()),
                             "capacity": market.capacity, "n": market.n,
                             "mean_positive_log_inflation": float(np.maximum(quote[:, k] - clean_log, 0).mean()),
                             "mae": float(np.abs(currency[:, k] - target_currency).mean())})
    directory.mkdir()
    outcomes = pd.DataFrame(rows)
    outcomes.to_csv(directory / "outcomes.csv.gz", index=False)
    pd.DataFrame(realized).to_csv(directory / "draws.csv", index=False)
    np.savez_compressed(directory / "execution.npz", quotes=np.concatenate(quotes),
                        finals=np.concatenate(finals), actions=np.concatenate(actions),
                        draw_indices=np.asarray(draw_indices), probabilities=probabilities)
    summary = {"method": method, "seed": seed, "budget": budget, "n": len(outcomes),
               "honest_mae": float(outcomes.clean_absolute_error.mean()),
               "expected_attack_mae": float(outcomes.expected_attack_absolute_error.mean()),
               "expected_attack_rmsle": float(np.sqrt(outcomes.expected_attack_squared_log_error.mean())),
               "mean_positive_expected_log_inflation": float(outcomes.positive_expected_log_inflation.mean()),
               "mean_expected_realized_positive_log_inflation": float(outcomes.expected_realized_positive_log_inflation.mean()),
               "expected_query_fraction": float(outcomes.expected_query_probability.mean()),
               "expected_failed_query_fraction": float(outcomes.expected_failed_query_probability.mean()),
               "hiding_fraction": float((outcomes.hidden_count > 0).mean()),
               "expected_signed_log_bias": float(outcomes.expected_signed_log_error.mean()),
               "max_remaining_regret": float(outcomes.best_response_regret_log.max()),
               "mean_remaining_regret": float(outcomes.best_response_regret_log.mean()),
               "mean_unilateral_deviation_envelope": float(outcomes.unilateral_deviation_envelope_log.mean()),
               "nonconverged_batch_fraction": float(1 - outcomes.groupby("batch").batch_converged.first().mean()),
               "probabilities": probabilities.tolist()}
    write_json(directory / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--partial", action="store_true")
    parser.add_argument("--execution-smoke", action="store_true")
    args = parser.parse_args()
    parent, output = args.parent.resolve(), args.output.resolve()
    manifest = read(parent / "run_manifest.json")
    config = dict(manifest["config"])
    full_parent = (parent / "completion.json").exists()
    require(full_parent or args.partial or args.execution_smoke, "Complete parent or explicit partial required")
    for name in ("run_all.py", "run_crossfit.py", "savval.py"):
        require(sha(Path(__file__).with_name(name)) == manifest["source_hashes"][name], "Parent core bytes changed")
    pairs = [(d, s) for d in config["datasets"] for s in config["seeds"]
             if (parent / d / f"seed-{s}" / "evaluation_completion.json").exists()]
    require(bool(pairs), "No completed parent pairs")
    if args.execution_smoke:
        require(("synthetic", 13) in pairs, "Smoke parent missing")
        pairs = [("synthetic", 13)]
        config.update({"budgets": [0, .1], "batch_size": 32})
    config["private_draw_repetitions"] = 20
    require(not output.exists(), "Fresh output required")
    output.mkdir(parents=True)
    snapshots = output / "source_snapshot"
    snapshots.mkdir()
    files = [Path(__file__), *[Path(__file__).with_name(n) for n in
             ["cdm_mechanism.py", "run_all.py", "run_crossfit.py", "savval.py", "analyze_nested.py"]],
             Path(__file__).parents[1] / "plan/cdm-development-v1.md",
             Path(__file__).parents[1] / "tests/test_cdm_mechanism.py"]
    hashes = {p.name: sha(p) for p in files}
    for p in files:
        (snapshots / p.name).write_bytes(p.read_bytes())
    write_json(output / "manifest.json", {"parent_binding": manifest["binding"],
               "parent_path": str(parent), "parent_complete_at_start": full_parent,
               "parent_config": manifest["config"], "config": config,
               "pairs": pairs, "prices": PRICES, "policies": list(POLICIES),
               "source_hashes": hashes, "execution_smoke": args.execution_smoke,
               "scope": "disjoint estimator/head/calibration retrospective development; fixed policy bank; not outer-crossfit CDM"})
    summaries, completed_pairs = [], []
    begun = time.time()
    torch.set_num_threads(4)
    with threadpool_limits(limits=4):
        for dataset in config["datasets"]:
            seeds = [s for d, s in pairs if d == dataset]
            if not seeds:
                continue
            first, old_head, evaluation, provenance = load_source(dataset, manifest["config"])
            train = pd.concat([first, old_head], ignore_index=True)
            estimator, guidance = inner_split(train, config["head_fitting_fraction"])
            guide_order = rank_subset(guidance, len(guidance), "cdm-head-calibration-v1")
            n_head = len(guide_order) // 2
            head_frame, calibration = guide_order.iloc[:n_head].copy(), guide_order.iloc[n_head:].copy()
            if args.execution_smoke:
                head_frame, calibration, evaluation = head_frame.iloc[:64].copy(), calibration.iloc[:64].copy(), evaluation.iloc[:64].copy()
            parts = [set(f.listing_id) for f in (estimator, head_frame, calibration, evaluation)]
            require(all(not parts[i] & parts[j] for i in range(4) for j in range(i)), "Fit/evaluation overlap")
            for seed in seeds:
                print(f"CDM {dataset} seed {seed}", flush=True)
                saved = parent / dataset / f"seed-{seed}"
                parent_fit = read(saved / "deployment_fit/fit_completion.json")
                require(parent_fit["inputs"]["estimator_ids"] == identifiers(estimator), "Exact estimator IDs")
                require(parent_fit["inputs"]["guidance_ids"] == identifiers(guidance), "Exact guidance IDs")
                require(parent_fit["inputs"]["binding"] == manifest["binding"], "Parent fit binding")
                own = output / dataset / f"seed-{seed}"
                own.mkdir(parents=True)
                write_json(own / "data_audit.json", {"provenance": provenance,
                           "estimator_ids_sha256": identifiers(estimator),
                           "guidance_ids_sha256": identifiers(guidance),
                           "head_ids_sha256": identifiers(head_frame),
                           "calibration_ids_sha256": identifiers(calibration),
                           "evaluation_ids_sha256": identifiers(evaluation)})
                for name, frame in [("head", head_frame), ("calibration", calibration), ("evaluation", evaluation)]:
                    frame[["listing_id"]].to_csv(own / f"{name}_ids.csv", index=False)
                for price_name, price_key in PRICES.items():
                    model_path = saved / "deployment_fit/models" / f"{price_key}.joblib"
                    model_hash = sha(model_path)
                    require(model_hash == parent_fit["files"][f"models/{price_key}.joblib"], "Price model hash")
                    model, _, _ = joblib.load(model_path)
                    price_folder = own / price_name
                    price_folder.mkdir()
                    head = fit_heads(model, head_frame, FEATURES[dataset], config, seed)
                    joblib.dump(head, price_folder / "head.joblib", compress=3)
                    cpred, cx, cvalid = model.predict(price_features(calibration, FEATURES[dataset]))
                    epred, ex, evalid = model.predict(price_features(evaluation, FEATURES[dataset]))
                    cscores = policy_scores(calibration.listing_id, cx, cpred,
                                           model.space.reported_missing(calibration), model.space, head)
                    escores = policy_scores(evaluation.listing_id, ex, epred,
                                           model.space.reported_missing(evaluation), model.space, head)
                    np.savez_compressed(price_folder / "calibration_arrays.npz", pred=cpred, scores=cscores, valid=cvalid,
                                        target_log=calibration.target_log.to_numpy())
                    np.savez_compressed(price_folder / "evaluation_arrays.npz", pred=epred, scores=escores, valid=evalid,
                                        target_log=evaluation.target_log.to_numpy())
                    for budget in config["budgets"]:
                        print(f"  {price_name} budget={budget}", flush=True)
                        budget_folder = price_folder / f"budget-{int(round(budget * 10000)):04d}"
                        budget_folder.mkdir()
                        solution = fit_probabilities(cpred, cscores, cvalid, calibration,
                                                     model.space, config, budget, budget_folder / "fit")
                        strategies = [(name, np.eye(len(POLICIES))[k]) for k, name in enumerate(POLICIES)]
                        strategies += [("uniform", np.full(len(POLICIES), 1 / len(POLICIES))),
                                       ("cdm", np.asarray(solution["probabilities"]))]
                        for name, alpha in strategies:
                            tick = time.time()
                            row = evaluate(epred, escores, evalid, evaluation, model.space, config,
                                           budget, alpha, name, seed, budget_folder / name)
                            row.update({"dataset": dataset, "price": price_name,
                                        "evaluation_seconds": time.time() - tick})
                            summaries.append(row)
                        write_json(budget_folder / "completion.json", {"status": "completed", "budget": budget,
                                   "price": price_name, "cells": len(strategies),
                                   "files": {str(p.relative_to(budget_folder)): sha(p) for p in budget_folder.rglob("*")
                                             if p.is_file() and p.name != "completion.json"}})
                    require(sha(model_path) == model_hash, "Immutable price model changed")
                    write_json(price_folder / "model_binding.json", {"parent_model_path": str(model_path), "parent_model_sha256": model_hash,
                               "head_sha256": sha(price_folder / "head.joblib"), "head_summary": head.target_summary})
                completed_pairs.append([dataset, seed])
                write_json(own / "completion.json", {"status": "completed", "parent_binding": manifest["binding"],
                           "dataset": dataset, "seed": seed, "price_count": len(PRICES), "budget_count": len(config["budgets"]),
                           "cells": len(PRICES) * len(config["budgets"]) * (len(POLICIES) + 2)})
                pd.DataFrame(summaries).to_csv(output / "all_summary.csv", index=False)
                print(f"COMPLETED CDM PAIR {dataset}/{seed}", flush=True)
    require(all(sha(p) == hashes[p.name] for p in files), "Source changed while running")
    scheduled = len(manifest["config"]["datasets"]) * len(manifest["config"]["seeds"])
    write_json(output / "completion.json", {"status": "completed", "pairs": completed_pairs,
               "cells": len(summaries), "seconds": time.time() - begun,
               "all_scheduled_pairs_completed": len(completed_pairs) == scheduled and not args.execution_smoke,
               "execution_smoke": args.execution_smoke, "summary_sha256": sha(output / "all_summary.csv")})
    print(f"COMPLETED CDM generation {output}", flush=True)


if __name__ == "__main__":
    main()
