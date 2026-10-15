"""Three recent baseline adapters; paired fixed-price backends and audited evaluation."""
from run_completion_sefa_v6 import *
import recent_acquisition_training_v1 as training
def pair(task):
 source,seed,cfg,outstr,smoke=task;common.guard();torch.set_num_threads(1 if smoke else 2);out=Path(outstr)/source/f'seed-{seed}';out.mkdir(parents=True,exist_ok=True);lock=(out/'execution.lock').open('a+');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 with threadpool_limits(limits=1 if smoke else 2):
  est,guide,evaluation,_=load_source(source,cfg);train=rank_subset(pd.concat([est,guide],ignore_index=True),len(est)+len(guide),'sav-val-cf-training-order-v2');train=rank_subset(train,len(train),'sefa-internal-validation-v6');cut=int(.8*len(train));fit=train.iloc[:cut].copy();validation=train.iloc[cut:].copy();records=[]
  method=cfg['recent_method']
  for index,setting in enumerate(training.configs(method,smoke)):
   _,receipt=training.fit(fit,validation,method,setting,seed,out/f'trial-{index}',source,smoke)
   records.append(dict(index=index,validation_nll=receipt['validation_nll'],settings=setting))
  selected=min(records,key=lambda r:(r['validation_nll'],r['index']))
  write(out/'selection.json',dict(status='selected_training_only',trials=records,selected=selected,held_out_evaluation_labels_used=False))
  (model,encoder,cuts),receipt=training.fit(train,train,method,selected['settings'],seed,out/'refit',source,smoke,refit=True);summaries=[]
  for backend in ['masking_suppression','robust_no_feedback']:
   old=common.PARENT/source/f'seed-{seed}';p=old/'deployment_models'/f'{backend}.joblib';price,_,_=joblib.load(p);pred,x,valid=price.predict(price_features(evaluation,FEATURES[source]));table=out/'scores.npz'
   if table.exists():scores=np.load(table)['scores']
   else:
    scores=training.acquisition(model,encoder,evaluation,price.space,seed,method);np.savez_compressed(table,scores=scores);write(out/'scores.json',dict(model_sha256=receipt['sha256'],evaluation_features_sha256=common.content(price_features(evaluation,FEATURES[source])),score_sha256=sha(table),label_inputs=False,algorithm=method+'_public_context_adaptation'))
   sc=json.loads((out/'scores.json').read_text());assert sc['model_sha256']==receipt['sha256'] and sc['score_sha256']==sha(table) and sc['evaluation_features_sha256']==common.content(price_features(evaluation,FEATURES[source]))
   # Perturb a concealed mileage value: state1 public score must stay unchanged.
   if backend=='masking_suppression':
    tiny=evaluation.iloc[:4].copy();changed=tiny.copy();changed['mileage_km']=123456789.;a=training.acquisition(model,encoder,tiny,price.space,seed,method);b=training.acquisition(model,encoder,changed,price.space,seed,method);state=common.LOOKUP[1];assert np.allclose(a[:,state],b[:,state],equal_nan=True)
    write(out/'public-input-check.json',dict(status='passed',hidden_value_perturbation='mileage at concealed state',zero_label_inputs=True,finite_scores=int(np.isfinite(scores).sum())))
   head=FrozenPublicScores(scores,pred)
   for budget in cfg['budgets']:
    d=out/backend/f'budget-{round(budget*10000):04d}';d.mkdir(parents=True,exist_ok=True);cp=d/'completion.json';inputs=dict(price_model=sha(p),score_table=sha(table),evaluation=common.content(evaluation),budget=budget)
    if cp.exists():
     r=json.loads(cp.read_text());assert r['inputs']==inputs and sha(d/'outcomes.csv.gz')==r['outcomes_sha256'];summaries.append(r['summary']);continue
    rows,su=evaluate_method(method+'4bin_'+backend,price,head,'sefa',evaluation,FEATURES[source],cfg,seed,budget);audit=common.matrix_audit(pred,scores,valid,evaluation,rows,budget);su.update(dataset=source,price_backend=backend,acquisition=method+'_four_bin_public_context_one_query_adaptation');rows.to_csv(d/'outcomes.csv.gz',index=False);write(cp,dict(status='completed_and_corroborated',inputs=inputs,summary=su,audit=audit,outcomes_sha256=sha(d/'outcomes.csv.gz')));summaries.append(su);write(out/'progress.json',dict(completed_cells=len(summaries),expected_cells=2*len(cfg['budgets'])));print('RECENT_CELL',source,seed,backend,budget,flush=True)
  pd.DataFrame(summaries).to_csv(out/'summary.csv',index=False);write(out/'completion.json',dict(status='completed_and_corroborated',cells=len(summaries),summary_sha256=sha(out/'summary.csv')));return summaries

def main(method):
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=2);p.add_argument('--smoke',action='store_true');p.add_argument('--ready-only',action='store_true');a=p.parse_args();common.guard();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);lock=(out/'execution.lock').open('a+');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);cfg=copy.deepcopy(json.loads((common.PARENT/'run_manifest.json').read_text())['config']);cfg['recent_method']=method
 used=json.loads((ROOT/'notes/recent-five-v1/SOURCES.json').read_text())
 for row in used['files']:assert sha(ROOT/row['path'])==row['sha256']
 if a.smoke:cfg.update(datasets=['synthetic'],seeds=[13],max_train=300,max_evaluation=100,budgets=[.1])
 tasks=[(d,s,cfg,str(out),a.smoke) for d in cfg['datasets'] for s in cfg['seeds']];manifest=dict(config=cfg,source_sha256=sha(ROOT/f'experiments/run_recent_{method}_v1.py'),adapter_sha256=sha(Path(__file__)),training_sha256=sha(Path(training.__file__)),official_sources=used,workers=a.workers,smoke_only=a.smoke,pairs=len(tasks),expected_cells=len(tasks)*2*len(cfg['budgets']),selection_trials=[0,1,2],scope=method+' task adaptation; training-only selection and full-training refit; public context, two-step training, one-query shared allocation')
 mp=out/'manifest.json'
 if mp.exists():assert json.loads(mp.read_text())==manifest
 else:write(mp,manifest)
 if a.ready_only:return
 rows=[]
 with ProcessPoolExecutor(max_workers=a.workers) as pool:
  fs={pool.submit(pair,t):t[:2] for t in tasks}
  for f in as_completed(fs):
   try:rows.extend(f.result())
   except Exception:write(out/'failure.json',dict(pair=fs[f],traceback=traceback.format_exc()));raise
   pd.DataFrame(rows).to_csv(out/'summary.csv',index=False);write(out/'progress.json',dict(completed_cells=len(rows),expected_cells=manifest['expected_cells']))
 assert len(rows)==manifest['expected_cells'];write(out/'completion.json',dict(status='completed_and_corroborated',cells=len(rows),summary_sha256=sha(out/'summary.csv'),manifest_sha256=sha(mp),smoke_only=a.smoke));common.guard()
