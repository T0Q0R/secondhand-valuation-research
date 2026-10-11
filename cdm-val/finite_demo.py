"""CDM finite mechanism demonstration; synthetic utility units, not market evidence.

Policy selection accepts public reports only. Each unilateral counterfactual
recomputes the complete batch allocation. Sellers act before the private draw.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linprog


BASE = np.array([120.0, 180.0, 140.0])
DAMAGE = np.array([[10.0, 25.0], [35.0, 5.0], [15.0, 20.0]])
CAPACITY = 1
PRIORITIES = list(itertools.permutations(range(3)))


def report(profile: tuple[int, ...]) -> np.ndarray:
    public = DAMAGE.copy()
    for item, hidden in enumerate(profile):
        if hidden >= 0:
            public[item, hidden] = np.nan
    return public


def select(public: np.ndarray, priority: tuple[int, ...]) -> list[tuple[int, int]]:
    """No private source values or original availability enter the policy."""
    selected = []
    for item in priority:
        missing = np.flatnonzero(np.isnan(public[item]))
        if len(missing):
            selected.append((item, int(missing[0])))
            if len(selected) == CAPACITY:
                break
    return selected


def execute(public: np.ndarray, priority: tuple[int, ...],
            source: np.ndarray = DAMAGE) -> tuple[np.ndarray, list[tuple[int, int]]]:
    selected = select(public, priority)
    if len(selected) > CAPACITY or len({i for i, _ in selected}) != len(selected):
        raise AssertionError("Hard capacity or one-query constraint failed")
    after = public.copy()
    for item, field in selected:
        # A missing original value stays missing and still consumes the slot.
        after[item, field] = source[item, field]
    quote = BASE - np.nansum(after, axis=1)
    return quote, selected


def payoff_matrix() -> tuple[np.ndarray, list[dict], int]:
    rows, descriptions, largest_queries = [], [], 0
    for peer_profile in itertools.product((-1, 0, 1), repeat=3):
        for item in range(3):
            truthful_profile = list(peer_profile)
            truthful_profile[item] = -1
            honest_public = report(tuple(truthful_profile))
            for hidden in (-1, 0, 1):
                deviated = list(truthful_profile)
                deviated[item] = hidden
                deviated_public = report(tuple(deviated))
                row = []
                for priority in PRIORITIES:
                    honest_quote, honest_queries = execute(honest_public, priority)
                    deviated_quote, deviated_queries = execute(deviated_public, priority)
                    largest_queries = max(largest_queries, len(honest_queries),
                                          len(deviated_queries))
                    row.append(deviated_quote[item] - honest_quote[item])
                rows.append(row)
                descriptions.append({"item": item, "hidden": hidden,
                                     "peer_profile": list(truthful_profile)})
    return np.asarray(rows, dtype=np.float64), descriptions, largest_queries


def solve(matrix: np.ndarray, errors: np.ndarray, allowance: float) -> dict:
    columns = matrix.shape[1]
    # D alpha <= t. Clip only AFTER mixing, through the t >= 0 constraint.
    constraint = np.vstack((np.column_stack((matrix, -np.ones(len(matrix)))),
                            np.r_[errors, 0.0][None, :]))
    rhs = np.r_[np.zeros(len(matrix)), allowance]
    result = linprog(np.r_[np.zeros(columns), 1.0], A_ub=constraint, b_ub=rhs,
                     A_eq=np.r_[np.ones(columns), 0.0][None, :], b_eq=[1.0],
                     bounds=[(0.0, None)] * (columns + 1), method="highs")
    if not result.success:
        raise RuntimeError(f"LP failed: {result.message}")
    probabilities, bound = result.x[:-1], float(result.x[-1])
    if not np.isclose(probabilities.sum(), 1.0, atol=1e-9):
        raise AssertionError("Invalid probabilities")
    if np.max(matrix @ probabilities - bound) > 1e-8:
        raise AssertionError("LP deviation feasibility failed")
    if float(errors @ probabilities) > allowance + 1e-8:
        raise AssertionError("Honest-error feasibility failed")
    return {"probabilities": probabilities.tolist(), "bound": bound,
            "honest_error": float(errors @ probabilities)}


def generate_rows(matrix: np.ndarray, errors: np.ndarray, allowance: float) -> dict:
    selected = [0]
    history = []
    for _ in range(len(matrix) + 1):
        restricted = solve(matrix[selected], errors, allowance)
        alpha = np.asarray(restricted["probabilities"])
        gains = matrix @ alpha
        strongest = int(np.argmax(gains))
        gap = max(0.0, float(gains[strongest]) - restricted["bound"])
        history.append({"constraints": len(selected), "bound": restricted["bound"],
                        "strongest_row": strongest, "separation_gap": gap})
        if gap <= 1e-9:
            return {**restricted, "iterations": history,
                    "selected_rows": selected, "full_separation_gap": gap}
        if strongest in selected:
            raise AssertionError("Violated row already in restricted LP")
        selected.append(strongest)
    raise RuntimeError("Constraint generation did not terminate")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve runs: output must be a fresh directory")

    matrix, descriptions, maximum_queries = payoff_matrix()
    truth = BASE - DAMAGE.sum(axis=1)
    errors = np.asarray([np.mean(np.abs(execute(report((-1, -1, -1)), p)[0] - truth))
                         for p in PRIORITIES])
    full = solve(matrix, errors, 0.0)
    generated = generate_rows(matrix, errors, 0.0)
    if abs(full["bound"] - generated["bound"]) > 1e-8:
        raise AssertionError("Full LP and row generation disagree")
    pure_bounds = np.maximum(0.0, matrix.max(axis=0))
    if full["bound"] > pure_bounds.min() + 1e-8:
        raise AssertionError("Feasible pure-strategy comparison failed")

    # This exact fixture has one naturally unavailable value. Failed replay is
    # charged; the selector receives the same public reports in both worlds.
    public = report((0, 0, -1))
    unavailable_source = DAMAGE.copy()
    unavailable_source[0, 0] = np.nan
    failed_quote, failed_actions = execute(public, PRIORITIES[0], unavailable_source)
    success_quote, success_actions = execute(public, PRIORITIES[0], DAMAGE)
    if failed_actions != success_actions or failed_actions != [(0, 0)]:
        raise AssertionError("Private availability affected allocation")
    if failed_quote[0] != BASE[0] - DAMAGE[0, 1]:
        raise AssertionError("Failed replay changed the report")
    if failed_quote[1] != success_quote[1]:
        raise AssertionError("Failure incorrectly freed a slot")

    args.output.mkdir(parents=True)
    np.save(args.output / "deviation_matrix.npy", matrix)
    (args.output / "deviations.json").write_text(json.dumps(descriptions, indent=2))
    source_bytes = Path(__file__).read_bytes()
    (args.output / "source_snapshot.py").write_bytes(source_bytes)
    receipt = {
        "status": "completed_synthetic_mechanism_demo_only",
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "utility_units": "artificial additive quote units; not money or log-price",
        "items": 3, "fields": 2, "capacity": CAPACITY,
        "hidden_limit": 1, "policies": [list(p) for p in PRIORITIES],
        "deviation_rows": len(matrix), "maximum_actual_queries": maximum_queries,
        "full_lp": full, "constraint_generation": generated,
        "pure_worst_gains": pure_bounds.tolist(),
        "best_pure_worst_gain": float(pure_bounds.min()),
        "uniform_mixture_worst_gain": max(0.0, float((matrix @ np.full(6, 1 / 6)).max())),
        "failed_query_charged": True, "public_input_equivalence": True,
        "limitations": ["finite fixture; not source-market performance",
                        "fixed opponents per unilateral deviation; no coalition guarantee",
                        "no unseen-type, unseen-policy or universal incentive guarantee"]
    }
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps({"rows": len(matrix), "policies": len(PRIORITIES),
                      "pure": receipt["best_pure_worst_gain"],
                      "uniform": receipt["uniform_mixture_worst_gain"],
                      "mixture": full["bound"], "capacity": maximum_queries,
                      "row_generation_iterations": len(generated["iterations"])}))


if __name__ == "__main__":
    main()
