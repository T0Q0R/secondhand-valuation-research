import numpy as np
import pytest
from equal_benefit_reference import choose_weight,reusable_tag,refit_static
from equal_tuning import fit_group
from run_all import rank_subset
from run_crossfit import inner_split
from savval import FEATURES,price_features,simulate_market

def test_benefit_selection_uses_own_objectives_and_complete_grid():
    rows=[{'gap_weight':b,'objective':v} for b,v in [(.25,2),(.5,1),(1.,3)]]
    assert choose_weight(rows)==.5
    assert choose_weight([dict(r,objective=1.) for r in rows])==.25
    with pytest.raises(ValueError):choose_weight(rows[:-1])
    with pytest.raises(ValueError):choose_weight([rows[0],rows[0],rows[2]])
    with pytest.raises(ValueError):choose_weight([dict(r,objective=np.nan) for r in rows])

def test_static_reuse_requires_exact_weight_and_role():
    assert reusable_tag(.5,1.)=='fixed__robust_no_feedback'
    assert reusable_tag(1.,1.)=='tuned__robust_no_feedback'
    assert reusable_tag(.25,1.) is None
    with pytest.raises(ValueError):reusable_tag(.75,.25)

def test_backbone_reuse_resets_residual_and_matches_full_static_refit():
    frame=rank_subset(simulate_market(100,8130),100,'equal-benefit-test')
    estimator,guidance=inner_split(frame,.3)
    config={'maximum_hidden':2,'catboost_iterations':8,'head_trees':8,'residual_epochs':2,
        'residual_hidden_width':64,'batch_size':40,'learning_rate':.001,'gap_penalty_weight':.5,
        'attack_loss_weight':.5,'anchor_weight':.25,'gap_tolerance_log':.02,'concealment_cost_log':0.}
    first,_=fit_group(estimator,guidance,FEATURES['synthetic'],config,13,{'fixed__robust_no_feedback':.5})
    fixed=first['fixed__robust_no_feedback'][0]
    public=price_features(guidance,FEATURES['synthetic']);before=fixed.predict(public)[0].copy()
    reused,trace=refit_static(fixed,estimator,guidance,FEATURES['synthetic'],config,13,1.)
    reference,_=fit_group(estimator,guidance,FEATURES['synthetic'],config,13,{'selected__robust_no_feedback':1.})
    actual=reused[0].predict(public)[0];expected=reference['selected__robust_no_feedback'][0].predict(public)[0]
    np.testing.assert_allclose(actual,expected,atol=1e-9,rtol=0)
    np.testing.assert_array_equal(fixed.predict(public)[0],before)
    assert reused[2]=='benefit' and len(trace)==2
