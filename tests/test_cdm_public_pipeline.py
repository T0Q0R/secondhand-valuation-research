import numpy as np
import pandas as pd

import cdm_public_pipeline as pipeline
from cdm_mechanism import POLICIES
from savval import StateSpace


class Head:
    def score(self,x,pred,space,kind,*,reported_missing):
        return np.where(reported_missing,1.,-np.inf)


class Model:
    space=StateSpace.build(2)


def quote(model,public):
    observed=public.mileage_km.fillna(50.).to_numpy(float)
    return 10.-observed/1000,np.column_stack((observed,np.ones(len(public))))


def public_frame():
    return pd.DataFrame({'mileage_km':[np.nan,np.nan],
                         'transmission':['manual','automatic'],
                         'fuel_type':['gas','gas'],
                         'feat_body_condition':['fair','good']})


def test_private_source_world_only_affects_replay_after_public_selection(monkeypatch):
    monkeypatch.setattr(pipeline,'current_quote',quote)
    public=public_frame()
    alpha=np.eye(len(POLICIES))[POLICIES.index('field-0')]
    def replay(value):
        def callback(frame,actions):
            result=frame.copy()
            success=np.zeros(len(frame),bool)
            for i in np.flatnonzero(actions>=0):
                if not np.isnan(value):
                    result.loc[i,'mileage_km']=value
                    success[i]=True
            return result,success
        return callback
    natural=pipeline.public_pipeline(Model(),Head(),['a','b'],public,alpha,.5,.2,replay(np.nan))
    hidden=pipeline.public_pipeline(Model(),Head(),['a','b'],public,alpha,.5,.2,replay(200.))
    np.testing.assert_array_equal(natural['actions'],hidden['actions'])
    np.testing.assert_array_equal(natural['actions'],[0,-1])
    assert not natural['query_succeeded'].any()
    assert hidden['query_succeeded'].tolist()==[True,False]
    assert natural['capacity']==hidden['capacity']==1
    assert natural['final_quote_log'][0]!=hidden['final_quote_log'][0]
    pd.testing.assert_frame_equal(public,public_frame())


def test_private_draw_selects_whole_rule_and_every_draw_obeys_capacity(monkeypatch):
    monkeypatch.setattr(pipeline,'current_quote',quote)
    alpha=np.full(len(POLICIES),1/len(POLICIES))
    for k in range(len(POLICIES)):
        result=pipeline.select_public(Model(),Head(),['a','b'],public_frame(),alpha,.5,(k+.5)/len(POLICIES))
        assert result['policy_index']==k
        assert (result['actions']>=0).sum()<=1
