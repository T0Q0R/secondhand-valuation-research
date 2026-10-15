from pathlib import Path
import json,hashlib,datetime
from zoneinfo import ZoneInfo
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
STAGES={'completion-ablation-v6':432,'completion-parameters-v6':270,'completion-stability-v6':144,'completion-sefa-v6-official':108,'completion-mechanisms-v1':90,'environment-shift-v1':189,'recovery-path-learning-v1':162,'recent-gdfs-v1':108,'recent-dime-v1':108,'recent-efa-v1':108}
METRICS=['mean_positive_log_inflation','clean_mae','attack_mae','failed_query_fraction','nonconverged_batch_fraction','max_remaining_response_regret']
HASHES={}
def sha(p):
 p=Path(p)
 if str(p) not in HASHES:HASHES[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 return HASHES[str(p)]
def main():
 receipts=[];allparts=[];bindings={};nonconv=[];missing_audit=[]
 for stage,n in STAGES.items():
  root=ROOT/'outputs'/stage;r=json.loads((root/'completion.json').read_text());assert r['cells']==n and r['summary_sha256']==sha(root/'summary.csv')
  df=pd.read_csv(root/'summary.csv');assert len(df)==n and not df.duplicated(['dataset','seed','method','budget']).any()
  assert df[METRICS].notna().all().all();assert (df['n']==1000).all();bindings[stage]=dict(cells=n,summary_sha256=sha(root/'summary.csv'),completion_sha256=sha(root/'completion.json'))
  cells=[]
  for cp in root.rglob('completion.json'):
   j=json.loads(cp.read_text())
   if 'summary' not in j:continue
   assert j['status']=='completed_and_corroborated';s=j['summary'];a=j.get('audit',{})
   if a.get('status')!='allocation_transition_all_legal_utilities_corroborated':missing_audit.append(str(cp.relative_to(ROOT)))
   if 'outcomes_sha256' in j:assert sha(cp.parent/'outcomes.csv.gz')==j['outcomes_sha256']
   elif 'reused_original_outcomes' in j:
    u=j['reused_original_outcomes'];assert sha(ROOT/u['path'])==u['sha256']
   elif 'reused_reference_receipt' in j:assert sha(ROOT/j['reused_reference_receipt'])==j['inputs']['baseline_receipt']
   else:assert 'reused' in j
   cells.append((s['dataset'],s['seed'],s['method'],s['budget']))
  assert len(cells)==n and len(set(cells))==n,stage
  assert set(cells)==set(df[['dataset','seed','method','budget']].itertuples(index=False,name=None))
  receipts.append(dict(stage=stage,cells=n,receipt_cells=len(cells),summary_sha256=sha(root/'summary.csv')))
  df['stage']=stage;allparts.append(df);nonconv.append(df[df.nonconverged_batch_fraction>0])
 assert not missing_audit,missing_audit
 allcells=pd.concat(allparts,ignore_index=True);allcells.to_csv(OUT/'verified_cell_summaries.csv',index=False);pd.concat(nonconv,ignore_index=True).to_csv(OUT/'nonconverged_cells_retained.csv',index=False)
 means=allcells[['stage','dataset','method','budget']+METRICS].groupby(['stage','dataset','method','budget']).agg(['mean','min','max']);means.to_csv(OUT/'descriptive_curves.csv')
 # RPL: all predefined weights, budgets and paired seeds; baseline is the matching beta=0.5/path=0 branch.
 rpl=allcells[allcells.stage=='recovery-path-learning-v1'];paired=[]
 for key,g in rpl.groupby(['dataset','seed','budget','beta']):
  ref=g[g.path_weight==0].iloc[0]
  for _,v in g[g.path_weight>0].iterrows():
   d=dict(dataset=key[0],seed=key[1],budget=key[2],beta=key[3],path_weight=v.path_weight)
   for m in METRICS:d[m+'_change']=v[m]-ref[m];d[m+'_relative_change']=(v[m]-ref[m])/abs(ref[m]) if ref[m]!=0 else np.nan
   paired.append(d)
 pd.DataFrame(paired).to_csv(OUT/'rpl_paired_changes.csv',index=False)
 main=rpl[(rpl.budget==.1)&(rpl.beta==.5)].groupby(['dataset','path_weight'])[METRICS].mean();main.to_csv(OUT/'rpl_primary_means.csv')
 primary=[]
 for dataset,g in main.groupby(level=0):
  b=g.xs(dataset).loc[0];v=g.xs(dataset).loc[1];primary.append(dict(dataset=dataset,inflation_reduction_percent=100*(b[METRICS[0]]-v[METRICS[0]])/b[METRICS[0]],honest_mae_change_percent=100*(v.clean_mae-b.clean_mae)/b.clean_mae,attacked_mae_change_percent=100*(v.attack_mae-b.attack_mae)/b.attack_mae,failed_query_change_pp=100*(v.failed_query_fraction-b.failed_query_fraction)))
 pd.DataFrame(primary).to_csv(OUT/'rpl_lambda1_primary_effects.csv',index=False)
 # Mechanism contrasts: fixed no-feedback reference, all refreshed/search variants retained.
 mech=allcells[allcells.stage=='completion-mechanisms-v1'];p=[]
 for key,g in mech.groupby(['dataset','seed','budget']):
  b=g[g.method=='feedback-off'].iloc[0]
  for _,v in g[g.method!='feedback-off'].iterrows():
   d=dict(dataset=key[0],seed=key[1],budget=key[2],method=v.method)
   for m in METRICS:d[m+'_change']=v[m]-b[m]
   p.append(d)
 pd.DataFrame(p).to_csv(OUT/'mechanism_vs_off.csv',index=False)
 # Recent families: default ACO k25 retained, k10/k50 separately available in original evidence.
 recent=pd.read_csv(ROOT/'outputs/recent-five-analysis-v1/five_families_inventory.csv');recent=recent[(recent.recent_family!='aco')|recent.method.str.endswith('_k25')]
 assert len(recent)==540
 orig=pd.read_csv(ROOT/'outputs/nested-development-v2/all_summary.csv');controls=orig[orig.method.isin(['masking_risk','masking_benefit','masking_suppression','robust_no_feedback','sav_val'])].copy();controls['recent_family']=controls.method;controls['price_backend']=controls.method.map({'masking_risk':'masking_suppression','masking_benefit':'masking_suppression','masking_suppression':'masking_suppression','robust_no_feedback':'robust_no_feedback','sav_val':'sav_val'})
 combined=pd.concat([recent,controls],ignore_index=True);combined.to_csv(OUT/'recent_and_simple_controls.csv',index=False)
 # Identical honest predictions on same backend and seed; hence acquisition curves cannot improve honest MAE.
 for _,g in recent.groupby(['dataset','seed','price_backend','budget']):assert g.clean_mae.max()-g.clean_mae.min()<1e-6
 out=dict(status='integrity_and_descriptive_review_completed',time=datetime.datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),cells=1719,stages=receipts,bindings=bindings,nonconverged_cells=len(pd.concat(nonconv)),independent_experimental_seeds=3,not_independent_cells=True,raw_hashes_verified=True,shared_predictor_audits_not_full_independent_reimplementations=True,paper_generated=False)
 (OUT/'completion.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2));print(pd.DataFrame(primary).to_string(index=False))
if __name__=='__main__':main()
