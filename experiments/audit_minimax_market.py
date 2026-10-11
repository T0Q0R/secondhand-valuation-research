"""Independent rational allocation and replay audit of unilateral response."""
import argparse,json,hashlib
from fractions import Fraction as F
from pathlib import Path
import numpy as np
from savval import StateSpace
from minimax_market import MinimaxMarket

def oracle(pred,scores,space,states,b):
    n=len(states);fields=[];g=[]
    for i,s in enumerate(states):
        options=[(F(float(v)),a) for a,v in enumerate(scores[i,s]) if np.isfinite(v) and v>0]
        if options:
            value=max(v for v,a in options);field=min(a for v,a in options if v==value)
        else:value=F(0);field=-1
        fields.append(field);g.append(value)
    positive=sorted((v for v in g if v>0),reverse=True)
    if b==0:p=[F(0)]*n
    elif b>=len(positive):p=[F(int(v>0)) for v in g]
    else:
        for k in range(b+1,len(positive)+1):
            threshold=F(k-b)/sum((1/v for v in positive[:k]),F(0))
            next_value=positive[k] if k<len(positive) else F(0)
            if next_value<=threshold<=positive[k-1]:break
        else:raise AssertionError('No threshold')
        p=[max(F(0),1-threshold/v) if v else F(0) for v in g]
    assert sum(p)<=b
    quotes=[]
    for i,s in enumerate(states):
        f=fields[i];after=s if f<0 else int(space.query_next[s,f])
        q=F(float(pred[i,s]));q1=F(float(pred[i,after]))
        quotes.append(float(q+p[i]*(q1-q)))
    return np.array(quotes)

def main(out):
    assert not out.exists();out.mkdir(parents=True)
    rng=np.random.default_rng(51008);space=StateSpace.build(2);count=0;response_count=0;max_regret=0
    for fixture in range(6):
        n=4;s=len(space.masks);natural=rng.random((n,4))<.2
        valid=~(space.masks[None,:,:]&natural[:,None,:]).any(axis=2)
        pred=rng.integers(1,40,(n,s)).astype(float)
        scores=rng.integers(0,20,(n,s,4)).astype(float)
        scores=np.where(natural[:,None,:]|space.masks[None,:,:],scores,-np.inf)
        for b in (0,1,n):
            market=MinimaxMarket(pred,scores,valid,space,b,cost=.125)
            states=np.array([rng.choice(np.flatnonzero(v)) for v in valid])
            for i in range(n):
                candidate=market.candidate_quotes(i,states)
                for h in np.flatnonzero(valid[i]):
                    changed=states.copy();changed[i]=h
                    exact=oracle(pred,scores,space,changed,b)
                    assert abs(candidate[h]-exact[i])<1e-9;count+=1
            result=market.response(sweeps=3,restarts=2);profile=result['states']
            exact=oracle(pred,scores,space,profile,b)
            assert np.max(abs(exact-result['expected_quotes']))<1e-9
            costs=.125*space.masks.sum(axis=1)
            for i in range(n):
                values=[]
                for h in np.flatnonzero(valid[i]):
                    changed=profile.copy();changed[i]=h
                    values.append(oracle(pred,scores,space,changed,b)[i]-costs[h])
                regret=max(0,max(values)-(exact[i]-costs[profile[i]]))
                assert abs(regret-result['regret'][i])<1e-9
                response_count+=1;max_regret=max(max_regret,regret)
    paths=[Path(__file__),Path('experiments/minimax_market.py'),Path('experiments/public_minimax_allocation.py')]
    for p in paths:(out/p.name).write_bytes(p.read_bytes())
    receipt={'status':'completed','fixtures':6,'budgets_per_fixture':3,'unilateral_quotes_checked':count,
             'final_item_regrets_checked':response_count,'max_final_regret':max_regret,
             'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
             'scope':'artificial finite worlds; independent rational threshold/replay oracle; finite-sweep responses are not equilibrium guarantees'}
    (out/'completion.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
