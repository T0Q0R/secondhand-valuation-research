"""Finite observable-report budget oracle; constructed theory, not vehicle results."""
from __future__ import annotations

import argparse
from collections import defaultdict
from fractions import Fraction as F
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

GAPS = ((F(9), F(8), F(1)), (F(1), F(72, 13), F(18)))
ALLOWANCES = (F(0), F(1,4), F(1,2), F(1), F(2), F(3), F(4), F(6))
N = 3
PRIORITIES = tuple(itertools.permutations(range(N)))
RULES = tuple('priority-'+''.join(map(str,p)) for p in PRIORITIES) + ('risk','none')


def keys():
    reports = [(0,)*N] + [tuple(int(i==j) for i in range(N)) for j in range(N)]
    return [(mode,r) for mode in range(len(GAPS)) for r in reports]


def actions(report, budget):
    missing = [i for i,x in enumerate(report) if not x]
    return [tuple(s) for k in range(min(budget,len(missing))+1)
            for s in itertools.combinations(missing,k)]


def quotes(mode, report, source, action, eta):
    after=list(report)
    for i in action:
        if source==i: after[i]=1
    return tuple(F(100)-g+min(eta,g/2) if after[i]
                 else F(100)-min(eta,g/2) for i,g in enumerate(GAPS[mode]))


def leverage(mode, eta):
    return tuple(max(F(0),g-2*eta) for g in GAPS[mode])


def rule_action(name, mode, report, budget, eta):
    if name=='none': return ()
    available=[i for i,x in enumerate(report) if not x and leverage(mode,eta)[i]>0]
    if name=='risk': ordering=sorted(available,key=lambda i:(-leverage(mode,eta)[i],i))
    else:
        priority=PRIORITIES[RULES.index(name)]
        ordering=[i for i in priority if i in available]
    return tuple(sorted(ordering[:budget]))


def waterfill(a, budget):
    positive=sorted((g for g in a if g>0),reverse=True)
    if not positive: return F(0),(F(0),)*N
    if budget==0: return positive[0],(F(0),)*N
    if budget>=len(positive): return F(0),tuple(F(int(g>0)) for g in a)
    for k in range(budget+1,len(positive)+1):
        t=F(k-budget)/sum((1/g for g in positive[:k]),F(0))
        p=tuple(max(F(0),1-t/g) if g>0 else F(0) for g in a)
        if sum(p,F(0))==budget and max((g*(1-x) for g,x in zip(a,p)),default=0)==t:
            return t,p
    raise AssertionError('Exact waterfill active set missing')


def systematic(p, budget):
    """Exact private-U subset lottery; every draw respects the integer budget."""
    ends=[F(0)]
    for value in p:
        if not 0<=value<=1: raise ValueError('Invalid marginal')
        ends.append(ends[-1]+value)
    if ends[-1]>budget: raise ValueError('Marginal sum exceeds actual budget')
    breaks=sorted({F(0),F(1),*(x-x.numerator//x.denominator for x in ends)})
    result=defaultdict(F)
    for lo,hi in zip(breaks,breaks[1:]):
        if lo==hi:continue
        u=(lo+hi)/2
        selected=tuple(i for i,(a,b) in enumerate(zip(ends,ends[1:]))
                       if any(a<=u+k<b for k in range(budget)))
        if len(selected)>budget:raise AssertionError('Actual capacity exceeded')
        result[selected]+=hi-lo
    assert sum(result.values(),F(0))==1
    assert all(sum((w for a,w in result.items() if i in a),F(0))==p[i] for i in range(N))
    return result


def make_problem(budget, eta):
    public=keys(); blocks={}; variables=[]
    for mode,r in public:
        blocks[(mode,r)]=[]
        for action in actions(r,budget):
            blocks[(mode,r)].append(len(variables));variables.append((mode,r,action))
    deviations=[];matrix=[];library=[]
    for mode in range(len(GAPS)):
        for seller in range(N):
            truthful=tuple(int(i==seller) for i in range(N));hidden=(0,)*N
            row=np.zeros(len(variables));lib=[]
            for profile,sign in [(hidden,1),(truthful,-1)]:
                for index in blocks[(mode,profile)]:
                    row[index]+=sign*float(quotes(mode,profile,seller,variables[index][2],eta)[seller])
            for name in RULES:
                qh=quotes(mode,hidden,seller,rule_action(name,mode,hidden,budget,eta),eta)[seller]
                qt=quotes(mode,truthful,seller,rule_action(name,mode,truthful,budget,eta),eta)[seller]
                lib.append(float(qh-qt))
            matrix.append(row);library.append(lib)
            deviations.append({'mode':mode,'source':seller,'seller':seller,
                               'truthful_report':list(truthful),'hidden_report':list(hidden)})
    eq=np.zeros((len(public),len(variables)))
    for k,key in enumerate(public):eq[k,blocks[key]]=1
    return variables,np.asarray(matrix),eq,np.asarray(library),deviations,blocks


def solve(matrix, equality):
    objective=np.r_[np.zeros(matrix.shape[1]),1.0]
    ub=np.column_stack((matrix,-np.ones(len(matrix))))
    eq=np.column_stack((equality,np.zeros(len(equality))))
    result=linprog(objective,A_ub=ub,b_ub=np.zeros(len(ub)),A_eq=eq,
                   b_eq=np.ones(len(eq)),bounds=[(0,None)]*len(objective),method='highs')
    if not result.success:raise RuntimeError(result.message)
    return result,ub,eq


def encode_certificate(result, ub, eq, probabilities=None):
    x=result.x.copy()
    if probabilities is not None:x[:-1]=probabilities
    c=np.r_[np.zeros(len(x)-1),1.0]
    y=result.ineqlin.marginals;z=result.eqlin.marginals
    residual=c-ub.T@y-eq.T@z
    assert max(np.max(ub@x),np.max(np.abs(eq@x-1)))<=1e-8
    assert y.max()<=1e-8 and residual.min()>=-1e-8
    assert abs(z.sum()-x[-1])<=1e-8
    return {'probabilities':x[:-1].tolist(),'bound':float(x[-1]),
            'inequality_dual':y.tolist(),'equality_dual':z.tolist(),
            'dual_objective':float(z.sum()),'dual_min_slack':float(residual.min())}


def run_case(budget,eta):
    variables,matrix,eq,library,descriptions,blocks=make_problem(budget,eta)
    result,ub,full_eq=solve(matrix,eq)
    probabilities=result.x[:-1].copy()
    # Disclosed L cannot be improved by querying natural peers. Remove that
    # irrelevant spending without changing any deviation payoff.
    for (mode,report),indices in blocks.items():
        if any(report):
            probabilities[indices]=0;probabilities[indices[0]]=1
    oracle=encode_certificate(result,ub,full_eq,probabilities)
    restricted,lib_ub,lib_eq=solve(library,np.ones((1,len(RULES))))
    analytic=[]
    for mode in range(len(GAPS)):
        a=leverage(mode,eta);t,p=waterfill(a,budget);dist=systematic(p,budget)
        analytic.append({'mode':mode,'leverages':list(map(str,a)),'bound':str(t),
                         'marginals':list(map(str,p)),
                         'hard_subset_lottery':[{'action':list(s),'mass':str(w)} for s,w in sorted(dist.items())]})
    expected=max(F(x['bound']) for x in analytic)
    assert abs(oracle['bound']-float(expected))<=1e-8
    restricted_cert=encode_certificate(restricted,lib_ub,lib_eq)
    assert restricted_cert['bound']+1e-8>=oracle['bound']
    risk=np.maximum(library[:,RULES.index('risk')],0).max()
    return {'budget':budget,'eta':str(eta),'public_classes':len(blocks),
            'variables':[{'mode':m,'report':list(r),'action':list(a)} for m,r,a in variables],
            'deviations':descriptions,'payoff_matrix':matrix.tolist(),'equality_matrix':eq.tolist(),
            'library_payoff_matrix':library.tolist(),'rules':list(RULES),
            'observable_oracle':oracle,'fixed_global_library':restricted_cert,
            'risk_bound':float(risk),'privileged_recoverability_bound':float(max(leverage(m,eta)[i] for m in range(2) for i in range(N))) if budget==0 else 0.0,
            'analytic':analytic,'scope':'Constructed one-field/at-most-one-recoverable finite family; not real-source evidence.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError('Preserve prior runs')
    args.output.mkdir(parents=True)
    cases=[]
    for eta,budget in itertools.product(ALLOWANCES,range(N+1)):
        case=run_case(budget,eta);name=f'case-{len(cases):02d}.json'
        (args.output/name).write_text(json.dumps(case,indent=2)+'\n');cases.append(name)
    (args.output/'solver_snapshot.py').write_bytes(Path(__file__).read_bytes())
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.iterdir()}
    receipt={'status':'finite_oracle_completed_independent_audit_pending','cases':cases,'case_count':len(cases),
             'files':files,'utility':'linear toy quote units','tolerance':1e-8,
             'scope':'No dataset fitting, unseen-world guarantee, novelty certification or manuscript promotion.'}
    (args.output/'completion.json').write_text(json.dumps(receipt,indent=2)+'\n')
    primary=json.loads((args.output/'case-01.json').read_text())
    print(json.dumps({k:primary[k] for k in ['budget','eta','risk_bound','privileged_recoverability_bound']}|
                     {'oracle':primary['observable_oracle']['bound'],'fixed_library':primary['fixed_global_library']['bound'],'cases':len(cases)}))


if __name__=='__main__':main()
