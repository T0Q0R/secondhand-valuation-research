"""Public-policy mixtures with exact finite unilateral deviation separation.

The estimator is fixed. This module optimizes/searches expected log quotes;
private source availability is used solely by the environment transition.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import linprog

from savval import ACTIONS, allocate, stable_rank


POLICIES = ("none", "suppression", "benefit", "risk",
            *[f"field-{a}" for a in range(4)], *[f"hash-{k}" for k in range(4)])


def policy_scores(ids, x, pred, missing, space, head):
    scores = [np.full(missing.shape, -np.inf)]
    for kind in ("suppression", "benefit", "risk"):
        scores.append(head.score(x, pred, space, kind, reported_missing=missing))
    for a in range(len(ACTIONS)):
        scores.append(np.where(missing & (np.arange(4)[None, None, :] == a), 1.0, -np.inf))
    for k in range(4):
        public_priorities = np.array([
            [int(stable_rank(str(identifier), f"cdm-public-hash-{k}-field-{a}")[:13], 16)
             / float(16 ** 13) + 1e-12 for a in range(4)] for identifier in ids
        ])
        scores.append(np.where(missing, public_priorities[:, None, :], -np.inf))
    result = np.asarray(scores, dtype=float)
    if result.shape != (len(POLICIES), *missing.shape):
        raise ValueError("Policy score dimensions")
    return result


class Market:
    def __init__(self, pred, scores, valid, space, capacity, cost=0.0):
        self.pred = np.asarray(pred, dtype=float)
        self.scores = np.asarray(scores, dtype=float)
        self.valid = np.asarray(valid, dtype=bool)
        self.space, self.capacity, self.cost = space, int(capacity), float(cost)
        self.n, self.s = self.pred.shape
        self.k = len(scores)
        if self.scores.shape != (self.k, self.n, self.s, len(ACTIONS)):
            raise ValueError("Score dimensions")
        if not self.valid[:, 0].all() or not 0 <= capacity <= self.n or cost < 0:
            raise ValueError("Invalid market")
        self.best_field = np.argmax(self.scores, axis=-1)
        self.merit = np.max(self.scores, axis=-1)

    def execute(self, states):
        states = np.asarray(states, dtype=int)
        if not self.valid[np.arange(self.n), states].all():
            raise ValueError("Impossible seller report")
        finals, actions = [], []
        for scores in self.scores:
            final, action, _ = allocate(scores, states, self.space, self.capacity)
            if (action >= 0).sum() > self.capacity:
                raise AssertionError("Actual hard capacity")
            finals.append(final)
            actions.append(action)
        final = np.asarray(finals)
        action = np.asarray(actions)
        quotes = self.pred[np.arange(self.n)[None, :], final].T
        return quotes, final.T, action.T

    def candidate_quotes(self, item, states):
        """All single-seller reports versus fixed peers, for every rule.

        Ranking is recalculated for every candidate; hidden validity and replay
        transitions do not determine query eligibility or priority.
        """
        states = np.asarray(states, dtype=int)
        peer_ids = np.arange(self.n)
        peers = peer_ids != item
        current_merit = self.merit[:, np.arange(self.n), states]
        own = self.merit[:, item, :]
        ahead = ((current_merit[:, None, peers] > own[:, :, None]) |
                 ((current_merit[:, None, peers] == own[:, :, None]) &
                  (peer_ids[peers][None, None, :] < item)))
        selected = ((ahead.sum(axis=-1) < self.capacity) & np.isfinite(own) & (own > 0))
        candidate = np.broadcast_to(np.arange(self.s), (self.k, self.s)).copy()
        fields = self.best_field[:, item, :]
        candidate[selected] = self.space.query_next[candidate[selected], fields[selected]]
        return self.pred[item, candidate].T

    def expected_candidates(self, item, states, probabilities):
        result = self.candidate_quotes(item, states) @ probabilities
        result -= self.cost * self.space.masks.sum(axis=1)
        return np.where(self.valid[item], result, -np.inf)

    def deviation_matrix(self, states):
        quotes = np.asarray([self.candidate_quotes(i, states) for i in range(self.n)])
        signed = quotes - quotes[:, 0:1, :]
        signed -= self.cost * self.space.masks.sum(axis=1)[None, :, None]
        return signed[self.valid], np.argwhere(self.valid)

    def response(self, probabilities, *, sweeps=20, restarts=4):
        probabilities = np.asarray(probabilities, dtype=float)
        if (probabilities < -1e-12).any() or abs(probabilities.sum() - 1) > 1e-9:
            raise ValueError("Mixture probabilities")
        starts = [np.zeros(self.n, dtype=int)]
        if restarts > 1:
            noquery = self.pred - self.cost * self.space.masks.sum(axis=1)[None, :]
            starts.append(np.argmax(np.where(self.valid, noquery, -np.inf), axis=1))
        for restart in range(2, restarts):
            rng = np.random.default_rng(1931 + restart)
            starts.append(np.array([rng.choice(np.flatnonzero(v)) for v in self.valid]))
        runs = []
        for initial in starts:
            states = initial.copy()
            visited = {tuple(states)}
            cycle = False
            count = 0
            for sweep in range(sweeps):
                changed = 0
                for item in range(self.n):
                    values = self.expected_candidates(item, states, probabilities)
                    best = int(np.argmax(values))
                    if values[best] > values[states[item]] + 1e-8:
                        states[item] = best
                        changed += 1
                count = sweep + 1
                if not changed:
                    break
                key = tuple(states)
                if key in visited:
                    cycle = True
                    break
                visited.add(key)
            quote, final, action = self.execute(states)
            net = quote @ probabilities - self.cost * self.space.masks[states].sum(axis=1)
            candidates = np.array([self.expected_candidates(i, states, probabilities)
                                   for i in range(self.n)])
            regret = np.maximum(candidates.max(axis=1) - net, 0.0)
            truthful_cf = candidates[:, 0]
            deviation = np.maximum(candidates.max(axis=1) - truthful_cf, 0.0)
            runs.append({"states": states, "finals": final, "actions": action,
                         "quotes": quote, "utility": net, "regret": regret,
                         "deviation_envelope": deviation, "sweeps": count,
                         "cycle": cycle, "converged": bool((regret < 1e-7).all())})
        # Same rule as the parent search: retain the restart with largest summed
        # seller utility. No equilibrium or global attack optimality is claimed.
        return max(runs, key=lambda row: float(row["utility"].sum()))


def solve_mixture(matrix, errors, allowance, *, separation_tolerance=1e-9):
    matrix, errors = np.asarray(matrix, dtype=float), np.asarray(errors, dtype=float)
    if matrix.ndim != 2 or len(errors) != matrix.shape[1] or not np.isfinite(matrix).all():
        raise ValueError("Finite payoff matrix required")
    k = matrix.shape[1]
    active = [0]
    history = []
    for _ in range(len(matrix) + 1):
        restricted = matrix[active]
        constraint = np.vstack((np.column_stack((restricted, -np.ones(len(active)))),
                                np.r_[errors, 0.0][None, :]))
        result = linprog(np.r_[np.zeros(k), 1.0], A_ub=constraint,
                         b_ub=np.r_[np.zeros(len(active)), allowance],
                         A_eq=np.r_[np.ones(k), 0.0][None, :], b_eq=[1.0],
                         bounds=[(0.0, None)] * (k + 1), method="highs")
        if not result.success:
            raise RuntimeError(f"Mixture LP failed: {result.message}")
        alpha, bound = result.x[:-1], float(result.x[-1])
        gains = matrix @ alpha
        strongest = int(np.argmax(gains))
        gap = max(0.0, float(gains[strongest]) - bound)
        history.append({"constraints": len(active), "bound": bound,
                        "strongest_row": strongest, "separation_gap": gap})
        if gap <= separation_tolerance:
            if (alpha < -1e-12).any() or abs(alpha.sum() - 1) > 1e-9:
                raise AssertionError("LP probability feasibility")
            if float(errors @ alpha) > allowance + 1e-7:
                raise AssertionError("LP honest-error feasibility")
            return {"probabilities": alpha.tolist(), "bound": bound,
                    "honest_error": float(errors @ alpha), "allowance": float(allowance),
                    "separation_gap": gap, "active_rows": active, "history": history,
                    "normal_error_constraint_has_rule_variation": bool(np.ptp(errors) > 1e-9)}
        if strongest in active:
            raise RuntimeError("LP violated a retained constraint; numerical tolerance failure")
        active.append(strongest)
    raise RuntimeError("Finite separation failed to terminate")
