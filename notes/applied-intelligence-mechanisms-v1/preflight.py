from pathlib import Path
import sys,importlib.util,json,tempfile,copy,os
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'experiments'))
import pandas as pd
import run_completion_ablation_v6 as c

def module(name):
 s=importlib.util.spec_from_file_location(name,Path(__file__).parent/f'{name}.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
analysis=module('analyze');tail=module('run_after_current');cfg=json.loads((Path(__file__).parent/'tail-config.json').read_text());assert tail.prerequisite(cfg) is False
# Known algebra test,no artificial result stored as research data.
rows=[]
for method,value in {'epoch-weak':10,'epoch-strong':7,'batch-weak':8,'batch-strong':6,'feedback-off':9}.items():rows.append(dict(dataset='toy',seed=0,budget=.1,method=method,**{m:value for m in analysis.METRICS}))
t=analysis.contrast_rows(pd.DataFrame(rows));assert set(t.loc[t.reference=='refresh_effect_under_weak_search','interaction'])=={1}
assert set(t.loc[(t.reference=='epoch-weak')&(t.intervention=='batch-strong'),'reduction'])=={4}
with tempfile.TemporaryDirectory() as td:
 tail.ROOT=Path(td);d=tail.ROOT/'old';d.mkdir();j=dict(cfg,predecessor_output='old',predecessor_pid=os.getpid())
 (d/'status.json').write_text(json.dumps(dict(status='running')));assert tail.prerequisite(j) is False
 (d/'failure.json').write_text('{}');rejected=False
 try:tail.prerequisite(j)
 except RuntimeError:rejected=True
 assert rejected;(d/'failure.json').unlink()
 (d/'status.json').write_text(json.dumps(dict(status='computations_and_aggregate_checks_completed_scientific_visual_review_pending')))
 rejected=False
 try:tail.prerequisite(j)
 except (FileNotFoundError,AssertionError):rejected=True
 assert rejected
c.guard();assert all(c.sha(ROOT/f)==h for f,h in cfg['frozen_files'].items())
c.write(Path(__file__).parent/'preflight.json',dict(status='passed',live_predecessor_not_bypassed=True,failure_blocks_tail=True,unverified_completion_rejected=True,contrast_algebra_checked=True,frozen_file_hashes_verified=len(cfg['frozen_files']),scientific_result=False))
print('preflight passed')
