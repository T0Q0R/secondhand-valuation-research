"""Controlled suppression/feedback/gap 2^3 ablation, with immutable checkpoints.
Never writes manuscript files. Original fits/results are read-only evidence.
"""
from pathlib import Path
import argparse,copy,fcntl,hashlib,json,itertools,os,sys,time,traceback,gc
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np,pandas as pd,torch,joblib
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from savval import FEATURES,ACTIONS,StateSpace,ActionHeads,fit_backbone,price_features
from run_all import load_source,rank_subset,evaluate_method,fit_methods
from run_crossfit import fold_assignments,inner_split,identifiers
PARENT=ROOT/'outputs/nested-development-v2'
PAPER_SHA='bf799e53b6ba4cbebf84ec78d6c2c3ffe581e6a9a21a8f4e312dd2646f656a24'
CODES=sorted([i for i in range(16) if i.bit_count()<=2],key=lambda i:(i.bit_count(),tuple(f for f in range(4) if i&(1<<f))))
BITS=np.array([[bool(c&(1<<f)) for f in range(4)] for c in CODES]);LOOKUP={v:i for i,v in enumerate(CODES)}
EXISTING={'on_sup_gap':'sav_val','on_ben_gap':'sav_benefit_head','on_sup_zero':'sav_no_gap'}
NEW=['off_gap','off_zero','on_ben_zero'];ALL=[*EXISTING,*NEW]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,j):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(j,indent=2)+'\n');tmp.replace(p)
def guard():
 if sha(ROOT/'paper/innovation-addendum-v1.tex')!=PAPER_SHA:raise RuntimeError('Manuscript frozen by experiment-first instruction; source changed')
def content(f):return hashlib.sha256(f.to_csv(index=False).encode()).hexdigest()
def dump(p,obj):
 tmp=p.with_name(p.name+'.tmp');joblib.dump(obj,tmp,compress=3);tmp.replace(p)
def head(model,frame,columns,config,seed):
 pp,x,v=model.predict(price_features(frame,columns));h=ActionHeads(config['head_trees'],seed);h.model.n_jobs=2
 return h.fit(x,pp,v,frame.target_log.to_numpy(),model.space,reported_missing=model.space.reported_missing(frame))
def stage_check(old,est,guide,seed):
 j=json.loads((old/'fit_completion.json').read_text());inputs=j['inputs']
 assert inputs['seed']==seed and inputs['estimator_content']==content(est) and inputs['guidance_content']==content(guide)
 p=old/'models/masking_suppression.joblib';assert sha(p)==j['files']['models/masking_suppression.joblib'];return p

def fit_stage(est,guide,columns,cfg,seed,out,old,smoke):
 out.mkdir(parents=True,exist_ok=True)
 if smoke:
  base=fit_backbone(price_features(est,columns),est.target_log.to_numpy(),StateSpace.build(2),cfg,seed,augment=True);initial=head(base,guide,columns,cfg,seed);base_sha=None
 else:
  oldbase=stage_check(old,est,guide,seed);base,initial,_=joblib.load(oldbase);base_sha=sha(oldbase);assert base.residual is None
 paths={}
 for name in (ALL if smoke else NEW):
  folder=out/name;folder.mkdir(exist_ok=True);cp=folder/'completion.json'
  inputs=dict(estimator=content(est),guidance=content(guide),seed=seed,name=name,config=cfg,base_model=base_sha)
  if cp.exists():
   j=json.loads(cp.read_text());assert j['inputs']==inputs and sha(folder/'model.joblib')==j['model_sha256'];paths[name]=folder/'model.joblib';continue
  feedback=name.startswith('on');kind='benefit' if '_ben_' in name else 'suppression';beta=0. if name.endswith('zero') else .5
  model=copy.deepcopy(base);current=initial;logs=[];started=time.time()
  for round_idx in range(2):
   rp=folder/f'round-{round_idx+1}.json';mp=folder/f'round-{round_idx+1}.joblib'
   if rp.exists():
    rr=json.loads(rp.read_text());assert rr['inputs']==inputs and rr['model_sha256']==sha(mp);model,current,logs=joblib.load(mp);continue
   public=price_features(est,columns);epochs=cfg['residual_epochs']//2
   trained=model.train_residual(public,est.target_log.to_numpy(),cfg,seed+round_idx,current if feedback else None,gap_weight=beta,policy_kind=kind,policy_aware=True,epochs=epochs)
   current=head(model,guide,columns,cfg,seed);logs.append(dict(round=round_idx+1,epochs=epochs,training=trained,head_targets=current.target_summary))
   dump(mp,(model,current,logs));write(rp,dict(inputs=inputs,model_sha256=sha(mp),status='round_completed'))
  dump(folder/'model.joblib',(model,current,kind));write(cp,dict(status='fitted',inputs=inputs,model_sha256=sha(folder/'model.joblib'),seconds=time.time()-started,rounds=logs))
  paths[name]=folder/'model.joblib';print('FIT',out,name,flush=True);del model,current;gc.collect()
 if not smoke:
  receipt=json.loads((old/'fit_completion.json').read_text())
  for key,name in EXISTING.items():
   p=old/'models'/f'{name}.joblib';assert sha(p)==receipt['files'][f'models/{name}.joblib'];paths[key]=p
 del base,initial;gc.collect();return paths

def matrix_audit(pred,scores,valid,frame,rows,budget):
 """Independent integer masks, rank counting, transitions and all own reports."""
 assert np.array_equal(valid,~(BITS[None,:,:]&~frame.loc[:,ACTIONS].notna().to_numpy()[:,None,:]).any(2))
 legal=0;maxreg=0.;n=len(frame)
 for start in range(0,n,100):
  rr=rows.iloc[start:start+100];pp=pred[start:start+100];sc=scores[start:start+100];vv=valid[start:start+100];nn=len(rr);ix=np.arange(nn);st=rr.state.to_numpy(int);cap=int(np.floor(nn*budget))
  field=sc.argmax(2);gain=np.take_along_axis(sc,field[:,:,None],2)[:,:,0];active=np.isfinite(gain)&(gain>0);peers=gain[ix,st]
  actor=np.arange(nn)[:,None,None];peer=np.arange(nn)[None,None,:]
  ahead=(((peers[None,None,:]>gain[:,:,None])|((peers[None,None,:]==gain[:,:,None])&(peer<actor)))&(peer!=actor)).sum(2)
  take=active&(ahead<cap);after=np.array([[LOOKUP[CODES[s]&~(1<<int(field[i,s]))] for s in range(11)] for i in range(nn)])
  options=np.where(take,pp[ix[:,None],after],pp);options=np.where(vv,options,-np.inf);quote=options[ix,st]
  actions=np.where(take[ix,st],field[ix,st],-1);final=np.where(take[ix,st],after[ix,st],st);success=np.array([a>=0 and bool(CODES[int(s)]&(1<<int(a))) for s,a in zip(st,actions)])
  regret=np.maximum(options.max(1)-quote,0);truth=pp[:,0];target=frame.iloc[start:start+nn].target_log.to_numpy();tp=np.expm1(target)
  assert np.array_equal(actions,rr.action) and np.array_equal(final,rr.final_state) and np.array_equal(success,rr.query_succeeded)
  values={'clean_prediction_log':truth,'attacked_prediction_log':quote,'target_log':target,'clean_absolute_error':abs(np.expm1(truth)-tp),'attack_absolute_error':abs(np.expm1(quote)-tp),'positive_log_inflation':np.maximum(quote-truth,0),'best_response_regret_log':regret,'unilateral_inflation_envelope_log':np.maximum(options.max(1)-truth,0)}
  for k,v in values.items():assert np.allclose(v,rr[k].to_numpy(),atol=1e-7,rtol=1e-10),k
  assert (actions>=0).sum()<=cap;legal+=int(vv.sum());maxreg=max(maxreg,float(regret.max()))
 return dict(status='allocation_transition_all_legal_utilities_corroborated',legal_deviations=legal,max_regret=maxreg,scope='Frozen predictor/head shared; separate integer states, rank count, transitions and utility algebra')

def worker(task):
 source,seed,cfg,output,smoke=task;torch.set_num_threads(2);guard();out=Path(output)/source/f'seed-{seed}';out.mkdir(parents=True,exist_ok=True)
 lock=(out/'execution.lock').open('a+');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 with threadpool_limits(limits=2):
  est0,guide0,evaluation,_=load_source(source,cfg);train=rank_subset(pd.concat([est0,guide0],ignore_index=True),len(est0)+len(guide0),'sav-val-cf-training-order-v2');columns=FEATURES[source]
  assigned=fold_assignments(train,cfg['outer_folds']);old=PARENT/source/f'seed-{seed}'
  if not smoke:
   oldassign=pd.read_csv(old/'outer_assignments.csv');assert oldassign.listing_id.tolist()==train.listing_id.tolist() and np.array_equal(assigned,oldassign.outer_fold)
  oof={k:np.empty((len(train),11)) for k in ALL}
  if not smoke:
   receipt=json.loads((old/'outer_audit.json').read_text());assert sha(old/'outer_predictions.npz')==receipt['prediction_sha256'];saved=np.load(old/'outer_predictions.npz')
   for k,name in EXISTING.items():oof[k][:]=saved[name]
  for fold in range(cfg['outer_folds']):
   working=train.loc[assigned!=fold];held=train.loc[assigned==fold];est,guide=inner_split(working,cfg['head_fitting_fraction']);assert not set(held.listing_id)&set(est.listing_id)|set(held.listing_id)&set(guide.listing_id)
   paths=fit_stage(est,guide,columns,cfg,seed,out/'fit'/f'outer-{fold}',old/f'outer-{fold}',smoke)
   for key in (ALL if smoke else NEW):
    model,_,_=joblib.load(paths[key]);oof[key][assigned==fold]=model.predict(price_features(held,columns))[0];del model;gc.collect()
  est,guide=inner_split(train,cfg['head_fitting_fraction']);paths=fit_stage(est,guide,columns,cfg,seed,out/'fit/deployment',old/'deployment_fit',smoke)
  if smoke:
   ref=out/'smoke_identity_reference'
   if not (out/'smoke_identity.json').exists():
    ref.mkdir(parents=True,exist_ok=True)
    originals=fit_methods(est,guide,columns,cfg,seed,ref)
    errors={}
    for key,name in EXISTING.items():
     mm,_,_=joblib.load(paths[key]);errors[key]=float(abs(mm.predict(price_features(evaluation,columns))[0]-originals[name][0].predict(price_features(evaluation,columns))[0]).max());assert errors[key]<1e-6
    write(out/'smoke_identity.json',dict(max_log_errors=errors,scope='Reused feedback-on schedule matches production training on identical tiny data'))
    del originals;gc.collect()
  np.savez_compressed(out/'outer_predictions.npz',**oof)
  pd.DataFrame(dict(listing_id=train.listing_id,outer_fold=assigned)).to_csv(out/'outer_assignments.csv',index=False)
  summaries=[];reuse_rows=None
  for key in ALL:
   dp=out/'deployment_models'/f'{key}.joblib';dp.parent.mkdir(exist_ok=True);dr=dp.with_suffix('.json')
   binding=dict(price_model_sha256=sha(paths[key]),outer_prediction_sha256=hashlib.sha256(oof[key].tobytes()).hexdigest(),training_content=content(train),head_trees=cfg['head_trees'],seed=seed)
   if key in EXISTING and not smoke:binding['original_deployment_sha256']=sha(old/'deployment_models'/f'{EXISTING[key]}.joblib')
   if dr.exists():
    prior=json.loads(dr.read_text());assert prior['inputs']==binding and prior['model_sha256']==sha(dp)
   else:
    if key in EXISTING and not smoke:
     p=old/'deployment_models'/f'{EXISTING[key]}.joblib';fitted=joblib.load(p)
     # Original receipt does not hash deployment files. Bind the current artifact;
     # every reused evaluation is separately replayed below against its frozen rows.
     binding['original_deployment_sha256']=sha(p)
     dump(dp,fitted)
    else:
     model,_,kind=joblib.load(paths[key]);pp,x,v=model.predict(price_features(train,columns));hh=ActionHeads(cfg['head_trees'],seed);hh.model.n_jobs=2;hh.fit(x,oof[key],v,train.target_log.to_numpy(),model.space,reported_missing=model.space.reported_missing(train));dump(dp,(model,hh,kind));del pp,x,v,hh,model
    write(dr,dict(inputs=binding,model_sha256=sha(dp),validation='Original reused outcomes independently replayed per cell; new heads use outer-held-out targets'))
   model,hh,stored_kind=joblib.load(dp)
   pp,x,v=model.predict(price_features(evaluation,columns));missing=model.space.reported_missing(evaluation)
   for suppression in ([0,1] if key.startswith('off_') else [int('_sup_' in key)]):
    feedback=int(key.startswith('on'));gap=int(key.endswith('gap'));kind='suppression' if suppression else 'benefit';name=f'S{suppression}F{feedback}G{gap}';scores=hh.score(x,pp,model.space,kind,reported_missing=missing)
    table=out/'state_tables'/f'{name}.npz';table.parent.mkdir(exist_ok=True)
    if not table.exists():np.savez_compressed(table,pred=pp,scores=scores,valid=v)
    for budget in cfg['budgets']:
     folder=out/'evaluation'/name/f'budget-{round(budget*10000):04d}';folder.mkdir(parents=True,exist_ok=True);cp=folder/'completion.json'
     inputs=dict(model_sha256=sha(dp),state_table_sha256=sha(table),evaluation_content=content(evaluation),budget=budget,kind=kind,source=source,seed=seed)
     if cp.exists():
      j=json.loads(cp.read_text());assert j['inputs']==inputs
      if 'outcomes_sha256' in j:assert sha(folder/'outcomes.csv.gz')==j['outcomes_sha256']
      summaries.append(j['summary']);continue
     if key in EXISTING and not smoke:
      ep=old/'per_listing_outcomes.csv.gz';er=json.loads((old/'evaluation_completion.json').read_text());assert sha(ep)==er['outcomes_sha256']
      if reuse_rows is None:reuse_rows=pd.read_csv(ep)
      rr=reuse_rows[(reuse_rows.method==EXISTING[key])&np.isclose(reuse_rows.budget,budget)].copy();assert rr.listing_id.tolist()==evaluation.listing_id.tolist();rr['method']=name
      original=pd.read_csv(old/'summary.csv');su=original[(original.method==EXISTING[key])&np.isclose(original.budget,budget)].iloc[0].to_dict();su['method']=name;reuse=dict(path=str(ep.relative_to(ROOT)),sha256=sha(ep),method=EXISTING[key],budget=budget)
     else:rr,su=evaluate_method(name,model,hh,kind,evaluation,columns,cfg,seed,budget);reuse=None
     audit=matrix_audit(pp,scores,v,evaluation,rr,budget);su.update(dataset=source,suppression_target=suppression,feedback=feedback,gap_penalty=gap)
     record=dict(status='completed_and_corroborated',inputs=inputs,summary=su,audit=audit)
     if reuse:record['reused_original_outcomes']=reuse
     else:rr.to_csv(folder/'outcomes.csv.gz',index=False);record['outcomes_sha256']=sha(folder/'outcomes.csv.gz')
     write(cp,record);summaries.append(su);write(out/'progress.json',dict(status='running',completed_cells=len(summaries),expected_cells=8*len(cfg['budgets']),last_cell=name,last_budget=budget,time=time.time()))
     print('CELL',source,seed,name,budget,len(summaries),'/',8*len(cfg['budgets']),flush=True)
   del model,hh,pp,x,v,scores;gc.collect()
  assert len(summaries)==8*len(cfg['budgets']);pd.DataFrame(summaries).to_csv(out/'summary.csv',index=False)
  write(out/'completion.json',dict(status='completed_and_corroborated',cells=len(summaries),summary_sha256=sha(out/'summary.csv'),outer_predictions_sha256=sha(out/'outer_predictions.npz'),script_sha256=sha(Path(__file__)),no_outer_label_leak=True,scope='Retrospective three-component controlled experiment, not confirmatory population evidence'));guard();return summaries

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=2);p.add_argument('--smoke',action='store_true');a=p.parse_args();guard();output=a.output.resolve();output.mkdir(parents=True,exist_ok=True)
 lock=(output/'execution.lock').open('a+');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 parent=json.loads((PARENT/'run_manifest.json').read_text());cfg=copy.deepcopy(parent['config'])
 for file in ['savval.py','run_all.py','run_crossfit.py']:assert sha(ROOT/'experiments'/file)==parent['source_hashes'][file]
 if a.smoke:cfg.update(max_train=300,max_evaluation=100,catboost_iterations=30,head_trees=16,residual_epochs=4,outer_folds=2,seeds=[13],datasets=['synthetic'],budgets=[0,.1,.3])
 tasks=[(d,s,cfg,str(output),a.smoke) for d in cfg['datasets'] for s in cfg['seeds']]
 manifest=dict(status='running',config=cfg,workers=a.workers,smoke_only=a.smoke,expected_pairs=len(tasks),expected_cells=len(tasks)*8*len(cfg['budgets']),script_sha256=sha(Path(__file__)),paper_frozen_sha256=PAPER_SHA,parent_manifest_sha256=sha(PARENT/'run_manifest.json'),thread_policy='2workers;torch2/BLAS2;head2;inherited CatBoost4')
 mp=output/'manifest.json'
 if mp.exists():assert json.loads(mp.read_text())==manifest
 else:write(mp,manifest)
 rows=[]
 with ProcessPoolExecutor(max_workers=a.workers) as pool:
  futures={pool.submit(worker,t):t[:2] for t in tasks}
  for future in as_completed(futures):
   pair=futures[future]
   try:rows.extend(future.result())
   except Exception:
    write(output/'failure.json',dict(pair=pair,traceback=traceback.format_exc(),time=time.time()));raise
   pd.DataFrame(rows).to_csv(output/'summary.csv',index=False);write(output/'progress.json',dict(status='running',completed_pairs=len(rows)//(8*len(cfg['budgets'])),expected_pairs=len(tasks),completed_cells=len(rows)))
 assert len(rows)==manifest['expected_cells'];write(output/'completion.json',dict(status='completed_and_corroborated',cells=len(rows),pairs=len(tasks),summary_sha256=sha(output/'summary.csv'),manifest_sha256=sha(mp),smoke_only=a.smoke));guard()
if __name__=='__main__':main()
