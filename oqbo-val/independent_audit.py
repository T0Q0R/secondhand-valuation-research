"""Independent reconstruction; never imports finite_oracle or its helpers."""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np

F=Fraction
G=((F(9),F(8),F(1)),(F(1),F(72,13),F(18)))
TOL=1e-8


def require(value,message):
    if not value:raise AssertionError(message)


def public_profiles():
    return [(0,0,0),(1,0,0),(0,1,0),(0,0,1)]


def legal_subsets(report,budget):
    possible=[]
    for bits in itertools.product((0,1),repeat=3):
        selected=tuple(i for i,b in enumerate(bits) if b)
        if len(selected)<=budget and all(report[i]==0 for i in selected):possible.append(selected)
    return set(possible)


def outcome(mode,report,available,selected,eta):
    final=list(report);fail=0
    for i in selected:
        if i==available:final[i]=1
        else:fail+=1
    prices=[]
    for i,g in enumerate(G[mode]):
        error=min(eta,g/2)
        prices.append(F(100)-g+error if final[i] else F(100)-error)
    return prices,fail


def validate_variables(case):
    budget=case['budget'];grouped={}
    expected={(m,r) for m in range(2) for r in public_profiles()}
    seen=set()
    for index,v in enumerate(case['variables']):
        require(set(v)=={'mode','report','action'},'Private information in public variable key')
        key=(v['mode'],tuple(v['report']));action=tuple(v['action'])
        require(key in expected,'Unsupported public report key')
        require(action in legal_subsets(key[1],budget),'Hard-budget/eligibility violation')
        require((key,action) not in seen,'Duplicated public action variable')
        seen.add((key,action));grouped.setdefault(key,[]).append(index)
    require(set(grouped)==expected,'Missing public equivalence class')
    for key,indices in grouped.items():
        require({tuple(case['variables'][i]['action']) for i in indices}==legal_subsets(key[1],budget),
                'Incomplete feasible action universe')
    return grouped


def reconstruct(case,grouped):
    eta=F(case['eta']);variables=case['variables'];rows=[];descriptions=[]
    # Independent enumeration uses the three singleton-recoverable worlds.
    for mode in range(2):
        for seller in range(3):
            observed=tuple(int(i==seller) for i in range(3));concealed=(0,0,0)
            row=[]
            for v in variables:
                coefficient=F(0)
                if v['mode']==mode and tuple(v['report'])==concealed:
                    coefficient+=outcome(mode,concealed,seller,tuple(v['action']),eta)[0][seller]
                if v['mode']==mode and tuple(v['report'])==observed:
                    coefficient-=outcome(mode,observed,seller,tuple(v['action']),eta)[0][seller]
                row.append(float(coefficient))
            rows.append(row);descriptions.append({'mode':mode,'source':seller,'seller':seller,
                             'truthful_report':list(observed),'hidden_report':list(concealed)})
    matrix=np.asarray(rows)
    require(np.array_equal(matrix,np.asarray(case['payoff_matrix'])),'Payoff reconstruction mismatch')
    require(descriptions==case['deviations'],'Counterfactual row mismatch')
    equality=np.zeros((len(grouped),len(variables)))
    for k,key in enumerate(grouped):equality[k,grouped[key]]=1
    require(np.array_equal(equality,np.asarray(case['equality_matrix'])),'Public quotient equality mismatch')
    library=[]
    for d in descriptions:
        values=[];mode=d['mode'];seller=d['seller']
        for name in case['rules']:
            gain=F(0)
            for report,sign in [(tuple(d['hidden_report']),1),(tuple(d['truthful_report']),-1)]:
                eligible=[i for i in range(3) if report[i]==0 and G[mode][i]-2*eta>0]
                if name=='none':chosen=()
                elif name=='risk':chosen=tuple(sorted(sorted(eligible,key=lambda i:(-(G[mode][i]-2*eta),i))[:case['budget']]))
                else:chosen=tuple(sorted([int(i) for i in name.split('-')[1] if int(i) in eligible][:case['budget']]))
                require(chosen in legal_subsets(report,case['budget']),'Library spends invalid capacity')
                gain+=sign*outcome(mode,report,seller,chosen,eta)[0][seller]
            values.append(float(gain))
        library.append(values)
    library=np.asarray(library)
    require(np.array_equal(library,np.asarray(case['library_payoff_matrix'])),'Library payoff mismatch')
    return matrix,equality,library


def dual_check(matrix,equality,certificate):
    x=np.r_[certificate['probabilities'],certificate['bound']]
    ub=np.column_stack((matrix,-np.ones(len(matrix))))
    eq=np.column_stack((equality,np.zeros(len(equality))))
    c=np.r_[np.zeros(len(x)-1),1.0]
    y=np.asarray(certificate['inequality_dual']);z=np.asarray(certificate['equality_dual'])
    require(x.min()>=-TOL and np.max(ub@x)<=TOL,'Primal deviation/nonnegative violation')
    require(np.max(np.abs(eq@x-1))<=TOL,'Probability normalization violation')
    require(y.max()<=TOL and (c-ub.T@y-eq.T@z).min()>=-TOL,'Invalid dual witness')
    require(abs(z.sum()-x[-1])<=TOL,'Primal-dual gap exceeds tolerance')
    return float(max(0,np.max(ub@x))),float(abs(z.sum()-x[-1]))


def audit_case(case):
    grouped=validate_variables(case);matrix,equality,library=reconstruct(case,grouped)
    primal,dualgap=dual_check(matrix,equality,case['observable_oracle'])
    dual_check(library,np.ones((1,len(case['rules']))),case['fixed_global_library'])
    eta=F(case['eta']);budget=case['budget'];exact_bounds=[];draws=0
    for item in case['analytic']:
        mode=item['mode'];a=tuple(max(F(0),g-2*eta) for g in G[mode])
        p=tuple(map(F,item['marginals']));t=F(item['bound'])
        require(tuple(map(F,item['leverages']))==a,'Incorrect quote leverage')
        require(all(0<=x<=1 for x in p) and sum(p,F(0))<=budget,'Exact marginal feasibility')
        require(max((g*(1-x) for g,x in zip(a,p)),default=F(0))==t,'Exact primal upper bound mismatch')
        if budget==0:require(t==max(a),'No-query lower bound mismatch')
        elif budget>=sum(g>0 for g in a):require(t==0,'Fully covered lower bound mismatch')
        else:
            active=[i for i,g in enumerate(a) if g>t]
            reciprocal=sum((1/a[i] for i in active),F(0))
            lam=[F(1)/(a[i]*reciprocal) if i in active else F(0) for i in range(3)]
            require(sum(lam,F(0))==1,'Exact adversarial witness normalization')
            require(F(len(active)-budget)/reciprocal==t,'Exact capacity lower bound mismatch')
        lottery=[(tuple(v['action']),F(v['mass'])) for v in item['hard_subset_lottery']]
        require(sum((w for _,w in lottery),F(0))==1,'Exact lottery normalization')
        for selected,mass in lottery:
            require(mass>0 and selected in legal_subsets((0,0,0),budget),'Exact hard draw violation')
            for source in [-1,0,1,2]:
                prices,failed=outcome(mode,(0,0,0),source,selected,eta)
                require(failed==len(selected)-int(source in selected),'Failed query accounting mismatch')
                require(failed<=len(selected)<=budget,'Failure incorrectly frees capacity')
                draws+=1
        require(all(sum((w for selected,w in lottery if i in selected),F(0))==p[i] for i in range(3)),
                'Exact lottery marginals mismatch')
        exact_bounds.append(t)
    require(abs(float(max(exact_bounds))-case['observable_oracle']['bound'])<=TOL,'Oracle fails rational lower bound')
    require(case['fixed_global_library']['bound']+TOL>=case['observable_oracle']['bound'],'Nested policy classes misordered')
    # Replay every compatible world/report. The lookup key excludes availability.
    probs=np.asarray(case['observable_oracle']['probabilities']);aliases=0;worlds=0;maximum_error=F(0)
    for mode in range(2):
        for source in [-1,0,1,2]:
            truthful=tuple(int(i==source) for i in range(3))
            reports=[truthful] if source<0 else [truthful,(0,0,0)]
            for report in reports:
                indices=grouped[(mode,report)]
                require(abs(probs[indices].sum()-1)<=TOL,'Execution lottery invalid')
                for index in indices:
                    selected=tuple(case['variables'][index]['action'])
                    after,failed=outcome(mode,report,source,selected,eta)
                    require(len(selected)<=budget and failed<=len(selected),'Actual draw capacity/failure violation')
                    if report==truthful:
                        targets=[F(100)-G[mode][i] if i==source else F(100) for i in range(3)]
                        maximum_error=max(maximum_error,*[abs(q-y) for q,y in zip(after,targets)])
                if report==(0,0,0):aliases+=1
                worlds+=1
    require(maximum_error<=eta,'Uniform honest absolute-error promise violated')
    privileged=[]
    for mode in range(2):
        for seller in range(3):
            report=(0,0,0);selected=(seller,) if budget else ()
            q=outcome(mode,report,seller,selected,eta)[0][seller]
            honest=outcome(mode,tuple(int(i==seller) for i in range(3)),seller,(),eta)[0][seller]
            privileged.append(max(F(0),q-honest))
    require(float(max(privileged))==case['privileged_recoverability_bound'],'Privileged diagnostic not actually attainable')
    return {'world_report_pairs':worlds,'aliased_world_lookups':aliases,'exact_draw_world_checks':draws,
            'max_honest_absolute_error':str(maximum_error),'primal_violation':primal,'duality_gap':dualgap}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise FileExistsError('Fresh independent audit required')
    receipt=json.loads((args.run/'completion.json').read_text())
    require(receipt['case_count']==32,'Contract case grid incomplete')
    for name,h in receipt['files'].items():require(hashlib.sha256((args.run/name).read_bytes()).hexdigest()==h,'Frozen file changed')
    results=[]
    for name in receipt['cases']:
        case=json.loads((args.run/name).read_text());results.append({'case':name,**audit_case(case)})
    fixture=json.loads((args.run/'case-01.json').read_text());rejected=[]
    for mutation in ['capacity','public_key','private_key','payoff']:
        changed=json.loads(json.dumps(fixture))
        if mutation=='capacity':changed['variables'][0]['action']=[0,1]
        if mutation=='public_key':changed['variables'][0]['report']=[1,1,0]
        if mutation=='private_key':changed['variables'][0]['source_id']=0
        if mutation=='payoff':changed['payoff_matrix'][0][0]+=1
        try:audit_case(changed)
        except AssertionError:rejected.append(mutation)
        else:raise AssertionError('Mutation accepted: '+mutation)
    require(abs(fixture['observable_oracle']['bound']-float(F(72,17)))<=TOL,'Primary rational value mismatch')
    require(abs(fixture['fixed_global_library']['bound']-float(F(72,13)))<=TOL,'Primary restricted value mismatch')
    args.output.mkdir(parents=True)
    (args.output/'auditor_snapshot.py').write_bytes(Path(__file__).read_bytes())
    result={'status':'independently_audited_finite_oracle','cases':results,'case_count':len(results),
            'mutations_rejected':rejected,'primary_values':{'observable':'72/17','fixed_global_library':'72/13','risk':'8','privileged':'0'},
            'run_completion_sha256':hashlib.sha256((args.run/'completion.json').read_bytes()).hexdigest(),
            'scope':'Exact rational analytic lower/upper construction plus numerical full-LP primal/dual checks at1e-8. No imported solver helpers, real-source result, first-ever novelty or unseen guarantee.'}
    (args.output/'completion.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'cases':len(results),'world_report_pairs':sum(x['world_report_pairs'] for x in results),
                      'exact_draw_world_checks':sum(x['exact_draw_world_checks'] for x in results),
                      'mutations_rejected':rejected,'primary_values':result['primary_values']}))


if __name__=='__main__':main()
