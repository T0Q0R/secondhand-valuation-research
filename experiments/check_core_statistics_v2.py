"""Separate arithmetic implementation for the saved paired bootstrap analysis."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np,pandas as pd

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def check(stage,source=None,receipt_name='completion.json'):
    source=ROOT/'outputs/core-evidence-audit-v2/analysis'/stage if source is None else Path(source).resolve()
    receipt=json.loads((source/receipt_name).read_text())
    for f,h in receipt['artifacts'].items():assert sha(source/f)==h
    keys=json.loads((source/'contrast_keys.json').read_text())
    z=np.load(source/'paired_tensors_and_draws.npz');x=z['differences'];si=z['seed_draws'];bi=z['batch_draws']
    assert x.shape[1]==len(keys['seed_ids'])==receipt['fitting_seeds']
    # Independent indexing and explicit summation over every resample.
    rebuilt=np.empty_like(z['bootstrap_replicates'])
    for r in range(len(si)):
        rebuilt[:,r,:]=np.stack([x[:,s,bi[r],:].mean(1) for s in si[r]]).mean(0)
    np.testing.assert_allclose(rebuilt,z['bootstrap_replicates'],rtol=1e-10,atol=1e-9)
    point=np.stack([np.stack([x[c,s].mean(0) for s in range(x.shape[1])]).mean(0) for c in range(len(x))])
    sd=np.sqrt(((rebuilt-rebuilt.mean(1)[:,None,:])**2).sum(1)/(len(si)-1))
    active=sd>1e-12*np.maximum(1,abs(point))
    studentized=np.divide(abs(rebuilt-point[:,None,:]),sd[:,None,:],out=np.zeros_like(rebuilt),where=active[:,None,:])
    q=float(np.percentile(studentized.max((0,2)),95));assert abs(q-receipt['studentized_max_deviation_quantile'])<1e-8
    lo=np.percentile(rebuilt,2.5,axis=1);hi=np.percentile(rebuilt,97.5,axis=1)
    table=pd.read_csv(source/'paired_contrasts.csv')
    assert len(table)==len(keys['keys'])*len(keys['metrics'])
    checked=0
    for c,key in enumerate(keys['keys']):
        f=table
        for k,v in key.items():f=f[np.isclose(f[k],v) if k=='budget' else f[k]==v]
        assert len(f)==len(keys['metrics'])
        for j,metric in enumerate(keys['metrics']):
            row=f[f.metric==metric].iloc[0]
            for field,value in [('reference_minus_candidate',point[c,j]),('lower',lo[c,j]),('upper',hi[c,j]),
                ('bootstrap_sd',sd[c,j]),('simultaneous_lower',point[c,j]-q*sd[c,j]),('simultaneous_upper',point[c,j]+q*sd[c,j])]:
                np.testing.assert_allclose(row[field],value,rtol=1e-9,atol=1e-8,err_msg=field)
            checked+=1
    # Destructive negative control: a changed saved point estimate must be rejected.
    rejected=False
    try:np.testing.assert_allclose(table.reference_minus_candidate.to_numpy()+1,point.ravel(),rtol=1e-9,atol=1e-8)
    except AssertionError:rejected=True
    assert rejected
    out=ROOT/'outputs/core-evidence-audit-v2/statistics-check'/stage;out.mkdir(parents=True,exist_ok=True)
    result=dict(status='completed',stage=stage,checked_metric_contrasts=checked,recomputed_bootstrap_replicates=len(si),
        checker_sha256=sha(Path(__file__)),analysis_completion_sha256=sha(source/receipt_name),
        changed_point_negative_control_rejected=rejected,finite_sample_fwer_certified=False,
        scope='separate indexing/summation implementation of all saved crossed resamples, marginal intervals and exploratory max-deviation bands; no inference about new training populations')
    (out/'completion.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',required=True)
    p.add_argument('--analysis-dir',type=Path);p.add_argument('--analysis-receipt',default='completion.json')
    a=p.parse_args();check(a.stage,a.analysis_dir,a.analysis_receipt)
