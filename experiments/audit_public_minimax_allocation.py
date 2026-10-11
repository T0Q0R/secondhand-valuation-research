"""Independent LP and exhaustive draw-interval integration of score baseline."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
from public_minimax_allocation import marginals,draw

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(out):
    assert not out.exists();out.mkdir(parents=True)
    rng=np.random.default_rng(20261008);cases=[];intervals=0
    fixtures=[(np.zeros((4,2)),np.ones((4,2),bool),2),
              (np.array([[2.],[1.]]),np.ones((2,1),bool),1),
              (np.ones((5,2)),np.zeros((5,2),bool),3)]
    for _ in range(80):
        n=int(rng.integers(1,40));f=int(rng.integers(1,6));b=int(rng.integers(0,n+1))
        scores=rng.lognormal(0,2,(n,f));eligible=rng.random((n,f))>.3
        fixtures.append((scores,eligible,b))
    for scores,eligible,b in fixtures:
        result=marginals(scores,eligible,b);n=len(scores)
        g=np.array([max([0.]+[float(scores[i,f]) for f in range(scores.shape[1]) if eligible[i,f]]) for i in range(n)])
        # Independent LP variables are item query probabilities plus epigraph.
        a=np.zeros((n+1,n+1));a[:n,:n]=-np.diag(g);a[:n,-1]=-1;a[n,:n]=1
        lp=linprog(np.r_[np.zeros(n),1],A_ub=a,b_ub=np.r_[-g,b],bounds=[(0,1)]*n+[(0,None)],method='highs')
        assert lp.success and abs(lp.fun-result['surrogate_bound'])<=1e-8*max(1,float(g.max()))
        p=result['probabilities'];ends=np.cumsum(p)
        cuts=sorted(set([0.,1.]+[float(v%1) for v in ends]))
        realized=np.zeros(n)
        for left,right in zip(cuts,cuts[1:]):
            if right-left<1e-14:continue
            actions=draw(result,(left+right)/2);selected=actions>=0
            assert selected.sum()<=b
            for i in np.flatnonzero(selected):assert eligible[i,actions[i]] and scores[i,actions[i]]==g[i]
            realized+=selected*(right-left);intervals+=1
        assert np.max(abs(realized-p),initial=0)<=1e-10
        for u in [0.,np.nextafter(1.,0.)]:draw(result,u)
        cases.append({'items':n,'fields':scores.shape[1],'capacity':b,'lp':float(lp.fun),'surrogate':result['surrogate_bound']})
    # Top-B is a useful control but cannot substitute for the minimax optimizer.
    assert abs(cases[1]['surrogate']-2/3)<1e-10
    greedy_bound=1.;assert greedy_bound>cases[1]['surrogate']
    invalid=[(np.array([[-1.]]),np.ones((1,1),bool),1),(np.ones((1,1)),np.ones((1,1),bool),.5),
             (np.array([[np.nan]]),np.ones((1,1),bool),1)]
    for args in invalid:
        try:marginals(*args)
        except ValueError:pass
        else:raise AssertionError('Invalid input accepted')
    paths=[Path(__file__),Path('experiments/public_minimax_allocation.py'),Path('plan/public-minimax-baseline-v1.md')]
    (out/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    result={'status':'completed','cases':len(cases),'integrated_draw_intervals':intervals,'invalid_inputs_rejected':len(invalid),
            'top_b_counterexample':{'top_b':greedy_bound,'minimax':cases[1]['surrogate']},
            'input_hashes':{str(p):sha(p) for p in paths},'scope':'public-score surrogate and draw implementability only; no trained-model or incentive-performance claim'}
    (out/'completion.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
