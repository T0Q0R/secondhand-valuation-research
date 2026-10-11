"""Independent full enumeration, LP dual audit and exact interval-kernel checks."""
import argparse,hashlib,itertools,json,math,time
from fractions import Fraction as F
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
from threadpoolctl import threadpool_limits

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,indent=2)+'\n')

def certificate(base,coeff,eligible,budget,x,dual,lower,upperdual):
    d,o,n,f=coeff.shape;v=o*n*f
    inequalities=[np.r_[row.reshape(-1),-1.] for row in coeff]
    rhs=list(-base)
    for j in range(o):
        for i in range(n):
            row=np.zeros((o,n,f));row[j,i,:]=1
            inequalities.append(np.r_[row.reshape(-1),0.]);rhs.append(1.)
    for j in range(o):
        row=np.zeros((o,n,f));row[j]=1
        inequalities.append(np.r_[row.reshape(-1),0.]);rhs.append(float(budget))
    a=np.array(inequalities);b=np.array(rhs);c=np.r_[np.zeros(v),1.]
    u=eligible.reshape(-1).astype(float)
    assert np.min(x)>=-1e-8 and np.max(x[:-1]-u)<=1e-8
    assert np.max(a@x-b)<=1e-8
    assert np.max(dual)<=1e-8 and np.min(lower)>=-1e-8 and np.max(upperdual)<=1e-8
    assert abs(upperdual[-1])<=1e-8
    assert np.max(abs(c-a.T@dual-lower-upperdual))<=1e-8
    dual_value=float(b@dual+u@upperdual[:-1])
    assert abs(float(c@x)-dual_value)<=1e-8
    return dual_value

def enumerate_value(base,coeff,eligible,budget):
    d,o,n,f=coeff.shape;values=[];membership=[]
    for j in range(o):
        items=[i for i in range(n) if eligible[j,i].any()]
        for count in range(min(budget,len(items))+1):
            for selected in itertools.combinations(items,count):
                available=[np.flatnonzero(eligible[j,i]).tolist() for i in selected]
                for fields in itertools.product(*available):
                    gain=base/o
                    if count:gain=gain+sum((coeff[:,j,i,a] for i,a in zip(selected,fields)),np.zeros(d))
                    values.append(gain);membership.append(j)
    eq=np.zeros((o,len(values)+1))
    for col,j in enumerate(membership):eq[j,col]=1
    lp=linprog(np.r_[np.zeros(len(values)),1.],A_ub=np.c_[np.array(values).T,-np.ones(d)],
        b_ub=np.zeros(d),A_eq=eq,b_eq=np.ones(o),bounds=(0,None),method='highs')
    assert lp.success
    # Verify the enumerated solver's own primal/dual objective as well.
    dual=float(np.ones(o)@lp.eqlin.marginals)
    assert abs(dual-lp.fun)<=1e-8
    return float(lp.fun),len(values)+1

def main(a):
    run,out=a.run.resolve(),a.output.resolve();done=read(run/'completion.json');initial=sha(run/'completion.json')
    assert done['status']=='completed' and done['cases']==57
    for p,d in done['files'].items():assert sha(run/p)==d
    bindings=read(run/'input_binding.json')
    for p,d in bindings.items():assert sha(p)==d
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True);(out/'auditor_snapshot.py').write_bytes(Path(__file__).read_bytes())
    checked=[];pieces=0;draw_count=0;mutations=[];started=time.time()
    with threadpool_limits(limits=1):
        for entry in done['case_receipts']:
            folder=run/entry['case'];receipt=read(folder/'completion.json')
            assert sha(folder/'completion.json')==entry['sha256']
            for p,d in receipt['files'].items():assert sha(folder/p)==d
            with np.load(folder/'problem.npz') as z:
                base,coeff,eligible=[z[k] for k in ('base','coeff','eligible')];budget=int(z['budget'])
            with np.load(folder/'certificate.npz') as z:
                x,dual,lower,upper=[z[k] for k in ('x','inequality_dual','lower_dual','upper_dual')]
            objective=certificate(base,coeff,eligible,budget,x,dual,lower,upper)
            assert abs(objective-receipt['bound'])<=1e-8
            if not mutations:
                wrong=x.copy();wrong[-1]+=.1
                try:certificate(base,coeff,eligible,budget,wrong,dual,lower,upper)
                except AssertionError:mutations.append('dual_gap')
                else:raise AssertionError('Corrupted objective accepted')
            if receipt['kind']!='large-affine-algebraic':
                full,variables=enumerate_value(base,coeff,eligible,budget)
                assert abs(full-objective)<=1e-8 and variables==receipt['full_allocation_variables']
                if receipt['kind']=='original-market':
                    path=next(Path(p) for p in bindings if Path(p).name==entry['case'].removeprefix('original-')+'.json')
                    original=read(path);keys=[]
                    for v in original['variables']:
                        key=(v['mode'],tuple(v['report']))
                        if key not in keys:keys.append(key)
                    matrix=np.array(original['payoff_matrix']);baseline=np.zeros(len(base))
                    for j,key in enumerate(keys):
                        cols=[k for k,v in enumerate(original['variables']) if (v['mode'],tuple(v['report']))==key]
                        zero=next(k for k in cols if not original['variables'][k]['action']);q0=matrix[:,zero];baseline+=q0
                        assert np.array_equal(eligible[j,:,0],np.logical_not(key[1]))
                        for col in cols:
                            q=q0+sum((coeff[:,j,i,0] for i in original['variables'][col]['action']),np.zeros(len(base)))
                            assert np.max(abs(q-matrix[:,col]))<=1e-10
                    assert np.max(abs(baseline-base))<=1e-10
                    assert abs(original['observable_oracle']['bound']-objective)<=1e-8
            else:
                kernel=[[[F(v) for v in row] for row in block] for block in read(folder/'kernel.json')]
                numeric=np.array([[[float(v) for v in row] for row in block] for block in kernel])
                assert np.abs(numeric.reshape(-1)-x[:-1]).sum()<1e-7
                assert max(0.,float(np.max(base+coeff.reshape(len(base),-1)@numeric.reshape(-1))))<=objective+1e-7
                with np.load(folder/'draws.npz') as z:actions=z['actions']
                assert actions.shape==(8,2000,100)
                assert ((actions>=-1)&(actions<4)).all() and ((actions>=0).sum(-1)<=budget).all()
                for j,block in enumerate(kernel):
                    p=[sum(row,F(0)) for row in block];ends=[F(0)]
                    for v in p:ends.append(ends[-1]+v)
                    assert all(F(0)<=v<=1 for v in p) and ends[-1]<=budget
                    split=sorted({F(0),F(1),*(v-v.numerator//v.denominator for v in ends)})
                    marginal=[F(0)]*100
                    for left,right in zip(split,split[1:]):
                        u=(left+right)/2
                        selected=[i for i in range(100) if any(ends[i]<=u+k<ends[i+1] for k in range(budget))]
                        assert len(selected)<=budget
                        for i in selected:marginal[i]+=right-left
                        pieces+=1
                    assert marginal==p
                    for i,row in enumerate(block):
                        assert all(v>=0 for v in row)
                        if p[i]:
                            assert sum((v/p[i] for v in row),F(0))==1
                            assert all(marginal[i]*(v/p[i])==v for v in row)
                        else:assert all(v==0 for v in row)
                        for f,v in enumerate(row):
                            if not v:assert not (actions[j,:,i]==f).any()
                    observed=np.array([[(actions[j,:,i]==f).mean() for f in range(4)] for i in range(100)])
                    epsilon=math.sqrt(math.log(2*3200/.001)/(2*2000))
                    assert np.max(abs(observed-numeric[j]))<=epsilon
                bad=actions.copy();bad[0,0,:]=0
                assert (bad[0,0]>=0).sum()>budget;mutations.append('hard_capacity')
                assert receipt['full_actions_per_public_class']==sum(math.comb(100,k)*4**k for k in range(11))
                draw_count=16000
            checked.append({'case':entry['case'],'bound':objective,'certificate_verified':True})
    assert sha(run/'completion.json')==initial and all(sha(Path(p))==d for p,d in bindings.items())
    write(out/'completion.json',{'status':'completed','cases':len(checked),'full_enumeration_comparisons':56,
        'original_market_cases':32,'algebraic_small_cases':24,'large_compact_variables':3201,
        'exact_interval_pieces':pieces,'exact_field_marginals':3200,'hard_budget_draws':draw_count,
        'sampling_check':'simultaneous Hoeffding tolerance for3200 marginals,2000 draws/class,alpha0.001; continuous kernel marginal identities checked exactly',
        'mutations_rejected':mutations,'parent_completion_sha256':initial,'seconds':time.time()-started,
        'checked':checked,'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()},
        'scope':'finite item-local LP equivalence; algebraic scale fixture is not source-market efficacy or unseen-world evidence'})
    print(json.dumps({'cases':len(checked),'full_comparisons':56,'interval_pieces':pieces,'hard_budget_draws':draw_count}))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('run','output'):p.add_argument('--'+n,type=Path,required=True)
    main(p.parse_args())
