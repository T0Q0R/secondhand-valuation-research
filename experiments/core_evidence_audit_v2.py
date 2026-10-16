"""Read-only fit/outcome re-derivation for the claim-bearing experiment blocks.

Shares data loading/model prediction, not allocation/state transitions/utility
oracles. Head targets and train/held-out ordering are reconstructed separately.
Never interprets a receipt alone as an independent empirical validation.
"""
from pathlib import Path
import argparse,copy,fcntl,gc,hashlib,itertools,json,math,sys,time,traceback
import joblib,numpy as np,pandas as pd,torch
from threadpoolctl import threadpool_limits
from sklearn.ensemble import ExtraTreesRegressor
from run_all import load_source
from savval import ACTIONS,FEATURES,price_features

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/core-evidence-audit-v2'
STAGES={'rpl':'recovery-path-learning-v1','mechanisms':'completion-mechanisms-v1',
        'sefa':'completion-sefa-v6-official','gdfs':'recent-gdfs-v1',
        'dime':'recent-dime-v1','efa':'recent-efa-v1','aco':'aco1-development-v2','rpl10':'rpl-ten-seed-v2'}
CODES=[sum(1<<f for f in combo) for k in range(3) for combo in itertools.combinations(range(4),k)]
BITS=np.array([[bool(v&(1<<f)) for f in range(4)] for v in CODES]);LOOKUP={v:i for i,v in enumerate(CODES)}
METRICS=['mean_positive_log_inflation','clean_mae','attack_mae','failed_query_fraction',
         'attack_signed_log_bias','mean_unilateral_inflation_envelope_log']
COLS=['positive_log_inflation','clean_absolute_error','attack_absolute_error',
      'failed_query_fraction','attack_signed_log_error','unilateral_inflation_envelope_log']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp')
    t.write_text(json.dumps(x,indent=2)+'\n');t.replace(p)
def content(f):return hashlib.sha256(f.to_csv(index=False).encode()).hexdigest()
def ids(f):return hashlib.sha256('\n'.join(f.listing_id).encode()).hexdigest()
def rank(f,salt):
    return f.iloc[sorted(range(len(f)),key=lambda i:hashlib.sha256(f'{salt}|{f.listing_id.iloc[i]}'.encode()).hexdigest())].reset_index(drop=True)
def split(f,fraction):
    f=rank(f,'sav-val-inner-guidance-v2');n=math.floor(len(f)*fraction)
    return f.iloc[n:].copy(),f.iloc[:n].copy()
class OneThreadBackbone:
    def __init__(self,model):self.model=getattr(model,'model',model)
    def predict(self,*a,**kw):return self.model.predict(*a,**dict(kw,thread_count=1))
def bounded(model):
    model.backbone=OneThreadBackbone(model.backbone)
    return model
def independent_scores(head,x,pred,evaluation,kind='suppression'):
    n,s,d=x.shape;i,j,a=np.indices((n,s,4))
    matrix=np.c_[x[i.ravel(),j.ravel()],pred[i.ravel(),j.ravel()],np.eye(4,dtype=np.float32)[a.ravel()]]
    head.model.n_jobs=1
    outputs=head.model.predict(matrix).reshape(n,s,4,3)
    score=outputs[...,0] if kind=='suppression' else np.where(np.arange(4)[None,None,:]==head.fixed_benefit_field,outputs[...,2],-np.inf)
    return np.where(evaluation[list(ACTIONS)].isna().to_numpy()[:,None,:]|BITS[None,:,:],score,-np.inf)
def parent(source,seed):
    n='nested-development-v2' if seed in [13,42,2026] else 'nested-seven-extra-seeds-v1'
    return ROOT/'outputs'/n/source/f'seed-{seed}'

def row_file(cp):
    r=read(cp)
    if 'outcomes_sha256' in r:
        p=cp.parent/'outcomes.csv.gz';assert sha(p)==r['outcomes_sha256'];return pd.read_csv(p),p
    if 'reused_original_outcomes' in r:u=r['reused_original_outcomes'];budget=u['budget'];p=ROOT/u['path'];h=u['sha256']
    else:
        u=r['reused'];budget=r['inputs']['budget']
        if u['type']=='ablation':
            return row_file(ROOT/u['root']/'evaluation'/u['method']/f'budget-{round(budget*10000):04d}'/'completion.json')
        assert u['type']=='original';p=ROOT/u['outcomes'];h=u['sha256']
    assert sha(p)==h;f=pd.read_csv(p)
    return f[(f.method==u['method'])&np.isclose(f.budget,budget)].copy(),p

def resolve_model(stage,source,seed,method):
    old=parent(source,seed)
    if stage in ['sefa','gdfs','dime','efa']:
        key=method.split('4bin_')[1];return dict(type='original',pair=old,key=key)
    if stage=='mechanisms' and method=='epoch-weak':return dict(type='original',pair=old,key='sav_val')
    if (stage=='mechanisms' and method=='feedback-off') or (stage=='rpl' or stage=='rpl10') and method.startswith('path-0-gap-') and seed in [13,42,2026]:
        key='off_zero' if method=='path-0-gap-0' else 'off_gap'
        return dict(type='ablation',pair=ROOT/'outputs/completion-ablation-v6'/source/f'seed-{seed}',key=key)
    return dict(type='direct',pair=ROOT/'outputs'/STAGES[stage]/source/f'seed-{seed}',key=method)

def paths(spec):
    p=spec['pair'];k=spec['key'];kind=spec['type']
    if kind=='original':return p/'deployment_models'/f'{k}.joblib',p/'outer_predictions.npz',k
    if kind=='ablation':return p/'deployment_models'/f'{k}.joblib',p/'outer_predictions.npz',k
    return p/k/'deployment_model.joblib',p/k/'outer_predictions.npz','prediction'

def independent_head(model,stored,train,columns,oof,seed,cfg):
    _,encoded,valid=model.predict(price_features(train,columns));natural=train[list(ACTIONS)].isna().to_numpy()
    np.testing.assert_array_equal(model.space.masks.astype(bool),BITS)
    eligible=valid[:,:,None]&(natural[:,None,:]|BITS[None,:,:]);i,s,a=np.nonzero(eligible)
    nxt=np.array([[LOOKUP[code&~(1<<f)] for f in range(4)] for code in CODES])
    before=oof[i,s];after=oof[i,nxt[s,a]];truth=oof[i,0];y=train.target_log.to_numpy()[i]
    targets=np.c_[np.maximum(before-truth,0)-np.maximum(after-truth,0),
                  (before-y)**2-(after-y)**2,(before-y)**2]
    matrix=np.c_[encoded[i,s],before,np.eye(4,dtype=np.float32)[a]]
    rebuilt=ExtraTreesRegressor(n_estimators=cfg['head_trees'],max_depth=12,min_samples_leaf=12,random_state=seed,n_jobs=1)
    rebuilt.fit(matrix,targets)
    for old,new in zip(stored.model.estimators_,rebuilt.estimators_):
        for key in ['children_left','children_right','feature','n_node_samples']:
            np.testing.assert_array_equal(getattr(old.tree_,key),getattr(new.tree_,key))
        for key in ['threshold','value','impurity','weighted_n_node_samples']:
            np.testing.assert_allclose(getattr(old.tree_,key),getattr(new.tree_,key),rtol=1e-8,atol=1e-10)
    assert len(stored.model.estimators_)==len(rebuilt.estimators_)==cfg['head_trees']
    fs=[targets[a==f,0].mean() if (a==f).any() else np.nan for f in range(4)]
    fb=[targets[a==f,1].mean() if (a==f).any() else np.nan for f in range(4)]
    assert stored.fixed_field==np.nanargmax(fs) and stored.fixed_benefit_field==np.nanargmax(fb)
    return len(i)

def fit_audit(spec,source,seed,cfg,train,evaluation):
    mp,op,key=paths(spec);p=spec['pair'];kind=spec['type'];k=spec['key'];bindings={}
    def bind(x):bindings[str(x.resolve())]=sha(x)
    cp=OUT/'fit-audit/models'/f'{sha(mp)}.json'
    if cp.exists():
        r=read(cp);assert r['checker_sha256']==sha(Path(__file__))
        assert all(sha(Path(f))==h for f,h in r['bindings'].items());return r
    assert not set(train.listing_id)&set(evaluation.listing_id)
    assignment=np.empty(len(train),int)
    order=rank(train,'sav-val-outer-v2').listing_id
    positions={str(v):i for i,v in enumerate(train.listing_id)}
    assignment[[positions[str(v)] for v in order]]=np.arange(len(train))%cfg['outer_folds']
    original=parent(source,seed);stored=pd.read_csv(original/'outer_assignments.csv')
    assert stored.listing_id.tolist()==train.listing_id.tolist()
    np.testing.assert_array_equal(assignment,stored.outer_fold);bind(original/'outer_assignments.csv')
    outer_receipt=read(original/'outer_audit.json');bind(original/'outer_audit.json')
    assert sha(original/'outer_predictions.npz')==outer_receipt['prediction_sha256']
    oof=np.load(op)[key];assert oof.shape==(len(train),11);bind(op);bind(mp)
    predicted=0
    for fold in [0,1,2,'deployment']:
        held=train.loc[assignment==fold] if isinstance(fold,int) else None
        estimator,guidance=split(train.loc[assignment!=fold] if isinstance(fold,int) else train,cfg['head_fitting_fraction'])
        if held is not None:
            assert not set(held.listing_id)&(set(estimator.listing_id)|set(guidance.listing_id))
            fr=outer_receipt['folds'][fold]
            assert fr['estimator_ids']==ids(estimator) and fr['guidance_ids']==ids(guidance) and fr['holdout_ids']==ids(held)
        assert not set(estimator.listing_id)&set(guidance.listing_id)
        origstage=original/(f'outer-{fold}' if isinstance(fold,int) else 'deployment_fit')
        base_receipt=read(origstage/'fit_completion.json');bind(origstage/'fit_completion.json')
        assert base_receipt['inputs']['seed']==seed
        assert base_receipt['inputs']['estimator_content']==content(estimator)
        assert base_receipt['inputs']['guidance_content']==content(guidance)
        if kind=='original':
            folder=p/(f'outer-{fold}' if isinstance(fold,int) else 'deployment_fit')
            modelpath=folder/'models'/f'{k}.joblib';r=read(folder/'fit_completion.json')
            assert sha(modelpath)==r['files'][f'models/{k}.joblib']
            trace=read(folder/'training_trace.json');bind(folder/'training_trace.json')
            assert sha(folder/'training_trace.json')==r['files']['training_trace.json']
            def finite_loss(x):
                if isinstance(x,dict):
                    for a,b in x.items():
                        if a=='loss':assert np.isfinite(b)
                        else:finite_loss(b)
                elif isinstance(x,list):
                    for b in x:finite_loss(b)
            finite_loss(trace)
        else:
            folder=(p/'fit'/(f'outer-{fold}' if isinstance(fold,int) else 'deployment')/k if kind=='ablation'
                    else p/k/(f'outer-{fold}' if isinstance(fold,int) else 'deployment'))
            r=read(folder/'completion.json');bind(folder/'completion.json');inp=r['inputs']
            assert inp['estimator']==content(estimator) and inp['guidance']==content(guidance) and inp['seed']==seed
            base=origstage/'models/masking_suppression.joblib';bind(base)
            assert sha(base)==base_receipt['files']['models/masking_suppression.joblib']
            assert inp.get('base',inp.get('base_model'))==sha(base)
            assert len(r['rounds'])==2
            for n,rr in enumerate(r['rounds'],1):
                assert rr['round']==n and rr['epochs']==cfg['residual_epochs']//2
                logs=rr.get('loss',rr.get('training'));assert len(logs)==rr['epochs']
                assert all(x['epoch']==i+1 and np.isfinite(x['loss']) for i,x in enumerate(logs))
                rc=read(folder/f'round-{n}.json');bind(folder/f'round-{n}.json');rp=folder/f'round-{n}.joblib';bind(rp)
                assert rc['inputs']==inp and rc.get('sha256',rc.get('model_sha256'))==sha(rp)
                round_model,_,round_logs=joblib.load(rp);assert round_logs==r['rounds'][:n]
                del round_model
            modelpath=folder/'model.joblib';assert sha(modelpath)==r['model_sha256']
        bind(modelpath);model,_,_=joblib.load(modelpath);bounded(model)
        if held is not None:
            actual=model.predict(price_features(held,FEATURES[source]))[0]
            np.testing.assert_allclose(actual,oof[assignment==fold],rtol=0,atol=2e-6);predicted+=len(held)
        else:
            deployed,head,_=joblib.load(mp);bounded(deployed)
            for f in [train,evaluation]:
                np.testing.assert_allclose(model.predict(price_features(f,FEATURES[source]))[0],
                                           deployed.predict(price_features(f,FEATURES[source]))[0],rtol=0,atol=2e-6)
            target_rows=independent_head(deployed,head,train,FEATURES[source],oof,seed,cfg)
        del model;gc.collect()
    result=dict(status='completed',checker_sha256=sha(Path(__file__)),source=source,seed=seed,
        model=str(mp.resolve()),heldout_prediction_rows=predicted,independently_refitted_heads=1,
        head_target_rows=target_rows,bindings=bindings,scope='reconstructed partitions/OOF; artifact/trace closure; independent deployment head target construction and refit; not fresh price-model retraining')
    write(cp,result);print('FIT_AUDITED',source,seed,kind,k,flush=True);return result

def recent_fit(stage,pair,source,seed,train,evaluation):
    """Bind every selection/refit input; replay public acquisition after loading."""
    import run_completion_sefa_v6 as sefa
    from recent_acquisition_training_v1 import acquisition as recent_acquisition
    ordered=rank(train,'sefa-internal-validation-v6');cut=int(.8*len(ordered))
    fit,val=ordered.iloc[:cut].copy(),ordered.iloc[cut:].copy();sel=read(pair/'selection.json')
    assert sel['held_out_evaluation_labels_used'] is False
    winner=min(sel['trials'],key=lambda r:(r['validation_nll'],r['index']))
    assert sel['selected']==winner
    bindings={str((pair/'selection.json').resolve()):sha(pair/'selection.json')}
    for trial in sel['trials']+[None]:
        folder=pair/('refit' if trial is None else f"trial-{trial['index']}")
        r=read(folder/'completion.json');inp=r['inputs'];full=ordered if trial is None else fit
        valid=ordered if trial is None else val
        assert inp.get('training',inp.get('train'))==content(full) and inp['validation']==content(valid)
        assert inp['seed']==seed and sha(folder/'model.joblib')==r['sha256']
        assert len(r['history'])==r.get('epochs_run',r.get('epochs'))
        assert all(np.isfinite(h['train_loss']) and np.isfinite(h['validation_nll']) for h in r['history'])
        if trial is not None:
            loss=r.get('best_validation_nll',r.get('validation_nll'))
            assert abs(loss-trial['validation_nll'])<1e-10
        else:
            assert inp.get('official',inp.get('config',{})) is not None
            assert inp['config']==winner['settings']
        model,enc,cuts=joblib.load(folder/'model.joblib')
        np.testing.assert_allclose(cuts,np.quantile(full.target_log,[.25,.5,.75]),rtol=0,atol=1e-12)
        expected=sefa.PublicEncoding().fit(price_features(full,FEATURES[source]))
        assert enc.__dict__==expected.__dict__
        for f in [folder/'completion.json',folder/'model.joblib']:
            bindings[str(f.resolve())]=sha(f)
    if stage=='sefa':scores=sefa.acquisition(model,enc,evaluation,NoneSpace(),seed)
    else:scores=recent_acquisition(model,enc,evaluation,NoneSpace(),seed,stage)
    saved=np.load(pair/'scores.npz')['scores'];assert scores.shape==saved.shape
    finite=np.isfinite(scores);np.testing.assert_array_equal(finite,np.isfinite(saved))
    np.testing.assert_allclose(scores[finite],saved[finite],rtol=1e-7,atol=1e-8)
    report=read(pair/'scores.json');assert report['model_sha256']==sha(pair/'refit/model.joblib')
    assert report['score_sha256']==sha(pair/'scores.npz')
    # Labels never enter inference: arbitrary label changes must leave scores equal.
    tiny=evaluation.iloc[:4].copy();changed=tiny.copy();changed['target_log']=999.;changed['mileage_km']=123456789.
    acquire=lambda f:sefa.acquisition(model,enc,f,NoneSpace(),seed) if stage=='sefa' else recent_acquisition(model,enc,f,NoneSpace(),seed,stage)
    a,b=acquire(tiny),acquire(changed)
    np.testing.assert_allclose(a[:,LOOKUP[1]],b[:,LOOKUP[1]],rtol=0,atol=1e-8)
    for f in [pair/'scores.npz',pair/'scores.json']:bindings[str(f.resolve())]=sha(f)
    return saved,dict(status='completed',bindings=bindings,selection_training_only=True,
           public_hidden_value_and_label_perturbation=True,score_replay=True,scope='selection/encoder/quantile/training trace audit and score replay; no classifier retraining')

class NoneSpace:
    def reported_missing(self,f):return f[list(ACTIONS)].isna().to_numpy()[:,None,:]|BITS[None,:,:]

def independent_outcomes(pred,scores,valid,evaluation,rows,budget):
    """Own-report counterfactuals ranked against frozen peer priorities."""
    expected_valid=~(BITS[None,:,:]&~evaluation[list(ACTIONS)].notna().to_numpy()[:,None,:]).any(2)
    np.testing.assert_array_equal(valid,expected_valid)
    assert rows.listing_id.tolist()==evaluation.listing_id.tolist()
    assert len(rows)==len(evaluation) and rows.listing_id.is_unique
    deviations=0;batch_records=[]
    for batch,start in enumerate(range(0,len(rows),100)):
        rr=rows.iloc[start:start+100];pp=pred[start:start+len(rr)];ss=scores[start:start+len(rr)]
        vv=valid[start:start+len(rr)];nn=len(rr);state=rr.state.to_numpy(int);ix=np.arange(nn)
        assert vv[ix,state].all();cap=math.floor(nn*budget)
        action=ss.argmax(2);priority=np.take_along_axis(ss,action[:,:,None],2)[:,:,0]
        peer_priorities=priority[ix,state];options=np.full((nn,11),-np.inf)
        actual_action=np.full(nn,-1);actual_final=state.copy()
        for i in range(nn):
            for s in np.flatnonzero(vv[i]):
                weight=priority[i,s];f=int(action[i,s]);others=[j for j in range(nn) if j!=i]
                ahead=sum(peer_priorities[j]>weight or (peer_priorities[j]==weight and j<i) for j in others)
                selected=np.isfinite(weight) and weight>0 and ahead<cap
                final=LOOKUP[CODES[s]&~(1<<f)] if selected else s
                options[i,s]=pp[i,final];deviations+=1
                if s==state[i]:actual_action[i]=f if selected else -1;actual_final[i]=final
        quoted=options[ix,state];truth=pp[:,0];target=evaluation.target_log.iloc[start:start+nn].to_numpy()
        succeeded=np.array([a>=0 and bool(CODES[s]&(1<<a)) for s,a in zip(state,actual_action)])
        regret=np.maximum(options.max(1)-quoted,0);assert (actual_action>=0).sum()<=cap
        for key,value in [('action',actual_action),('final_state',actual_final),('query_succeeded',succeeded),('hidden_count',BITS[state].sum(1)),('batch',np.full(nn,batch))]:
            np.testing.assert_array_equal(rr[key],value)
        yp=np.expm1(target);hp=np.expm1(truth);ap=np.expm1(quoted)
        metrics=dict(clean_prediction_log=truth,attacked_prediction_log=quoted,target_log=target,
             clean_sq_log_loss=(truth-target)**2,attack_sq_log_loss=(quoted-target)**2,
             clean_absolute_error=abs(hp-yp),attack_absolute_error=abs(ap-yp),positive_log_inflation=np.maximum(quoted-truth,0),
             positive_price_inflation=np.maximum(ap-hp,0),attack_signed_log_error=quoted-target,
             clean_signed_log_error=truth-target,clean_underprediction_log=np.maximum(target-truth,0),
             best_response_regret_log=regret,unilateral_inflation_envelope_log=np.maximum(options.max(1)-truth,0))
        for key,v in metrics.items():np.testing.assert_allclose(rr[key],v,atol=1e-7,rtol=1e-10,err_msg=key)
        assert rr.batch_converged.nunique()==1
        assert bool(rr.batch_converged.iloc[0])==bool((regret<1e-7).all())
        rr=rr.copy();rr['failed_query_fraction']=((rr.action>=0)&~rr.query_succeeded).astype(float)
        batch_records.append(dict(batch=batch,n=nn,**{m:float(rr[c].mean()) for m,c in zip(METRICS,COLS)},
            max_regret=float(regret.max()),nonconverged=not bool(rr.batch_converged.iloc[0])))
    f=rows;summary=dict(n=len(f),clean_rmsle=float(np.sqrt(f.clean_sq_log_loss.mean())),attack_rmsle=float(np.sqrt(f.attack_sq_log_loss.mean())),
        clean_mae=float(f.clean_absolute_error.mean()),attack_mae=float(f.attack_absolute_error.mean()),
        mean_positive_log_inflation=float(f.positive_log_inflation.mean()),mean_positive_price_inflation=float(f.positive_price_inflation.mean()),
        clean_signed_log_bias=float(f.clean_signed_log_error.mean()),attack_signed_log_bias=float(f.attack_signed_log_error.mean()),
        clean_underprediction_log=float(f.clean_underprediction_log.mean()),actual_audit_fraction=float((f.action>=0).mean()),
        hiding_fraction=float((f.hidden_count>0).mean()),max_remaining_response_regret=float(f.best_response_regret_log.max()),
        mean_remaining_response_regret=float(f.best_response_regret_log.mean()),mean_unilateral_inflation_envelope_log=float(f.unilateral_inflation_envelope_log.mean()),
        failed_query_fraction=float(((f.action>=0)&~f.query_succeeded).mean()),nonconverged_batch_fraction=float(np.mean([b['nonconverged'] for b in batch_records])))
    return summary,batch_records,deviations

def audit_pair(stage,source,seed,limit=None):
    if stage=='aco':
        from audit_core_aco_v2 import audit_pair as audit_aco
        return audit_aco(source,seed,limit)
    root=ROOT/'outputs'/STAGES[stage];cfg=read(root/'manifest.json')['config']
    e,g,evaluation,_=load_source(source,cfg);train=rank(pd.concat([e,g],ignore_index=True),'sav-val-cf-training-order-v2')
    p=root/source/f'seed-{seed}';allcp=[]
    for cp in p.glob('**/completion.json'):
        r=read(cp)
        if 'summary' in r:allcp.append((cp,r))
    expected=(18 if stage in ['rpl','rpl10'] else 10 if stage=='mechanisms' else 12)
    assert len(allcp)==expected,(stage,source,seed,len(allcp),expected)
    if limit:allcp=allcp[:limit]
    fit_reports={};outcome_reports=[];last_model=None;cache=None;recent_scores=None
    if stage in ['sefa','gdfs','dime','efa']:
        recent_scores,recent_report=recent_fit(stage,p,source,seed,train,evaluation)
        write(OUT/'fit-audit'/stage/source/f'seed-{seed}'/'acquisition.json',recent_report)
    for cp,r in sorted(allcp):
        s=r['summary'];method=s['method'];budget=float(s['budget'])
        spec=resolve_model(stage,source,seed,method);mp,_,_=paths(spec)
        freport=fit_audit(spec,source,seed,cfg,train,evaluation);fit_reports[str(mp.resolve())]=freport
        op=OUT/'outcome-audit'/stage/source/f'seed-{seed}'/method/f'budget-{round(budget*10000):04d}.json'
        binding=dict(cell_receipt=sha(cp),model=sha(mp),checker=sha(Path(__file__)))
        if op.exists():
            prior=read(op);assert prior['binding']==binding
            assert all(sha(Path(f))==h for f,h in prior['bindings'].items());outcome_reports.append(prior);continue
        if last_model!=str(mp):
            model,head,_=joblib.load(mp);bounded(model);head.model.n_jobs=1
            pred,x,valid=model.predict(price_features(evaluation,FEATURES[source]))
            np.testing.assert_array_equal(model.space.masks.astype(bool),BITS)
            scores=(recent_scores if recent_scores is not None else independent_scores(head,x,pred,evaluation))
            cache=pred,scores,valid;last_model=str(mp)
        rows,rowpath=row_file(cp)
        assert np.isclose(rows.budget,budget).all() and (rows.seed==seed).all()
        summary,batches,deviations=independent_outcomes(*cache,evaluation,rows,budget)
        for key,val in summary.items():np.testing.assert_allclose(s[key],val,atol=1e-7,rtol=1e-10,err_msg=key)
        # Cell input hashes must bind the same model and evaluation, not just rows.
        inp=r['inputs'];assert inp.get('model',inp.get('price_model'))==sha(mp)
        assert inp['evaluation']==content(evaluation)
        if recent_scores is not None:assert inp['score_table']==sha(p/'scores.npz')
        result=dict(status='completed',binding=binding,bindings={str(cp.resolve()):sha(cp),str(rowpath.resolve()):sha(rowpath),str(mp.resolve()):sha(mp)},
            stage=stage,dataset=source,seed=seed,method=method,budget=budget,summary=summary,batches=batches,
            outcome_rows=len(rows),legal_unilateral_deviations=deviations)
        write(op,result);outcome_reports.append(result);print('OUTCOME_AUDITED',stage,source,seed,method,budget,flush=True)
    result=dict(status='completed' if not limit else 'smoke_only',stage=stage,dataset=source,seed=seed,
        cells=len(outcome_reports),checker_sha256=sha(Path(__file__)),fit_model_count=len(fit_reports),
        outcome_rows=sum(r['outcome_rows'] for r in outcome_reports),legal_unilateral_deviations=sum(r['legal_unilateral_deviations'] for r in outcome_reports))
    write(OUT/'pair-checks'/stage/source/f'seed-{seed}.json',result);return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=STAGES,required=True)
    p.add_argument('--source');p.add_argument('--seed',type=int);p.add_argument('--smoke',action='store_true');a=p.parse_args()
    OUT.mkdir(exist_ok=True);torch.set_num_threads(1)
    lock=(OUT/'execution.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    manifest=read(ROOT/'outputs'/STAGES[a.stage]/'manifest.json')
    cfg=manifest['parent_config'] if a.stage=='aco' else manifest['config'];results=[]
    with threadpool_limits(limits=1):
        for source in ([a.source] if a.source else cfg['datasets']):
            for seed in ([a.seed] if a.seed is not None else cfg['seeds']):
                results.append(audit_pair(a.stage,source,seed,1 if a.smoke else None))
    if not a.smoke and a.source is None:
        for name in ['fit-audit','outcome-audit']:
            write(OUT/name/a.stage/'completion.json',dict(status='completed',stage=a.stage,
                checker_sha256=sha(Path(__file__)),cells=sum(x['cells'] for x in results),pairs=results,
                scope='shared loader/model primitives; independently reconstructed partitions/head targets or integer allocation and all legal unilateral utilities'))
if __name__=='__main__':main()
