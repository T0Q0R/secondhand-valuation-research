import numpy as np

from conditional_neighbor_head import ConditionalNeighborHead, encoder_groups
from savval import ACTIONS, Encoder
import pandas as pd


def bank_head(available=None):
    # One observed context and four optional original-field coordinates.
    bank = np.array([[0, 10, 20, 30, 40], [2, -10, -20, -30, -40]], float)
    losses = np.arange(16, dtype=float)[None].repeat(2, axis=0)
    losses[1] *= 3
    groups = {"context": [0], **{field: [i + 1] for i, field in enumerate(ACTIONS)}}
    return ConditionalNeighborHead(bank, np.ones((2, 4), bool) if available is None else available,
                                   losses, groups, np.ones(5), k=1)


def test_hidden_coordinates_and_quote_do_not_enter_conditional_neighbors():
    head = bank_head()
    missing = np.ones((1, 1, 4), bool)
    x = np.array([[[.1, 123, 456, 789, 999]]], float)
    first = head.score(x, np.zeros((1, 1)), None, "benefit", reported_missing=missing)
    x[:, :, 1:] = -99999
    second = head.score(x, np.full((1, 1), 1e6), None, "benefit", reported_missing=missing)
    np.testing.assert_array_equal(first, second)
    np.testing.assert_array_equal(first[0, 0], [1, 2, 4, 8])


def test_observed_optional_availability_and_no_neighbor_are_publicly_conditioned():
    available = np.zeros((2, 4), bool)
    head = bank_head(available)
    missing = np.array([[[False, True, True, True]]])
    scores = head.score(np.zeros((1, 1, 5)), np.zeros((1, 1)), None, "benefit", reported_missing=missing)
    assert np.isneginf(scores).all()
    assert head.last_coverage["no_eligible_neighbor_states"] == 1


def test_neighbor_ties_use_fixed_bank_order_and_observed_fields_are_not_queried():
    head = bank_head()
    x = np.array([[[1, 0, 0, 0, 0]]], float)
    missing = np.ones((1, 1, 4), bool)
    scores = head.score(x, np.zeros((1, 1)), None, "benefit", reported_missing=missing)
    np.testing.assert_array_equal(scores[0, 0], [1, 2, 4, 8])
    missing[0, 0, 1] = False
    scores = head.score(x, np.zeros((1, 1)), None, "benefit", reported_missing=missing)
    assert np.isneginf(scores[0, 0, 1])


def test_field_dictionary_serialization_order_does_not_change_neighbors():
    head = bank_head()
    head.bank = head.bank.astype(np.float32).astype(float)
    changed = ConditionalNeighborHead(head.bank, head.available, head.losses,
        dict(reversed(list(head.groups.items()))), head.weights, k=1)
    x = np.array([[[.31415927, 0, 0, 0, 0]]], np.float32)
    missing = np.ones((1, 1, 4), bool)
    np.testing.assert_array_equal(
        head.score(x, np.zeros((1, 1)), None, "benefit", reported_missing=missing),
        changed.score(x, np.zeros((1, 1)), None, "benefit", reported_missing=missing))


def test_encoder_groups_include_indicators_and_infrequent_categories():
    frame = pd.DataFrame({"year": [2020] * 12, "mileage_km": np.arange(12, dtype=float),
        "transmission": ["a"] * 10 + ["b", "c"], "fuel_type": ["gas"] * 12,
        "feat_body_condition": ["used"] * 12})
    frame.loc[0, "mileage_km"] = np.nan
    encoder = Encoder().fit(frame)
    groups, weights = encoder_groups(encoder)
    assert len(weights) == encoder.transform(frame).shape[1]
    assert sorted(i for block in groups.values() for i in block) == list(range(len(weights)))
    assert len(groups["mileage_km"]) == 2
    assert len(groups["transmission"]) == 2  # frequent category plus rare bucket
