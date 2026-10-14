from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'experiments'))
import torch,joblib,numpy as np,pandas as pd
from threadpoolctl import threadpool_limits
import run_completion_ablation_v6 as c
from run_environment_shift_v1 import shifted,model_path
from savval import FEATURES,price_features
from run_all import load_source,evaluate_method

def main():
 torch.set_num_threads(1);cfg=json.loads((c.PARENT/'run_manifest.json').read_text())['config'];checks=[]
 for source in cfg['datasets']:
  _,_,evaluation,_=load_source(source,cfg);frame=evaluation.iloc[:100].copy();original=pd.read_csv(c.PARENT/source/'seed-13/per_listing_outcomes.csv.gz')
  for method in ['masking_risk','masking_benefit']:
   model,head,kind=joblib.load(model_path(source,13,method));head.model.n_jobs=1;kind=method.removeprefix("masking_")
   for rate in [0.,.3]:
    f=shifted(frame,rate);pred,x,valid=model.predict(price_features(f,FEATURES[source]));scores=head.score(x,pred,model.space,kind,reported_missing=model.space.reported_missing(f));rows,s=evaluate_method(method,model,head,kind,f,FEATURES[source],cfg,13,.1);c.matrix_audit(pred,scores,valid,f,rows,.1)
    if rate==0:
     ref=original[(original.method==method)&np.isclose(original.budget,.1)].iloc[:100];assert ref.listing_id.tolist()==rows.listing_id.tolist();assert np.allclose(ref.attacked_prediction_log,rows.attacked_prediction_log)
    checks.append(dict(source=source,method=method,rate=rate,kind=kind))
 c.write(ROOT/'notes/environment-shift-v1/baseline-smoke.json',dict(status='passed',checks=checks,smoke_only=True,scope='12engineering100-row cells;zero-shift response matches original saved first batch'))
 print('PASS risk/benefit12cells and exact zero-shift original response')
if __name__=='__main__':
 with threadpool_limits(limits=1):main()
