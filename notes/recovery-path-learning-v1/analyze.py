from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'experiments'))
import numpy as np,pandas as pd
import run_completion_ablation_v6 as c
from run_all import load_source
from savval import ACTIONS
METRICS=['mean_positive_log_inflation','clean_mae','attack_mae','failed_query_fraction']
def rows_for(cp):
 j=json.loads(cp.read_text())
 if 'outcomes_sha256' in j:
  p=cp.parent/'outcomes.csv.gz';assert c.sha(p)==j['outcomes_sha256'];return pd.read_csv(p)
 u=j['reused'];assert u['type']=='ablation';p=ROOT/u['root']/'evaluation'/u['method']/f"budget-{round(j['inputs']['budget']*10000):04d}";rr=json.loads((p/'completion.json').read_text());assert c.sha(p/'outcomes.csv.gz')==rr['outcomes_sha256'];return pd.read_csv(p/'outcomes.csv.gz')
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=True);root=ROOT/'outputs/recovery-path-learning-v1';r=json.loads((root/'completion.json').read_text());assert r['cells']==162 and r['summary_sha256']==c.sha(root/'summary.csv');df=pd.read_csv(root/'summary.csv');assert len(df)==162
 paired=[];gates=[]
 for key,g in df.groupby(['dataset','seed','budget','beta']):
  ref=g[g.path_weight==0].iloc[0]
  for _,v in g[g.path_weight>0].iterrows():
   for metric in METRICS:paired.append(dict(dataset=key[0],seed=key[1],budget=key[2],beta=key[3],path_weight=v.path_weight,metric=metric,reference=ref[metric],candidate=v[metric],reduction=ref[metric]-v[metric]))
   for tol in [0.,.01,.02,.05,.1]:gates.append(dict(dataset=key[0],seed=key[1],budget=key[2],beta=key[3],path_weight=v.path_weight,honest_error_tolerance=tol,honest_pass=bool(v.clean_mae<=ref.clean_mae*(1+tol)),attacked_mae_not_worse=bool(v.attack_mae<=ref.attack_mae),inflation_not_worse=bool(v.mean_positive_log_inflation<=ref.mean_positive_log_inflation),failed_queries_not_worse=bool(v.failed_query_fraction<=ref.failed_query_fraction)))
 sub=[];edges=[];cfg=json.loads((root/'manifest.json').read_text())['config']
 for source in cfg['datasets']:
  est,guide,evaluation,_=load_source(source,cfg);low,high=np.quantile(pd.concat([est,guide]).target_log,[.1,.9]);labels=np.where(evaluation.target_log<=low,'price_low10',np.where(evaluation.target_log>=high,'price_high10','price_middle80'));missing=evaluation.loc[:,ACTIONS].isna().any(axis=1).to_numpy()
  for cp in (root/source).glob('seed-*/*/evaluation-*/completion.json'):
   j=json.loads(cp.read_text());s=j['summary'];rr=rows_for(cp);assert rr.listing_id.tolist()==evaluation.listing_id.tolist();edges.append(dict(dataset=source,seed=s['seed'],method=s['method'],budget=s['budget'],**j['gain_paths']))
   group_masks={k:labels==k for k in ['price_low10','price_middle80','price_high10']};group_masks.update(natural_complete=~missing,natural_missing=missing)
   for name,mask in group_masks.items():
    z=rr.loc[mask];sub.append(dict(dataset=source,seed=s['seed'],method=s['method'],budget=s['budget'],group=name,n=len(z),training_log_price_q10=low,training_log_price_q90=high,clean_mae=z.clean_absolute_error.mean(),attack_mae=z.attack_absolute_error.mean(),inflation=z.positive_log_inflation.mean(),failed_query_fraction=((z.action>=0)&~z.query_succeeded).mean()))
 assert len(edges)==162
 pd.DataFrame(paired).to_csv(out/'paired_component_effects.csv',index=False);pd.DataFrame(gates).to_csv(out/'honest_tolerance_sensitivity.csv',index=False);pd.DataFrame(sub).to_csv(out/'price_tail_and_natural_missing_groups.csv',index=False);pd.DataFrame(edges).to_csv(out/'gain_amplification_paths.csv',index=False)
 (out/'INTERNAL_REPORT.md').write_text('RPL candidate pilot complete;not evidence of novelty or superiority until reviewed.3fitting seeds,original fixed populations,all weights retained. Finite training-graph zero-penalty implication does not generalize automatically. Compare honest/attacked errors,inflation,failed queries,zero-budget estimator effects and all nonconverged outcomes. Training-only price quantiles define subgroups. No paper generated.\n')
 c.write(out/'completion.json',dict(status='computed_checked_scientific_review_pending',cells=162,new_price_fits=144,new_evaluations=108,reused=54,artifacts={p.name:c.sha(p) for p in out.iterdir() if p.is_file() and p.name!='completion.json'}))
 c.guard()
if __name__=='__main__':main()
