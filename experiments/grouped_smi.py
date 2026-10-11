"""Clean-room categorical one-hot adaptation of inspected SMI equations 7/8."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from support_margin import LinearModel, MarginResult, MarginSolveError, sign_consistent


@dataclass(frozen=True)
class GroupedFamily:
    models: tuple[LinearModel, ...]
    groups: tuple[tuple[int, ...], ...]
    omitted_groups: tuple[frozenset[int], ...]
    categorical_groups: frozenset[int]

    def retained(self, missing_groups):
        missing_groups=frozenset(missing_groups)
        if not missing_groups <= frozenset(range(len(self.groups))):
            raise ValueError('Unknown missing field')
        if len(self.models)!=len(self.omitted_groups) or self.omitted_groups[0]:
            raise ValueError('Full model must be first')
        expected={frozenset(g for g in range(len(self.groups)) if p & (1 << g))
                  for p in range(1 << len(self.groups))}
        if set(self.omitted_groups)!=expected or len(self.models)!=len(expected):
            raise ValueError('Complete group-reduced family required')
        full=self.models[0]
        retained=[]
        for model,omitted in zip(self.models,self.omitted_groups):
            expected_columns=frozenset(c for g in omitted for c in self.groups[g])
            if model.omitted!=expected_columns:
                raise ValueError('Reduced model does not omit complete fields')
            if omitted<=missing_groups and (not omitted or sign_consistent(full,model)):
                retained.append(model)
        if missing_groups and not any(m.omitted==frozenset(c for g in missing_groups for c in self.groups[g]) for m in retained):
            raise MarginSolveError('Fully reduced model is not sign consistent')
        return retained


def solve_grouped_smi(report,family,epsilon,domain):
    if domain not in ('free','nonnegative','unit_box'):
        raise ValueError('Unknown mileage domain')
    x=np.array(report,dtype=float,copy=True)
    if x.ndim!=1 or np.isinf(x).any() or not np.isfinite(epsilon) or epsilon<0:
        raise ValueError('Finite report and nonnegative epsilon required')
    missing_groups=[]
    for g,columns in enumerate(family.groups):
        flags=np.isnan(x[list(columns)])
        if flags.any() and not flags.all():
            raise ValueError('Partial categorical/field withholding is not allowed')
        if flags.all():missing_groups.append(g)
    missing=np.flatnonzero(np.isnan(x))
    if set(missing)!=set(c for g in missing_groups for c in family.groups[g]):
        raise ValueError('Only optional fields may be missing in solver input')
    models=family.retained(missing_groups)
    if not len(missing):
        value=float(models[0].weights @ x+models[0].intercept)
        return MarginResult(x,value,value,0.,value,value,1)
    observed=np.flatnonzero(np.isfinite(x))
    constants=np.array([m.weights[observed] @ x[observed]+m.intercept for m in models])
    weights=np.stack([m.weights[missing] for m in models])
    lower=np.full(len(missing),-np.inf);upper=np.full(len(missing),np.inf)
    integrality=np.zeros(len(missing),int)
    categorical=[]
    for g in missing_groups:
        local=np.flatnonzero(np.isin(missing,family.groups[g]))
        if g in family.categorical_groups:
            lower[local]=0;upper[local]=1;integrality[local]=1
            constraint=np.zeros(len(missing));constraint[local]=1;categorical.append(constraint)
        else:
            if len(local)!=1:raise ValueError('Only scalar continuous optional groups are supported')
            if domain!='free':lower[local]=0
            if domain=='unit_box':upper[local]=1
    cats=np.array(categorical).reshape((-1,len(missing)))
    first_constraints=[LinearConstraint(np.c_[weights,-np.ones(len(models))],-np.inf,epsilon-constants)]
    if len(cats):first_constraints.append(LinearConstraint(np.c_[cats,np.zeros(len(cats))],1.,1.))
    first=milp(np.r_[np.zeros(len(missing)),1.],integrality=np.r_[integrality,0],
               bounds=Bounds(np.r_[lower,-np.inf],np.r_[upper,np.inf]),constraints=first_constraints,
               options={'mip_rel_gap':0.})
    if not first.success:raise MarginSolveError(f'Grouped equation (7): status {first.status}: {first.message}')
    ystar=float(first.fun)
    objective=np.sign(models[0].weights[missing])
    second_constraints=[LinearConstraint(weights,ystar-constants,ystar+epsilon-constants)]
    if len(cats):second_constraints.append(LinearConstraint(cats,1.,1.))
    second=milp(objective,integrality=integrality,bounds=Bounds(lower,upper),
                constraints=second_constraints,options={'mip_rel_gap':0.})
    if not second.success:raise MarginSolveError(f'Grouped equation (8): status {second.status}: {second.message}')
    imputed=second.x.copy()
    imputed[integrality==1]=np.rint(imputed[integrality==1])
    centers=constants+weights @ imputed
    if centers.min()<ystar-2e-6 or centers.max()>ystar+epsilon+2e-6:
        raise MarginSolveError('Grouped equation (8) margin feasibility failed')
    if len(cats) and not np.allclose(cats @ imputed,1,atol=1e-9,rtol=0):
        raise MarginSolveError('Grouped one-hot feasibility failed')
    x[missing]=imputed
    return MarginResult(x,float(centers[0]),ystar,float(objective @ imputed),
                        float(centers.min()),float(centers.max()),len(models))
