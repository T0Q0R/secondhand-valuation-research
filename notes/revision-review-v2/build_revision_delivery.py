"""Archive the bounded revision evidence; never label incomplete MUCars complete."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
tracker=json.loads((H/'review-tracker.json').read_text())
actions={
'A':('addressed_scope_and_finite_diagnostic','Restricted frontier scope; finite four-field recovery-path check; no empirical T* claim.'),
'B':('addressed_posthoc_sensitivity_not_confirmatory','Complete simultaneous families and source-wise sensitivity; confirmatory/FWER certification not established.'),
'C':('addressed_full_real_cohort_evaluation','Full JU1374/14-batch and MU10672/107-batch evaluation, all 480 cells corroborated; weighted exploratory analysis.'),
'D':('addressed_descriptive_multiobjective','Constant-predictor degeneracy, three co-primary descriptive outcomes, cap harm interpretation.'),
'E':('addressed_heuristic_threshold_sensitivity','Continuous effects and complete declared gate grids.'),
'F':('addressed_bounded_independent_oracle','Shared primitives disclosed; independent bit-mask state/field oracle, shared model remains outside scope.'),
'G':('addressed_main_text_comparators','BEN/ACO inflation comparison in main text; conditional MU gains retained.'),
'H':('addressed_with_bounded_three_seed_cost_sensitivity','History governance, analytical final-record envelope, all cost regimes including favorable SYN reversal; not universal dominance.'),
'I':('addressed_status_and_history','Canonical entries updated; old review and 26-page delivery marked historical.')}
for key,(status,action) in actions.items():tracker['comments'][key].update(status=status,action=action)
tracker.update(status='substantive_revision_in_progress',manuscript_pages=30,formal_submission_ready=False,author_public_release_decisions_pending=True)
(H/'review-tracker.json').write_text(json.dumps(tracker,indent=2)+'\n')
paths=[ROOT/'paper/innovation-addendum-v1.tex',ROOT/'paper/innovation-addendum-v1.pdf']
for p in H.rglob('*'):
 if not p.is_file() or '__pycache__' in p.parts:continue
 if 'repository-entry-files' in p.parts:continue
 if p.name.startswith(('resize-checkpoints-','rebalance-checkpoints-')):continue
 if p.name.endswith('checkpoint-evidence.zip') or p.name in ['full-expanded-evidence.zip','full-expanded-evidence-index.json']:continue
 if p.suffix in ['.png','.pdf','.log','.b64'] or p.name in ['revision-delivery-index.json','isolated-replay-context.json']:continue
 if p.parent==H/'qa' and p.name not in ['render-audit.json','correspondence-audit.json','package-consistency-findings.json','package-consistency-initial-findings.json'] and not p.name.endswith('-geometry-audit.json'):continue
 paths.append(p)
for name in ['completion.json','paired_tensors_and_draws.npz','contrast_specifications.json','contrasts.csv']:
 paths.append(ROOT/'outputs/matched-factorial-ten-seeds-v1-pipeline/analysis'/name)
paths.extend([ROOT/'outputs/minimax-response-full-v1-analysis/contrasts.csv',ROOT/'outputs/minimax-response-full-v1-statistics-check/completion.json'])
paths.extend(ROOT/'outputs/review-expanded-primary-v2-analysis'/name for name in ['completion.json','expanded_feedback_contrasts.csv','expanded_cell_means.csv'])
paths=sorted(set(paths)); dest=ROOT/'paper/revision-delivery-v2.zip'
with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in paths:z.write(p,str(p.relative_to(ROOT)))
index={'status':'bounded_revision_checkpoint','scope':'current 30-page revised manuscript, A-I response, aggregate replay inputs and completed full-real-cohort supplements; author/release/external-training pending',
 'archive':str(dest.relative_to(ROOT)),'bytes':dest.stat().st_size,'sha256':sha(dest),
 'manuscript_sha256':sha(ROOT/'paper/innovation-addendum-v1.tex'),'pdf_sha256':sha(ROOT/'paper/innovation-addendum-v1.pdf'),
 'files':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths],
 'no_weights_or_raw_listings':True,'external_full_training_reproduction':False,'public_release':False,
 'external_evidence_archives':[json.loads((H/'evaluation/full-expanded-evidence-index.json').read_text()) | {'files': 'see separate full-expanded-evidence-index.json'}]}
with zipfile.ZipFile(dest) as z:
 assert z.testzip() is None
 assert set(z.namelist())=={a['path'] for a in index['files']}
 for a in index['files']:assert hashlib.sha256(z.read(a['path'])).hexdigest()==a['sha256']
(H/'revision-delivery-index.json').write_text(json.dumps(index,indent=2)+'\n')
print(json.dumps({k:v for k,v in index.items() if k!='files'}));print('VERIFIED FILES',len(paths))
