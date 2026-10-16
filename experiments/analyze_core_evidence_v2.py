"""Analysis phase: reconstruct paired batch tensors from audited outcomes.
Bootstrap draws are saved so the separate statistics checker can re-evaluate
every replicate with different arithmetic. All intervals are exploratory.
"""
from pathlib import Path
import argparse,functools,json
import numpy as np,pandas as pd,torch,joblib
from threadpoolctl import threadpool_limits
import core_evidence_audit_v2 as a

@functools.lru_cache(maxsize=2)
def original_rows(pair):
    pair=Path(pair);r=a.read(pair/'evaluation_completion.json');p=pair/'per_listing_outcomes.csv.gz'
    assert a.sha(p)==r['outcomes_sha256'];return pd.read_csv(p),p

def control(source,seed,backend,budget,cfg):
    cp=a.OUT/'outcome-audit/auxiliary-controls'/source/f'seed-{seed}'/backend/f'budget-{round(budget*10000):04d}.json'
    if cp.exists():
        r=a.read(cp);assert r['checker_sha256']==a.sha(Path(a.__file__))
        assert all(a.sha(Path(f))==h for f,h in r['bindings'].items());return r['batches']
    e,g,ev,_=a.load_source(source,cfg);train=a.rank(pd.concat([e,g],ignore_index=True),'sav-val-cf-training-order-v2')
    spec=dict(type='original',pair=a.parent(source,seed),key='masking_suppression' if backend=='masking_risk' else backend)
    a.fit_audit(spec,source,seed,cfg,train,ev);mp,_,_=a.paths(spec)
    model,head,_=joblib.load(mp);a.bounded(model);pred,x,valid=model.predict(a.price_features(ev,a.FEATURES[source]))
    score=a.independent_scores(head,x,pred,ev,'risk' if backend=='masking_risk' else 'suppression');full,p=original_rows(str(spec['pair']))
    rr=full[(full.method==backend)&np.isclose(full.budget,budget)].copy()
    summary,batches,dev=a.independent_outcomes(pred,score,valid,ev,rr,budget)
    saved=pd.read_csv(spec['pair']/'summary.csv');s=saved[(saved.method==backend)&np.isclose(saved.budget,budget)].iloc[0]
    for k,v in summary.items():np.testing.assert_allclose(s[k],v,rtol=1e-10,atol=1e-7)
    a.write(cp,dict(status='completed',checker_sha256=a.sha(Path(a.__file__)),bindings={str(mp):a.sha(mp),str(p):a.sha(p)},summary=summary,batches=batches,legal_unilateral_deviations=dev))
    return batches

def make_contrasts(stage,group):
    methods=sorted(group.method.unique())
    if stage in ['rpl','rpl10']:
        return [(('path-0-gap-0' if m.endswith('gap-0') else 'path-0-gap-0.5'),m)
                for m in methods if not m.startswith('path-0-gap-')]
    if stage=='mechanisms':return [('feedback-off',m) for m in methods if m!='feedback-off']
    if stage=='aco':return [('masking_risk' if m.startswith('masking_') else 'robust_no_feedback',m) for m in methods]
    return [('masking_risk' if m.endswith('masking_suppression') else 'robust_no_feedback',m) for m in methods]

def bootstrap(values,seed_draws,batch_draws):
    # Multinomial-weight formulation, deliberately different from checker indexing.
    ns,nb=values.shape[1:3]
    sw=np.stack([(seed_draws==k).mean(1) for k in range(ns)],axis=1)
    bw=np.stack([(batch_draws==k).mean(1) for k in range(nb)],axis=1)
    return np.einsum('csbm,rs,rb->crm',values,sw,bw,optimize=True)

def intervals(x,replicates):
    point=x.mean((1,2));sd=replicates.std(1,ddof=1)
    active=sd>1e-12*np.maximum(1,abs(point))
    z=np.divide(abs(replicates-point[:,None,:]),sd[:,None,:],out=np.zeros_like(replicates),where=active[:,None,:])
    q=float(np.quantile(z.max((0,2)),.95))
    return point,np.quantile(replicates,.025,axis=1),np.quantile(replicates,.975,axis=1),sd,q

def main(stage,reps=4000):
    root=a.ROOT/'outputs'/a.STAGES[stage];manifest=a.read(root/'manifest.json')
    cfg=manifest['parent_config'] if stage=='aco' else manifest['config']
    out=a.OUT/'analysis'/stage;out.mkdir(parents=True,exist_ok=True)
    for name in ['fit-audit','outcome-audit']:
        r=a.read(a.OUT/name/stage/'completion.json');assert r['status']=='completed' and r['checker_sha256']==a.sha(Path(a.__file__))
    records=[];bindings={};batches=[]
    for cp in sorted((a.OUT/'outcome-audit'/stage).glob('*/seed-*/*/budget-*.json')):
        r=a.read(cp);assert r['status']=='completed' and r['binding']['checker']==a.sha(Path(a.__file__))
        assert all(a.sha(Path(f))==h for f,h in r['bindings'].items());bindings[str(cp)]=a.sha(cp)
        key={k:r[k] for k in ['dataset','seed','method','budget']}
        records.append(dict(**key,**r['summary']))
        batches.extend(dict(**key,**b) for b in r['batches'])
    df=pd.DataFrame(records);assert len(df)==a.read(a.OUT/'outcome-audit'/stage/'completion.json')['cells']
    produced=pd.read_csv(root/'summary.csv')
    assert len(produced)==len(df)
    merged=df.merge(produced,on=['dataset','seed','method','budget'],suffixes=('_audited','_producer'),validate='one_to_one')
    for k in a.METRICS:np.testing.assert_allclose(merged[k+'_audited'],merged[k+'_producer'],atol=1e-7,rtol=1e-10)
    batch=pd.DataFrame(batches);values=[];metadata=[];all_batches=[]
    for (source,budget),group in df.groupby(['dataset','budget'],sort=True):
        for ref,method in make_contrasts(stage,group):
            delta=[]
            for seed in cfg['seeds']:
                candidate=batch[(batch.dataset==source)&(batch.budget==budget)&(batch.seed==seed)&(batch.method==method)].sort_values('batch')
                reference=batch[(batch.dataset==source)&(batch.budget==budget)&(batch.seed==seed)&(batch.method==ref)].sort_values('batch')
                if reference.empty:
                    reference=pd.DataFrame(control(source,seed,ref,float(budget),cfg)).sort_values('batch')
                assert len(candidate)==len(reference)==10
                assert (candidate.n==100).all() and (reference.n==100).all()
                np.testing.assert_array_equal(candidate.batch,reference.batch)
                delta.append(reference[a.METRICS].to_numpy()-candidate[a.METRICS].to_numpy())
            values.append(np.stack(delta));metadata.append(dict(dataset=source,budget=float(budget),reference=ref,candidate=method))
    x=np.stack(values);rng=np.random.default_rng(20261016)
    si=rng.integers(x.shape[1],size=(reps,x.shape[1]));bi=rng.integers(x.shape[2],size=(reps,x.shape[2]))
    rep=bootstrap(x,si,bi);point,lo,hi,sd,q=intervals(x,rep);contrast=[]
    for c,m in enumerate(metadata):
        for j,metric in enumerate(a.METRICS):
            contrast.append(dict(**m,metric=metric,reference_minus_candidate=point[c,j],
                lower=lo[c,j],upper=hi[c,j],bootstrap_sd=sd[c,j],
                simultaneous_lower=point[c,j]-q*sd[c,j],simultaneous_upper=point[c,j]+q*sd[c,j],
                fitting_seeds=x.shape[1],batches=x.shape[2],resamples=reps))
    df.to_csv(out/'audited_cell_summaries.csv',index=False);batch.to_csv(out/'audited_batch_means.csv',index=False)
    pd.DataFrame(contrast).to_csv(out/'paired_contrasts.csv',index=False)
    np.savez_compressed(out/'paired_tensors_and_draws.npz',differences=x,seed_draws=si,batch_draws=bi,bootstrap_replicates=rep)
    a.write(out/'contrast_keys.json',dict(keys=metadata,metrics=a.METRICS,seed_ids=cfg['seeds']))
    # Descriptive Pareto membership, no selection or acceptance gate.
    means=df.groupby(['dataset','budget','method'])[a.METRICS[:4]].mean().reset_index();parts=[]
    for _,g in means.groupby(['dataset','budget']):
        v=g[a.METRICS[:4]].to_numpy();g=g.copy()
        g['descriptive_nondominated']=~((v[:,None,:]<=v[None,:,:]).all(2)&(v[:,None,:]<v[None,:,:]).any(2)).any(0);parts.append(g)
    pd.concat(parts).to_csv(out/'multiobjective_means.csv',index=False)
    a.write(out/'completion.json',dict(status='completed',stage=stage,cells=len(df),contrasts=len(metadata),metrics=a.METRICS,
        fitting_seeds=x.shape[1],batches=10,resamples=reps,simultaneous_family_size=len(metadata)*len(a.METRICS),
        studentized_max_deviation_quantile=q,source_bindings=bindings,analysis_script_sha256=a.sha(Path(__file__)),
        artifacts={p.name:a.sha(p) for p in out.iterdir() if p.is_file() and p.name!='completion.json'},
        scope='exploratory crossed fitting-seed and batch bootstrap; fixed training population and evaluation cohort; not a confirmatory or finite-sample FWER certificate'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=a.STAGES,required=True);args=p.parse_args()
    torch.set_num_threads(1)
    with threadpool_limits(limits=1):main(args.stage)
