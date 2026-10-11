"""Exact rational witnesses plus independent complete-subset LP comparisons."""
import argparse,hashlib,itertools,json,math,time
from fractions import Fraction as F
from pathlib import Path
import numpy as np
from scipy import sparse
from scipy.optimize import linprog
from threadpoolctl import threadpool_limits

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,indent=2)+'\n')

def lp_compare(n,B):
    subsets=list(itertools.combinations(range(n),B));k=len(subsets);m=n-B
    not_queried=np.ones((n,k))
    for col,s in enumerate(subsets):not_queried[list(s),col]=0
    blocks=[]
    for j in range(B,n):
        g=np.full(n,1/(B+2));g[:B]=2;g[j]=1
        blocks.append(g[:,None]*not_queried)
    outputs={}
    for name,matrix,eq in [
        ('global',sparse.csr_matrix(np.vstack(blocks)),sparse.csr_matrix(np.ones((1,k)))),
        ('context',sparse.block_diag(blocks,format='csr'),sparse.kron(sparse.eye(m),np.ones((1,k)),format='csr'))]:
        d,v=matrix.shape;c=np.r_[np.zeros(v),1.]
        a=sparse.hstack([matrix,-np.ones((d,1))],format='csr')
        e=sparse.hstack([eq,np.zeros((eq.shape[0],1))],format='csr')
        r=linprog(c,A_ub=a,b_ub=np.zeros(d),A_eq=e,b_eq=np.ones(eq.shape[0]),bounds=(0,None),method='highs')
        assert r.success
        assert abs(r.fun-r.eqlin.marginals.sum())<=1e-8
        assert np.max(a@r.x)<=1e-8 and np.max(abs(e@r.x-1))<=1e-8
        outputs[name]={'bound':float(r.fun),'variables':v+1,'dual_bound':float(r.eqlin.marginals.sum())}
    return outputs

def main(a):
    out=a.output.resolve()
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True);(out/'checker_snapshot.py').write_bytes(Path(__file__).read_bytes())
    contract=Path('plan/context-mixture-gap-v1.md');design=Path('notes/design/紧凑OQBO与固定混合差距.md')
    inputs={str(p.resolve()):sha(p) for p in [contract,design]};cases=[];full=0;rows=0;started=time.time()
    with threadpool_limits(limits=1):
        for B in [1,2,3,4,6,8,10,16,20]:
            for n in sorted({B+1,2*B+1,B*B+B}):
                tg=F(2*(n-B),2*n-B);tc=F(2,B+2);epsilon=F(1,B+2)
                pg=[1-tg/2]*B+[1-tg]*(n-B)
                assert sum(pg)==B and all(0<=p<=1 for p in pg)
                sg=F(B,2)+(n-B);sc=F(B,2)+1
                global_lambda=[F(1,2)/sg]*B+[1/sg]*(n-B)
                assert sum(global_lambda)==1 and F(n-B)/sg==tg
                local_lambda=[F(1,2)/sc]*B+[1/sc]
                assert sum(local_lambda)==1 and 1/sc==tc
                assert all(w*g==1/sg for w,g in zip(global_lambda,[2]*B+[1]*(n-B)))
                for j in range(B,n):
                    g=[F(2)]*B+[epsilon]*(n-B);g[j]=F(1)
                    pc=[F(B+1,B+2)]*B+[F(0)]*(n-B);pc[j]=F(B,B+2)
                    assert sum(pc)==B and all(0<=p<=1 for p in pc)
                    assert max(v*(1-p) for v,p in zip(g,pg))<=tg
                    assert max(v*(1-p) for v,p in zip(g,pc))==tc
                    assert g[:B]==[F(2)]*B and all(g[i]<2 for i in range(B,n))
                    rows+=n
                case={'budget':B,'items':n,'contexts':n-B,'global_bound':str(tg),'context_bound':str(tc),
                    'ratio':str(tg/tc),'global_core_marginal':str(pg[0]),'global_other_marginal':str(pg[-1]),
                    'context_core_marginal':str(F(B+1,B+2)),'context_active_marginal':str(F(B,B+2)),
                    'global_dual_core_weight':str(global_lambda[0]),'global_dual_other_weight':str(global_lambda[-1]),
                    'context_dual_core_weight':str(local_lambda[0]),'context_dual_active_weight':str(local_lambda[-1]),
                    'risk_bound':'1','fixed_subset_count':math.comb(n,B)}
                if (n-B)*math.comb(n,B)<=20000:
                    comparison=lp_compare(n,B)
                    assert abs(comparison['global']['bound']-float(tg))<=1e-8
                    assert abs(comparison['context']['bound']-float(tc))<=1e-8
                    case['full_enumeration']=comparison;full+=1
                cases.append(case)
    assert len(cases)==26 and all(sha(Path(p))==v for p,v in inputs.items())
    write(out/'cases.json',cases);write(out/'input_binding.json',inputs)
    write(out/'completion.json',{'status':'completed','exact_cases':len(cases),'full_subset_lp_pairs':full,
        'exact_context_item_rows':rows,'seconds':time.time()-started,'largest_ratio':cases[-1]['ratio'],
        'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()},
        'scope':'constructed publicly observable context family; exact rational lower/primal witnesses and small complete-subset LPs; no real-source or first-in-literature guarantee'})
    print(json.dumps({'cases':len(cases),'full_lp_pairs':full,'exact_rows':rows,'largest_ratio':cases[-1]['ratio']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args())
