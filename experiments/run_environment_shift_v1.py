"""Frozen-model natural-availability stress test; simulated shift,not new markets."""
from pathlib import Path
import argparse,copy,fcntl,gc,hashlib,json,time
import numpy as np,pandas as pd,torch,joblib
from threadpoolctl import threadpool_limits
import run_completion_ablation_v6 as c
from savval import ACTIONS,FEATURES,price_features
from run_all import load_source,evaluate_method
from mechanism_diagnostics_v1 import recovery_diagnostics
ROOT=c.ROOT
METHODS=['epoch-weak','epoch-strong','batch-weak','batch-strong','feedback-off','masking_risk','masking_benefit'];RATES=[0.,.1,.3]
def shifted(frame,rate):
 f=frame.copy()
 for field in ACTIONS:
  u=np.array([int(hashlib.sha256(f'availability-stress-v1|{i}|{field}'.encode()).hexdigest()[:16],16)/2**64 for i in f.listing_id])
  f.loc[f[field].notna()&(u<rate),field]=np.nan
 return f

def resolve_rows(cp):
 r=json.loads(cp.read_text())
 if 'outcomes_sha256' in r:
  p=cp.parent/'outcomes.csv.gz';assert c.sha(p)==r['outcomes_sha256'];return pd.read_csv(p)
 u=r['reused']
 if u['type']=='ablation':
  p=ROOT/u['root']/'evaluation'/u['method']/'budget-1000';q=json.loads((p/'completion.json').read_text());assert c.sha(p/'outcomes.csv.gz')==q['outcomes_sha256'];return pd.read_csv(p/'outcomes.csv.gz')
 assert u['type']=='original';p=ROOT/u['outcomes'];assert c.sha(p)==u['sha256'];rr=pd.read_csv(p);return rr[(rr.method==u['method'])&np.isclose(rr.budget,.1)].copy()

def model_path(source,seed,method):
 if method in ['masking_risk','masking_benefit']:return c.PARENT/source/f'seed-{seed}'/'deployment_models/masking_suppression.joblib'
 if method=='epoch-weak':return c.PARENT/source/f'seed-{seed}'/'deployment_models/sav_val.joblib'
 if method=='feedback-off':return ROOT/'outputs/completion-ablation-v6'/source/f'seed-{seed}'/'deployment_models/off_gap.joblib'
 return ROOT/'outputs/completion-mechanisms-v1'/source/f'seed-{seed}'/method/'deployment_model.joblib'

def pair(task):
 source,seed,cfg,outstr,smoke=task;assert not smoke;torch.set_num_threads(2);c.guard();out=Path(outstr)/source/f'seed-{seed}';out.mkdir(parents=True,exist_ok=True);lock=(out/'execution.lock').open('a+');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 manifest=json.loads((Path(outstr)/'manifest.json').read_text());assert all(c.sha(ROOT/p)==h for p,h in manifest['dependency_sha256'].items())
 with threadpool_limits(limits=2):
  _,_,original,_=load_source(source,cfg);summaries=[]
  for method in METHODS:
   mp=model_path(source,seed,method)
   extra=method in ['masking_risk','masking_benefit']
   if extra:
    old=c.PARENT/source/f'seed-{seed}';baseline_cp=old/'evaluation_completion.json';receipt=json.loads(baseline_cp.read_text());assert c.sha(old/'summary.csv')==receipt['summary_sha256'];assert c.sha(old/'per_listing_outcomes.csv.gz')==receipt['outcomes_sha256']
    table=pd.read_csv(old/'summary.csv');base=dict(summary=table[(table.method==method)&np.isclose(table.budget,.1)].iloc[0].to_dict())
   else:
    baseline_cp=ROOT/'outputs/completion-mechanisms-v1'/source/f'seed-{seed}'/method/'evaluation-1000/completion.json';base=json.loads(baseline_cp.read_text());assert base['status']=='completed_and_corroborated' and base['inputs']['model']==c.sha(mp)
   model,head,kind=joblib.load(mp);head.model.n_jobs=2
   if extra:kind=method.removeprefix("masking_")
   for rate in RATES:
    name=f'{method}-missing-{rate:g}';cell=out/name;cell.mkdir(exist_ok=True);cp=cell/'completion.json';frame=shifted(original,rate);inputs=dict(model=c.sha(mp),baseline_receipt=c.sha(baseline_cp),rate=rate,original_evaluation=c.content(original),shifted_evaluation=c.content(frame),config=cfg)
    if cp.exists():
     rr=json.loads(cp.read_text());assert rr['inputs']==inputs and (not rate or c.sha(cell/'outcomes.csv.gz')==rr['outcomes_sha256']);summaries.append(rr['summary']);continue
    pred,x,valid=model.predict(price_features(frame,FEATURES[source]));scores=head.score(x,pred,model.space,kind,reported_missing=model.space.reported_missing(frame))
    if rate==0:
     if extra:
      table=pd.read_csv(old/'per_listing_outcomes.csv.gz');rows=table[(table.method==method)&np.isclose(table.budget,.1)].copy()
     else:rows=resolve_rows(baseline_cp)
     summary=copy.deepcopy(base['summary'])
    else:rows,summary=evaluate_method(name,model,head,kind,frame,FEATURES[source],cfg,seed,.1)
    assert rows.listing_id.tolist()==frame.listing_id.tolist();audit=c.matrix_audit(pred,scores,valid,frame,rows,.1)
    summary.update(method=name,dataset=source,model_variant=method,additional_missing_probability=rate,natural_missing_field_fraction=float(frame.loc[:,ACTIONS].isna().to_numpy().mean()),newly_missing_field_fraction=float((frame.loc[:,ACTIONS].isna()&original.loc[:,ACTIONS].notna()).to_numpy().mean()))
    receipt=dict(status='completed_and_corroborated',inputs=inputs,summary=summary,audit=audit,recovery_paths=recovery_diagnostics(pred,valid,model.space,frame,rows))
    if rate:rows.to_csv(cell/'outcomes.csv.gz',index=False);receipt['outcomes_sha256']=c.sha(cell/'outcomes.csv.gz')
    else:receipt['reused_reference_receipt']=str(baseline_cp.relative_to(ROOT))
    c.write(cp,receipt);summaries.append(summary);c.write(out/'progress.json',dict(completed_cells=len(summaries),expected_cells=21));print('SHIFT',source,seed,name,flush=True);del pred,x,valid,scores;gc.collect()
   del model,head;gc.collect()
  pd.DataFrame(summaries).to_csv(out/'summary.csv',index=False);c.write(out/'completion.json',dict(status='completed_and_corroborated',cells=len(summaries),summary_sha256=c.sha(out/'summary.csv')));c.guard();return summaries

def main():
 p=argparse.ArgumentParser();p.add_argument('--ready-only',action='store_true',required=True);a=p.parse_args();c.guard();out=ROOT/'outputs/environment-shift-v1';out.mkdir(exist_ok=True);cfg=copy.deepcopy(json.loads((c.PARENT/'run_manifest.json').read_text())['config']);cfg['budgets']=[.1]
 paths=['experiments/savval.py','experiments/run_all.py','experiments/run_completion_ablation_v6.py','experiments/mechanism_diagnostics_v1.py']
 manifest=dict(config=cfg,expected_cells=189,expected_pairs=9,smoke_only=False,source_sha256=c.sha(Path(__file__)),dependency_sha256={p:c.sha(ROOT/p) for p in paths},rates=RATES,methods=METHODS,new_training_fits=0,new_evaluation_cells=126,reused_cells=63,scope='Retrospective paired natural-availability stress; MCAR additions among currently observed actionable fields; same hashed masks across seeds/methods,nested rates;not real-market generalization')
 cp=out/'manifest.json'
 if cp.exists():assert json.loads(cp.read_text())==manifest
 else:c.write(cp,manifest)
if __name__=='__main__':main()
