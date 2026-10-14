from pathlib import Path
import argparse,json,hashlib
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=True);root=ROOT/'outputs/environment-shift-v1';r=json.loads((root/'completion.json').read_text());assert r['cells']==189 and r['summary_sha256']==sha(root/'summary.csv');df=pd.read_csv(root/'summary.csv');assert len(df)==189
 metrics=['mean_positive_log_inflation','clean_mae','attack_mae','failed_query_fraction','hiding_fraction','actual_audit_fraction','max_remaining_response_regret'];rows=[];paths=[]
 for key,g in df.groupby(['dataset','seed']):
  for method,h in g.groupby('model_variant'):
   ref=h[h.additional_missing_probability==0].iloc[0]
   for _,v in h[h.additional_missing_probability>0].iterrows():
    for m in metrics:rows.append(dict(dataset=key[0],seed=key[1],model_variant=method,rate=v.additional_missing_probability,contrast='shift-minus-original',metric=m,difference=v[m]-ref[m]))
  for rate,h in g.groupby('additional_missing_probability'):
   ref=h[h.model_variant=='feedback-off'].iloc[0]
   for _,v in h[~h.model_variant.isin(['feedback-off','masking_risk','masking_benefit'])].iterrows():
    for m in metrics:rows.append(dict(dataset=key[0],seed=key[1],model_variant=v.model_variant,rate=rate,contrast='feedback-minus-off',metric=m,difference=v[m]-ref[m]))
 for cp in root.glob('*/seed-*/*/completion.json'):
  j=json.loads(cp.read_text());assert j['status']=='completed_and_corroborated'
  if 'outcomes_sha256' in j:assert sha(cp.parent/'outcomes.csv.gz')==j['outcomes_sha256']
  s=j['summary'];paths.append(dict(dataset=s['dataset'],seed=s['seed'],method=s['model_variant'],rate=s['additional_missing_probability'],**j['recovery_paths']))
 assert len(paths)==189
 contrast=pd.DataFrame(rows);contrast.to_csv(out/'paired_shift_and_feedback_effects.csv',index=False);contrast.groupby(['dataset','model_variant','rate','contrast','metric']).difference.agg(['mean','min','max','count']).to_csv(out/'descriptive_three_seed_ranges.csv');pd.DataFrame(paths).to_csv(out/'recovery_paths.csv',index=False)
 (out/'INTERNAL_REPORT.md').write_text('Environment-shift calculations completed;scientific interpretation and figureQA pending. Additional10%/30% natural absence among currently observed fields,not total missing rate. Same masks and targets across models/seeds,nested rates;three seeds are fitting replicates on fixed populations. No nominal uncertainty/generalization claim. Compare all4primary metrics with query rate/regret;keep nonconverged. No paper generated.\n')
 (out/'completion.json').write_text(json.dumps(dict(status='computed_and_checked_interpretation_visual_QA_pending',cells=189,reused=63,new_evaluations=126,new_fits=0,artifacts={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='completion.json'}),indent=2)+'\n')
if __name__=='__main__':main()
