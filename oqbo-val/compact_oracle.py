"""Exact finite marginal formulation for item-local, unit-cost query lotteries."""
import argparse,bisect,hashlib,itertools,json,math,time
from fractions import Fraction as F
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
from threadpoolctl import threadpool_limits

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,indent=2)+'\n')

def compact(base,coeff,eligible,budget):
    d,o,n,f=coeff.shape;v=o*n*f
    a=np.zeros((d+o*n+o,v+1));b=np.r_[-base,np.ones(o*n),np.full(o,budget)]
    a[:d,:v]=coeff.reshape(d,v);a[:d,-1]=-1
    for j in range(o):
        for i in range(n):a[d+j*n+i,(j*n+i)*f:(j*n+i+1)*f]=1
        a[d+o*n+j,j*n*f:(j+1)*n*f]=1
    c=np.r_[np.zeros(v),1.];upper=np.r_[eligible.reshape(-1).astype(float),np.inf]
    result=linprog(c,A_ub=a,b_ub=b,bounds=list(zip(np.zeros(v+1),upper)),method='highs')
    if not result.success:raise RuntimeError(result.message)
    return result,a,b,c,upper

def full(base,coeff,eligible,budget):
    d,o,n,f=coeff.shape;columns=[];blocks=[]
    for j in range(o):
        block=[]
        choices=[[-1]+np.flatnonzero(eligible[j,i]).tolist() for i in range(n)]
        for action in itertools.product(*choices):
            if sum(x>=0 for x in action)>budget:continue
            column=base/o
            for i,x in enumerate(action):
                if x>=0:column=column+coeff[:,j,i,x]
            block.append(len(columns));columns.append(column)
        blocks.append(block)
    matrix=np.asarray(columns).T;eq=np.zeros((o,len(columns)+1))
    for j,block in enumerate(blocks):eq[j,block]=1
    c=np.r_[np.zeros(len(columns)),1.]
    result=linprog(c,A_ub=np.c_[matrix,-np.ones(d)],b_ub=np.zeros(d),
        A_eq=eq,b_eq=np.ones(o),bounds=(0,None),method='highs')
    if not result.success:raise RuntimeError(result.message)
    return result,len(columns)

def original_fixture(path):
    x=json.loads(path.read_text());keys=[]
    for v in x['variables']:
        key=(v['mode'],tuple(v['report']))
        if key not in keys:keys.append(key)
    matrix=np.array(x['payoff_matrix']);coeff=np.zeros((len(matrix),len(keys),3,1));base=np.zeros(len(matrix));eligible=np.zeros((len(keys),3,1),bool)
    for j,key in enumerate(keys):
        block=[i for i,v in enumerate(x['variables']) if (v['mode'],tuple(v['report']))==key]
        empty=next(i for i in block if not x['variables'][i]['action'])
        q0=matrix[:,empty];base+=q0
        for i,reported in enumerate(key[1]):eligible[j,i,0]=not reported
        for col in block:
            action=x['variables'][col]['action']
            if len(action)==1:coeff[:,j,action[0],0]=matrix[:,col]-q0
        for col in block:
            predicted=q0.copy()
            for i in x['variables'][col]['action']:predicted+=coeff[:,j,i,0]
            assert np.allclose(predicted,matrix[:,col],atol=1e-10,rtol=0)
    return base,coeff,eligible,x['budget'],x['observable_oracle']['bound']

def rational_kernel(y,budget):
    result=[];repair=0.
    for block in y:
        rows=[[F(str(max(0.,float(v)))) for v in row] for row in block]
        for i,row in enumerate(rows):
            mass=sum(row,F(0))
            if mass>1:rows[i]=[v/mass for v in row]
        total=sum((sum(row,F(0)) for row in rows),F(0))
        if total>budget:rows=[[v*budget/total for v in row] for row in rows]
        repaired=np.array([[float(v) for v in row] for row in rows])
        repair+=float(np.abs(repaired-block).sum());result.append(rows)
    assert repair<1e-7
    return result,repair

def draws(kernel,budget,count):
    rng=np.random.default_rng(640107);result=[];den=2**53
    for rows in kernel:
        mass=[sum(row,F(0)) for row in rows];ends=list(itertools.accumulate(mass))
        assert ends[-1]<=budget and all(p<=1 for p in mass)
        fields=[list(itertools.accumulate(row)) for row in rows]
        block=np.full((count,len(rows)),-1,dtype=np.int16)
        for r in range(count):
            u=F(int(rng.integers(den)),den)
            for k in range(budget):
                point=u+k
                if point>=ends[-1]:break
                i=bisect.bisect_right(ends,point)
                assert block[r,i]==-1
                v=F(int(rng.integers(den)),den)*mass[i]
                field=bisect.bisect_right(fields[i],v)
                assert rows[i][field]>0
                block[r,i]=field
            assert (block[r]>=0).sum()<=budget
        result.append(block)
    return np.array(result)

def main(args):
    out=args.output.resolve()
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True);(out/'solver_snapshot.py').write_bytes(Path(__file__).read_bytes())
    contract=Path('plan/compact-oqbo-v1.md');(out/'contract.md').write_bytes(contract.read_bytes())
    inputs={str(contract.resolve()):sha(contract)};cases=[];rng=np.random.default_rng(71007)
    for p in sorted(Path('oqbo-val/outputs/finite-demo-01').glob('case-*.json')):
        base,coeff,elig,budget,expected=original_fixture(p)
        inputs[str(p.resolve())]=sha(p)
        cases.append((f'original-{p.stem}',base,coeff,elig,budget,expected,'original-market'))
    for k in range(24):
        n=2+k%5;f=1+k%3;o=1+(k//3)%3;d=8+k%11;budget=k%(min(n,3)+1)
        base=rng.integers(5,21,d).astype(float);coeff=rng.integers(-5,4,(d,o,n,f)).astype(float)
        elig=rng.random((o,n,f))>.2
        cases.append((f'algebraic-{k:02d}',base,coeff,elig,budget,None,'affine-algebraic'))
    base=rng.uniform(80,100,96);coeff=rng.normal(-.4,2,(96,8,100,4));elig=np.ones((8,100,4),bool)
    cases.append(('large-algebraic',base,coeff,elig,10,None,'large-affine-algebraic'))
    receipts=[];begun=time.time()
    with threadpool_limits(limits=1):
        for name,base,coeff,eligible,budget,expected,kind in cases:
            folder=out/name;folder.mkdir();tick=time.time()
            solution,a,b,c,upper=compact(base,coeff,eligible,budget)
            compact_seconds=time.time()-tick
            np.savez_compressed(folder/'problem.npz',base=base,coeff=coeff,eligible=eligible,budget=budget)
            np.savez_compressed(folder/'certificate.npz',x=solution.x,inequality_dual=solution.ineqlin.marginals,
                lower_dual=solution.lower.marginals,upper_dual=solution.upper.marginals)
            record={'kind':kind,'compact_variables':len(c),'bound':float(solution.fun),'compact_seconds':compact_seconds}
            if kind!='large-affine-algebraic':
                tick=time.time();reference,columns=full(base,coeff,eligible,budget)
                assert abs(reference.fun-solution.fun)<1e-8
                if expected is not None:assert abs(expected-solution.fun)<1e-8
                record.update(full_bound=float(reference.fun),full_allocation_variables=columns+1,full_seconds=time.time()-tick,original_bound=expected)
            else:
                kernel,repair=rational_kernel(solution.x[:-1].reshape(eligible.shape),budget)
                repaired=np.array([[[float(v) for v in row] for row in block] for block in kernel])
                repaired_bound=max(0.,float(np.max(base+coeff.reshape(len(base),-1)@repaired.reshape(-1))))
                assert repaired_bound<=solution.fun+1e-7
                write(folder/'kernel.json',[[[str(v) for v in row] for row in block] for block in kernel])
                np.savez_compressed(folder/'draws.npz',actions=draws(kernel,budget,2000))
                record.update(full_actions_per_public_class=sum(math.comb(100,k)*4**k for k in range(11)),
                    marginal_repair_l1=repair,repaired_bound=repaired_bound,draws_per_class=2000)
            write(folder/'completion.json',{**record,'status':'completed',
                  'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}})
            receipts.append({'case':name,'sha256':sha(folder/'completion.json'),**record})
    assert all(sha(Path(p))==d for p,d in inputs.items())
    write(out/'input_binding.json',inputs)
    write(out/'completion.json',{'status':'completed','cases':len(receipts),'small_full_comparisons':56,
        'seconds':time.time()-begun,'case_receipts':receipts,'independent_audit':'pending',
        'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()}})
    print(json.dumps({'cases':len(receipts),'small_full_comparisons':56,'large':receipts[-1]}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args())
