"""Equation-level clean-room SMI solver, not an official Weka reproduction.

Zhang, Liu and Li (2020), equations (7) and (8), as inspected in PMC8459828.
The returned prediction is the FULL model evaluated at the stage-two imputed
record, not the stage-one lower-margin objective. Variables are free unless
explicit bounds are supplied. Discrete/categorical feasibility is not enforced.
No training or market adaptation is silently supplied by this module.
"""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog


class MarginSolveError(RuntimeError):
    """Report infeasibility/unboundedness rather than inventing a fallback."""


@dataclass(frozen=True)
class LinearModel:
    weights: np.ndarray
    intercept: float
    omitted: frozenset[int] = frozenset()

    def __post_init__(self):
        w = np.array(self.weights, dtype=float, copy=True)
        if w.ndim != 1 or not np.isfinite(w).all() or not np.isfinite(self.intercept):
            raise ValueError("Finite one-dimensional model coefficients required")
        if any(j < 0 or j >= len(w) or w[j] != 0 for j in self.omitted):
            raise ValueError("Omitted columns must exist and have zero coefficients")
        w.setflags(write=False)
        object.__setattr__(self, "weights", w)


@dataclass(frozen=True)
class MarginResult:
    imputed_record: np.ndarray
    prediction: float
    lower_margin_objective: float
    stage_two_objective: float
    minimum_model_center: float
    maximum_model_center: float
    retained_models: int


def sign_consistent(full: LinearModel, reduced: LinearModel) -> bool:
    """Compare every retained coefficient; exact zeros are separate signs."""
    if len(full.weights) != len(reduced.weights):
        raise ValueError("Model dimensions differ")
    kept = [j for j in range(len(full.weights)) if j not in reduced.omitted]
    return bool(np.array_equal(np.sign(full.weights[kept]), np.sign(reduced.weights[kept])))


def solve_smi(report, models, epsilon, *, missing_bounds=None) -> MarginResult:
    """Solve paper equations (7), then (8), for one numeric report.

    models[0] is full; remaining supplied models have sign-consistent retained
    coefficients and omit subsets of the currently missing columns. Include
    every such model for an SMI comparison. A model omitting all missing
    columns must be present. NaNs are the only missing-value indicator.

    Optional bounds change the feasible domain and must be disclosed. With
    free variables, (8) need not have a finite solution for every model family;
    this function raises with the solver status instead of substituting y*.
    """
    x = np.array(report, dtype=float, copy=True)
    if x.ndim != 1 or np.isinf(x).any() or not np.isfinite(epsilon) or epsilon < 0:
        raise ValueError("A numeric report and nonnegative finite epsilon required")
    if not models or models[0].omitted or any(len(m.weights) != len(x) for m in models):
        raise ValueError("A full model followed by dimension-matched reduced models required")
    missing = np.flatnonzero(np.isnan(x))
    if len(missing) == 0:
        value = float(models[0].weights @ x + models[0].intercept)
        return MarginResult(x, value, value, 0., value, value, 1)
    missing_set = frozenset(missing)
    if len(missing) == len(x):
        raise ValueError("The source formulation requires at least one observed attribute")
    for m in models[1:]:
        if not m.omitted or not m.omitted <= missing_set or not sign_consistent(models[0], m):
            raise ValueError("Reduced models must omit missing columns and be sign consistent")
    if not any(m.omitted == missing_set for m in models[1:]):
        raise ValueError("The fully reduced model is required")
    observed = np.flatnonzero(~np.isnan(x))
    constants = np.array([m.weights[observed] @ x[observed] + m.intercept for m in models])
    weights = np.stack([m.weights[missing] for m in models])
    bounds = [(None, None)] * len(missing) if missing_bounds is None else list(missing_bounds)
    if len(bounds) != len(missing):
        raise ValueError("One bound pair per missing coordinate is required")
    # w_missing x - y <= -(known_part + intercept - epsilon).
    first = linprog(np.r_[np.zeros(len(missing)), 1.],
                    A_ub=np.c_[weights, -np.ones(len(models))],
                    b_ub=epsilon - constants, bounds=bounds + [(None, None)], method="highs")
    if not first.success:
        raise MarginSolveError(f"Equation (7): status {first.status}: {first.message}")
    ystar = float(first.fun)
    # Eq. (8b),(8c) require every model center to be in [y*,y*+epsilon].
    objective = np.sign(models[0].weights[missing])
    second = linprog(objective, A_ub=np.r_[weights, -weights],
                     b_ub=np.r_[ystar + epsilon - constants, constants - ystar],
                     bounds=bounds, method="highs")
    if not second.success:
        raise MarginSolveError(f"Equation (8): status {second.status}: {second.message}")
    x[missing] = second.x
    centers = constants + weights @ second.x
    if centers.min() < ystar - 1e-7 or centers.max() > ystar + epsilon + 1e-7:
        raise MarginSolveError("Equation (8) numerical feasibility failed")
    return MarginResult(x, float(centers[0]), ystar, float(second.fun),
                        float(centers.min()), float(centers.max()), len(models))
