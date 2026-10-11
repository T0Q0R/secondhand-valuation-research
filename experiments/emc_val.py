"""Finite public disclosure certificates; strategic CP is an existing method."""
from __future__ import annotations

import numpy as np
import pandas as pd


class TreeInputs:
    """Persistable training-schema encoder, operating only on public columns."""
    def __init__(self, frame):
        self.columns = list(frame.columns)
        self.numeric = [c for c in self.columns if pd.api.types.is_numeric_dtype(frame[c])]
        self.categorical = [c for c in self.columns if c not in self.numeric]

    def prepare(self, frame):
        result = frame[self.columns].copy()
        for c in self.numeric:
            result[c] = pd.to_numeric(result[c], errors='coerce').astype(float)
            if c in {'mileage_km', 'feat_battery_range', 'feat_battery_capacity'}:
                result[c] = np.log1p(result[c].clip(lower=0))
        for c in self.categorical:
            result[c] = result[c].fillna('<MISSING>').astype(str)
        return result


def conformal_quantile(scores, alpha):
    values = np.asarray(scores, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError("Require nonempty finite calibration scores")
    if not 0 < alpha < 1:
        raise ValueError("Require alpha in (0,1)")
    k = int(np.ceil((len(values) + 1) * (1 - alpha)))
    return (float(np.sort(values)[k - 1]) if k <= len(values) else float('inf')), k


def inherited_endpoints(lower, upper, masks):
    """All inputs are predictions on subreports; no private completions."""
    lower, upper = np.asarray(lower), np.asarray(upper)
    masks = np.asarray(masks, dtype=bool)
    if lower.shape != upper.shape or lower.ndim != 2 or lower.shape[1] != len(masks):
        raise ValueError("Inconsistent state endpoint arrays")
    result_l, result_u = np.empty_like(lower), np.empty_like(upper)
    for h, mask in enumerate(masks):
        # A superset of hidden fields is a weaker public report.
        weak = np.all(masks | ~mask, axis=1)
        result_l[:, h] = lower[:, weak].max(axis=1)
        result_u[:, h] = upper[:, weak].min(axis=1)
    return result_l, result_u


def lower_quote(lower):
    # Do not reset an empty double-sided interval's quote: that breaks the order.
    return np.maximum(0, lower)


def public_allocate(scores, reported_missing, states, capacity, next_states):
    """Single-field hard cap; only before-query scores/public eligibility."""
    n = len(states)
    if not 0 <= capacity <= n:
        raise ValueError("Invalid capacity")
    public = np.asarray(scores)[np.arange(n), states].copy()
    public[~reported_missing[np.arange(n), states]] = -np.inf
    public[~np.isfinite(public) | (public <= 0)] = -np.inf
    fields = np.argmax(public, axis=1)
    values = public[np.arange(n), fields]
    order = np.argsort(-values, kind='stable')
    chosen = order[np.isfinite(values[order])][:capacity]
    actions = np.full(n, -1, dtype=int)
    actions[chosen] = fields[chosen]
    final = np.asarray(states).copy()
    final[chosen] = next_states[states[chosen], fields[chosen]]
    return final, actions
