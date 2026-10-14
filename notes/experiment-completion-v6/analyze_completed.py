"""Fail-closed aggregate/contrast export after all queued experiments.
No manuscript writes, outcome-dependent method selection, or invented CIs.
"""
from pathlib import Path
import argparse,hashlib,itertools,json,sys
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[2]
JOBS={'ablation':('outputs/completion-ablation-v6',432),'parameters':('outputs/completion-parameters-v6',270),'stability':('outputs/completion-stability-v6',144),'sefa':('outputs/completion-sefa-v6-official',108)}
METRICS=['mean_positive_log_inflation','clean_mae','attack_mae','failed_query_fraction','actual_audit_fraction','max_remaining_response_regret','mean_unilateral_inflation_envelope_log','attack_signed_log_bias']
DEFAULTS={'anchor_weight':.25,'attack_loss_weight':.5,'learning_rate':.001,'residual_epochs':12,'head_trees':160,'residual_hidden_width':64}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def check(condition,message):
 if not condition:raise ValueError(message)
def paired_ablations(frame):
 keys=['dataset','seed','budget'];ref=frame[frame.method=='S1F1G1'].set_index(keys);rows=[]
 for name,variant in frame.groupby('method'):
  if name=='S1F1G1':continue
  other=variant.set_index(keys);check(other.index.equals(ref.index) or set(other.index)==set(ref.index),'ablation pairing incomplete');other=other.loc[ref.index]
  for metric in METRICS:
   for index,a,b in zip(ref.index,ref[metric],other[metric]):rows.append(dict(zip(keys,index),removed_configuration=name,metric=metric,full=a,removed=b,removed_minus_full=b-a,relative_reduction=(b-a)/b if b>0 and metric not in ['attack_signed_log_bias'] else None))
 return pd.DataFrame(rows)
def factorial_effects(frame):
 rows=[];axes=['suppression_target','feedback','gap_penalty']
 for key,g in frame.groupby(['dataset','seed','budget']):
  check(len(g)==8,'factorial lacks8cells')
  for order in [1,2,3]:
   for subset in itertools.combinations(axes,order):
    weight=np.prod([2*g[a].to_numpy()-1 for a in subset],axis=0)
    for m in METRICS:rows.append(dict(dataset=key[0],seed=key[1],budget=key[2],effect=':'.join(subset),metric=m,high_minus_low_effect=float(np.sum(weight*g[m])/4)))
 return pd.DataFrame(rows)
def verify_job(path,expected):
 path=ROOT/path;c=json.loads((path/'completion.json').read_text());m=json.loads((path/'manifest.json').read_text());check(c['status']=='completed_and_corroborated' and c['cells']==expected,'incomplete '+str(path));check(sha(path/'summary.csv')==c['summary_sha256'],'summary checksum');check(sha(path/'manifest.json')==c['manifest_sha256'],'manifest checksum');d=pd.read_csv(path/'summary.csv');check(len(d)==expected,'wrong row count');check(set(d.dataset)=={'synthetic','jucars','mucars'} and set(d.seed)=={13,42,2026},'wrong source/seed coverage');check(not d.duplicated(['dataset','seed','method','budget']).any(),'duplicate cells');check(d[METRICS].notna().all().all(),'missing metrics');check(set(d.n)=={1000},'unexpected evaluation cohort size')
 files={};deviations=0;cells=0
 for p in path.glob('*/seed-*/**/completion.json'):
  r=json.loads(p.read_text())
  if 'summary' in r:
   check('corroborated' in r['status'],'uncorroborated cell');check('rank' in r['audit']['scope'] or 'separate integer' in r['audit']['scope'].lower(),'unbounded audit scope');deviations+=r['audit']['legal_deviations'];cells+=1
  for key,name in [('outcomes_sha256','outcomes.csv.gz'),('model_sha256','model.joblib')]:
   if key in r:
    q=p.parent/name;check(q.exists() and sha(q)==r[key],'artifact hash '+str(q));files[str(q.relative_to(ROOT))]=r[key]
 check(cells==expected,'per-cell completion count');return d,dict(cells=expected,legal_deviations=deviations,summary_sha256=sha(path/'summary.csv'),checked_artifacts=len(files),manifest_sha256=sha(path/'manifest.json'))
def curve_records(core,stability):
 rows=[]
 for axis,xname,values in [('gap_weight','beta',[0,.1,.25,.5,1,2]),('tolerance','tolerance',[0,.01,.02,.05,.1])]:
  for value in values:
   mask=np.isclose(core[xname],value)&np.isclose(core.beta,.5 if axis=='tolerance' else value)&np.isclose(core.tolerance,.02 if axis=='gap_weight' else value)&(core['rounds']==2)&core.feedback
   g=core[mask].copy();check(len(g)==18,'parameter curve missing point');g['curve_axis']=axis;g['parameter_value']=value;rows.append(g)
 feedback=core[(core.axis=='feedback_schedule')|(core.method=='beta-0.5')].copy();feedback['curve_axis']='feedback_schedule';feedback['parameter_value']=feedback['rounds'];rows.append(feedback)
 base=core[(core.method=='beta-0.5')&np.isclose(core.budget,.1)]
 for axis,default in DEFAULTS.items():
  a=stability[stability.axis==axis].copy();b=base.copy();b['parameter_value']=default;a['curve_axis']=axis;b['curve_axis']=axis;rows += [a,b]
 return pd.concat(rows,ignore_index=True)
def summarize_ranges(d,keys,metrics):
 long=d.melt(id_vars=keys+['seed'],value_vars=metrics,var_name='metric',value_name='value');g=long.groupby(keys+['metric']).value.agg(['mean','min','max','count']).reset_index();g['uncertainty']='observed3fitting_seed_range_not_confidence_interval';return g

def self_test():
 rows=[]
 for a,b,c in itertools.product([0,1],repeat=3):
  row=dict(dataset='toy',seed=13,budget=.1,method=f'S{a}F{b}G{c}',suppression_target=a,feedback=b,gap_penalty=c)
  for metric in METRICS:row[metric]=10+2*a+3*b+5*c+7*a*b
  rows.append(row)
 frame=pd.DataFrame(rows);effects=factorial_effects(frame);e=effects[effects.metric==METRICS[0]].set_index('effect').high_minus_low_effect
 check(abs(e['suppression_target']-5.5)<1e-12,'factorial A');check(abs(e['feedback']-6.5)<1e-12,'factorial B');check(abs(e['gap_penalty']-5)<1e-12,'factorial C');check(abs(e['suppression_target:feedback']-3.5)<1e-12,'factorial AB');check(abs(e['suppression_target:feedback:gap_penalty'])<1e-12,'factorial ABC');p=paired_ablations(frame);check(len(p)==7*len(METRICS),'paired count');check((p[p.removed_configuration=='S0F0G0'].removed_minus_full==-17).all(),'contrast sign')
 print('PASS: known-factor factorial contrasts and paired sign; toy values never saved as results')

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path);p.add_argument('--self-test',action='store_true');a=p.parse_args()
 if a.self_test:self_test();return
 check(a.output is not None,'output required');out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);tables={};checks={};check(sha(ROOT/'paper/innovation-addendum-v1.tex')=='bf799e53b6ba4cbebf84ec78d6c2c3ffe581e6a9a21a8f4e312dd2646f656a24','Frozen manuscript changed')
 for name,(path,n) in JOBS.items():tables[name],checks[name]=verify_job(path,n)
 ab=paired_ablations(tables['ablation']);ab.to_csv(out/'paired_ablations.csv',index=False);factorial_effects(tables['ablation']).to_csv(out/'factorial_main_and_interaction_effects.csv',index=False)
 summarize_ranges(tables['ablation'],['dataset','method','budget'],METRICS).to_csv(out/'ablation_means_and_seed_ranges.csv',index=False)
 curves=curve_records(tables['parameters'],tables['stability']);curves.to_csv(out/'parameter_curve_points.csv',index=False);summarize_ranges(curves,['dataset','curve_axis','parameter_value','feedback','budget'],METRICS).to_csv(out/'parameter_curve_means_and_seed_ranges.csv',index=False)
 original=pd.read_csv(ROOT/'outputs/nested-development-v2/all_summary.csv');aco=pd.read_csv(ROOT/'outputs/aco1-development-v2/summary.csv');comparators=pd.concat([original.assign(origin='original3seed'),aco.assign(origin='ACO2024adaptation'),tables['sefa'].assign(origin='SEFA2025adaptation')],ignore_index=True);comparators.to_csv(out/'baseline_all_seed_cells.csv',index=False);summarize_ranges(comparators,['dataset','method','budget'],METRICS).to_csv(out/'baseline_means_and_seed_ranges.csv',index=False)
 smi=pd.read_csv(ROOT/'outputs/grouped-smi-development-v2/summary.csv');smi.to_csv(out/'deterministic_SMI2020_zero_budget_separate_regime.csv',index=False)
 # Preserve every nonconverged result; no success-only filtering.
 nonconverged=pd.concat([v.assign(job=k) for k,v in tables.items()]).query('nonconverged_batch_fraction > 0');nonconverged.to_csv(out/'nonconverged_cells_retained.csv',index=False)
 outputs={q.name:sha(q) for q in out.glob('*.csv')};report=dict(status='computed_and_corroborated_aggregates_scientific_and_visual_review_pending',jobs=checks,total_cells=sum(x[1] for x in JOBS.values()),nonconverged_cells=len(nonconverged),new_baseline='SEFA2025official4-bin acquisition with shared-budget price-backend adapter',source_sha256=sha(Path(__file__)),csv_sha256=outputs,manuscript_generation=False,uncertainty='3seed ranges and paired observations; no new confirmatory CI or population-generalization claim',pending=['inspect metric tradeoffs and method ranking honestly','render/audit curves using frozen CSVs','justify defaults from training-only selection or identify them as engineering defaults','commit finished results/checkpoints to private GitHub before further work','only then decide whether experiment gate permits manuscript backfill']);(out/'completion.json').write_text(json.dumps(report,indent=2)+'\n')
 (out/'INTERNAL_REPORT.md').write_text('# Internal experiment handoff\n\nAll queued computations and aggregate integrity checks finished. This does not certify a stronger algorithm or paper readiness. Read completion.json and all retained nonconverged cells. Curves/visual QA and scientific interpretation remain pending; do not auto-rewrite the paper. Three-seed ranges are not CIs. SMIs use a separate deterministic zero-budget regime. No evaluation-driven default selection. Finished evidence awaits GitHub sync by the next active collaborator.\n')
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
