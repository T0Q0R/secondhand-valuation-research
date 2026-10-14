"""Inventory already completed evidence without replaying training/audits."""
from pathlib import Path
import json,hashlib,itertools
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;bindings={}
def read(p):
 p=ROOT/p;bindings[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest();return pd.read_csv(p) if p.suffix=='.csv' else json.loads(p.read_text())
a=read(Path('outputs/nested-development-v2/all_summary.csv'));b=read(Path('outputs/nested-seven-extra-seeds-v1/all_summary.csv'));full=pd.concat([a,b]);assert len(full)==1860 and full.seed.nunique()==10 and full.dataset.nunique()==3
assert not full.duplicated(['dataset','seed','method','budget']).any()
for run in ['nested-development-v2','nested-seven-extra-seeds-v1']:
    receipt=read(Path('outputs')/run/'completion.json')
    assert receipt['status']=='completed'
    assert receipt['summary_sha256']==hashlib.sha256((ROOT/'outputs'/run/'all_summary.csv').read_bytes()).hexdigest()

summary=full.groupby('method').agg(cells=('n','size'),sources=('dataset','nunique'),fitting_seeds=('seed','nunique'),capacity_levels=('budget','nunique')).reset_index();summary.to_csv(HERE/'existing_original_methods.csv',index=False)
items=[]
def item(id,category,producer,auditor,description,limit):
 p=read(Path(producer));audit=read(Path(auditor));items.append(dict(id=id,category=category,status='existing_completion_and_receipt_bound',producer=producer,auditor=auditor,description=description,limit=limit,producer_status=p.get('status','read_receipt'),auditor_status=audit.get('status','read_receipt')))
item('original_controls_ablations','classical_and_single_ablations','outputs/nested-development-v2/completion.json','outputs/nested-development-v2-audit-01/analysis_completion.json','12methods,3sources,10fitting seeds with seven-extra-seed extension;1860cells','Existing single removals do not substitute for a complete controlled three-component factorial; separate seven-seed receipt retained')
read(Path('outputs/nested-seven-extra-seeds-v1/completion.json'))
item('matched_factorial','controlled_factorial','outputs/matched-factorial-ten-seeds-v1/completion.json','outputs/matched-factorial-ten-seeds-v1-pipeline/outcome-audit/completion.json','24 objective/acquisition/feedback/allocation combinations;4320cells','No gap-weight axis; cannot call it complete suppression/feedback/gap 2^3 ablation. Producer root status is historical; completed audits supply actual state')
item('SMI2020','direct_prior_adaptation','outputs/grouped-smi-development-v2/completion.json','outputs/grouped-smi-development-v2-interval-cached-audit/completion.json','12cells across3sources;94527oracle checks','Whole-category regression adaptation and fallback, not original unchanged execution; one deterministic fit/source')
item('ACO2024','recent_prior_adaptation','outputs/aco1-development-v2/completion.json','outputs/aco1-development-v2-audit/analysis_completion.json','144cells across9source/seed pairs; neighborhood10/25/50','One-query local adaptation; not original unchanged sequential method or evidence of full multi-step optimum')
item('equal_tuning','parameter_selection','outputs/equal-tuning-size-development-v1/completion.json','outputs/equal-tuning-size-development-v1-audit-full-01/completion.json','972cells; three source-specific train-size levels;three seeds;equal gap-weight grid.25/.5/1','Training-internal selection, not all globally fixed-beta deployment sensitivity curves. Selection folds/candidate80% fits cannot silently stand in for uniform-beta full fits')
item('ordinary_benefit_size','strong_reference','outputs/equal-benefit-size-reference-development-v1/completion.json','outputs/equal-benefit-size-reference-development-v1-audit-full-01/completion.json','324cells;27source/size/seed cases','Retain matched training-size references, not a new run')
item('resource_transfer','efficiency_robustness','outputs/online-resource-development-v2/completion.json','outputs/online-resource-and-transfer-v2-audit/completion.json','Existing efficiency and transferred-response evidence','Check exact timed components before claiming speed advantage')
pd.DataFrame(items).to_csv(HERE/'coverage_inventory.csv',index=False)
rows=[]
for s,f,g in itertools.product([0,1],repeat=3):
 if f and s and g:existing='sav_val'
 elif f and s and not g:existing='sav_no_gap'
 elif f and not s and g:existing='sav_benefit_head'
 else:existing=''
 rows.append(dict(suppression_target=s,feedback=f,gap_penalty=g,beta=.5 if g else 0.,epochs=12,rounds=2,existing_exact_feedback_on_match=existing,
  required='Reuse matching completed outer/deployment predictions and models only after hash/cohort checks' if existing else 'Fit controlled two-round branch or share exact same estimator across score-only contrast',
  caveat='Original static robust has one12-epoch optimizer run; controlled feedback-off uses two6-epoch rounds to match optimizer resets and head refreshes'))
pd.DataFrame(rows).to_csv(HERE/'three_component_ablation.csv',index=False)
manifest=dict(status='existing_evidence_inventoried_new_experiments_not_complete',original_rows=1860,original_methods=summary.method.tolist(),paper_generation='paused_until_required_experiments_and_checks_complete',paper_source_sha256=hashlib.sha256((ROOT/'paper/innovation-addendum-v1.tex').read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),input_sha256=bindings,scope='Receipt/source binding and actual summary coverage only; not a new independent replay of existing raw outcomes')
(HERE/'inventory-completion.json').write_text(json.dumps(manifest,indent=2)+'\n');print(summary.to_string(index=False));print('coverage items',len(items),'ablation combinations',len(rows))
