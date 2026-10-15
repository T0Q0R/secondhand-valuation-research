from pathlib import Path
import argparse,json,hashlib
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);parts=[];bindings={}
 for method in ['gdfs','dime','efa']:
  d=ROOT/f'outputs/recent-{method}-v1';r=json.loads((d/'completion.json').read_text());assert r['cells']==108 and r['summary_sha256']==sha(d/'summary.csv');t=pd.read_csv(d/'summary.csv');t['recent_family']=method;parts.append(t);bindings[str(d.relative_to(ROOT))]=sha(d/'summary.csv')
 new=pd.concat(parts,ignore_index=True);assert len(new)==324;new.to_csv(a.output/'new_baselines.csv',index=False)
 sefa=ROOT/'outputs/completion-sefa-v6-official';r=json.loads((sefa/'completion.json').read_text());assert r['cells']==108 and r['summary_sha256']==sha(sefa/'summary.csv');t=pd.read_csv(sefa/'summary.csv');t['recent_family']='sefa';parts.append(t)
 aco=ROOT/'outputs/aco1-development-v2';r=json.loads((aco/'completion.json').read_text());assert r['cells']==144 and r['summary_sha256']==sha(aco/'summary.csv');t=pd.read_csv(aco/'summary.csv');t['recent_family']='aco';t['price_backend']=t.price_key;parts.append(t)
 combined=pd.concat(parts,ignore_index=True);combined.to_csv(a.output/'five_families_inventory.csv',index=False)
 # Retain parameter variants separately: no cherry-picking ACO based on evaluation results.
 metrics=['clean_mae','attack_mae','mean_positive_log_inflation','failed_query_fraction','max_remaining_response_regret','nonconverged_batch_fraction'];combined.groupby(['recent_family','method','dataset','price_backend','budget'])[metrics].agg(['mean','min','max']).to_csv(a.output/'seed_summary.csv')
 original=pd.read_csv(ROOT/'outputs/nested-development-v2/all_summary.csv');paired=[]
 for row in combined.to_dict('records'):
  base_method='masking_risk' if row['price_backend']=='masking_suppression' else 'robust_no_feedback'
  match=original[(original.dataset==row['dataset'])&(original.seed==row['seed'])&(original.method==base_method)&((original.budget-row['budget']).abs()<1e-9)]
  if len(match)!=1:continue
  base=match.iloc[0];record={k:row[k] for k in ['recent_family','method','dataset','seed','price_backend','budget']};record['reference']=base_method
  for m in metrics:record[m+'_new_minus_reference']=row[m]-base[m]
  paired.append(record)
 pd.DataFrame(paired).to_csv(a.output/'paired_reference_differences.csv',index=False)
 (a.output/'completion.json').write_text(json.dumps(dict(status='aggregated_scientific_visual_review_pending',new_cells=324,families=5,all_inventory_rows=len(combined),bindings=bindings,seed_range_is_not_confidence_interval=True,all_nonconverged_retained=True,manuscript_generated=False),indent=2)+'\n')
if __name__=='__main__':main()
