"""Recomputed positive/heterogeneous-cost responses on a declared robust subset.

Frozen predictions/scores are reused. Responses are recomputed, never obtained
by subtracting costs from the saved zero-cost reports. Every returned profile
has a separate algebraic allocation/transition/unilateral-utility cross-check.
"""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse, fcntl, hashlib, json, sys, time
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments'))
from savval import StateSpace
from cdm_mechanism import Market
from minimax_market import MinimaxMarket
RUN = ROOT / 'outputs/matched-factorial-ten-seeds-v1'
OUT = ROOT / 'outputs/review-cost-sensitivity-v2'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp'); tmp.write_text(json.dumps(x, indent=2) + '\n'); tmp.replace(p)

def response(market, costs, allocation):
    n, s = market.pred.shape
    def candidates(i, states):
        value = market.candidate_quotes(i, states)
        if allocation == 'top_b': value = value[:, 0]
        return np.where(market.valid[i], value - costs[i], -np.inf)
    def execute(states):
        if allocation == 'minimax':
            r = market.expected_execution(states)
            return r['fields'], r['probabilities'], r['pre_quotes'], r['queried_quotes']
        q, _, fields = market.execute(states)
        return fields[:, 0], (fields[:, 0] >= 0).astype(float), market.pred[np.arange(n), states], q[:, 0]
    starts = [np.zeros(n, int), np.argmax(np.where(market.valid, market.pred - costs, -np.inf), axis=1)]
    for restart in [2, 3]:
        rng = np.random.default_rng(1931 + restart)
        starts.append(np.array([rng.choice(np.flatnonzero(v)) for v in market.valid]))
    results = []
    for initial in starts:
        states = initial.copy(); visited = {tuple(states)}; cycle = False
        for sweep in range(20):
            changed = False
            for i in range(n):
                values = candidates(i, states); best = int(np.argmax(values))
                if values[best] > values[states[i]] + 1e-8: states[i] = best; changed = True
            if not changed: break
            if tuple(states) in visited: cycle = True; break
            visited.add(tuple(states))
        fields, p, q0, q1 = execute(states); q = q0 + p * (q1 - q0)
        utility = q - costs[np.arange(n), states]
        options = np.array([candidates(i, states) for i in range(n)])
        regret = np.maximum(options.max(axis=1) - utility, 0)
        results.append({'states': states, 'fields': fields, 'p': p, 'q0': q0, 'q1': q1, 'q': q,
                        'utility': utility, 'regret': regret, 'deviation': np.maximum(options.max(axis=1) - options[:, 0], 0),
                        'cycle': cycle, 'sweeps': sweep + 1})
    return max(results, key=lambda r: float(r['utility'].sum()))

def independent_execution(pred, scores, states, capacity, allocation, masks):
    n = len(states); raw = scores[np.arange(n), states]
    fields = np.argmax(raw, axis=1); gains = raw[np.arange(n), fields]
    positive = np.isfinite(gains) & (gains > 0); fields = np.where(positive, fields, -1)
    p = np.zeros(n)
    if allocation == 'top_b':
        order = np.lexsort((np.arange(n), -gains)); selected = order[positive[order]][:capacity]; p[selected] = 1
        fields = np.where(p > 0, fields, -1)
    elif positive.sum() <= capacity: p[positive] = 1
    elif capacity > 0:
        g = np.sort(gains[positive])[::-1]; inverse = np.cumsum(1 / g)
        for k in range(capacity + 1, len(g) + 1):
            level = (k - capacity) / inverse[k - 1]
            if k == len(g) or level >= g[k]: break
        p[positive] = np.maximum(1 - level / gains[positive], 0)
    codes = [sum(1 << f for f, v in enumerate(row) if v) for row in masks]
    lookup = {code: i for i, code in enumerate(codes)}
    final = np.array([lookup[codes[s] & ~(1 << f)] if f >= 0 else s for s, f in zip(states, fields)])
    q0 = pred[np.arange(n), states]; q1 = pred[np.arange(n), final]
    return fields, p, q0, q1, q0 + p * (q1 - q0)

def worker(task):
    source, seed, feedback, allocation, scenario = task
    folder = OUT / source / f'seed-{seed}' / feedback / allocation / scenario
    cp = folder / 'completion.json'
    if cp.exists():
        c = json.loads(cp.read_text()); assert sha(folder / 'batch_summary.csv') == c['summary_sha256']
        assert c['script_sha256'] == sha(Path(__file__))
        return pd.read_csv(folder / 'batch_summary.csv').to_dict('records')
    old = RUN / source / f'seed-{seed}/evaluation/budget-1000/robust/suppression' / feedback / allocation
    space = StateSpace.build(2); rows = []; bindings = {}
    for batch in range(10):
        path = old / f'batch-{batch}/arrays.npz'; saved = old / f'batch-{batch}/outcomes.csv.gz'
        bindings[str(path)] = sha(path); bindings[str(saved)] = sha(saved)
        z = np.load(path); f = pd.read_csv(saved); pred, scores, valid = z['pred'], z['scores'], z['valid']; n = len(f)
        mean = .005 if scenario == 'uniform005' else .02
        factors = np.ones(n)
        if scenario == 'heterogeneous020':
            factors = np.array([.5 + int(hashlib.sha256(('cost-sensitivity-v2|' + str(x)).encode()).hexdigest()[:8], 16) / 2**32 for x in f.listing_id])
        cost = mean * factors[:, None] * space.masks.sum(axis=1)[None, :]
        market = MinimaxMarket(pred, scores, valid, space, 10, 0) if allocation == 'minimax' else Market(pred, scores[None], valid, space, 10, 0)
        if batch == 0 and scenario == 'uniform005':
            zero = response(market, np.zeros_like(cost), allocation)
            assert np.array_equal(zero['states'], z['states']), 'Zero-cost response differs from frozen run'
            assert np.allclose(zero['q'], f.expected_quote_log, atol=1e-10)
        r = response(market, cost, allocation)
        fields, p, q0, q1, q = independent_execution(pred, scores, r['states'], 10, allocation, space.masks)
        assert np.array_equal(fields, r['fields']) and np.allclose(p, r['p'], atol=1e-10, rtol=0)
        assert np.allclose(q, r['q'], atol=1e-10, rtol=0)
        options = np.full((n, pred.shape[1]), -np.inf)
        for i in range(n):
            for state in np.flatnonzero(valid[i]):
                trial = r['states'].copy(); trial[i] = state
                qq = independent_execution(pred, scores, trial, 10, allocation, space.masks)[-1]
                options[i, state] = qq[i] - cost[i, state]
        utility = q - cost[np.arange(n), r['states']]
        regret = np.maximum(options.max(axis=1) - utility, 0)
        assert np.allclose(regret, r['regret'], atol=1e-9, rtol=0)
        success = np.zeros(n, bool); chosen = fields >= 0; success[chosen] = space.masks[r['states'][chosen], fields[chosen]]
        target = np.expm1(f.target_log.to_numpy()); honest = pred[:, 0]
        rows.append({'dataset': source, 'seed': seed, 'feedback': feedback, 'allocation': allocation, 'scenario': scenario,
                     'batch': batch, 'n': n, 'mean_cost_per_field': float((mean * factors).mean()),
                     'inflation': float(np.maximum(q - honest, 0).mean()), 'honest_mae': float(abs(np.expm1(honest) - target).mean()),
                     'attacked_mae': float(((1 - p) * abs(np.expm1(q0) - target) + p * abs(np.expm1(q1) - target)).mean()),
                     'failed_query': float((p * ~success).mean()), 'net_deviation': float(np.maximum(options.max(axis=1) - options[:, 0], 0).mean()),
                     'max_regret': float(regret.max()), 'converged': bool((regret < 1e-7).all()), 'reports_changed_from_zero': int((r['states'] != z['states']).sum())})
        write(folder / f'batch-{batch}.json', rows[-1])
    folder.mkdir(parents=True, exist_ok=True); pd.DataFrame(rows).to_csv(folder / 'batch_summary.csv', index=False)
    write(cp, {'status': 'completed_and_corroborated', 'script_sha256': sha(Path(__file__)), 'summary_sha256': sha(folder / 'batch_summary.csv'), 'input_hashes': bindings})
    return rows

def main(workers, smoke):
    OUT.mkdir(parents=True, exist_ok=True)
    lock = (OUT / 'execution.lock').open('w'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    tasks = [(d, s, f, a, c) for d in ['synthetic', 'jucars', 'mucars'] for s in [13, 42, 2026]
             for f in ['none', 'policy'] for a in ['top_b', 'minimax'] for c in ['uniform005', 'uniform020', 'heterogeneous020']]
    if smoke: tasks = [('mucars', 13, 'none', a, 'uniform005') for a in ['top_b', 'minimax']]
    write(OUT / ('smoke-manifest.json' if smoke else 'manifest.json'), {'tasks': [list(t) for t in tasks], 'script_sha256': sha(Path(__file__)),
          'scope': 'robust initial objective, suppression score, 3 fitting seeds, existing 1000-record cohorts; post-hoc response-cost sensitivity',
          'parent_manifest_sha256': sha(RUN / 'manifest.json'), 'heterogeneous_rule': '0.02 times stable listing factor in [0.5,1.5)', 'no_retraining': True})
    rows = []; started = time.time()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(worker, task) for task in tasks]):
            rows.extend(future.result()); pd.DataFrame(rows).to_csv(OUT / ('smoke-summary.csv' if smoke else 'partial_summary.csv'), index=False)
            write(OUT / 'progress.json', {'completed_cells': len(rows) // 10, 'expected_cells': len(tasks), 'seconds': time.time() - started})
            print(f'COST CELLS {len(rows)//10}/{len(tasks)}', flush=True)
    if not smoke:
        frame = pd.DataFrame(rows); frame.to_csv(OUT / 'batch_summary.csv', index=False)
        group = frame.groupby(['dataset', 'seed', 'feedback', 'allocation', 'scenario'])
        summary = group[['inflation', 'honest_mae', 'attacked_mae', 'failed_query', 'net_deviation', 'mean_cost_per_field']].mean()
        summary['max_regret'] = group.max_regret.max(); summary['nonconverged_batches'] = group.converged.apply(lambda a: int((~a).sum()))
        summary.to_csv(OUT / 'summary.csv')
        write(OUT / 'completion.json', {'status': 'completed_and_corroborated', 'cells': len(tasks), 'batches': len(rows),
              'summary_sha256': sha(OUT / 'summary.csv'), 'manifest_sha256': sha(OUT / 'manifest.json'),
              'scope': 'independent algebraic replay and every legal unilateral utility at returned profiles; no global equilibrium guarantee'})

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--workers', type=int, default=2); parser.add_argument('--smoke', action='store_true')
    a = parser.parse_args(); main(a.workers, a.smoke)
