"""Post-hoc frozen-outcome diagnostics. No training or response reoptimization.
Exact conditional crossed-bootstrap variance includes weighted partial batches.
Positive-cost concealment is bounded, not reconstructed from absent states.
"""
from pathlib import Path
import itertools, json, math, hashlib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).resolve().parent
bindings={}
def bind(p):
    p=ROOT/p; bindings[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest(); return p
def moments(n):
    b=len(n); n=np.asarray(n,float)
    if np.all(n==n[0]):
        m=np.ones(b)/b; return m,(np.diag(m)-np.outer(m,m))/b
    assert np.all(n[:-1]==n[0]) and n[-1]<n[0]
    a,t=n[0],n[-1]; m=np.zeros(b); second=np.zeros((b,b)); p=1/(b-1)
    for k in range(b+1):
        prob=math.comb(b,k)*(1/b)**k*(1-1/b)**(b-k); l=b-k; d=a*l+t*k
        v=a*l*p/d; vt=t*k/d
        m[:-1]+=prob*v; m[-1]+=prob*vt
        second[:-1,:-1]+=prob*a*a*l*(l-1)*p*p/d**2
        second[np.arange(b-1),np.arange(b-1)]+=prob*a*a*l*p/d**2
        second[:-1,-1]+=prob*a*t*k*l*p/d**2; second[-1,:-1]+=prob*a*t*k*l*p/d**2
        second[-1,-1]+=prob*vt*vt
    c=second-np.outer(m,m)
    assert abs(m.sum()-1)<1e-12 and np.max(abs(c.sum(0)))<1e-12
    assert np.linalg.eigvalsh(c).min()>-1e-12
    return m,c

def decompose(y,n):
    s,b=y.shape; m,c=moments(n); row=y@m-(y@m).mean(); col=y.mean(0)
    residual=y-col[None,:]-row[:,None]
    vs=float(row@row/s**2); vb=float(col@c@col); vi=float(np.einsum('sb,bc,sc->',residual,c,residual)/s**2)
    assert min(vs,vb,vi)>-1e-13
    vs,vb,vi=map(lambda x:max(x,0),[vs,vb,vi]); total=vs+vb+vi
    wf=np.asarray(n)/sum(n); rf=y@wf-(y@wf).mean(); floor=float(rf@rf/s**2)
    return dict(seed_variance=vs,batch_variance=vb,interaction_variance=vi,total_variance=total,
        seed_share=vs/total,batch_share=vb/total,interaction_share=vi/total,
        conditional_sd=math.sqrt(total),thirty_seed_sd_ratio=math.sqrt((vs/3+vb+vi/3)/total),
        evaluation_noise_free_sd_ratio=math.sqrt(floor/total))
# Independent exact enumeration, including unequal ratio weights.
for n in [[1,1],[3,1]]:
    toy=np.array([[1.,5.],[3.,2.]])
    values=[]
    for si in itertools.product(range(2),repeat=2):
        for bi in itertools.product(range(2),repeat=2):
            weights=np.array(n)[list(bi)]; values.append((toy[list(si)][:,list(bi)]*weights).sum()/2/weights.sum())
    assert np.isclose(decompose(toy,n)['total_variance'],np.var(values),atol=1e-12)
meta=json.loads(bind(Path('outputs/matched-factorial-ten-seeds-v1-pipeline/analysis/contrast_specifications.json')).read_text())
z=np.load(bind(Path('outputs/matched-factorial-ten-seeds-v1-pipeline/analysis/paired_tensors_and_draws.npz')))
full=pd.read_csv(bind(Path('outputs/review-expanded-primary-v2-analysis/corroborated_batch_means.csv')))
rows=[]; matrices={}
for source in ['jucars','mucars']:
    t=z[source+'__tensor'][meta['budgets'].index(.1)]; seeds=z[source+'__seeds'].astype(int)
    for objective,score,allocation in itertools.product(['masking','robust'],['suppression','benefit','risk'],['top_b','minimax']):
        indices=[meta['cells'].index([objective,score,fb,allocation]) for fb in ['none','policy']]
        capped=t[:,:,indices[0],0]-t[:,:,indices[1],0]
        f=full[(full.dataset==source)&(full.initial_objective==objective)&(full.score==score)&(full.allocation==allocation)]
        a=f[f.feedback=='none'].pivot(index='seed',columns='batch',values=meta['metrics'][0]).reindex(seeds)
        b=f[f.feedback=='policy'].pivot(index='seed',columns='batch',values=meta['metrics'][0]).reindex(seeds)
        uncapped=(a-b).to_numpy(); n=f.groupby('batch').n.first().to_numpy()
        assert np.allclose(capped,uncapped[:,:10],atol=2e-15,rtol=0)
        for regime,y,nn in [('capped',capped,[100]*10),('uncapped',uncapped,n)]:
            key='__'.join([source,objective,score,allocation,regime]); matrices[key]=y; matrices[key+'__n']=np.asarray(nn)
            rows.append(dict(dataset=source,initial_objective=objective,score=score,allocation=allocation,coverage=regime,
                fitting_seeds=len(seeds),batches=y.shape[1],listings=int(sum(nn)),difference=float(np.average(y.mean(0),weights=nn)),**decompose(y,nn)))
variance=pd.DataFrame(rows); variance.to_csv(OUT/'variance_components.csv',index=False)
np.savez_compressed(OUT/'paired_differences.npz',**matrices)
# Bounds verified against exhaustive single-seller synthetic utility tables,
# including returned states with negative net utility and nonzero regret.
checks=0
for c in [0,.005,.02]:
    for gains in itertools.product([-.02,0,.01,.08],repeat=3):
        utility=np.array([0,*gains])-c*np.array([0,1,1,2]); best=max(utility)
        for j,(gain,k) in enumerate(zip([0,*gains],[0,1,1,2])):
            inflation=max(gain,0); deviation=max(best,0); regret=best-utility[j]; d=inflation-deviation
            assert c*k-regret-1e-12<=d<=c*k+1e-12; checks+=1
cost=pd.read_csv(bind(Path('outputs/review-cost-sensitivity-v2/batch_summary.csv')))
cost['cost_lower']=(cost.inflation-cost.net_deviation).clip(lower=0)
cost['cost_upper']=np.minimum((cost.inflation-cost.net_deviation+cost.max_regret).clip(lower=0),2*cost.mean_cost_per_field)
cost['hidden_lower']=cost.cost_lower/np.where(cost.scenario=='heterogeneous020',.03,cost.mean_cost_per_field)
cost['hidden_upper']=np.minimum(2,cost.cost_upper/np.where(cost.scenario=='heterogeneous020',.01,cost.mean_cost_per_field))
assert (cost.cost_lower<=cost.cost_upper+1e-12).all()
assert (cost.loc[cost.max_regret==0,'cost_upper']-cost.loc[cost.max_regret==0,'cost_lower']).abs().max()<1e-12
cost['failed_share_lower']=cost.failed_query/.1
# Read zero-cost states and listing means directly; order by cardinality then
# field index, implemented from integer bit masks without StateSpace imports.
codes=sorted([i for i in range(16) if i.bit_count()<=2],key=lambda i:(i.bit_count(),tuple(f for f in range(4) if i&(1<<f))))
zero=[]
for source,seed,feedback,allocation,batch in itertools.product(['synthetic','jucars','mucars'],[13,42,2026],['none','policy'],['top_b','minimax'],range(10)):
    folder=Path(f'outputs/matched-factorial-ten-seeds-v1/{source}/seed-{seed}/evaluation/budget-1000/robust/suppression/{feedback}/{allocation}/batch-{batch}')
    zz=np.load(bind(folder/'arrays.npz')); ff=pd.read_csv(bind(folder/'outcomes.csv.gz')); k=np.array([codes[int(s)].bit_count() for s in zz['states']])
    assert np.array_equal(zz['states'],ff.state.to_numpy())
    assert np.max(abs(ff.regret))<1e-7
    zero.append(dict(dataset=source,seed=seed,feedback=feedback,allocation=allocation,scenario='zero',batch=batch,n=len(ff),
        inflation=ff.positive_expected_log_inflation.mean(),net_deviation=ff.deviation_envelope.mean(),
        honest_mae=ff.honest_absolute_error.mean(),attacked_mae=ff.expected_attacked_absolute_error.mean(),failed_query=ff.failed_query_probability.mean(),
        max_regret=ff.regret.max(),converged=True,cost_lower=0,cost_upper=0,hidden_lower=k.mean(),hidden_upper=k.mean(),failed_share_lower=ff.failed_query_probability.mean()/.1))
allb=pd.concat([pd.DataFrame(zero),cost],ignore_index=True);allb.to_csv(OUT/'cost_mechanism_batches.csv',index=False)
metrics=['inflation','net_deviation','honest_mae','attacked_mae','failed_query','cost_lower','cost_upper','hidden_lower','hidden_upper','failed_share_lower']
means=[]
for keys,g in allb.groupby(['dataset','feedback','allocation','scenario']):
    means.append(dict(zip(['dataset','feedback','allocation','scenario'],keys),**{x:np.average(g[x],weights=g.n) for x in metrics},
        batches=len(g),nonconverged_batches=int((~g.converged).sum()),max_regret=g.max_regret.max()))
pd.DataFrame(means).to_csv(OUT/'cost_mechanism_means.csv',index=False)
summary={'status':'completed','training_runs':0,'response_reoptimizations':0,'variance_rows':len(rows),
 'cost_batch_rows':len(allb),'positive_cost_nonconverged_batches':int((~cost.converged).sum()),
 'exact_variance_oracle':'all 16 seed/batch resamples for balanced and unequal-weight 2x2 arrays',
 'cost_bound_oracle_cases':checks,'bounds_scope':'All retained batches; heterogeneous costs imply ranges, not exact mean concealed fields.',
 'variance_scope':'Conditional bootstrap variance given fitted models and fixed training/validation records; not training-population uncertainty or equivalence.',
 'input_sha256':bindings}
summary['output_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('*.csv')}
summary['output_sha256']['paired_differences.npz']=hashlib.sha256((OUT/'paired_differences.npz').read_bytes()).hexdigest()
summary['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
(OUT/'completion.json').write_text(json.dumps(summary,indent=2)+'\n')
print(variance[(variance.dataset=='mucars')&(variance.initial_objective=='masking')&(variance.score=='suppression')].to_string(index=False))
print(pd.DataFrame(means).query("dataset=='synthetic' and allocation=='top_b'").to_string(index=False))
