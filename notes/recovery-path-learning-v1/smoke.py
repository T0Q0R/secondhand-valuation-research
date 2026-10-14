from pathlib import Path
import sys,copy,json
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'experiments'))
import torch,numpy as np,joblib
from threadpoolctl import threadpool_limits
import run_completion_ablation_v6 as c
from run_all import load_source,evaluate_method
from savval import FEATURES,price_features
from recovery_path_training_v1 import train_residual
from run_recovery_path_learning_v1 import variants

def main():
 torch.set_num_threads(1);cfg=json.loads((c.PARENT/'run_manifest.json').read_text())['config'];cfg=dict(cfg,residual_epochs=4,head_trees=12);est,guide,evaluation,_=load_source('synthetic',cfg);est=est.iloc[:201];guide=guide.iloc[:81];evaluation=evaluation.iloc[:101];columns=FEATURES['synthetic'];base,_,_=joblib.load(c.PARENT/'synthetic/seed-13/deployment_fit/models/masking_suppression.joblib');results={}
 for name,v in variants().items():
  model=copy.deepcopy(base);reference=copy.deepcopy(base);cc=dict(cfg,recovery_path_weight=v['path_weight']);logs=[]
  for i in range(2):
   logs.extend(train_residual(model,price_features(est,columns),est.target_log.to_numpy(),cc,13+i,None,gap_weight=v['beta'],epochs=2))
   if v['path_weight']==0:reference.train_residual(price_features(est,columns),est.target_log.to_numpy(),cfg,13+i,None,gap_weight=v['beta'],epochs=2)
  pred,x,valid=model.predict(price_features(evaluation,columns));identity=None
  if v['path_weight']==0:identity=float(abs(pred-reference.predict(price_features(evaluation,columns))[0]).max());assert identity<1e-7
  h=c.head(model,guide,columns,cfg,13);h.model.n_jobs=1;scores=h.score(x,pred,model.space,'suppression',reported_missing=model.space.reported_missing(evaluation));rows,s=evaluate_method(name,model,h,'suppression',evaluation,columns,cfg,13,.1);audit=c.matrix_audit(pred,scores,valid,evaluation,rows,.1)
  assert all(np.isfinite(z['loss']) and z['mean_training_path_penalty']>=0 for z in logs)
  results[name]=dict(identity_max_error=identity,epoch_count=len(logs),finite_loss=True,utility_check=audit['status'])
 # The primitive penalizes gain amplification,not every price increase.
 def penalty(qh,qbefore,qafter):return max(max(qafter-qh,0)-max(qbefore-qh,0),0)
 assert penalty(10,12,14)==2 and penalty(10,8,9)==0 and penalty(10,12,10)==0
 c.guard();c.write(ROOT/'notes/recovery-path-learning-v1/smoke.json',dict(status='passed',branches=results,fixture_checks=3,smoke_only=True,scope='201estimator/81guidance/101evaluation engineering checks;not performance evidence'))
 print('PASS six branches,zero-weight identities,finite losses,independent utility audit,and gain fixtures')
if __name__=='__main__':
 with threadpool_limits(limits=1):main()
