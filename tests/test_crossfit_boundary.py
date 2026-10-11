import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
from run_crossfit import fold_assignments, inner_split
from savval import simulate_market


def test_outer_and_inner_roles_are_balanced_disjoint_and_outcome_independent():
    data = simulate_market(97, 8701)
    folds = fold_assignments(data, 3)
    perturbed = data.copy()
    perturbed.target_log = np.random.default_rng(5).normal(size=len(data)) * 100
    assert np.array_equal(fold_assignments(perturbed, 3), folds)
    assert max(np.bincount(folds)) - min(np.bincount(folds)) <= 1
    for fold in range(3):
        outer_ids = set(data.loc[folds == fold, "listing_id"])
        estimator, guidance = inner_split(data.loc[folds != fold], .3)
        estimator_ids, guidance_ids = set(estimator.listing_id), set(guidance.listing_id)
        assert not estimator_ids & guidance_ids
        assert not outer_ids & (estimator_ids | guidance_ids)
        assert outer_ids | estimator_ids | guidance_ids == set(data.listing_id)
        pe, pg = inner_split(perturbed.loc[folds != fold], .3)
        assert estimator.listing_id.tolist() == pe.listing_id.tolist()
        assert guidance.listing_id.tolist() == pg.listing_id.tolist()
