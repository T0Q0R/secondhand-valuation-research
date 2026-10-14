"""Uniform full-pipeline parameter curves; no manuscript writes or test-set tuning."""
from pathlib import Path
import argparse,copy,fcntl,gc,hashlib,json,os,sys,time,traceback
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np,pandas as pd,torch,joblib
from threadpoolctl import threadpool_limits
import run_completion_ablation_v6 as common
from savval import FEATURES,ActionHeads,price_features
from run_all import load_source,rank_subset,evaluate_method
from run_crossfit import fold_assignments,inner_split
ROOT=common.ROOT;PARENT=common.PARENT
sha=common.sha;write=common.write;dump=common.dump;content=common.content

def variants():
 rows={}
 axes={'anchor_weight':[0.,.125,.5,1.], 'attack_loss_weight':[0.,.25,1.,2.], 'learning_rate':[.0003,.003], 'residual_epochs':[6,24], 'head_trees':[80,320], 'residual_hidden_width':[32,128]}
 for axis,values in axes.items():
  for value in values:rows[f'{axis}-{value:g}']=dict(beta=.5,tolerance=.02,rounds=2,feedback=True,axis=axis,updates={axis:value})
 return rows

def fit_one(est,guide,columns,cfg,seed,out,old,v):
 out.mkdir(parents=True,exist_ok=True);basepath=common.stage_check(old,est,guide,seed)
 inputs=dict(estimator=content(est),guidance=content(guide),base=sha(basepath),seed=seed,config=cfg,variant=v)
 cp=out/'completion.json';path=out/'model.joblib'
 if cp.exists():
  r=json.loads(cp.read_text());assert r['inputs']==inputs and r['model_sha256']==sha(path);return path
 model,current,_=joblib.load(basepath);assert model.residual is None;model.width=cfg['residual_hidden_width'];current=common.head(model,guide,columns,cfg,seed) if 'head_trees' in v.get('updates',{}) else current;current.model.n_jobs=2;logs=[];started=time.time()
 for i in range(v['rounds']):
  rp=out/f'round-{i+1}.json';mp=out/f'round-{i+1}.joblib'
  if rp.exists():
   r=json.loads(rp.read_text());assert r['inputs']==inputs and sha(mp)==r['sha256'];model,current,logs=joblib.load(mp);continue
  loss=model.train_residual(price_features(est,columns),est.target_log.to_numpy(),cfg,seed+i,current if v['feedback'] else None,gap_weight=v['beta'],policy_kind='suppression',policy_aware=True,epochs=cfg['residual_epochs']//v['rounds'])
  current=common.head(model,guide,columns,cfg,seed);logs.append(dict(round=i+1,epochs=cfg['residual_epochs']//v['rounds'],loss=loss));dump(mp,(model,current,logs));write(rp,dict(inputs=inputs,sha256=sha(mp)))
 dump(path,(model,current,'suppression'));write(cp,dict(status='fitted',inputs=inputs,model_sha256=sha(path),seconds=time.time()-started,rounds=logs));return path

def pair(task):
 source,seed,cfg,outstr,smoke=task;torch.set_num_threads(2);common.guard();out=Path(outstr)/source/f'seed-{seed}';out.mkdir(parents=True,exist_ok=True)
 lock=(out/'execution.lock').open('a+');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 with threadpool_limits(limits=2):
  est0,guide0,evaluation,_=load_source(source,cfg);train=rank_subset(pd.concat([est0,guide0],ignore_index=True),len(est0)+len(guide0),'sav-val-cf-training-order-v2');assigned=fold_assignments(train,cfg['outer_folds']);columns=FEATURES[source];old=PARENT/source/f'seed-{seed}'
  original_assign=pd.read_csv(old/'outer_assignments.csv');assert original_assign.listing_id.tolist()==train.listing_id.tolist() and np.array_equal(assigned,original_assign.outer_fold)
  settings=variants()
  if smoke:settings={'stability-smoke':dict(beta=.5,tolerance=.02,rounds=2,feedback=True,axis='smoke',updates={'residual_hidden_width':32,'head_trees':80,'residual_epochs':6})}
  summaries=[]
  for name,v in settings.items():
   scfg=copy.deepcopy(cfg);scfg['gap_penalty_weight']=v['beta'];scfg['gap_tolerance_log']=v['tolerance'];scfg['feedback_rounds']=v['rounds'];scfg.update(v.get('updates',{}))
   if not smoke and not v.get('updates') and v['beta'] in [0.,.5] and v['tolerance']==.02 and v['rounds']==2:
    if v['feedback']:
     method='sav_val' if v['beta']==.5 else 'sav_no_gap';modelpath=old/'deployment_models'/f'{method}.joblib';outcomes=old/'per_listing_outcomes.csv.gz';receipt=json.loads((old/'evaluation_completion.json').read_text());assert sha(outcomes)==receipt['outcomes_sha256'];assert sha(old/'summary.csv')==receipt['summary_sha256']
     origin=dict(type='original',method=method,outcomes=str(outcomes.relative_to(ROOT)),sha256=sha(outcomes));source_rows=pd.read_csv(outcomes);source_summary=pd.read_csv(old/'summary.csv')
    else:
     shared=ROOT/'outputs/completion-ablation-v6'/source/f'seed-{seed}';assert (shared/'completion.json').exists();modelpath=shared/'deployment_models/off_gap.joblib';assert sha(modelpath)==json.loads(modelpath.with_suffix('.json').read_text())['model_sha256'];origin=dict(type='ablation',root=str(shared.relative_to(ROOT)),method='S1F0G1');source_rows=source_summary=None
   else:
    origin=None;oof=np.empty((len(train),11));vd=out/name;vd.mkdir(exist_ok=True)
    for fold in range(cfg['outer_folds']):
     est,guide=inner_split(train.loc[assigned!=fold],cfg['head_fitting_fraction']);held=train.loc[assigned==fold];assert not (set(held.listing_id)&(set(est.listing_id)|set(guide.listing_id)))
     p=fit_one(est,guide,columns,scfg,seed,vd/f'outer-{fold}',old/f'outer-{fold}',v);model,_,_=joblib.load(p);oof[assigned==fold]=model.predict(price_features(held,columns))[0];del model;gc.collect()
    est,guide=inner_split(train,cfg['head_fitting_fraction']);p=fit_one(est,guide,columns,scfg,seed,vd/'deployment',old/'deployment_fit',v)
    np.savez_compressed(vd/'outer_predictions.npz',prediction=oof)
    modelpath=vd/'deployment_model.joblib';dr=vd/'deployment_model.json';binding=dict(price_sha256=sha(p),oof_sha256=hashlib.sha256(oof.tobytes()).hexdigest(),training=content(train),seed=seed,head_trees=scfg['head_trees'])
    if dr.exists():
     r=json.loads(dr.read_text());assert r['inputs']==binding and r['sha256']==sha(modelpath)
    else:
     model,_,kind=joblib.load(p);pp,x,valid=model.predict(price_features(train,columns));hh=ActionHeads(scfg['head_trees'],seed);hh.model.n_jobs=2;hh.fit(x,oof,valid,train.target_log.to_numpy(),model.space,reported_missing=model.space.reported_missing(train));dump(modelpath,(model,hh,kind));write(dr,dict(inputs=binding,sha256=sha(modelpath)));del model,hh,pp,x,valid;gc.collect()
   model,hh,kind=joblib.load(modelpath);pred,x,valid=model.predict(price_features(evaluation,columns));scores=hh.score(x,pred,model.space,'suppression',reported_missing=model.space.reported_missing(evaluation))
   if smoke:
    assert model.residual[0].out_features==32 and len(hh.model.estimators_)==80
    receipt=json.loads((out/name/'deployment/completion.json').read_text());assert sum(x['epochs'] for x in receipt['rounds'])==6
    write(out/'identity.json',dict(status='structural_controls_pass',residual_width=32,head_tree_count=80,total_epochs=6,scope='New controls propagate through outer fitting and deployment; baseline identity established by core parameter smoke'))
   for budget in cfg['budgets']:
    d=out/name/f'evaluation-{round(budget*10000):04d}';d.mkdir(parents=True,exist_ok=True);cp=d/'completion.json';inputs=dict(variant=v,model=sha(modelpath),evaluation=content(evaluation),budget=budget)
    if cp.exists():
     r=json.loads(cp.read_text());assert r['inputs']==inputs
     if 'outcomes_sha256' in r:assert sha(d/'outcomes.csv.gz')==r['outcomes_sha256']
     summaries.append(r['summary']);continue
    if origin and origin['type']=='original':
     rr=source_rows[(source_rows.method==origin['method'])&np.isclose(source_rows.budget,budget)].copy();su=source_summary[(source_summary.method==origin['method'])&np.isclose(source_summary.budget,budget)].iloc[0].to_dict()
    elif origin:
     cell=shared/'evaluation/S1F0G1'/f'budget-{round(budget*10000):04d}';r=json.loads((cell/'completion.json').read_text());assert sha(cell/'outcomes.csv.gz')==r['outcomes_sha256'];rr=pd.read_csv(cell/'outcomes.csv.gz');su=r['summary']
    else:rr,su=evaluate_method(name,model,hh,'suppression',evaluation,columns,scfg,seed,budget)
    assert rr.listing_id.tolist()==evaluation.listing_id.tolist();audit=common.matrix_audit(pred,scores,valid,evaluation,rr,budget);su.update(method=name,dataset=source,beta=v['beta'],tolerance=v['tolerance'],rounds=v['rounds'],feedback=v['feedback'],axis=v['axis'],parameter_value=list(v.get('updates',{}).values())[0] if v.get('updates') else None);r=dict(status='completed_and_corroborated',inputs=inputs,summary=su,audit=audit)
    if origin:r['reused']=origin
    else:rr.to_csv(d/'outcomes.csv.gz',index=False);r['outcomes_sha256']=sha(d/'outcomes.csv.gz')
    write(cp,r);summaries.append(su);write(out/'progress.json',dict(status='running',completed_cells=len(summaries),expected_cells=len(settings)*len(cfg['budgets']),last_variant=name,last_budget=budget));print('CELL',source,seed,name,budget,len(summaries),flush=True)
   del model,hh,pred,x,scores,valid;gc.collect()
  pd.DataFrame(summaries).to_csv(out/'summary.csv',index=False);write(out/'completion.json',dict(status='completed_and_corroborated',cells=len(summaries),summary_sha256=sha(out/'summary.csv')));common.guard();return summaries

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=2);p.add_argument('--smoke',action='store_true');p.add_argument('--ready-only',action='store_true');a=p.parse_args();common.guard();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);lock=(out/'execution.lock').open('a+');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 cfg=copy.deepcopy(json.loads((PARENT/'run_manifest.json').read_text())['config']);cfg['budgets']=[.1]
 if a.smoke:cfg.update(datasets=['synthetic'],seeds=[13],budgets=[.1])
 tasks=[(d,s,cfg,str(out),a.smoke) for d in cfg['datasets'] for s in cfg['seeds']];manifest=dict(config=cfg,workers=a.workers,smoke_only=a.smoke,settings=variants(),expected_pairs=len(tasks),expected_cells=len(tasks)*(1 if a.smoke else len(variants()))*len(cfg['budgets']),source_sha256=sha(Path(__file__)),common_source_sha256=sha(Path(common.__file__)),paper_frozen_sha256=common.PAPER_SHA,scope='Additional loss/optimizer/capacity stability,one factor at a time; no evaluation-driven default selection')
 mp=out/'manifest.json'
 if mp.exists():assert json.loads(mp.read_text())==manifest
 else:write(mp,manifest)
 if a.ready_only:return
 rows=[]
 with ProcessPoolExecutor(max_workers=a.workers) as pool:
  futures={pool.submit(pair,t):t[:2] for t in tasks}
  for f in as_completed(futures):
   try:rows.extend(f.result())
   except Exception:write(out/'failure.json',dict(pair=futures[f],traceback=traceback.format_exc()));raise
   pd.DataFrame(rows).to_csv(out/'summary.csv',index=False);write(out/'progress.json',dict(completed_cells=len(rows),expected_cells=manifest['expected_cells']))
 assert len(rows)==manifest['expected_cells'];write(out/'completion.json',dict(status='completed_and_corroborated',cells=len(rows),summary_sha256=sha(out/'summary.csv'),manifest_sha256=sha(mp),smoke_only=a.smoke));common.guard()
if __name__=='__main__':main()
