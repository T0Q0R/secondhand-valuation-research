"""Cross-check scalar interval geometry against the separate HiGHS LP oracle."""
import itertools
import numpy as np
import pytest
from grouped_smi_oracle import enumerate_objectives as lp
from grouped_smi_interval_oracle import enumerate_objectives as interval

@pytest.mark.parametrize('sign',[-1.,0.,1.])
def test_complete_categorical_family_against_linear_programs(sign):
    rng=np.random.default_rng(910061)
    groups=((1,),(2,3),(4,5,6))
    for case in range(10):
        full=rng.uniform(.1,2.,7)*rng.choice([-1.,1.],7);full[1]=sign*rng.uniform(.1,2.)
        records=[]
        for pattern in range(8):
            omitted=[g for g in range(3) if pattern&(1<<g)]
            columns=[c for g in omitted for c in groups[g]]
            weights=full*rng.uniform(.2,1.5,7);weights[columns]=0.
            records.append({'weights':weights.tolist(),'intercept':float(rng.normal()),
                            'omitted_groups':omitted,'omitted_columns':columns})
        for mask in itertools.product([False,True],repeat=3):
            report=np.array([rng.normal(),rng.uniform(-.1,1.1),1.,0.,0.,1.,0.])
            for g,missing in enumerate(mask):
                if missing:report[list(groups[g])]=np.nan
            for domain in ('free','nonnegative','unit_box'):
                actual=interval(report,records,groups,[1,2],.15,domain)
                expected=lp(report,records,groups,[1,2],.15,domain)
                assert actual['status']==expected['status']
                if actual['status']=='solved':
                    assert actual['retained']==expected['retained']
                    assert actual['lower']==pytest.approx(expected['lower'],abs=1e-7)
                    assert actual['second']==pytest.approx(expected['second'],abs=1e-7)

def test_inconsistent_reduced_family_is_preserved():
    records=[{'weights':[1.,1.],'intercept':0.,'omitted_groups':[],'omitted_columns':[]},
             {'weights':[-1.,0.],'intercept':0.,'omitted_groups':[0],'omitted_columns':[1]}]
    assert interval([1.,np.nan],records,[[1]],[],.15,'free')=={'status':'inconsistent_family'}
