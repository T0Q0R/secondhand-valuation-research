"""Independent categorical enumeration and continuous LP oracle for SMI audit.

This module does not call the production mixed-integer solver or family filter.
"""
from __future__ import annotations

import itertools

import numpy as np
from scipy.optimize import linprog


def enumerate_objectives(report,model_records,groups,categorical,epsilon,domain):
    x=np.array(report,float,copy=True)
    missing={g for g,columns in enumerate(groups) if np.isnan(x[list(columns)]).all()}
    if not missing:
        value=float(np.array(model_records[0]['weights']) @ x+model_records[0]['intercept'])
        return {'status':'solved','lower':value,'second':0.,'retained':1}
    retained=[]
    full=np.array(model_records[0]['weights'])
    for record in model_records:
        omitted=set(record['omitted_groups'])
        if not omitted<=missing:continue
        coefficients=np.array(record['weights'])
        kept=[j for j in range(len(full)) if j not in record['omitted_columns']]
        if np.array_equal(np.sign(coefficients[kept]),np.sign(full[kept])):
            retained.append(record)
    if not any(set(record['omitted_groups'])==missing for record in retained):
        return {'status':'inconsistent_family'}
    categorical_missing=sorted(missing & set(categorical))
    continuous=[c for g in sorted(missing-set(categorical)) for c in groups[g]]
    if len(continuous)>1:raise ValueError('Oracle supports one continuous optional field')
    bounds={'free':(None,None),'nonnegative':(0,None),'unit_box':(0,1)}[domain]
    matrix=np.array([record['weights'] for record in retained])
    intercepts=np.array([record['intercept'] for record in retained])
    candidates=[]
    for assignment in itertools.product(*[groups[g] for g in categorical_missing]):
        completed=x.copy()
        for g,chosen in zip(categorical_missing,assignment):
            completed[list(groups[g])]=0.;completed[chosen]=1.
        cat_objective=float(sum(np.sign(full[chosen]) for chosen in assignment))
        if continuous:
            col=continuous[0];completed[col]=0.
            constants=matrix @ completed+intercepts;slopes=matrix[:,col]
            first=linprog([0.,1.],A_ub=np.c_[slopes,-np.ones(len(retained))],
                          b_ub=epsilon-constants,bounds=[bounds,(None,None)],method='highs')
            if first.status==3:return {'status':'unbounded_stage_7'}
            if first.status==2:continue
            if not first.success:raise RuntimeError(f'Independent LP status {first.status}')
            lower=float(first.fun)
        else:
            constants=matrix @ completed+intercepts;slopes=None
            lower=float(np.max(constants-epsilon))
        candidates.append((constants,slopes,cat_objective,lower))
    if not candidates:return {'status':'infeasible_stage_7'}
    ystar=min(c[3] for c in candidates)
    second_values=[]
    for constants,slopes,cat_objective,_ in candidates:
        if continuous:
            second=linprog([np.sign(full[continuous[0]])],A_ub=np.r_[slopes,-slopes][:,None],
                           b_ub=np.r_[ystar+epsilon-constants,constants-ystar],bounds=[bounds],method='highs')
            if second.status==3:return {'status':'unbounded_stage_8'}
            if second.status==2:continue
            if not second.success:raise RuntimeError(f'Independent LP status {second.status}')
            second_values.append(float(second.fun)+cat_objective)
        elif constants.min()>=ystar-1e-7 and constants.max()<=ystar+epsilon+1e-7:
            second_values.append(cat_objective)
    if not second_values:return {'status':'infeasible_stage_8'}
    return {'status':'solved','lower':ystar,'second':min(second_values),'retained':len(retained)}
