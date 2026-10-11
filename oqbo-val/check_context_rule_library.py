"""Exact stronger comparator; imports no preceding gap implementation."""
from fractions import Fraction as F
from pathlib import Path
import argparse, hashlib, json

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def evaluate(n,b,freeze=False,uniform=False):
    denom=b+1 if uniform else b+2
    weights=[1 if uniform else 2]+[1]*b
    worst=F(0); allocations=0; rows=0
    for j in range(b,n):
        active=b if freeze else j
        rules=[set(range(b))]+[(set(range(b))-{i})|{active} for i in range(b)]
        counts=[0]*n
        for weight,selected in zip(weights,rules):
            assert len(selected)==b and all(0<=i<n for i in selected)
            for i in selected: counts[i]+=weight
            allocations+=1
        assert sum(counts)==b*denom
        gaps=[F(2)]*b+[F(1,b+2)]*(n-b); gaps[j]=F(1)
        loss=max(g*(1-F(c,denom)) for g,c in zip(gaps,counts))
        if not freeze and not uniform:
            assert counts[:b]==[b+1]*b
            assert counts[j]==b
            assert all(counts[i]==0 for i in range(b,n) if i!=j)
        worst=max(worst,loss);rows+=n
    return worst,allocations,rows

def main(out):
    src=Path('oqbo-val/outputs/context-mixture-gap-v1')
    inputs=[src/'cases.json',src/'completion.json',Path('plan/context-rule-library-v1.md')]
    binding={str(p):sha(p) for p in inputs}
    assert not out.exists();out.mkdir(parents=True)
    old=json.loads((src/'cases.json').read_text());cases=[];allocations=rows=0
    for case in old:
        n,b=case['items'],case['budget']
        value,a,r=evaluate(n,b)
        # B core constraints: 2(1-p_i)<=t; active constraint: 1-p_j<=t.
        # Sum of required probabilities <=B implies t>=(B+1-B)/(B/2+1).
        lower=F(1)/(F(b,2)+1)
        assert value==lower==F(case['context_bound'])
        cases.append({'items':n,'budget':b,'contexts':n-b,'unique_rules':b+1,
                      'core_rule_weight':str(F(2,b+2)),'swap_rule_weight':str(F(1,b+2)),
                      'attained_bound':str(value),'budget_lower_bound':str(lower)})
        allocations+=a;rows+=r
    target=F(2,6)
    mutations={name:str(evaluate(9,4,**kw)[0]) for name,kw in
               [('fixed_active_item',{'freeze':True}),('uniform_weights',{'uniform':True})]}
    assert all(F(v)>target for v in mutations.values())
    assert all(sha(Path(p))==v for p,v in binding.items())
    (out/'checker_snapshot.py').write_bytes(Path(__file__).read_bytes())
    for name,data in [('cases.json',cases),('input_binding.json',binding)]:
        (out/name).write_text(json.dumps(data,indent=2)+'\n')
    result={'status':'completed','exact_cases':len(cases),'context_rule_allocations':allocations,
            'exact_context_item_rows':rows,'mutations_rejected':mutations,
            'scope':'same constructed family; fixed weights over B+1 context-aware rules attain context optimum; no real-data or novelty guarantee',
            'files':{p.name:sha(p) for p in out.iterdir()}}
    (out/'completion.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    main(p.parse_args().output)
