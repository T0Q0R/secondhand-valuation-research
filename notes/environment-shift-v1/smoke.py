from pathlib import Path
import sys,json,copy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'experiments'))
import torch,joblib,numpy as np
from threadpoolctl import threadpool_limits
import run_completion_ablation_v6 as c
from run_environment_shift_v1 import shifted
from savval import ACTIONS,FEATURES,price_features
from run_all import load_source,evaluate_method

def main():
 torch.set_num_threads(1);cfg=json.loads((c.PARENT/'run_manifest.json').read_text())['config'];checks=[]
 for source in cfg['datasets']:
  _,_,allrows,_=load_source(source,cfg);frame=allrows.iloc[:100].copy();model,head,_=joblib.load(c.PARENT/source/'seed-13/deployment_models/sav_val.joblib');head.model.n_jobs=1
  previous=frame.loc[:,ACTIONS].isna().to_numpy()
  for rate in [0.,.1,.3]:
   f=shifted(frame,rate);assert shifted(frame,rate).equals(f);assert f.target_log.equals(frame.target_log) and f.listing_id.equals(frame.listing_id)
   missing=f.loc[:,ACTIONS].isna().to_numpy();assert (missing|previous==missing).all();previous=missing
   if rate==0:assert f.equals(frame)
   pred,x,valid=model.predict(price_features(f,FEATURES[source]));scores=head.score(x,pred,model.space,'suppression',reported_missing=model.space.reported_missing(f));rows,s=evaluate_method('smoke',model,head,'suppression',f,FEATURES[source],cfg,13,.1);audit=c.matrix_audit(pred,scores,valid,f,rows,.1)
   checks.append(dict(source=source,rate=rate,rows=len(rows),legal_deviations=audit['legal_deviations']))
 c.guard();c.write(ROOT/'notes/environment-shift-v1/smoke.json',dict(status='passed',smoke_only=True,checks=checks,hash_mask_determinism=True,nested_masks=True,zero_rate_identity=True,targets_ids_unchanged=True,scope='9engineering cells on100records/source;not scientific outcomes'))
 print('PASS:9 shifted evaluation smoke cells,determinism,nesting,identity and independent utility checks')
if __name__=='__main__':
 with threadpool_limits(limits=1):main()
