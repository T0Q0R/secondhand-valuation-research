"""Corroborate/aggregate supplements after their resumable producers complete.

Final-profile and all unilateral quotations use an independent algebraic
allocation and bit transition implementation. Prediction/scoring remain shared.
"""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse, hashlib, itertools, json, sys, time
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
METRICS = ['positive_expected_log_inflation', 'honest_absolute_error', 'expected_attacked_absolute_error',
           'failed_query_probability', 'deviation_envelope', 'expected_realized_positive_log_inflation',
           'expected_signed_log_error', 'expected_squared_log_error']
CODES = sorted([m for m in range(16) if m.bit_count() <= 2], key=lambda m: (m.bit_count(), tuple(f for f in range(4) if m & (1 << f))))
MASKS = np.array([[bool(m & (1 << f)) for f in range(4)] for m in CODES])
LOOKUP = {m: i for i, m in enumerate(CODES)}
NEXT = np.array([[LOOKUP[m & ~(1 << f)] for f in range(4)] for m in CODES])
SOURCE_CACHE = {}

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp'); temporary.write_text(json.dumps(value, indent=2) + '\n'); temporary.replace(path)

def candidate_quotes(pred, scores, states, capacity, allocation):
    """All n x S unilateral quotations, independent of production markets."""
    n, states_count = pred.shape
    own_field = np.argmax(scores, axis=2)
    own_gain = scores[np.arange(n)[:, None], np.arange(states_count)[None, :], own_field]
    positive = np.isfinite(own_gain) & (own_gain > 0)
    gain = np.where(positive, own_gain, 0.)
    current = gain[np.arange(n), states]
    if allocation == 'top_b':
        peer_index = np.arange(n)[None, None, :]
        actor = np.arange(n)[:, None, None]
        ahead = ((current[None, None, :] > gain[:, :, None]) |
                 ((current[None, None, :] == gain[:, :, None]) & (peer_index < actor))) & (peer_index != actor)
        probability = positive & (ahead.sum(axis=2) < capacity)
    elif capacity == 0: probability = np.zeros_like(gain)
    else:
        trials = np.broadcast_to(current, (n, states_count, n)).copy()
        trials[np.arange(n)[:, None], np.arange(states_count)[None, :], np.arange(n)[:, None]] = gain
        ordered = np.sort(trials, axis=2)[:, :, ::-1]
        count = (ordered > 0).sum(axis=2)
        reciprocal = np.divide(1., ordered, out=np.zeros_like(ordered), where=ordered > 0)
        inverse = np.cumsum(reciprocal, axis=2)
        k = np.arange(1, n + 1)[None, None, :]
        levels = np.divide(k - capacity, inverse, out=np.zeros_like(inverse), where=inverse > 0)
        following = np.concatenate([ordered[:, :, 1:], np.zeros((n, states_count, 1))], axis=2)
        possible = (k > capacity) & (k <= count[:, :, None]) & (levels >= following)
        active = np.argmax(possible, axis=2)
        level = levels[np.arange(n)[:, None], np.arange(states_count)[None, :], active]
        probability = np.maximum(1 - np.divide(level, gain, out=np.ones_like(gain), where=gain > 0), 0)
        probability = np.where(count <= capacity, positive.astype(float), probability)
    after = pred[np.arange(n)[:, None], NEXT[np.arange(states_count)[None, :], own_field]]
    return pred + probability * (after - pred), probability, own_field, after

def probe():
    # The slow algebraic oracle is a separate implementation, no production
    # market replay/state/query helper is called in these comparisons.
    sys.path.insert(0, str(HERE))
    from cost_sensitivity import independent_execution
    rng = np.random.default_rng(7619); checked = 0
    for n in [1, 5, 20]:
        pred = rng.normal(10, .2, (n, 11)); scores = rng.normal(0, 1, (n, 11, 4))
        states = rng.integers(0, 11, n)
        for b in sorted({0, n // 2, n}):
            for allocation in ['top_b', 'minimax']:
                values = candidate_quotes(pred, scores, states, b, allocation)[0]
                for i in range(n):
                    for s in range(11):
                        changed = states.copy(); changed[i] = s
                        actual = independent_execution(pred, scores, changed, b, allocation, MASKS)[-1][i]
                        assert np.isclose(values[i, s], actual, atol=1e-11, rtol=0)
                        checked += 1
    return checked

def full_source(name):
    if name not in SOURCE_CACHE:
        path = ROOT.parent / 'experiments/data/processed' / (name + '_bvival_v1') / 'splits/validation.csv'
        expected = json.loads((ROOT / 'notes/revision-review-v2/state-audit/completion.json').read_text())['full_validation_records'][name]['input_sha256']
        assert sha(path) == expected
        frame = pd.read_csv(path)
        ranks = frame.listing_id.astype(str).map(lambda x: hashlib.sha256(('sav-val-evaluation-order-v1|' + x).encode()).hexdigest())
        SOURCE_CACHE[name] = frame.loc[ranks.sort_values(kind='stable').index].reset_index(drop=True)
    return SOURCE_CACHE[name]

def audit_cell(task):
    cp, out = task
    relative = cp.parent.relative_to(ROOT / 'outputs/review-expanded-primary-v2')
    target = out / 'cell-receipts' / relative / 'checked.json'
    if target.exists():
        old = json.loads(target.read_text()); assert old['cell_completion_sha256'] == sha(cp)
        assert old['checker_sha256'] == sha(Path(__file__))
        return old['batch_means']
    source, seed_name, initial, score, feedback, allocation = relative.parts
    record = json.loads(cp.read_text()); rows = []; listing_rows = deviations = 0
    assert sha(cp.parent / 'summary.json') == record['summary_sha256']
    assert sha(cp.parent / 'inputs.json') == record['inputs_sha256']
    source_frame = full_source(source)
    inputs = json.loads((cp.parent / 'inputs.json').read_text())
    assert inputs['evaluation_content'] == hashlib.sha256(source_frame.to_csv(index=False).encode()).hexdigest()
    assert inputs['allocation'] == allocation and inputs['budget'] == .1
    for name, value in sorted(record['batch_receipts'].items()):
        bp = cp.parent / name; assert sha(bp) == value; b = json.loads(bp.read_text())
        folder = bp.parent; assert sha(folder / 'arrays.npz') == b['arrays_sha256']; assert sha(folder / 'outcomes.csv.gz') == b['outcomes_sha256']
        z = np.load(folder / 'arrays.npz'); f = pd.read_csv(folder / 'outcomes.csv.gz')
        pred, scores, valid, states = z['pred'], z['scores'], z['valid'], z['states']; n = len(f); B = int(np.floor(.1 * n))
        batch = int(folder.name.split('-')[1]); expected = source_frame.iloc[batch*100:batch*100+n]
        assert f.listing_id.astype(str).tolist() == expected.listing_id.astype(str).tolist()
        assert np.allclose(f.target_log, expected.target_log, atol=1e-12, rtol=0)
        natural = expected[['mileage_km','transmission','fuel_type','feat_body_condition']].isna().to_numpy()
        assert np.array_equal(valid, ~(natural[:,None,:] & MASKS[None,:,:]).any(axis=2))
        assert not (np.isfinite(scores) & ~(natural[:,None,:] | MASKS[None,:,:])).any()
        assert B == b['capacity'] and valid[np.arange(n), states].all()
        options, probabilities, fields, after = candidate_quotes(pred, scores, states, B, allocation)
        q = options[np.arange(n), states]; p = probabilities[np.arange(n), states]
        field = fields[np.arange(n), states]
        chosen = p > 0; assert np.array_equal(field[chosen], z['fields'][chosen])
        assert np.allclose(p, z['probabilities'], atol=1e-10, rtol=0)
        before = pred[np.arange(n), states]; recovered = after[np.arange(n), states]
        honest = pred[:, 0]; y = f.target_log.to_numpy(); yc = np.expm1(y)
        success = MASKS[states, field]
        regret = np.maximum(np.max(np.where(valid, options, -np.inf), axis=1) - q, 0)
        deviation = np.maximum(np.max(np.where(valid, options, -np.inf), axis=1) - options[:, 0], 0)
        metrics = {'positive_expected_log_inflation': np.maximum(q - honest, 0), 'honest_absolute_error': abs(np.expm1(honest) - yc),
                   'expected_attacked_absolute_error': (1-p)*abs(np.expm1(before)-yc)+p*abs(np.expm1(recovered)-yc),
                   'failed_query_probability': p * ~success, 'deviation_envelope': deviation,
                   'expected_realized_positive_log_inflation': (1-p)*np.maximum(before-honest,0)+p*np.maximum(recovered-honest,0),
                   'expected_signed_log_error': q-y, 'expected_squared_log_error': (1-p)*(before-y)**2+p*(recovered-y)**2}
        for key, values in metrics.items(): assert np.allclose(values, f[key], atol=2e-6, rtol=1e-10), key
        assert np.allclose(regret, f.regret, atol=1e-9, rtol=0)
        assert bool(f.converged.iloc[0]) == bool((regret < 1e-7).all())
        listing_rows += n; deviations += int(valid.sum())
        rows.append({'dataset': source, 'seed': int(seed_name.split('-')[1]), 'initial_objective': initial, 'score': score,
                     'feedback': feedback, 'allocation': allocation, 'batch': int(folder.name.split('-')[1]), 'n': n,
                     **{key: float(values.mean()) for key, values in metrics.items()}, 'max_regret': float(regret.max()),
                     'nonconverged': not bool((regret < 1e-7).all())})
    write(target, {'status': 'completed', 'checker_sha256': sha(Path(__file__)), 'cell_completion_sha256': sha(cp),
                   'listing_rows': listing_rows, 'legal_unilateral_deviations': deviations, 'batch_means': rows})
    return rows

def analyze_expanded(frame, out):
    cells = list(itertools.product(['masking','robust'], ['suppression','benefit','risk'], ['none','policy'], ['top_b','minimax']))
    rows = []; means = []; rng = np.random.default_rng(2026101319)
    for source, sf in frame.groupby('dataset'):
        batches = sorted(sf.batch.unique()); seeds = sorted(sf.seed.unique())
        assert len(seeds) == 10 and len(batches) == {'jucars': 14, 'mucars': 107}[source]
        count = sf.groupby('batch').n.first().reindex(batches).to_numpy()
        tensor = np.empty((10, len(batches), 24, 8))
        for i, seed in enumerate(seeds):
            for j, batch in enumerate(batches):
                block = sf[(sf.seed == seed) & (sf.batch == batch)]
                for k, cell in enumerate(cells):
                    selected = block[(block.initial_objective == cell[0]) & (block.score == cell[1]) & (block.feedback == cell[2]) & (block.allocation == cell[3])]
                    assert len(selected) == 1
                    tensor[i,j,k] = selected[METRICS].iloc[0]
        sd = rng.integers(0,10,(10000,10)); bd = rng.integers(0,len(batches),(10000,len(batches)))
        weights = count / count.sum()
        point = np.einsum('b,sbcm->cm', weights, tensor) / 10
        for k, cell in enumerate(cells): means.append({'dataset': source, **dict(zip(['initial_objective','score','feedback','allocation'], cell)), **dict(zip(METRICS, point[k]))})
        for initial, score, allocation in itertools.product(['masking','robust'], ['suppression','benefit','risk'], ['top_b','minimax']):
            before = cells.index((initial, score, 'none', allocation)); after = cells.index((initial, score, 'policy', allocation))
            difference = tensor[:,:,before] - tensor[:,:,after]
            for metric_index, metric in enumerate(METRICS):
                matrix = difference[:,:,metric_index]; values = np.empty(10000)
                for k in range(10000):
                    draw = matrix[sd[k,:,None], bd[k,None,:]]
                    values[k] = (draw * count[bd[k]][None,:]).sum() / (10 * count[bd[k]].sum())
                lower, upper = np.quantile(values,[.025,.975])
                rows.append({'dataset': source, 'initial_objective': initial, 'score': score, 'allocation': allocation, 'metric': metric,
                             'difference': float((matrix.mean(axis=0)*weights).sum()), 'lower': lower, 'upper': upper,
                             'fitting_seeds':10, 'evaluation_batches':len(batches), 'listings':int(count.sum())})
    pd.DataFrame(rows).to_csv(out/'expanded_feedback_contrasts.csv',index=False); pd.DataFrame(means).to_csv(out/'expanded_cell_means.csv',index=False)

def finish_expanded(workers, source=None):
    run = ROOT / 'outputs/review-expanded-primary-v2'; out = ROOT / 'outputs/review-expanded-primary-v2-analysis'; out.mkdir(exist_ok=True)
    paths = sorted(run.glob((source or '*') + '/seed-*/*/*/*/*/completion.json')); assert len(paths) == (240 if source else 480)
    if source: out = out / source; out.mkdir(exist_ok=True)
    rows = []; finished = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(audit_cell,(path,out)) for path in paths]):
            rows.extend(future.result()); finished += 1
            write(out/'progress.json',{'audited_cells': finished, 'audited_batch_records': len(rows), 'expected_cells': len(paths)})
    frame = pd.DataFrame(rows); frame.to_csv(out/'corroborated_batch_means.csv',index=False); analyze_expanded(frame,out)
    write(out/'completion.json',{'status':'completed_and_corroborated','cells':len(paths),'batches':len(frame),'outcome_rows':int(frame.n.sum()),
          'checker_sha256':sha(Path(__file__)), 'parent_manifest_sha256':sha(run/'manifest.json'),
          'cell_completion_hashes': {str(p.relative_to(ROOT)): sha(p) for p in paths},
          'scope':'all final profiles, independent allocation/bit transitions and every legal unilateral utility; 10000 weighted crossed-bootstrap exploratory intervals, no fresh-cohort or training-population guarantee',
          'files':{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='completion.json'}})

def finish_cost():
    run = ROOT/'outputs/review-cost-sensitivity-v2'; out = ROOT/'outputs/review-cost-sensitivity-v2-analysis';out.mkdir(exist_ok=True)
    original = ROOT/'outputs/matched-factorial-ten-seeds-v1'
    summary = pd.read_csv(run/'summary.csv'); baseline=[]
    for source, seed, feedback, allocation in itertools.product(['synthetic','jucars','mucars'],[13,42,2026],['none','policy'],['top_b','minimax']):
        value=json.loads((original/source/f'seed-{seed}/evaluation/budget-1000/robust/suppression'/feedback/allocation/'summary.json').read_text())
        baseline.append({'dataset':source,'seed':seed,'feedback':feedback,'allocation':allocation,'scenario':'zero',
                         'inflation':value['positive_expected_log_inflation'],'honest_mae':value['honest_absolute_error'],
                         'attacked_mae':value['expected_attacked_absolute_error'],'failed_query':value['failed_query_probability'],
                         'net_deviation':value['deviation_envelope'],'max_regret':value['max_regret'],'nonconverged_batches':value['nonconverged_batches']})
    combined=pd.concat([pd.DataFrame(baseline),summary],ignore_index=True)
    means=combined.groupby(['dataset','scenario','feedback','allocation'])[['inflation','honest_mae','attacked_mae','failed_query','net_deviation']].mean().reset_index()
    contrasts=[]
    for (source,scenario,allocation), group in combined.groupby(['dataset','scenario','allocation']):
        b=group[group.feedback=='none'].set_index('seed');a=group[group.feedback=='policy'].set_index('seed');assert set(b.index)==set(a.index)=={13,42,2026}
        contrasts.append({'dataset':source,'scenario':scenario,'allocation':allocation,**{m:float((b[m]-a[m]).mean()) for m in ['inflation','honest_mae','attacked_mae','failed_query','net_deviation']}})
    combined.to_csv(out/'all_seed_cells.csv',index=False);means.to_csv(out/'source_means.csv',index=False);pd.DataFrame(contrasts).to_csv(out/'feedback_point_contrasts.csv',index=False)
    write(out/'completion.json',{'status':'completed','posthoc':True,'seeds':3,'new_positive_cost_cells':108,'zero_cost_reference_cells':36,
          'scope':'all declared cost conditions; point outcomes on robust/suppression subset, no full-factorial or confirmatory claim',
          'parent_completion_sha256':sha(run/'completion.json'),'script_sha256':sha(Path(__file__)),
          'files':{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='completion.json'}})

def main(kind,workers,source=None):
    checked=probe();print('ALGEBRAIC PROBES '+str(checked),flush=True)
    name='review-expanded-primary-v2' if kind=='expanded' else 'review-cost-sensitivity-v2'
    if not source:
        while not (ROOT/'outputs'/name/'completion.json').exists(): time.sleep(15)
    if kind=='expanded': finish_expanded(workers,source)
    else: finish_cost()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--kind',choices=['expanded','cost'],required=True);p.add_argument('--workers',type=int,default=6);p.add_argument('--source',choices=['jucars','mucars']);p.add_argument('--probe-only',action='store_true');a=p.parse_args()
    if a.probe_only:print('ALGEBRAIC PROBES '+str(probe()))
    else:main(a.kind,a.workers,a.source)
