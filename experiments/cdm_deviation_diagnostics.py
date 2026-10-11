"""Common-profile CDM diagnostic statistics; no probability fitting."""
from __future__ import annotations

import numpy as np


PROFILE_NAMES = ('truthful', 'no_query_max', 'random_603',
                 'saved_suppression_response', 'saved_benefit_response')


def top_mass_mean(values, fraction=.05):
    """Exact upper empirical tail mean, including fractional boundary mass."""
    values = np.asarray(values, dtype=float).ravel()
    if not len(values) or not np.isfinite(values).all() or not 0 < fraction <= 1:
        raise ValueError('Finite nonempty values and a valid tail fraction required')
    ordered = np.sort(values)[::-1]
    mass = fraction * len(ordered)
    whole = int(np.floor(mass))
    remainder = mass - whole
    total = ordered[:whole].sum()
    if remainder > 0 and whole < len(ordered):
        total += remainder * ordered[whole]
    return float(total / mass)


def measures(values):
    values = np.asarray(values, dtype=float).ravel()
    return {'mean_envelope': float(values.mean()),
            'maximum_envelope': float(values.max()),
            'p95_envelope': float(np.quantile(values, .95)),
            'cvar95_envelope': top_mass_mean(values)}


def profile_bank(pred, valid, suppression_states, benefit_states):
    n = len(pred)
    rng = np.random.default_rng(603)
    profiles = [np.zeros(n, int), np.argmax(np.where(valid, pred, -np.inf), axis=1),
                np.array([rng.choice(np.flatnonzero(v)) for v in valid]),
                np.asarray(suppression_states, int), np.asarray(benefit_states, int)]
    result = np.asarray(profiles)
    if result.shape != (5, n) or not valid[np.arange(n)[None], result].all():
        raise ValueError('Every common profile must be legal')
    return result


def envelopes(signed_quotes, valid, probabilities):
    """Expectation over complete rules precedes legal-report maximization."""
    gains = signed_quotes @ np.asarray(probabilities).T
    gains = np.where(np.asarray(valid)[:, :, None], gains, -np.inf)
    states = gains.argmax(axis=1)
    values = np.maximum(gains.max(axis=1), 0.0)
    return values, states
