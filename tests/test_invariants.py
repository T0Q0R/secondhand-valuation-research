import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
from savval import ACTIONS, ActionHeads, Encoder, StateSpace, allocate, audit_deviations, price_features, strategic_response


def test_attacker_accounts_for_verification_avoidance():
    # One listing, one slot: hide only A is fully undone. Hide A+B leaves B
    # unverified, despite A+B having a lower *pre-audit* quote than A alone.
    space = StateSpace.build(2)
    pred = np.zeros((1, len(space.masks)))
    pred[0, 1], pred[0, 2], pred[0, 5] = 10, 6, 8
    scores = np.full((1, len(space.masks), 4), -np.inf)
    scores[0, 1, 0] = 1
    scores[0, 2, 1] = 1
    scores[0, 5, 0] = 1
    result = strategic_response(pred, scores, np.ones_like(pred, bool), space, budget=1)
    assert result["states"][0] == 5
    assert result["final_state"][0] == 2
    assert result["utility"][0] == 6
    assert result["best_response_converged"]


def test_capacity_reallocated_when_report_changes():
    space = StateSpace.build(1)
    pred = np.array([[0, 3, 2, 1, 1], [0, 4, 2, 1, 1]], dtype=float)
    scores = np.full((2, 5, 4), -np.inf)
    scores[:, 1, 0] = [2, 1]
    final, actions, _ = allocate(scores, np.array([1, 1]), space, capacity=1)
    assert actions.tolist() == [0, -1]
    assert final.tolist() == [0, 1]
    for capacity_fraction in [0, 0.5, 1]:
        result = strategic_response(pred, scores, np.ones_like(pred, bool), space, budget=capacity_fraction)
        assert (result["action"] >= 0).sum() <= int(2 * capacity_fraction)
        assert np.isfinite(result["regret"]).all()


def test_naturally_unavailable_values_cannot_be_revealed():
    frame = pd.DataFrame({"mileage_km": [np.nan, 100.0], "transmission": ["M", "M"], "fuel_type": ["P", "P"], "feat_body_condition": ["G", "G"]})
    space = StateSpace.build(2)
    _, valid = space.materialize(frame)
    assert not valid[0, space.masks[:, 0]].any()
    assert valid[1].all()


def test_hidden_values_do_not_change_pre_action_input():
    space = StateSpace.build(2)
    a = pd.DataFrame({"year": [2020, 2021], "mileage_km": [100.0, 200.0], "transmission": ["M", "A"], "fuel_type": ["P", "D"], "feat_body_condition": ["G", "F"]})
    flat, _ = space.materialize(a)
    encoder = Encoder().fit(flat)
    b = a.copy()
    b.loc[0, "mileage_km"] = 999999.0
    fa, _ = space.materialize(a)
    fb, _ = space.materialize(b)
    xa, xb = encoder.transform(fa), encoder.transform(fb)
    assert np.array_equal(xa[1], xb[1])
    assert not np.array_equal(xa[0], xb[0])
    # Heads are a pure function of masked state, before-price and action.
    pa, pb = np.zeros((2, len(space.masks))), np.zeros((2, len(space.masks)))
    ha = ActionHeads.matrix(xa.reshape(2, len(space.masks), -1), pa)
    hb = ActionHeads.matrix(xb.reshape(2, len(space.masks), -1), pb)
    assert np.array_equal(ha[4:8], hb[4:8])


def test_targets_and_aliases_rejected_from_predictors():
    for prohibited in ["target_log", "price_value_JOD", "mileage_text", "engine_type", "listing_id"]:
        with pytest.raises(ValueError):
            price_features(pd.DataFrame({prohibited: [1]}), [prohibited])


def test_natural_missingness_and_withholding_are_publicly_indistinguishable():
    space = StateSpace.build(1)
    a = pd.DataFrame({"mileage_km": [np.nan, 100.0], "transmission": ["M", "M"], "fuel_type": ["P", "P"], "feat_body_condition": ["G", "G"]})
    flat, valid = space.materialize(a)
    encoder = Encoder().fit(flat)
    x = encoder.transform(flat).reshape(2, len(space.masks), -1)
    missing = space.reported_missing(a)
    assert np.array_equal(x[0, 0], x[1, 1])
    assert np.array_equal(missing[0, 0], missing[1, 1])
    heads = ActionHeads(5, 13)
    pred = np.ones((2, len(space.masks)))
    heads.fit(x, pred, valid, np.ones(2), space, reported_missing=missing)
    merit = heads.score(x, pred, space, "suppression", reported_missing=missing)
    assert np.array_equal(merit[0, 0], merit[1, 1])


def test_failed_query_spends_capacity_and_does_not_invent_a_value():
    space = StateSpace.build(1)
    scores = np.full((2, 5, 4), -np.inf)
    scores[0, 0, 0] = 3  # Record 0 has naturally absent mileage.
    scores[1, 1, 0] = 2  # Record 1 strategically hid its mileage.
    final, action, _ = allocate(scores, np.array([0, 1]), space, capacity=1)
    assert action.tolist() == [0, -1]
    assert final.tolist() == [0, 1]


def test_exact_unilateral_audit_agrees_with_search_across_costs_and_ties():
    space = StateSpace.build(2)
    rng = np.random.default_rng(821)
    n, s = 6, len(space.masks)
    pred = rng.normal(10, .2, (n, s))
    scores = np.where(space.reveal[None] >= 0, rng.integers(0, 4, (n, s, 4)), -np.inf)
    valid = np.ones((n, s), bool)
    for budget in [0, .5, 1]:
        for cost in [0, .05]:
            result = strategic_response(pred, scores, valid, space, budget=budget, sweeps=20, restarts=3, cost=cost)
            audit = audit_deviations(pred, scores, valid, result['states'], space, result['capacity'], cost)
            assert np.allclose(result['regret'], audit['regret'])
            final_quote = pred[np.arange(n), result['final_state']]
            assert (audit['maximum_quote'] >= final_quote - 1e-9).all()
