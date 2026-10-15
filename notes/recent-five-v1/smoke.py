from pathlib import Path
import sys,json,os
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'experiments'))
import recent_acquisition_training_v1 as t
import torch,numpy as np
from threadpoolctl import threadpool_limits
torch.set_num_threads(1)
cfg=json.loads((t.shared.common.PARENT/'run_manifest.json').read_text())['config'];cfg.update(max_train=300,max_evaluation=100)
est,guide,ev,_=t.shared.load_source('synthetic',cfg);train=est.iloc[:100];val=guide.iloc[:40];out=ROOT/'outputs/recent-five-engineering-smoke-v1';out.mkdir(exist_ok=True);results=[]
with threadpool_limits(limits=1):
 for method in ['gdfs','dime','efa']:
  model,receipt=t.fit(train,val,method,t.configs(method,True)[0],13,out/method,'synthetic',True)
  model,enc,cuts=model
  old=t.shared.common.PARENT/'synthetic/seed-13/deployment_models/masking_suppression.joblib';price,_,_=t.shared.joblib.load(old)
  tiny=ev.iloc[:20].copy();pred,x,valid=price.predict(t.shared.price_features(tiny,t.shared.FEATURES['synthetic']))
  scores=t.acquisition(model,enc,tiny,price.space,13,method)
  changed=tiny.copy();changed['mileage_km']=123456789.
  other=t.acquisition(model,enc,changed,price.space,13,method)
  assert np.allclose(scores[:,t.shared.common.LOOKUP[1]],other[:,t.shared.common.LOOKUP[1]],equal_nan=True)
  assert np.isfinite(scores[price.space.reported_missing(tiny)]).all()
  # Replay uses an actual100-record batch to satisfy independent integer audit contract.
  pred,x,valid=price.predict(t.shared.price_features(ev,t.shared.FEATURES['synthetic']));scores=t.acquisition(model,enc,ev,price.space,13,method)
  rows,su=t.shared.evaluate_method(method,price,t.shared.FrozenPublicScores(scores,pred),method,ev,t.shared.FEATURES['synthetic'],cfg,13,.1)
  audit=t.shared.common.matrix_audit(pred,scores,valid,ev,rows,.1)
  results.append(dict(method=method,epochs=receipt['epochs'],public_input_check=True,audit=audit,finite_loss=True))
  print('SMOKE_PASS',method,flush=True)
t.shared.write(ROOT/'notes/recent-five-v1/smoke.json',dict(status='passed',engineering_only=True,methods=results,scientific_results=False))
