import numpy as np
import pytest

from cdm_deviation_diagnostics import envelopes, profile_bank, top_mass_mean
from cdm_mechanism import Market
from analyze_cdm_development import candidate_quotes, allocate_independent
from savval import StateSpace


def test_fractional_upper_tail_mass():
    assert top_mass_mean([0., 2., 4.], .5) == pytest.approx(10 / 3)
    assert top_mass_mean([0., 2., 4.], 1.) == 2.
    assert top_mass_mean([0., 2., 4.], .05) == 4.
    with pytest.raises(ValueError):
        top_mass_mean([], .05)


def test_expectation_then_max_and_legal_reports():
    signed = np.array([[[0., 0.], [4., -6.], [-6., 4.], [100., 100.]]])
    legal = np.array([[True, True, True, False]])
    value, state = envelopes(signed, legal, [[.5, .5], [1., 0.]])
    assert value.tolist() == [[0., 4.]]
    assert state.tolist() == [[0, 1]]
    # A draw-aware attacker would obtain four; that is a different game.
    assert (np.maximum(signed[0, :3], 0).max(axis=0) @ [.5, .5]) == 4.


def test_common_profiles_are_legal_and_repeatable():
    pred = np.array([[1., 8., 9.], [3., 2., 1.]])
    legal = np.array([[True, True, False], [True, False, True]])
    a = profile_bank(pred, legal, [1, 0], [0, 2])
    assert np.array_equal(a, profile_bank(pred, legal, [1, 0], [0, 2]))
    assert a[1].tolist() == [1, 0]


@pytest.mark.parametrize('capacity', [0, 1, 3])
def test_complete_reallocation_oracles_with_ties_and_failed_replay(capacity):
    space = StateSpace.build(2)
    n, s = 3, len(space.masks)
    rng = np.random.default_rng(8241)
    pred = rng.normal(size=(n, s))
    scores = rng.choice([-np.inf, 0., 1., 2.], size=(4, n, s, 4))
    # Publicly absent field on a truthful item: a query can consume capacity
    # while replay leaves its report unchanged. Equal merit tests row-ID ties.
    scores[:, 0, 0, :] = -np.inf
    scores[:, 0, 0, 0] = 2.
    valid = np.ones((n, s), bool)
    states = np.array([0, 1, 2])
    vectorized = np.asarray([Market(pred, scores, valid, space, capacity)
                             .candidate_quotes(i, states) for i in range(n)])
    sorted_oracle = candidate_quotes(pred, scores, states, space, capacity)
    direct = np.empty_like(sorted_oracle)
    for i in range(n):
        for state in range(s):
            altered = states.copy(); altered[i] = state
            for k in range(len(scores)):
                final, action = allocate_independent(scores[k], altered, space, capacity)
                assert (action >= 0).sum() <= capacity
                direct[i, state, k] = pred[i, final[i]]
    assert np.allclose(vectorized, direct, rtol=0, atol=1e-12)
    assert np.allclose(sorted_oracle, direct, rtol=0, atol=1e-12)
