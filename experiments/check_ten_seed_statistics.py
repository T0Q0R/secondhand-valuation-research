"""Rebuild contrast matrices from source records; independently weight resamples."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,indent=2)+'\n')
def close(a,b):
    if not np.allclose(a,b,atol=1e-12,rtol=1e-10):raise AssertionError('Statistic reconstruction mismatch')

def main(a):
    run,out=a.run.resolve(),a.output.resolve();done=read(run/'completion.json');manifest=read(run/'manifest.json')
    assert done['status']=='selected-source-union-audited' and done['training_seeds_per_source']==10
    initial=sha(run/'completion.json')
    for p,d in done['files'].items():assert sha(run/p)==d
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True);(out/'checker_snapshot.py').write_bytes(Path(__file__).read_bytes())
    report=pd.read_csv(run/'primary_contrasts.csv');inputs=read(run/'input_binding.json')
    frames={};source_hashes={}
    for pair in manifest['pair_receipts']:
        p=Path(pair['root'])/pair['dataset']/f"seed-{pair['seed']}"/'per_listing_outcomes.csv.gz'
        assert sha(p)==inputs[str(p)];source_hashes[str(p)]=sha(p)
        frame=pd.read_csv(p);frames[(pair['dataset'],pair['seed'])]=frame[frame.budget==.1]
    with np.load(run/'paired_batch_matrices.npz') as z:stored={k:z[k] for k in z.files}
    seeds=stored['seeds'];assert len(seeds)==len(set(seeds))==10
    batches=stored['batch_draws'];draws=stored['seed_draws']
    assert batches.shape==draws.shape==(1000,10)
    assert ((batches>=0)&(batches<10)).all() and ((draws>=0)&(draws<10)).all()
    bc=np.array([np.bincount(row,minlength=10) for row in batches])
    sc=np.array([np.bincount(row,minlength=10) for row in draws])
    checked=[];mutations=[]
    for _,r in report.iterrows():
        rows=[]
        for seed in seeds:
            frame=frames[(r.dataset,int(seed))]
            ours=frame[frame.method=='sav_val'].set_index('listing_id')
            reference=frame[frame.method==r.reference].set_index('listing_id')
            assert ours.index.is_unique and reference.index.is_unique and set(ours.index)==set(reference.index)
            reference=reference.loc[ours.index];assert np.array_equal(ours.batch,reference.batch)
            delta=reference.positive_log_inflation.to_numpy()-ours.positive_log_inflation.to_numpy()
            rows.append([float(delta[ours.batch.to_numpy()==batch].mean()) for batch in range(10)])
        matrix=np.array(rows);close(matrix,stored[r.dataset+'__'+r.reference])
        # Count-weighted sums are independent of the generator's indexed grid.
        conditional=bc@matrix.mean(0)/10
        crossed=np.sum((sc@matrix)*bc,axis=1)/100
        close(matrix.mean(),r.difference)
        close(np.quantile(conditional,[.025,.975]),[r.conditional_batch_lower,r.conditional_batch_upper])
        close(np.quantile(crossed,[.025,.975]),[r.seed_batch_lower,r.seed_batch_upper])
        close(np.std(matrix.mean(1),ddof=1),r.seed_difference_sd)
        if not mutations:
            for name,wrong,expected in [('effect_direction',-matrix,matrix),
                    ('interval_endpoint',r.seed_batch_lower+.1,np.quantile(crossed,.025))]:
                try:close(wrong,expected)
                except AssertionError:mutations.append(name)
                else:raise AssertionError('Corruption accepted')
            assert len(seeds[:-1])!=10;mutations.append('missing_seed')
        checked.append({'dataset':r.dataset,'reference':r.reference,'difference':float(matrix.mean()),
                        'seed_batch_interval':np.quantile(crossed,[.025,.975]).tolist()})
    assert sha(run/'completion.json')==initial and all(sha(Path(p))==v for p,v in source_hashes.items())
    write(out/'completion.json',{'status':'completed','contrasts':len(checked),'source_seed_pairs':len(frames),
        'resamples_per_contrast':1000,'mutations_rejected':mutations,'parent_completion_sha256':initial,
        'scope':'independent record-level contrast and count-weighted bootstrap reconstruction; not a guarantee of nominal coverage with10 shared batches',
        'checked':checked,'source_outcome_hashes':source_hashes,'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()}})
    print(json.dumps({'contrasts':len(checked),'source_seed_pairs':len(frames),'mutations':mutations}))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('run','output'):p.add_argument('--'+n,type=Path,required=True)
    main(p.parse_args())
