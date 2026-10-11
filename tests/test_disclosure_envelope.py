import itertools
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
from disclosure_envelope import disclosure_envelope


def lattice(d):
    return np.array(list(itertools.product([False, True], repeat=d)), dtype=bool)


def test_further_withholding_cannot_increase_quote_and_uses_public_inputs():
    masks = lattice(4)
    raw = np.random.default_rng(104).normal(size=(7, len(masks)))
    closed = disclosure_envelope(raw, masks)
    for h, report in enumerate(masks):
        for j, further in enumerate(masks):
            if np.all(further | ~report):
                assert np.all(closed[:, j] <= closed[:, h] + 1e-12)
        # These perturbed states disclose a value hidden in the public report,
        # and so must not affect its quote.
        altered = raw.copy()
        incompatible = ~(masks | ~report).all(axis=1)
        altered[:, incompatible] += 1000
        np.testing.assert_allclose(disclosure_envelope(altered, masks)[:, h], closed[:, h])


def test_zero_uplift_can_coexist_with_large_honest_overvaluation():
    masks = lattice(1)
    # Truthful base quote is 1, but the fully hidden base quote is 10.
    closed = disclosure_envelope(np.array([[1., 10.]]), masks)
    assert closed[0, 0] == closed[0, 1] == 10.
    assert closed[0, 0] - 1. == 9.
    with pytest.raises(ValueError, match="complete"):
        disclosure_envelope(np.array([[1.]]), np.array([[False]]))
