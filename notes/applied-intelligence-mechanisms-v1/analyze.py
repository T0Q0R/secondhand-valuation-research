"""Fail-closed mechanism summaries. Three fitting seeds; no pseudo-replicated CIs."""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'experiments'))
import pandas as pd,numpy as np
import run_completion_ablation_v6 as c
from run_completion_mechanisms_v1 import variants
METRICS=['mean_positive_log_inflation','clean_mae','attack_mae','failed_query_fraction','hiding_fraction','mean_unilateral_inflation_envelope_log','max_remaining_response_regret','nonconverged_batch_fraction']
COMPARISONS=[('epoch-weak','batch-weak'),('epoch-strong','batch-strong'),('epoch-weak','epoch-strong'),('batch-weak','batch-strong'),('epoch-weak','batch-strong')]+[('feedback-off',x) for x in variants() if x!='feedback-off']
def contrast_rows(table):
 out=[]
 for key,g in table.groupby(['dataset','seed','budget']):
  g=g.set_index('method');assert set(g.index)==set(variants())
  for ref,intervention in COMPARISONS:
   for metric in METRICS:
    out.append(dict(dataset=key[0],seed=key[1],budget=key[2],reference=ref,intervention=intervention,metric=metric,reference_value=float(g.loc[ref,metric]),intervention_value=float(g.loc[intervention,metric]),reduction=float(g.loc[ref,metric]-g.loc[intervention,metric])))
  for metric in METRICS:
   interaction=(g.loc['batch-strong',metric]-g.loc['epoch-strong',metric])-(g.loc['batch-weak',metric]-g.loc['epoch-weak',metric])
   out.append(dict(dataset=key[0],seed=key[1],budget=key[2],reference='refresh_effect_under_weak_search',intervention='refresh_effect_under_strong_search',metric=metric,interaction=float(interaction)))
 return pd.DataFrame(out)
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=True);c.guard();src=ROOT/'outputs/completion-mechanisms-v1';manifest=json.loads((src/'manifest.json').read_text());receipt=json.loads((src/'completion.json').read_text())
 assert receipt['status']=='completed_and_corroborated' and receipt['cells']==90 and receipt['manifest_sha256']==c.sha(src/'manifest.json') and receipt['summary_sha256']==c.sha(src/'summary.csv')
 assert all(c.sha(ROOT/p)==h for p,h in manifest['dependency_sha256'].items())
 table=pd.read_csv(src/'summary.csv');assert len(table)==90 and not table.duplicated(['dataset','seed','method','budget']).any()
 paths=[];logs=[];bindings={}
 for source in manifest['config']['datasets']:
  for seed in manifest['config']['seeds']:
   pair=src/source/f'seed-{seed}';r=json.loads((pair/'completion.json').read_text());assert r['cells']==10 and r['summary_sha256']==c.sha(pair/'summary.csv')
   for method,v in variants().items():
    for budget in manifest['config']['budgets']:
     cell=pair/method/f'evaluation-{round(budget*10000):04d}';cp=cell/'completion.json';r=json.loads(cp.read_text());assert r['status']=='completed_and_corroborated';bindings[str(cp.relative_to(ROOT))]=c.sha(cp)
     if 'outcomes_sha256' in r:assert c.sha(cell/'outcomes.csv.gz')==r['outcomes_sha256']
     paths.append(dict(dataset=source,seed=seed,method=method,budget=budget,**r['recovery_paths']))
    if method in ['epoch-weak','feedback-off']:continue
    for stage in ['outer-0','outer-1','outer-2','deployment']:
     fit=pair/method/stage;r=json.loads((fit/'completion.json').read_text());assert c.sha(fit/'model.joblib')==r['model_sha256']
     for rd in r['rounds']:
      for epoch in rd['loss']:logs.append(dict(dataset=source,seed=seed,method=method,stage=stage,round=rd['round'],fit_seconds=r['seconds'],**epoch))
 contrasts=contrast_rows(table);contrasts.to_csv(out/'paired_mechanism_contrasts.csv',index=False)
 contrasts.groupby(['dataset','budget','reference','intervention','metric']).agg(fitting_seeds=('seed','nunique'),reduction_mean=('reduction','mean'),reduction_min=('reduction','min'),reduction_max=('reduction','max'),interaction_mean=('interaction','mean')).to_csv(out/'descriptive_seed_summary.csv')
 pd.DataFrame(paths).to_csv(out/'recovery_paths.csv',index=False);pd.DataFrame(logs).to_csv(out/'training_response_diagnostics.csv',index=False)
 (out/'INTERNAL_REPORT.md').write_text('Mechanism calculations and hash checks completed; scientific interpretation and visual QA pending.\n\n90 cells:36 reused references,54 new evaluations,108 new price fits. Three fitting seeds per source share fixed training/evaluation records; seed ranges are not confidence intervals. Contrasts are retrospective, not confirmatory. Reduction=reference-intervention; positive is a decrease, not automatically desirable for hiding/failure rate. Interaction=(batchStrong-epochStrong)-(batchWeak-epochWeak). Stronger search remains heuristic; retain regret/nonconvergence. Recovery-edge denominators count only legal hidden-field transitions; realized counts use successful queries. Effects are algorithmic interventions in a stipulated seller model, not causal evidence on real sellers.\n\nCombine with existing1/2/4-round parameter results; never select default from evaluation outcomes. Evaluate inflation jointly with honest/attacked MAE and failed queries. No manuscript generated.\n')
 c.write(out/'completion.json',dict(status='aggregate_checked_scientific_visual_review_pending',cells=90,new_evaluation_cells=54,new_price_fits=108,training_epoch_rows=len(logs),path_rows=len(paths),contrast_rows=len(contrasts),cell_bindings=bindings,artifacts={p.name:c.sha(p) for p in out.iterdir() if p.is_file() and p.name!='completion.json'},paper_generated=False))
if __name__=='__main__':main()
