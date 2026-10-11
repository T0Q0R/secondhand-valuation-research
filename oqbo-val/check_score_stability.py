"""Exact finite checks of conditional score stability; no empirical performance."""
import argparse,csv,hashlib,itertools,json,sys
from fractions import Fraction as F
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from public_minimax_allocation import marginals

def exact(scores,budget):
    n=len(scores)
    if budget==0:return max(scores),[F(0)]*n
    if budget>=n:return F(0),[F(1)]*n
    ordered=sorted(scores,reverse=True)
    for k in range(budget+1,n+1):
        threshold=F(k-budget)/sum((1/x for x in ordered[:k]),F(0))
        if (ordered[k] if k<n else 0)<=threshold<=ordered[k-1]:
            p=[max(F(0),1-threshold/x) for x in scores]
            assert sum(p)==budget and max(x*(1-y) for x,y in zip(scores,p))==threshold
            return threshold,p
    raise AssertionError('No exact threshold')

def main(out):
    assert not out.exists();out.mkdir(parents=True)
    grid=list(itertools.product([F(1,2),F(1),F(2)],repeat=3))
    cache={};float_error=0.;lp_error=0.
    for scores,budget in itertools.product(grid,range(4)):
        t,p=exact(scores,budget);cache[(scores,budget)]=(t,p)
        g=np.array([float(v) for v in scores]);n=len(g)
        objective=np.r_[np.zeros(n),1.]
        inequalities=np.column_stack([-np.diag(g),-np.ones(n)])
        inequalities=np.vstack([inequalities,np.r_[np.ones(n),0.]])
        solved=linprog(objective,A_ub=inequalities,b_ub=np.r_[-g,budget],bounds=[(0,1)]*n+[(0,None)],method='highs')
        assert solved.success
        lp_error=max(lp_error,abs(solved.fun-float(t)))
        production=marginals(g[:,None],np.ones((n,1),bool),budget)
        error=max(abs(float(a)-b) for a,b in zip(p,production['probabilities']))
        float_error=max(float_error,error)
        assert error<1e-12 and abs(solved.fun-float(t))<1e-10
    records=[];active_changes=0;epsilon=F(1,8)
    for g,gp,budget in itertools.product(grid,grid,range(4)):
        t,p=cache[(g,budget)];tp,pp=cache[(gp,budget)]
        delta=max(abs(x-y) for x,y in zip(g,gp));m=min(*g,*gp)
        bound=min(F(1),2*delta/m)
        td=abs(t-tp);pd=max(abs(x-y) for x,y in zip(p,pp))
        assert td<=delta and pd<=bound
        active_changes+=int([x>0 for x in p]!=[x>0 for x in pp])
        q0=[F(i+1) for i in range(3)];q1=[F(-i,3) for i in range(3)]
        q0p=[v+epsilon for v in q0];q1p=[v-epsilon for v in q1]
        R=max(abs(x-y) for x,y in zip(q1p,q0p))
        q=[(1-a)*b+a*c for a,b,c in zip(p,q0,q1)]
        qp=[(1-a)*b+a*c for a,b,c in zip(pp,q0p,q1p)]
        quote_change=max(abs(x-y) for x,y in zip(q,qp))
        assert quote_change<=epsilon+R*bound
        # The final max/positive-part step uses an anchor perturbed by -epsilon.
        envelope=max(F(0),*q);envelope_p=max(F(0),*(v+epsilon for v in qp))
        assert abs(envelope-envelope_p)<=2*epsilon+R*bound
        records.append({'g':str(g),'g_prime':str(gp),'budget':budget,'delta':str(delta),'m':str(m),
                        'threshold_change':str(td),'probability_change':str(pd),'probability_bound':str(bound),
                        'quote_change':str(quote_change),'quote_bound':str(epsilon+R*bound),
                        'envelope_change':str(abs(envelope-envelope_p)),'envelope_bound':str(2*epsilon+R*bound)})
    boundaries=[]
    for k in range(1,13):
        d=F(1,10**k)
        _,p=exact((1+d,F(1)),1);_,pp=exact((F(1),1+d),1)
        smooth=abs(p[0]-pp[0]);assert smooth==d/(2+d)
        # Exact top-B ranking selects different items despite a score perturbation d.
        top_change=F(1)
        _,low=exact((2*d,d),1);_,lowp=exact((d,2*d),1)
        assert abs(low[0]-lowp[0])==F(1,3)
        # One item, two fields: allocation probability is unchanged, field identity flips.
        before=marginals(np.array([[float(1+d),1.]]),np.ones((1,2),bool),1)
        after=marginals(np.array([[1.,float(1+d)]]),np.ones((1,2),bool),1)
        assert before['fields'][0]==0 and after['fields'][0]==1
        assert before['probabilities'][0]==after['probabilities'][0]==1
        boundaries.append({'delta':str(d),'top_b_quote_jump':str(top_change),'minimax_fixed_field_quote_change':str(smooth),
                           'vanishing_score_floor_probability_jump':'1/3','field_switch_quote_jump':'1'})
    assert active_changes>0
    with (out/'exact_pairs.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    (out/'boundary_cases.json').write_text(json.dumps(boundaries,indent=2)+'\n')
    (out/'checker_snapshot.py').write_bytes(Path(__file__).read_bytes())
    result={'status':'completed_exact_finite_checks','score_vectors':len(grid),'exact_pair_budget_cases':len(records),
            'active_set_change_cases':active_changes,'lp_and_production_comparisons':len(cache),
            'maximum_production_probability_error':float_error,'maximum_lp_objective_error':lp_error,
            'boundary_scales':len(boundaries),'scope':'constructed exact arithmetic and numerical implementation checks; analytic proof separate; no empirical attribution or first-result claim',
            'allocator_sha256':hashlib.sha256((ROOT/'experiments/public_minimax_allocation.py').read_bytes()).hexdigest(),
            'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}}
    (out/'completion.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    main(p.parse_args().output)
