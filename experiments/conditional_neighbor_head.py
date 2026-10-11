"""Clean-room one-query regression ACO adaptation; see its explicit contract."""
from __future__ import annotations

import hashlib

import numpy as np

from savval import ACTIONS


def encoder_groups(encoder):
    """Original-field blocks, respecting indicator and infrequent OHE widths."""
    transformer = encoder.transformer
    groups = {field: [] for field in encoder.columns}
    weights = []
    numeric = transformer.output_indices_["numeric"]
    for j, field in enumerate(encoder.numeric):
        groups[field].append(numeric.start + j)
        weights.append(1.)
    imputer = transformer.named_transformers_["numeric"].named_steps["simpleimputer"]
    for j, original in enumerate(imputer.indicator_.features_):
        groups[encoder.numeric[original]].append(numeric.start + len(encoder.numeric) + j)
        weights.append(.5)
    if len(weights) != numeric.stop:
        raise ValueError("Unexpected numeric encoder output layout")
    categorical = transformer.named_transformers_["categorical"]
    cursor = transformer.output_indices_["categorical"].start
    for field, categories, rare in zip(encoder.categorical, categorical.categories_, categorical.infrequent_categories_):
        width = len(categories) if rare is None else len(categories) - len(rare) + 1
        groups[field] = list(range(cursor, cursor + width))
        weights.extend([.5] * width)
        cursor += width
    if cursor != transformer.output_indices_["categorical"].stop:
        raise ValueError("Unexpected grouped categorical encoder output layout")
    if sorted(j for block in groups.values() for j in block) != list(range(len(weights))):
        raise ValueError("Original-field blocks do not partition encoded coordinates")
    if not set(ACTIONS) <= set(groups):
        raise ValueError("All original acquisition fields required")
    return groups, np.array(weights)


class ConditionalNeighborHead:
    def __init__(self, bank_encoded, bank_available, losses, groups, weights, k=25):
        self.bank = np.asarray(bank_encoded, dtype=float)
        self.available = np.asarray(bank_available, dtype=bool)
        self.losses = np.asarray(losses, dtype=float)
        self.groups, self.weights, self.k = groups, np.asarray(weights, float), int(k)
        n, d = self.bank.shape
        if n < 1 or self.available.shape != (n, 4) or self.losses.shape != (n, 16):
            raise ValueError("Four original fields and sixteen bank observation patterns required")
        if self.weights.shape != (d,) or np.any(self.weights <= 0) or self.k < 1:
            raise ValueError("Positive coordinate weights and neighbor count required")
        if not np.isfinite(self.bank).all() or not np.isfinite(self.losses).all():
            raise ValueError("Finite bank values and losses required")
        if sorted(j for block in groups.values() for j in block) != list(range(d)):
            raise ValueError("Field groups must partition bank coordinates")
        if not set(ACTIONS) <= set(groups):
            raise ValueError("Acquisition groups missing")
        self.pattern_eligible_counts = []
        self.bank_ood_new_hiding_counts = []
        self._cache = None
        for pattern in range(16):
            missing = ((pattern >> np.arange(4)) & 1).astype(bool)
            eligible = self.available[:, ~missing].all(axis=1)
            self.pattern_eligible_counts.append(int(eligible.sum()))
            self.bank_ood_new_hiding_counts.append(int((self.available[:, missing].sum(1) > 2).sum()))

    def _pattern_bank(self, pattern):
        missing = ((pattern >> np.arange(4)) & 1).astype(bool)
        unseen = {ACTIONS[j] for j in np.flatnonzero(missing)}
        blocks = sorted([block for field, block in self.groups.items() if field not in unseen], key=min)
        eligible = np.flatnonzero(self.available[:, ~missing].all(axis=1))
        return missing, blocks, eligible, self.bank[eligible]

    def score(self, x, pred, space, kind, *, reported_missing):
        if kind != "benefit":
            raise ValueError("ACO-1 adaptation uses conditional prediction-loss benefit")
        x = np.asarray(x)
        n, s, d = x.shape
        if pred.shape != (n, s) or reported_missing.shape != (n, s, 4) or d != self.bank.shape[1]:
            raise ValueError("Public query array shape mismatch")
        if not np.isfinite(x).all():
            raise ValueError("Finite public encoding required")
        # Memoization changes runtime only, not scores or eligibility. Before-
        # query prediction is deliberately unused by this neighbor-mask loss
        # approximation; all loss values are from allowed training-bank rows.
        digest = hashlib.sha256(np.ascontiguousarray(x).tobytes() + np.ascontiguousarray(reported_missing).tobytes()).hexdigest()
        if self._cache is not None and self._cache[0] == digest:
            return self._cache[1].copy()
        flat = x.reshape(-1, d)
        patterns = reported_missing.reshape(-1, 4).astype(int) @ (1 << np.arange(4))
        result = np.full((len(flat), 4), -np.inf)
        missing_neighbor_states = 0
        for pattern in np.unique(patterns):
            missing, blocks, eligible, bank = self._pattern_bank(int(pattern))
            selected = np.flatnonzero(patterns == pattern)
            if not len(eligible):
                missing_neighbor_states += len(selected)
                continue
            count = min(self.k, len(eligible))
            for chunk_start in range(0, len(selected), 256):
                idx = selected[chunk_start:chunk_start + 256]
                query = np.asarray(flat[idx], dtype=float)
                distances = np.zeros((len(idx), len(eligible)))
                # Canonical original-field order survives JSON key sorting.
                # One-hot products count exact category matches (0/1), avoiding
                # sqrt-weight Gram cancellation at equal neighbor distances.
                for block in blocks:
                    if np.all(self.weights[block] == .5):
                        q, b = query[:, block], bank[:, block]
                        distances += .5 * (q.sum(1)[:, None] + b.sum(1)[None] - 2 * q @ b.T)
                    else:
                        for j in block:
                            distances += self.weights[j] * np.square(query[:, j, None] - bank[None, :, j])
                neighbors = eligible[np.argsort(distances, axis=1, kind="stable")[:, :count]]
                for field in np.flatnonzero(missing):
                    after = int(pattern) & ~(1 << field)
                    gains = self.losses[neighbors, int(pattern)] - self.losses[neighbors, after]
                    result[idx, field] = gains.mean(1)
        shaped = result.reshape(n, s, 4)
        self.last_coverage = {"queried_public_states": n * s, "no_eligible_neighbor_states": missing_neighbor_states}
        self._cache = (digest, shaped.copy())
        return shaped
