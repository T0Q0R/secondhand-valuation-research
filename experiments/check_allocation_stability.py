"""Exact represented-score condition checks and independent recovery reconstruction."""
import argparse,hashlib,itertools,json
from fractions import Fraction as F
from pathlib import Path
import numpy as np
import pandas as pd

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main(a):
    assert not a.output.exists()
    done=json.loads((a.analysis/'completion.json').read_text())
    assert done['saved_batches']==1080 and done['batch_radius_rows']==4320
    for name,h in done['files'].items():assert sha(a.analysis/name)==h
    binding=json.loads((a.analysis/'input_binding.json').read_text())
    for p,h in binding.items():assert sha(Path(p))==h
    data=pd.read_csv(a.analysis/'batch_certificates.csv')
    keys=['dataset','seed','price','score','generating_allocator','batch','relative_radius']
    assert len(data)==4320 and not data.duplicated(keys).any()
    indexed=data.set_index(keys);checked=0;maximum_numeric_error=0.
    masks=[set(c) for size in range(3) for c in itertools.combinations(range(4),size)]
    for path in sorted(a.run.glob('*/seed-*/*/*/*/batch-*/execution.npz')):
        assert sha(path)==binding[str(path)]
        dataset,seed,price,score,allocator,batch=path.parent.relative_to(a.run).parts
        key=(dataset,int(seed.split('-')[1]),price,score,allocator,int(batch.split('-')[1]))
        z=np.load(path);pairs=[];spans=[];states=z['states'];pred=z['pred']
        for i,state in enumerate(states):
            options=sorted([(F(float(v)),j) for j,v in enumerate(z['scores'][i,state]) if np.isfinite(v)],key=lambda x:(-x[0],x[1]))
            pairs.append(options)
            if options and options[0][0]>0:
                field=options[0][1];next_state=masks.index(masks[state]-{field})
                spans.append(abs(F(float(pred[i,next_state]))-F(float(pred[i,state]))))
        R=max(spans,default=F(0));positives=[opts[0][0] for opts in pairs if opts and opts[0][0]>0]
        capacity=json.loads((path.parent/'completion.json').read_text())['capacity']
        for alpha in [.001,.01,.05,.1]:
            r=indexed.loc[(*key,alpha)]
            assert r.positive_items==len(positives) and r.zero_recovery_span==(R==0)
            np.testing.assert_allclose(r.recovery_span,float(R),atol=1e-12,rtol=1e-12)
            if not positives:
                assert not r.radius_defined and not r.minimax_certificate
                assert pd.isna(r.probability_bound) and pd.isna(r.expected_quote_bound)
            else:
                delta=F(float(alpha*np.median([float(v) for v in positives])))
                support=all((opts[0][0]>delta if opts[0][0]>0 else opts[0][0]<-delta) for opts in pairs if opts)
                fields=all(len(opts)==1 or opts[0][0]-opts[1][0]>2*delta for opts in pairs if opts and opts[0][0]>0)
                m=min(positives)-delta;cert=support and fields
                assert r.radius_defined and r.support_condition==support and r.field_condition==fields and r.minimax_certificate==cert
                np.testing.assert_allclose([r.delta,r.minimum_score_floor],[float(delta),float(m)],atol=1e-12,rtol=1e-12)
                ranking=sorted(positives,reverse=True)
                top=cert and (capacity==0 or capacity>=len(ranking) or ranking[capacity-1]-ranking[capacity]>2*delta)
                assert r.top_b_constancy_certificate==top
                if cert:
                    prob=min(F(1),2*delta/m);assert r.nontrivial_probability_bound==(prob<1)
                    np.testing.assert_allclose([r.probability_bound,r.expected_quote_bound],[float(prob),float(R*prob)],atol=1e-12,rtol=1e-12)
                    maximum_numeric_error=max(maximum_numeric_error,abs(r.expected_quote_bound-float(R*prob)))
                else:assert pd.isna(r.probability_bound) and pd.isna(r.expected_quote_bound)
            checked+=1
    assert checked==4320
    groups=['dataset','price','score','generating_allocator','relative_radius']
    columns=['radius_defined','support_condition','field_condition','minimax_certificate','nontrivial_probability_bound','top_b_constancy_certificate','zero_recovery_span']
    expected=data.groupby(groups)[columns].sum();reported=pd.read_csv(a.analysis/'coverage.csv').set_index(groups)
    assert len(reported)==144 and (reported.batches_per_group==30).all()
    for ix,row in expected.iterrows():np.testing.assert_array_equal(row.to_numpy(),reported.loc[ix,columns].to_numpy())
    for name,h in done['files'].items():assert sha(a.analysis/name)==h
    a.output.mkdir(parents=True);(a.output/'checker_snapshot.py').write_bytes(Path(__file__).read_bytes())
    result={'status':'completed','batch_radius_rows':checked,'aggregate_groups':144,
            'condition_arithmetic':'exact fractions of represented scores and perturbation radii',
            'display_bound_tolerance':1e-12,'maximum_display_quote_bound_error':maximum_numeric_error,
            'parent_completion_sha256':sha(a.analysis/'completion.json'),
            'scope':'all fixed-profile sufficient conditions and recovery spans reconstructed; displayed bounds are floating approximations, no adapted-response or calibrated head-error guarantee'}
    (a.output/'completion.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['run','analysis','output']:p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
