"""Finite recovery-path diagnostics on all frozen primary factorial cells."""
from pathlib import Path
import hashlib, json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / 'outputs/matched-factorial-ten-seeds-v1'
OUT = Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

# Publicly declared report-state order, generated with bit codes rather than
# the production StateSpace class or its recovery table.
codes = sorted([m for m in range(16) if m.bit_count() <= 2], key=lambda m: (m.bit_count(), tuple(f for f in range(4) if m & (1 << f))))
lookup = {m: i for i, m in enumerate(codes)}
next_state = np.array([[lookup[m & ~(1 << f)] for f in range(4)] for m in codes])
hidden = np.array([[bool(m & (1 << f)) for f in range(4)] for m in codes])
two = np.array([m.bit_count() == 2 for m in codes])
parent = ROOT / 'outputs/matched-factorial-ten-seeds-v1-pipeline/outcome-audit/completion.json'
receipt = json.loads(parent.read_text()); assert receipt['status'] == 'completed'
paths = sorted(RUN.glob('*/seed-*/evaluation/budget-1000/*/*/*/*/completion.json'))
assert len(paths) == 720
rows, edge_rows, bindings, seen, mappings = [], [], {}, set(), {}
example = None
for cp in paths:
    assert sha(cp) == receipt['cell_completion_hashes'][str(cp.resolve())]
    source, seed_name, _, _, initial, score, feedback, allocation = cp.parent.relative_to(RUN).parts
    pair = (source, seed_name)
    if pair not in mappings:
        entries = json.loads((RUN / source / seed_name / 'fit/cell_mapping.json').read_text())
        mappings[pair] = {tuple(x['cell']): x['fit_id'] for x in entries}
    fit_id = mappings[pair][(initial, score, feedback, allocation)]
    cell = json.loads(cp.read_text())
    bindings[str(cp.relative_to(ROOT))] = sha(cp)
    sums = {'rows': 0, 'positive_recovery_rows': 0, 'gain_increasing_recovery_rows': 0,
            'two_hidden_gain_increasing_recovery_rows': 0, 'actual_positive_probability_rows': 0,
            'E_sum': 0., 'R_sum': 0., 'C_sum': 0., 'G_sum': 0., 'identity_max_error': 0.}
    for name, value in cell['batch_receipts'].items():
        bp = cp.parent / name; assert sha(bp) == value; b = json.loads(bp.read_text()); folder = bp.parent
        array_path = folder / 'arrays.npz'; frame_path = folder / 'outcomes.csv.gz'
        assert sha(array_path) == b['arrays_sha256'] and sha(frame_path) == b['outcomes_sha256']
        bindings[str(array_path.relative_to(ROOT))] = b['arrays_sha256']
        bindings[str(frame_path.relative_to(ROOT))] = b['outcomes_sha256']
        z = np.load(array_path); pred, valid, states = z['pred'], z['valid'], z['states']; n = len(states); ids = np.arange(n)
        frame = pd.read_csv(frame_path)
        raw = z['scores'][ids, states]; field = np.argmax(raw, axis=1)
        gain = raw[ids, field]; eligible = np.isfinite(gain) & (gain > 0)
        relaxed = states.copy(); relaxed[eligible] = next_state[states[eligible], field[eligible]]
        honest, before, local = pred[:, 0], pred[ids, states], pred[ids, relaxed]
        actual = frame.expected_quote_log.to_numpy()
        E, R, C, G = before - honest, local - before, actual - local, actual - honest
        err = float(np.max(abs(E + R + C - G))); assert err < 1e-12
        positive = R > 1e-10
        increases_gain = positive & (before >= honest - 1e-10) & (local > honest + 1e-10)
        sums['rows'] += n; sums['positive_recovery_rows'] += int(positive.sum())
        sums['gain_increasing_recovery_rows'] += int(increases_gain.sum())
        sums['two_hidden_gain_increasing_recovery_rows'] += int((increases_gain & two[states]).sum())
        sums['actual_positive_probability_rows'] += int((z['probabilities'] > 0).sum())
        for key, values in [('E_sum', E), ('R_sum', R), ('C_sum', C), ('G_sum', G)]: sums[key] += float(values.sum())
        sums['identity_max_error'] = max(sums['identity_max_error'], err)
        key = (source, seed_name, fit_id, folder.name)
        if key not in seen:
            seen.add(key)
            after = pred[:, next_state]
            edges = valid[:, :, None] & hidden[None, :, :]
            delta = after - pred[:, :, None]
            bad = edges & (delta > 1e-10)
            adverse = bad & (pred[:, :, None] >= honest[:, None, None] - 1e-10) & (after > honest[:, None, None] + 1e-10)
            relevant = adverse & two[None, :, None]
            edge_rows.append({'dataset': source, 'seed': int(seed_name.split('-')[1]), 'fit_id': fit_id, 'batch': folder.name,
                              'prediction_rows': n, 'eligible_success_edges': int(edges.sum()), 'positive_recovery_edges': int(bad.sum()),
                              'gain_increasing_edges': int(adverse.sum()), 'two_hidden_gain_increasing_edges': int(relevant.sum())})
            if example is None and source == 'mucars' and relevant.any():
                i, s, f = np.argwhere(relevant)[0]
                example = {'dataset': source, 'fit_id': fit_id, 'seed': int(seed_name.split('-')[1]), 'honest_quote_log': float(honest[i]),
                           'two_hidden_quote_log': float(pred[i, s]), 'one_recovered_quote_log': float(after[i, s, f]),
                           'state_mask': [bool(v) for v in hidden[s]], 'recovered_field_index': int(f),
                           'scope': 'one finite prediction-table witness, not an estimate of seller behavior or deployment prevalence'}
    for key in ['E', 'R', 'C', 'G']: sums[key + '_mean'] = sums[key + '_sum'] / sums['rows']
    rows.append({'dataset': source, 'seed': int(seed_name.split('-')[1]), 'initial_objective': initial, 'score': score,
                 'feedback': feedback, 'allocation': allocation, **sums})
pd.DataFrame(rows).to_csv(OUT / 'recovery_path_cells.csv', index=False)
pd.DataFrame(edge_rows).to_csv(OUT / 'recovery_edges_unique_fits.csv', index=False)
summary = pd.DataFrame(edge_rows).groupby('dataset').sum(numeric_only=True).drop(columns=['seed'])
summary.to_csv(OUT / 'recovery_edges_source_totals.csv')
record = {'status': 'completed', 'primary_cells': len(rows), 'returned_profile_rows': sum(r['rows'] for r in rows),
          'unique_fit_batches': len(seen), 'identity_max_error': max(r['identity_max_error'] for r in rows),
          'source_edge_totals': summary.to_dict('index'), 'witness': example,
          'scope': 'finite recovery-path diagnostic on the real four-field predictor class; no causal explanation of feedback harm and no empirical frontier optimality claim',
          'parent_outcome_receipt_sha256': sha(parent), 'checker_sha256': sha(Path(__file__))}
(OUT / 'recovery_completion.json').write_text(json.dumps(record, indent=2) + '\n')
(OUT / 'recovery_input_binding.json').write_text(json.dumps(bindings, indent=2) + '\n')
print(json.dumps(record))
