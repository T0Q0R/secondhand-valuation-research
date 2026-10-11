"""Constructed statistical counterexamples; never empirical performance evidence."""
import argparse, hashlib, itertools, json
from fractions import Fraction
from pathlib import Path
import numpy as np
from analyze_matched_factorial import CELLS, METRICS, specifications, paired_matrix, intervals

def main(out):
    assert not out.exists()
    tensor=np.zeros((3,4,24,len(METRICS)))
    score_effect={'suppression':2,'benefit':4,'risk':6}
    for seed,batch,ci in itertools.product(range(3),range(4),range(24)):
        initial,score,feedback,allocation=CELLS[ci]
        f=int(feedback=='policy');a=int(allocation=='minimax')
        value=100+13*seed+2*batch+7*(initial=='robust')+score_effect[score]+5*f-3*a-2*f*a
        tensor[seed,batch,ci,:]=value
    rng=np.random.default_rng(93);sd=rng.integers(0,3,(1000,3));bd=rng.integers(0,4,(1000,4))
    checked=0
    for spec in specifications():
        family=spec['family'];cell=spec['terms'][0]['cell']
        if family=='feedback':expected=-5+2*(cell[3]=='minimax')
        elif family=='allocation':expected=3+2*(cell[2]=='policy')
        elif family=='initial_objective':expected=-7
        elif family=='acquisition':expected=6-score_effect[spec['terms'][1]['cell'][1]]
        elif family=='feedback_allocation_interaction':expected=2
        elif family=='joint_policy':expected=0
        else:raise AssertionError(family)
        value=paired_matrix(tensor,spec,0)
        np.testing.assert_array_equal(value,np.full((3,4),expected))
        np.testing.assert_allclose(intervals(value,sd,bd),[expected,expected],atol=1e-12)
        checked+=1
    # Exact enumeration of both crossed draws includes non-additive cluster variation.
    matrix=np.array([[0,2],[4,8]],dtype=float)
    choices=list(itertools.product(range(2),repeat=2))
    pairs=list(itertools.product(choices,choices))
    seed_draws=np.array([s for s,b in pairs]);batch_draws=np.array([b for s,b in pairs])
    exact=[]
    for ss,bb in pairs:
        exact.append(float(sum((Fraction(int(matrix[s,b]),4) for s in ss for b in bb),Fraction(0))))
    expected=np.percentile(exact,[2.5,97.5])
    actual=intervals(matrix,seed_draws,batch_draws)
    np.testing.assert_allclose(actual,expected,atol=1e-12)
    assert actual[1]>actual[0]
    # Losing pairing manufactures variability even when every true paired effect is constant.
    baseline=np.arange(12,dtype=float).reshape(3,4)*100
    candidate=baseline-1
    paired=intervals(baseline-candidate,sd,bd)
    independent_candidate_seed=rng.integers(0,3,(1000,3))
    independent_candidate_batch=rng.integers(0,4,(1000,4))
    broken=(baseline[sd[:,:,None],bd[:,None,:]].mean(axis=(1,2))-
            candidate[independent_candidate_seed[:,:,None],independent_candidate_batch[:,None,:]].mean(axis=(1,2)))
    assert paired[0]==paired[1]==1 and np.ptp(np.percentile(broken,[2.5,97.5]))>0
    out.mkdir(parents=True)
    result={'status':'completed','scope':'constructed statistical fixtures only; not empirical performance',
            'contrast_vectors':checked,'harmful_feedback_both_allocators_positive_interaction':True,
            'positive_interaction_with_zero_joint_gain':True,'exact_crossed_draws':len(pairs),
            'nondegenerate_interval':actual.tolist(),'paired_constant_effect_interval':paired.tolist(),
            'unpaired_artificial_interval':np.percentile(broken,[2.5,97.5]).tolist(),
            'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('analyze_matched_factorial.py')]}}
    (out/'completion.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'checker_snapshot.py').write_bytes(Path(__file__).read_bytes());print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    main(p.parse_args().output)
