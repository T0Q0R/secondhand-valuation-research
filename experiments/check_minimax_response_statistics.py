"""Independently reconstruct all paired allocation statistics from outcome records."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def close(a, b):
    np.testing.assert_allclose(a, b, rtol=1e-9, atol=1e-10)

def main(run, audit, analysis, output):
    assert not output.exists()
    parent = json.loads((analysis / 'completion.json').read_text())
    assert parent['status'] == 'completed' and parent['contrasts'] == 18
    assert parent['run_completion_sha256'] == sha(run / 'completion.json')
    assert parent['audit_completion_sha256'] == sha(audit / 'completion.json')
    audit_done = json.loads((audit / 'completion.json').read_text())
    assert audit_done['status'] == 'completed' and audit_done['outcome_rows'] == 108000
    report = pd.read_csv(analysis / 'contrasts.csv')
    assert len(report) == 18 and not report.duplicated(['dataset', 'price', 'score']).any()
    expected = {(d,p,s) for d in ['synthetic','jucars','mucars']
                for p in ['masking','robust'] for s in ['benefit','suppression','risk']}
    assert set(map(tuple, report[['dataset','price','score']].to_numpy())) == expected
    metrics = ['positive_expected_log_inflation', 'honest_absolute_error',
               'expected_attacked_absolute_error', 'failed_query_probability', 'deviation_envelope']
    stored = np.load(analysis / 'paired_seed_batch_matrices.npz')
    bindings, verified, total_rows = {}, [], 0
    for r in report.itertuples(index=False):
        key = '__'.join([r.dataset,r.price,r.score])
        arrays = {}
        for allocator in ['top_b','minimax']:
            records = []
            for seed in [13,42,2026]:
                folder = run / r.dataset / f'seed-{seed}' / r.price / r.score / allocator
                paths = sorted(folder.glob('batch-*/completion.json'))
                assert len(paths) == 10
                for cp in paths:
                    assert sha(cp) == audit_done['batch_completion_hashes'][str(cp)]
                    receipt = json.loads(cp.read_text())
                    path = cp.parent / 'outcomes.csv.gz'
                    assert sha(path) == receipt['outcomes_sha256']
                    bindings[str(path)] = sha(path)
                    f = pd.read_csv(path); f['seed'] = seed
                    assert len(f) == 100
                    records.append(f)
            frame = pd.concat(records, ignore_index=True)
            assert len(frame) == 3000
            frame = frame.set_index(['seed','batch','listing_id']).sort_index()
            assert frame.index.is_unique
            arrays[allocator] = frame
            total_rows += len(frame)
        left, right = arrays['top_b'], arrays['minimax']
        assert left.index.equals(right.index)
        close(left.target_log, right.target_log)
        seeds = sorted(left.index.get_level_values('seed').unique())
        batches = sorted(left.index.get_level_values('batch').unique())
        assert len(seeds) == 3 and len(batches) == 10
        assert list(stored[key+'__seed_ids']) == seeds
        assert list(stored[key+'__batch_ids']) == batches
        sc = np.array([np.bincount(x, minlength=3) for x in stored[key+'__seed_draws']])
        bc = np.array([np.bincount(x, minlength=10) for x in stored[key+'__batch_draws']])
        assert sc.shape == (1000,3) and bc.shape == (1000,10)
        assert (sc.sum(1)==3).all() and (bc.sum(1)==10).all()
        reductions = {}
        for metric in metrics:
            # Explicit per-cluster sums, followed by count-weighted bootstrap.
            matrix = np.array([[sum(left.xs((s,b))[metric]-right.xs((s,b))[metric])/100
                                for b in batches] for s in seeds])
            close(matrix, stored[key+'__'+metric])
            center = float(matrix.sum()/30)
            draws = np.einsum('ri,ij,rj->r', sc, matrix, bc)/30
            lo, hi = np.percentile(draws, [2.5,97.5])
            for suffix, value in [('top_b',left[metric].sum()/3000),
                                  ('minimax',right[metric].sum()/3000),
                                  ('reduction',center),('lower',lo),('upper',hi)]:
                close(getattr(r,metric+'_'+suffix), value)
            reductions[metric] = center
        base = left[metrics[0]].mean()
        inflation = 100*reductions[metrics[0]]/base
        honest = -100*reductions[metrics[1]]/left[metrics[1]].mean()
        close(r.inflation_reduction_percent, inflation)
        close(r.honest_mae_increase_percent, honest)
        assert r.point_gate == (inflation >= 10 and honest <= 5)
        assert r.positive_inflation_interval == (r.positive_expected_log_inflation_lower > 0)
        for label, members in [('triple',[metrics[0],metrics[1],metrics[3]]),
                                ('including_attacked_mae',metrics[:4])]:
            vals = [reductions[m] for m in members]
            assert getattr(r,'minimax_dominates_'+label) == (min(vals)>=-1e-10 and max(vals)>1e-10)
            assert getattr(r,'top_b_dominates_'+label) == (max(vals)<=1e-10 and min(vals)<-1e-10)
        for name, frame in arrays.items():
            close(getattr(r,name+'_max_regret'), frame.regret.max())
            close(getattr(r,name+'_signed_bias'), frame.expected_signed_log_error.mean())
            n = 0
            for _, group in frame.groupby(level=['seed','batch']):
                assert group.converged.nunique() == 1
                n += not bool(group.converged.iloc[0])
            assert getattr(r,name+'_nonconverged_batches') == n
        verified.append(key)
    assert total_rows == 108000
    mutations = []
    for name, value in [('effect_direction',-matrix),('altered_endpoint',matrix+.01)]:
        try:
            close(value,matrix)
        except AssertionError:
            mutations.append(name)
        else:
            raise AssertionError('Mutation accepted')
    assert len(expected-{tuple(report.iloc[0][['dataset','price','score']])}) != 18
    mutations.append('missing_contrast')
    assert all(sha(Path(p)) == value for p,value in bindings.items())
    output.mkdir(parents=True)
    (output/'checker_snapshot.py').write_bytes(Path(__file__).read_bytes())
    result = {'status':'completed','contrasts':len(verified),'outcome_rows':total_rows,
              'metrics_per_contrast':5,'resamples':1000,'mutations_rejected':mutations,
              'scope':'independent raw-record and count-weighted statistics, gates and dominance checks; not coverage or equilibrium proof',
              'analysis_files':{p.name:sha(p) for p in analysis.iterdir() if p.is_file()},
              'outcome_hashes':bindings}
    (output/'completion.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='outcome_hashes'}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['run','audit','analysis','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args()
    main(a.run,a.audit,a.analysis,a.output)
