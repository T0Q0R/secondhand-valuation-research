"""Boundary cases that can invalidate EMC's stated guarantees."""
import numpy as np

from emc_val import conformal_quantile, inherited_endpoints, lower_quote, public_allocate


def test_small_calibration_requires_infinite_sentinel():
    q, rank = conformal_quantile(np.arange(10, dtype=float), .05)
    assert rank == 11 and np.isposinf(q)
    q, rank = conformal_quantile(np.arange(19, dtype=float), .05)
    assert rank == 19 and q == 18


def test_empty_certificate_cannot_reset_price_and_reward_hiding():
    # Complete evidence has conflicting base certificates; hiding looks benign.
    masks = np.array([[False], [True]])
    lo, hi = inherited_endpoints(np.array([[20., 10.]]), np.array([[5., 30.]]), masks)
    assert lo[0, 0] > hi[0, 0]  # Explicitly invalid, never reverse endpoints.
    quote = lower_quote(lo)
    assert quote.tolist() == [[20., 10.]]
    # A tempting zero-on-invalid rule would let withholding earn 10 instead of 0.
    assert quote[0, 0] >= quote[0, 1]


def test_failed_query_spends_only_slot_and_visible_field_is_ineligible():
    scores = np.array([[[100., 2.]], [[100., 1.]]])
    missing = np.array([[[False, True]], [[False, True]]])
    # Both fields absent naturally in the replay table: query changes no state.
    final, actions = public_allocate(scores, missing, np.array([0, 0]), 1, np.array([[0, 0]]))
    assert actions.tolist() == [1, -1] and final.tolist() == [0, 0]
