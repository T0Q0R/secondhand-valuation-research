"""Reconstruct nested splits, OOF predictions and deployment heads of completed fits."""
import argparse, copy, fcntl, hashlib, itertools, json, math
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import ExtraTreesRegressor
from run_all import load_source
from savval import ACTIONS, FEATURES, price_features

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(p)
def content(frame): return hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()
def ids(frame): return frame.listing_id.astype(str).tolist()
def rank(frame, salt):
    return sorted(range(len(frame)), key=lambda i:hashlib.sha256(f'{salt}|{frame.listing_id.iloc[i]}'.encode()).hexdigest())
def split(frame, fraction):
    ordered=frame.iloc[rank(frame,'sav-val-inner-guidance-v2')].reset_index(drop=True)
    cut=math.floor(fraction*len(frame))
    return ordered.iloc[cut:].copy(), ordered.iloc[:cut].copy()
def partition(receipt, estimator, guidance, heldout):
    assert receipt['estimator_ids']==ids(estimator) and receipt['guidance_ids']==ids(guidance)
    assert receipt['heldout_ids']==ids(heldout)
    assert not set(ids(estimator)) & set(ids(guidance))
    assert not set(ids(heldout)) & (set(ids(estimator))|set(ids(guidance)))
def prediction_equal(a,b): np.testing.assert_allclose(a,b,atol=2e-6,rtol=0)

def epoch_trace(logs, n, seed, epochs, objective, feedback, cfg):
    assert len(logs)==epochs
    rng=np.random.default_rng(seed)
    cap=sum(math.floor(cfg.get('training_budget',.1)*min(cfg['batch_size'],n-start))
            for start in range(0,n,cfg['batch_size']))
    for epoch, record in enumerate(logs):
        permutation=rng.permutation(n)
        assert record['permutation_sha256']==hashlib.sha256(permutation.tobytes()).hexdigest()
        assert record['epoch']==epoch and record['updates']==math.ceil(n/cfg['batch_size'])
        assert record['examples']==n and record['objective']==objective
        assert record['policy_feedback']==feedback and np.isfinite(record['loss'])
        assert -1e-8<=record['query_mass']<=cap+1e-8
        if not feedback: assert record['query_mass']==0

def verify_stage(stage, estimator, guidance, cfg, seed, columns, fit_ids, bind):
    done=read(stage/'completion.json');assert done['status']=='completed'
    assert done['config']==cfg and done['seed']==seed
    assert done['estimator_content_sha256']==content(estimator)
    assert done['guidance_content_sha256']==content(guidance)
    expected={'estimator':content(estimator),'guidance':content(guidance),'config':cfg,'seed':seed,'columns':columns}
    assert read(stage/'inputs.json')==expected
    receipts=read(stage/'receipts.json')
    assert sha(stage/'receipts.json')==done['receipts_sha256']
    assert set(receipts)==set(done['model_hashes'])==fit_ids
    for path in [stage/'completion.json',stage/'inputs.json',stage/'receipts.json']:bind[str(path)]=sha(path)
    for key, r in receipts.items():
        initial, feedback, _, _=key.split('__')
        assert r['estimator_ids']==ids(estimator) and r['guidance_ids']==ids(guidance)
        assert r['head_fits']==1+cfg['feedback_rounds']
        epoch_trace(r['initial_training'],len(estimator),seed,cfg['initial_epochs'],initial,False,cfg)
        assert len(r['feedback_training'])==cfg['feedback_rounds']
        for round_id, trace in enumerate(r['feedback_training']):
            assert trace['round']==round_id
            count=cfg['feedback_epochs']//cfg['feedback_rounds']+int(round_id<cfg['feedback_epochs']%cfg['feedback_rounds'])
            epoch_trace(trace['training'],len(estimator),seed+100+round_id,count,'robust',feedback=='policy',cfg)
        path=stage/(key+'.joblib');assert sha(path)==done['model_hashes'][key];bind[str(path)]=sha(path)
        cp=stage/'checkpoints'/(key+'.json');saved=read(cp)
        assert saved['training']==r
        model_path=cp.with_suffix('.joblib');assert sha(model_path)==saved['sha256']
        bind[str(cp)]=sha(cp);bind[str(model_path)]=sha(model_path)
    for initial in ['masking','robust']:
        cp=stage/'checkpoints'/('initial__'+initial+'.json');r=read(cp)
        assert r['training']['initial_training']==receipts[initial+'__none__shared__shared']['initial_training']
        path=cp.with_suffix('.joblib');assert sha(path)==r['sha256']
        bind[str(cp)]=sha(cp);bind[str(path)]=sha(path)
    return receipts

def rebuild_head(model, head, train, columns, oof, cfg, seed):
    _, encoded, valid=model.predict(price_features(train,columns))
    masks=model.space.masks
    natural=train[list(ACTIONS)].isna().to_numpy()
    missing=natural[:,None,:]|masks[None,:,:]
    eligible=valid[:,:,None]&missing
    i,s,a=np.nonzero(eligible)
    lookup={tuple(x):k for k,x in enumerate(masks)}
    next_state=np.empty((len(masks),4),dtype=int)
    for state, mask in enumerate(masks):
        for action in range(4):
            recovered=mask.copy();recovered[action]=False
            next_state[state,action]=lookup[tuple(recovered)]
    before=oof[i,s];after=oof[i,next_state[s,a]];honest=oof[i,0];y=train.target_log.to_numpy()[i]
    suppression=np.maximum(before-honest,0)-np.maximum(after-honest,0)
    benefit=(before-y)**2-(after-y)**2;risk=(before-y)**2
    matrix=np.concatenate([encoded[i,s],before[:,None],np.eye(4,dtype=np.float32)[a]],axis=1)
    targets=np.column_stack([suppression,benefit,risk])
    rebuilt=ExtraTreesRegressor(n_estimators=cfg['head_trees'],max_depth=12,
                              min_samples_leaf=12,random_state=seed,n_jobs=1)
    rebuilt.fit(matrix,targets)
    assert len(head.model.estimators_)==len(rebuilt.estimators_)==cfg['head_trees']
    for original, new in zip(head.model.estimators_,rebuilt.estimators_):
        for key in ['children_left','children_right','feature','n_node_samples']:
            assert np.array_equal(getattr(original.tree_,key),getattr(new.tree_,key)), key
        for key in ['threshold','value','impurity','weighted_n_node_samples']:
            np.testing.assert_allclose(getattr(original.tree_,key),getattr(new.tree_,key),rtol=1e-8,atol=1e-10,err_msg=key)
    field_s=np.array([suppression[a==k].mean() if (a==k).any() else np.nan for k in range(4)])
    field_b=np.array([benefit[a==k].mean() if (a==k).any() else np.nan for k in range(4)])
    assert head.fixed_field==np.nanargmax(field_s) and head.fixed_benefit_field==np.nanargmax(field_b)
    assert head.target_summary['records']==len(train) and head.target_summary['action_states']==len(i)
    np.testing.assert_allclose([head.target_summary['mean_suppression'],head.target_summary['mean_benefit']],
                               [suppression.mean(),benefit.mean()],rtol=1e-10,atol=1e-12)
    return len(i)

def audit_pair(run,dataset,seed,cfg,train,evaluation,provenance):
    pair=run/dataset/f'seed-{seed}';fit=pair/'fit';binding={}
    def bind(path): binding[str(path)]=sha(path)
    done=read(fit/'completion.json');assert done['status']=='completed_nested_fit'
    assert done['rows']==len(train) and done['outer_folds']==cfg['outer_folds']
    assert done['cells']==24 and done['unique_fits_per_stage']==14
    expected={'train_sha256':content(train),'evaluation_sha256':content(evaluation),'provenance':provenance}
    assert read(pair/'data_binding.json')==expected
    assert not set(ids(train))&set(ids(evaluation))
    assert len(set(ids(train)))==len(train) and len(set(ids(evaluation)))==len(evaluation)
    bind(pair/'data_binding.json');bind(fit/'completion.json');bind(fit/'inputs.json')
    inp=read(fit/'inputs.json');assert inp['train_content']==content(train)
    assert inp['columns']==FEATURES[dataset] and inp['config']==cfg and inp['seed']==seed
    for path,h in inp['sources'].items(): assert sha(Path(path))==h
    for filename,key in [('outer_predictions.npz','outer_predictions_sha256'),('outer_assignments.csv','assignment_sha256'),
                         ('fold_receipts.json','fold_receipts_sha256'),('cell_mapping.json','cell_mapping_sha256')]:
        assert sha(fit/filename)==done[key];bind(fit/filename)
    mapping=read(fit/'cell_mapping.json')
    expected_mapping={}
    for initial,score,feedback,allocation in itertools.product(['masking','robust'],['suppression','benefit','risk'],['none','policy'],['top_b','minimax']):
        expected_mapping[(initial,score,feedback,allocation)]=initial+('__none__shared__shared' if feedback=='none' else f'__policy__{score}__{allocation}')
    assert len(mapping)==24 and {tuple(x['cell']):x['fit_id'] for x in mapping}==expected_mapping
    fit_ids=set(expected_mapping.values());assert len(fit_ids)==14
    assigned=np.empty(len(train),dtype=int);assigned[rank(train,'sav-val-outer-v2')]=np.arange(len(train))%cfg['outer_folds']
    stored=pd.read_csv(fit/'outer_assignments.csv');assert ids(stored)==ids(train)
    assert np.array_equal(stored.outer_fold,assigned)
    oof=np.load(fit/'outer_predictions.npz');assert set(oof.files)==fit_ids
    receipts=read(fit/'fold_receipts.json');assert len(receipts)==cfg['outer_folds']
    predicted=0
    for fold,r in enumerate(receipts):
        assert r['fold']==fold
        estimator,guidance=split(train.loc[assigned!=fold],cfg['head_fitting_fraction'])
        held=train.loc[assigned==fold];partition(r,estimator,guidance,held)
        stage=fit/f'outer-{fold}'
        verify_stage(stage,estimator,guidance,cfg,seed,FEATURES[dataset],fit_ids,binding)
        for key in sorted(fit_ids):
            model,_=joblib.load(stage/(key+'.joblib'))
            actual,_,_=model.predict(price_features(held,FEATURES[dataset]))
            prediction_equal(actual,oof[key][assigned==fold]);predicted+=len(held)
    estimator,guidance=split(train,cfg['head_fitting_fraction'])
    verify_stage(fit/'deployment_fit',estimator,guidance,cfg,seed,FEATURES[dataset],fit_ids,binding)
    assert set(done['deployment_model_hashes'])==fit_ids
    targets=0
    for key in sorted(fit_ids):
        path=fit/'deployment_models'/(key+'.joblib');assert sha(path)==done['deployment_model_hashes'][key];bind(path)
        model,head=joblib.load(path)
        fitted,_=joblib.load(fit/'deployment_fit'/(key+'.joblib'))
        assert set(model.residual.state_dict())==set(fitted.residual.state_dict())
        for name,value in model.residual.state_dict().items():
            assert torch.equal(value,fitted.residual.state_dict()[name])
        full=pd.concat([train,evaluation],ignore_index=True)
        original=fitted.predict(price_features(full,FEATURES[dataset]))
        deployed=model.predict(price_features(full,FEATURES[dataset]))
        for old,new in zip(original,deployed): assert np.array_equal(old,new)
        targets+=rebuild_head(model,head,train,FEATURES[dataset],oof[key],cfg,seed)
        print(f'HEAD VERIFIED {dataset}/{seed}/{key}',flush=True)
    assert all(sha(Path(path))==h for path,h in binding.items())
    return {'status':'completed','dataset':dataset,'seed':seed,'heldout_prediction_rows':predicted,
            'independently_refitted_heads':14,'head_target_rows':targets,'bound_files':binding}

def mutation_checks(cfg):
    trace={'epoch':0,'updates':1,'examples':2,'objective':'masking','policy_feedback':False,'loss':1.,'query_mass':0.,
           'permutation_sha256':hashlib.sha256(np.random.default_rng(1).permutation(2).tobytes()).hexdigest()}
    local={**cfg,'batch_size':20}
    epoch_trace([trace],2,1,1,'masking',False,local)
    bad=copy.deepcopy(trace);bad['permutation_sha256']='corrupt'
    frame=pd.DataFrame({'listing_id':['a','b','c']});e,g,h=[frame.iloc[[i]] for i in range(3)]
    receipt={'estimator_ids':['a'],'guidance_ids':['b'],'heldout_ids':['c']}
    partition(receipt,e,g,h);wrong={**receipt,'heldout_ids':['a']}
    checks=[('permutation',lambda:epoch_trace([bad],2,1,1,'masking',False,local)),
            ('heldout_partition',lambda:partition(wrong,e,g,h)),
            ('heldout_prediction',lambda:prediction_equal(np.zeros(3),np.ones(3)))]
    rejected=[]
    for name, call in checks:
        try:call()
        except AssertionError:rejected.append(name)
        else:raise AssertionError('Mutation accepted: '+name)
    return rejected

def main(a):
    run=a.run.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    lock=(out/'execution.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    manifest=read(run/'manifest.json');cfg=manifest['config'];torch.set_num_threads(2)
    for name,h in manifest['source_hashes'].items():
        assert sha(run/'source_snapshot'/name)==h and sha(Path(__file__).with_name(name))==h
    all_pairs=[(d,s) for d in cfg['datasets'] for s in cfg['seeds']]
    available=[(d,s) for d,s in all_pairs if (run/d/f'seed-{s}'/'fit/completion.json').exists()]
    if not a.completed_only:assert len(available)==len(all_pairs),'Full fit set incomplete'
    assert available
    if (out/'inputs.json').exists():
        previous=read(out/'inputs.json')
        selected=[tuple(x) for x in previous['selected_pairs']]
        assert set(selected)<=set(available)
        if a.completed_only: available=selected
    inputs={'run_manifest_sha256':sha(run/'manifest.json'),'checker_sha256':sha(Path(__file__)),
            'selected_pairs':[list(x) for x in available],'completed_only':a.completed_only}
    if (out/'inputs.json').exists():assert read(out/'inputs.json')==inputs
    else:write(out/'inputs.json',inputs)
    results=[];cache={}
    for dataset,seed in available:
        checkpoint=out/dataset/f'seed-{seed}.json'
        reuse=(a.reuse/dataset/f'seed-{seed}.json') if a.reuse else None
        candidate=checkpoint if checkpoint.exists() else reuse
        if candidate is not None and candidate.exists():
            old_input=read(candidate.parent.parent/'inputs.json');assert old_input['checker_sha256']==inputs['checker_sha256'] and old_input['run_manifest_sha256']==inputs['run_manifest_sha256']
            r=read(candidate);assert all(sha(Path(p))==h for p,h in r['bound_files'].items())
            assert r['status']=='completed' and (r['dataset'],r['seed'])==(dataset,seed)
        else:
            if dataset not in cache:
                e,g,v,provenance=load_source(dataset,cfg);cache[dataset]=(pd.concat([e,g],ignore_index=True),v,provenance)
            train,evaluation,provenance=cache[dataset]
            r=audit_pair(run,dataset,seed,cfg,train,evaluation,provenance)
        write(checkpoint,r);results.append(r)
        print(f'FIT VERIFIED {dataset}/{seed}',flush=True)
    assert sha(run/'manifest.json')==inputs['run_manifest_sha256']
    assert sha(Path(__file__))==inputs['checker_sha256']
    for name,h in manifest['source_hashes'].items():assert sha(Path(__file__).with_name(name))==h
    result={'status':'completed','coverage':'all_configured_fits' if len(available)==len(all_pairs) else 'partial_completed_fits',
            'execution_smoke':cfg.get('execution_smoke',False),'source_seed_pairs':len(results),'configured_pairs':len(all_pairs),
            'heldout_prediction_rows':sum(r['heldout_prediction_rows'] for r in results),
            'independently_refitted_heads':sum(r['independently_refitted_heads'] for r in results),
            'mutations_rejected':mutation_checks(cfg),'inputs':inputs,
            'scope':'split and matched-budget receipts, all OOF predictions and independently reconstructed deployment heads; not full optimizer replay or performance evidence'}
    (out/'checker_snapshot.py').write_bytes(Path(__file__).read_bytes());write(out/'completion.json',result)
    print(json.dumps(result),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['run','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--completed-only',action='store_true');p.add_argument('--reuse',type=Path)
    main(p.parse_args())
