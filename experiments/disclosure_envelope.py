"""Generic disclosure-monotone closure, used only as a diagnostic control.

This is not a reproduction of the AAAI 2021 classifier or an original
incentive-compatibility theorem. It illustrates why zero withholding uplift
alone need not imply accurate valuation. All subsets are evaluated, including
mask patterns absent from the backbone's two-hidden-field augmentation.
"""
from __future__ import annotations

import numpy as np


def disclosure_envelope(predictions, masks):
    """At report H, maximize base quotes over further-withheld reports J >= H.

    The input covers the complete Boolean lattice of optional-field masks.
    Any further withholding shrinks the maximization set, so it cannot raise
    the resulting quote. Each compatible input hides every field hidden in H;
    therefore the envelope can be computed from the public report alone.
    """
    predictions = np.asarray(predictions, dtype=float)
    masks = np.asarray(masks, dtype=bool)
    if predictions.ndim != 2 or masks.ndim != 2 or predictions.shape[1] != len(masks):
        raise ValueError("Prediction/mask shape mismatch")
    if not np.isfinite(predictions).all():
        raise ValueError("Envelope needs finite base quotes")
    if len(masks) != 2 ** masks.shape[1] or len({tuple(m) for m in masks}) != len(masks):
        raise ValueError("A complete optional-field mask lattice is required")
    compatible = (masks[None, :, :] | ~masks[:, None, :]).all(axis=2)
    return np.stack([predictions[:, compatible[h]].max(axis=1) for h in range(len(masks))], axis=1)
