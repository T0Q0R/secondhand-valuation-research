from pathlib import Path
import sys,copy,json,time,tempfile
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'experiments'))
import numpy as np,pandas as pd,torch,joblib
from threadpoolctl import threadpool_limits
import run_completion_ablation_v6 as c
import run_completion_mechanisms_v1 as runner
from mechanism_training_v1 import train_residual
from mechanism_diagnostics_v1 import recovery_diagnostics
from savval import FEATURES,price_features,audit_deviations,strategic_response
from run_all import load_source,evaluate_method

def main():
 torch.set_num_threads(1);c.guard();cfg=json.loads((c.PARENT/'run_manifest.json').read_text())['config'];cfg=copy.deepcopy(cfg);cfg.update(residual_epochs=4,head_trees=12)
 est,guide,evaluation,_=load_source('synthetic',cfg);est=est.iloc[:201];guide=guide.iloc[:81];evaluation=evaluation.iloc[:101];columns=FEATURES['synthetic']
 base,initial,_=joblib.load(c.PARENT/'synthetic/seed-13/deployment_fit/models/masking_suppression.joblib');initial.model.n_jobs=1
 results={};times={}
 for name,v in runner.variants().items():
  model=copy.deepcopy(base);policy=copy.deepcopy(initial);scfg=dict(cfg,mechanism_score_refresh=v['refresh'],mechanism_restarts=v['restarts'],training_attacker_sweeps=v['sweeps']);started=time.time();logs=[]
  reference=copy.deepcopy(base);refhead=copy.deepcopy(initial)
  for i in range(2):
   logs.extend(train_residual(model,price_features(est,columns),est.target_log.to_numpy(),scfg,13+i,policy if v['feedback'] else None,epochs=2))
   policy=c.head(model,guide,columns,cfg,13);policy.model.n_jobs=1
   if name in ['epoch-weak','feedback-off']:
    reference.train_residual(price_features(est,columns),est.target_log.to_numpy(),cfg,13+i,refhead if v['feedback'] else None,epochs=2)
    refhead=c.head(reference,guide,columns,cfg,13);refhead.model.n_jobs=1
  pred,x,valid=model.predict(price_features(evaluation,columns));scores=policy.score(x,pred,model.space,'suppression',reported_missing=model.space.reported_missing(evaluation))
  identity=None
  if name in ['epoch-weak','feedback-off']:
   rp,rx,rv=reference.predict(price_features(evaluation,columns));rs=refhead.score(rx,rp,reference.space,'suppression',reported_missing=reference.space.reported_missing(evaluation));finite=np.isfinite(scores)
   identity=dict(prediction=float(abs(pred-rp).max()),score=float(abs(scores[finite]-rs[finite]).max()));assert identity['prediction']<1e-7 and identity['score']<1e-7
  rows,summary=evaluate_method(name,model,policy,'suppression',evaluation,columns,cfg,13,.1)
  audit=c.matrix_audit(pred,scores,valid,evaluation,rows,.1)
  diag=recovery_diagnostics(pred,valid,model.space,evaluation,rows)
  # Independent loop checks transition enumeration,including natural missingness.
  values=[]
  for i in range(len(pred)):
   for s in range(11):
    if not valid[i,s]:continue
    code=c.CODES[s]
    for a in range(4):
     if code&(1<<a):values.append(pred[i,c.LOOKUP[code&~(1<<a)]]-pred[i,s])
  assert len(values)==diag['legal_hidden_recovery_edges'] and sum(d>1e-8 for d in values)==diag['recovery_raises_quote_edges']
  # Separate actual-allocator audit checks training-search output for both strengths.
  response=strategic_response(pred[:100],scores[:100],valid[:100],model.space,budget=.1,sweeps=v['sweeps'],restarts=v['restarts'])
  rr=audit_deviations(pred[:100],scores[:100],valid[:100],response['states'],model.space,10,0.)
  assert np.allclose(rr['regret'],response['regret'],atol=1e-9)
  assert len(logs)==4 and all(np.isfinite(z['loss']) for z in logs)
  times[name]=time.time()-started;results[name]=dict(identity=identity,audit=audit,diagnostics=diag,epochs=len(logs),training_batches=sum(z['response_batches'] for z in logs))
 # Resume and tamper binding for fit_one,use tiny split bound to copied existing backbone.
 with tempfile.TemporaryDirectory() as td:
  old=Path(td)/'old';(old/'models').mkdir(parents=True);bp=old/'models/masking_suppression.joblib';c.dump(bp,(base,initial,'suppression'))
  c.write(old/'fit_completion.json',dict(inputs=dict(seed=13,estimator_content=c.content(est),guidance_content=c.content(guide)),files={'models/masking_suppression.joblib':c.sha(bp)}))
  v=runner.variants()['batch-strong'];scfg=dict(cfg,mechanism_score_refresh='batch',mechanism_restarts=4,training_attacker_sweeps=20)
  fit=runner.fit_one(est,guide,columns,scfg,13,Path(td)/'fit',old,v);before=c.sha(fit)
  assert runner.fit_one(est,guide,columns,scfg,13,Path(td)/'fit',old,v)==fit and c.sha(fit)==before
  rejected=False
  try:runner.fit_one(est,guide,columns,dict(scfg,learning_rate=.002),13,Path(td)/'fit',old,v)
  except AssertionError:rejected=True
  assert rejected
 c.write(ROOT/'notes/applied-intelligence-mechanisms-v1/smoke.json',dict(status='passed',smoke_only=True,scope='Engineering checks on201estimator/81guidance/101evaluation rows with existing backbone;not scientific outcomes',branches=results,seconds=times,resume_sha_unchanged=True,changed_config_rejected=True,paper_sha=c.sha(ROOT/'paper/innovation-addendum-v1.tex')))
 print(json.dumps(dict(status='passed',seconds=times)))
if __name__=='__main__':
 with threadpool_limits(limits=1):main()
