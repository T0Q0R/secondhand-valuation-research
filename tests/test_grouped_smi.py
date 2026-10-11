import numpy as np
import pytest

from grouped_smi import GroupedFamily,solve_grouped_smi
from support_margin import LinearModel,MarginSolveError


def family():
    # One observed mandatory coordinate, one mileage, and one two-level category.
    groups=((1,),(2,3))
    coefficients=[([1,1,1,2],0),([1,0,1,2],0),([1,1,0,0],0),([1,0,0,0],1)]
    models=[];omitted=[]
    for pattern,(w,b) in enumerate(coefficients):
        dropped=frozenset(g for g in range(2) if pattern & (1<<g))
        omitted.append(dropped)
        models.append(LinearModel(np.array(w,float),b,frozenset(c for g in dropped for c in groups[g])))
    return GroupedFamily(tuple(models),groups,tuple(omitted),frozenset({1}))


def test_categorical_two_stage_and_full_quote():
    f=family()
    result=solve_grouped_smi([0,np.nan,np.nan,np.nan],f,1.,'unit_box')
    # Enumerating two category choices gives y*=0. With centers in [0,1],
    # category one and mileage zero is the only feasible imputation.
    assert result.lower_margin_objective==pytest.approx(0)
    assert result.stage_two_objective==pytest.approx(1)
    assert result.prediction==pytest.approx(1)
    np.testing.assert_allclose(result.imputed_record,[0,0,1,0])
    assert result.prediction!=result.lower_margin_objective
    assert result.retained_models==4


def test_public_group_withholding_and_inconsistent_family():
    f=family()
    with pytest.raises(ValueError,match='Partial'):
        solve_grouped_smi([0,1,np.nan,0],f,1.,'unit_box')
    changed=list(f.models)
    changed[-1]=LinearModel(np.array([-1,0,0,0.]),1,frozenset({1,2,3}))
    invalid=GroupedFamily(tuple(changed),f.groups,f.omitted_groups,f.categorical_groups)
    with pytest.raises(MarginSolveError,match='sign consistent'):
        solve_grouped_smi([0,np.nan,np.nan,np.nan],invalid,1.,'unit_box')
