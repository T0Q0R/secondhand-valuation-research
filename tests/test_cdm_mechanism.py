import numpy as np
from scipy.optimize import linprog

from cdm_mechanism import Market, solve_mixture
from savval import StateSpace, allocate


def fixture():
    rng = np.random.default_rng(809)
    space = StateSpace.build(2)
    pred = rng.normal(10, .1, (7, 11))
    missing = np.broadcast_to(space.masks[None], (7, 11, 4)).copy()
    missing[0, :, 3] = True  # Naturally absent; replay must stay in the same state.
    scores = np.where(missing[None], rng.random((3, 7, 11, 4)), -np.inf)
    valid = np.ones((7, 11), bool)
    valid[0, space.masks[:, 3]] = False
    return Market(pred, scores, valid, space, 2, .01)


def test_exact_unilateral_rank_matches_complete_reallocation():
    market = fixture()
    states = np.array([1, 2, 3, 4, 5, 6, 7])
    for i in range(market.n):
        candidate = market.candidate_quotes(i, states)
        for s in np.flatnonzero(market.valid[i]):
            trial = states.copy()
            trial[i] = s
            quotes, _, actions = market.execute(trial)
            np.testing.assert_array_equal(candidate[s], quotes[i])
            assert np.all((actions >= 0).sum(axis=0) <= 2)


def test_failure_consumes_slot_and_private_validity_does_not_allocate():
    market = fixture()
    market.scores[:] = -np.inf
    market.scores[:, 0, 0, 3] = 10  # Natural missingness; no recorded value.
    market.scores[:, 1, 1, 0] = 9
    states = np.zeros(7, int)
    states[1] = 1
    market.capacity = 1
    quote, finals, action = market.execute(states)
    np.testing.assert_array_equal(action[0], [3, 3, 3])
    np.testing.assert_array_equal(finals[0], [0, 0, 0])
    np.testing.assert_array_equal(action[1], [-1, -1, -1])
    changed_validity = market.valid.copy()
    changed_validity[2, 4] = False
    other = Market(market.pred, market.scores, changed_validity, market.space, 1)
    np.testing.assert_array_equal(other.execute(states)[2], action)


def test_signed_gain_mixes_before_positive_truncation():
    # Clipping each column first changes the minimax value from zero to one.
    matrix = np.array([[2., -2.], [-2., 2.], [0., 0.]])
    result = solve_mixture(matrix, [0., 0.], 0.)
    assert abs(result['bound']) < 1e-9
    np.testing.assert_allclose(result['probabilities'], [.5, .5])
    wrong = solve_mixture(np.maximum(matrix, 0), [0., 0.], 0.)
    assert abs(wrong['bound'] - 1.) < 1e-9


def test_normal_error_cap_and_full_lp_equivalence():
    matrix = np.array([[0., 4., 1.], [3., 0., 2.], [0., 0., 0.]])
    errors = np.array([1., 5., 2.])
    result = solve_mixture(matrix, errors, 2.)
    constraint = np.vstack([np.c_[matrix, -np.ones(3)], np.r_[errors, 0.]])
    full = linprog([0, 0, 0, 1], A_ub=constraint, b_ub=[0, 0, 0, 2],
                   A_eq=[[1, 1, 1, 0]], b_eq=[1], bounds=[(0, None)] * 4)
    assert full.success
    assert abs(result['bound'] - full.x[-1]) < 1e-9
    assert result['honest_error'] <= 2 + 1e-9
    assert result['normal_error_constraint_has_rule_variation']


def test_response_is_against_expected_rule_and_exact_remaining_regret():
    market = fixture()
    alpha = np.array([.2, .3, .5])
    response = market.response(alpha, sweeps=8, restarts=2)
    for i in range(market.n):
        trial_utility = []
        for s in np.flatnonzero(market.valid[i]):
            trial = response['states'].copy()
            trial[i] = s
            quote, _, _ = market.execute(trial)
            trial_utility.append(quote[i] @ alpha - .01 * market.space.masks[s].sum())
        regret = max(0, max(trial_utility) - response['utility'][i])
        assert abs(regret - response['regret'][i]) < 1e-9
