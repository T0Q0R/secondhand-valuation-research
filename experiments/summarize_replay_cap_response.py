"""Conditional paired-batch intervals and all-cell multiobjective accounting."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd

root=Path(__file__).resolve().parents[1]
run=root/'outputs/replay-cap-response-full-v1';audit=root/'outputs/replay-cap-response-full-v1-audit-v2'
out=root/'outputs/replay-cap-response-full-v1-analysis'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
done=json.loads((audit/'completion.json').read_text());assert done['status']=='completed'
assert sha(run/'completion.json')==done['parent_completion_sha256']
for name,digest in done['files'].items():assert sha(audit/name)==digest
if out.exists():raise FileExistsError(out)
out.mkdir();(out/'analysis_snapshot.py').write_bytes(Path(__file__).read_bytes())
manifest=json.loads((run/'manifest.json').read_text());source=Path(manifest['source'])
d=pd.read_csv(audit/'verified_summary.csv');keys=['dataset','seed','price','budget','method']
old=d[d.variant=='original'].set_index(keys);new=d[d.variant=='capped'].set_index(keys)
columns=['inflation','attacked_mae','failed','query','deviation','honest_mae']
counts={c:{'decreased':int(((new[c]-old[c]) < -1e-10).sum()),
           'unchanged':int((abs(new[c]-old[c])<=1e-10).sum()),
           'increased':int(((new[c]-old[c]) > 1e-10).sum())} for c in columns}
counts['nonconverged_cells']={'original':int((old.nonconverged_batch_fraction>0).sum()),'capped':int((new.nonconverged_batch_fraction>0).sum())}
counts['capped_max_regret']=float(new.max_regret.max())
write(out/'all_cell_accounting.json',counts)
rng=np.random.default_rng(20261007);draws=rng.integers(0,10,size=(1000,10))
metrics={'inflation':'positive_expected_log_inflation','attacked_mae':'expected_attack_absolute_error',
         'failed':'expected_failed_query_probability','query':'expected_query_probability','honest_mae':'clean_absolute_error'}
bindings={str(p):sha(p) for p in [audit/'completion.json',audit/'verified_summary.csv',run/'completion.json']}
rows=[]
for dataset in ['synthetic','jucars','mucars']:
    for method in manifest['methods']:
        blocks=[];ids=None
        for seed in [13,42,2026]:
            rel=Path(dataset)/f'seed-{seed}'/'robust'/'budget-1000'/method
            a=pd.read_csv(source/rel/'outcomes.csv.gz');b=pd.read_csv(run/rel/'outcomes.csv.gz')
            assert a.listing_id.equals(b.listing_id) and a.batch.equals(b.batch)
            if ids is None:ids=a.listing_id.tolist()
            else:assert ids==a.listing_id.tolist()
            for p in [source/rel/'outcomes.csv.gz',run/rel/'outcomes.csv.gz']:bindings[str(p)]=sha(p)
            blocks.append((a.groupby('batch')[list(metrics.values())].mean(),b.groupby('batch')[list(metrics.values())].mean()))
        before=np.mean([a.to_numpy() for a,b in blocks],axis=0)
        after=np.mean([b.to_numpy() for a,b in blocks],axis=0)
        row={'dataset':dataset,'method':method,'training_seeds':3,'shared_batches':10,'bootstrap_draws':1000}
        for j,name in enumerate(metrics):
            delta=before[:,j]-after[:,j] if name=='inflation' else after[:,j]-before[:,j]
            lo,hi=np.quantile(delta[draws].mean(1),[.025,.975])
            row.update({f'{name}_original':float(before[:,j].mean()),f'{name}_capped':float(after[:,j].mean()),
                        f'{name}_difference':float(delta.mean()),f'{name}_lower':float(lo),f'{name}_upper':float(hi)})
        row['inflation_reduction_percent']=100*row['inflation_difference']/row['inflation_original']
        row['attacked_mae_change_percent']=100*row['attacked_mae_difference']/row['attacked_mae_original']
        row['original_conditional_failure_rate']=row['failed_original']/row['query_original'] if row['query_original'] else None
        row['capped_conditional_failure_rate']=row['failed_capped']/row['query_capped'] if row['query_capped'] else None
        row['conditional_original_practical_gate']=bool(row['inflation_reduction_percent']>=10 and row['inflation_lower']>0 and row['honest_mae_capped']<=1.05*row['honest_mae_original'])
        rows.append(row)
primary=pd.DataFrame(rows);primary.to_csv(out/'primary_paired_intervals.csv',index=False)
for _,r in primary.iterrows():
    for variant,frame in [('original',old),('capped',new)]:
        selected=frame.reset_index().query('dataset == @r.dataset and method == @r.method and price == "robust" and budget == 0.1')
        assert len(selected)==3
        for name in metrics:assert np.isclose(selected[name].mean(),r[f'{name}_{variant}'],atol=1e-8,rtol=1e-10)
assert all(sha(Path(p))==v for p,v in bindings.items())
write(out/'input_binding.json',bindings)
write(out/'completion.json',{'status':'completed','primary_contrasts':12,'all_paired_cells':432,
    'interval_scope':'unadjusted percentile95% paired resampling of10 shared batches after averaging3 fixed seeds; not training-population or independent30-batch inference',
    'practical_gate_scope':'descriptive original10% inflation /5% honest-error criterion plus positive conditional interval; no attacked-error or failed-query dominance implied',
    'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()}})
print(primary[['dataset','method','inflation_reduction_percent','inflation_lower','inflation_upper','attacked_mae_change_percent','conditional_original_practical_gate']].to_string(index=False))
