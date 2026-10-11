"""Independent categorical enumeration with exact scalar interval geometry.

With a sign-consistent retained family, every retained mileage slope has
the full model's sign or is zero. The fully reduced model has zero slope.
Thus the stage-one minimax envelope attains its minimum at the domain
endpoint in its decreasing direction, or at the largest zero-slope
intercept on an unbounded side. Stage two intersects scalar intervals.
This oracle uses neither the production MILP nor the slow audit LP solver.
"""
from __future__ import annotations
import itertools
import numpy as np

def scalar_objectives(constants, slopes, epsilon, bounds, direction):
    constants, slopes = np.asarray(constants, float), np.asarray(slopes, float)
    lower, upper = bounds
    positive, negative, zero = slopes>0, slopes<0, slopes==0
    if positive.any() and negative.any():
        raise ValueError('Sign-consistent scalar slopes required')
    if positive.any():
        if lower is not None: optimum = float(np.max(constants + slopes*lower) - epsilon)
        elif zero.any(): optimum = float(np.max(constants[zero]) - epsilon)
        else: return {'status':'unbounded_stage_7'}
    elif negative.any():
        if upper is not None: optimum = float(np.max(constants + slopes*upper) - epsilon)
        elif zero.any(): optimum = float(np.max(constants[zero]) - epsilon)
        else: return {'status':'unbounded_stage_7'}
    else:
        optimum = float(np.max(constants) - epsilon)
    return {'status':'solved', 'lower':optimum}

def second_objective(constants, slopes, optimum, epsilon, bounds, direction):
    constants, slopes = np.asarray(constants, float), np.asarray(slopes, float)
    zero = slopes==0
    if np.any(constants[zero] < optimum-1e-7) or np.any(constants[zero] > optimum+epsilon+1e-7):
        return {'status':'infeasible_stage_8'}
    lo = -np.inf if bounds[0] is None else float(bounds[0])
    hi = np.inf if bounds[1] is None else float(bounds[1])
    selected = ~zero
    if selected.any():
        a = (optimum-constants[selected])/slopes[selected]
        b = (optimum+epsilon-constants[selected])/slopes[selected]
        lo = max(lo,float(np.minimum(a,b).max()))
        hi = min(hi,float(np.maximum(a,b).min()))
    if lo>hi+1e-7:return {'status':'infeasible_stage_8'}
    if lo>hi:lo=hi=(lo+hi)/2
    if direction>0:
        if not np.isfinite(lo):return {'status':'unbounded_stage_8'}
        value=lo
    elif direction<0:
        if not np.isfinite(hi):return {'status':'unbounded_stage_8'}
        value=-hi
    else:value=0.
    return {'status':'solved','second':float(value)}

def enumerate_objectives(report,model_records,groups,categorical,epsilon,domain):
    x=np.array(report,float,copy=True)
    missing={g for g,columns in enumerate(groups) if np.isnan(x[list(columns)]).all()}
    if not missing:
        value=float(np.array(model_records[0]['weights']) @ x+model_records[0]['intercept'])
        return {'status':'solved','lower':value,'second':0.,'retained':1}
    full=np.asarray(model_records[0]['weights'])
    retained=[]
    for record in model_records:
        omitted=set(record['omitted_groups'])
        if not omitted<=missing:continue
        kept=[j for j in range(len(full)) if j not in record['omitted_columns']]
        if np.array_equal(np.sign(np.asarray(record['weights'])[kept]),np.sign(full[kept])):
            retained.append(record)
    if not any(set(r['omitted_groups'])==missing for r in retained):return {'status':'inconsistent_family'}
    categorical_missing=sorted(missing & set(categorical))
    continuous=[c for g in sorted(missing-set(categorical)) for c in groups[g]]
    if len(continuous)>1:raise ValueError('Oracle supports one continuous optional field')
    bounds={'free':(None,None),'nonnegative':(0,None),'unit_box':(0,1)}[domain]
    matrix=np.asarray([r['weights'] for r in retained]);intercepts=np.array([r['intercept'] for r in retained])
    candidates=[]
    direction=float(np.sign(full[continuous[0]])) if continuous else 0.
    for assignment in itertools.product(*[groups[g] for g in categorical_missing]):
        completed=x.copy()
        for g,chosen in zip(categorical_missing,assignment):
            completed[list(groups[g])]=0.;completed[chosen]=1.
        cat_objective=float(sum(np.sign(full[chosen]) for chosen in assignment))
        if continuous:completed[continuous[0]]=0.
        constants=matrix @ completed+intercepts
        slopes=matrix[:,continuous[0]] if continuous else None
        first=(scalar_objectives(constants,slopes,epsilon,bounds,direction) if continuous else
               {'status':'solved','lower':float(np.max(constants)-epsilon)})
        if first['status']=='unbounded_stage_7':return first
        candidates.append((constants,slopes,cat_objective,first['lower']))
    if not candidates:return {'status':'infeasible_stage_7'}
    optimum=min(c[3] for c in candidates);seconds=[]
    for constants,slopes,cat_objective,_ in candidates:
        if continuous:
            second=second_objective(constants,slopes,optimum,epsilon,bounds,direction)
            if second['status']=='unbounded_stage_8':return second
            if second['status']=='solved':seconds.append(second['second']+cat_objective)
        elif constants.min()>=optimum-1e-7 and constants.max()<=optimum+epsilon+1e-7:
            seconds.append(cat_objective)
    if not seconds:return {'status':'infeasible_stage_8'}
    return {'status':'solved','lower':optimum,'second':min(seconds),'retained':len(retained)}
