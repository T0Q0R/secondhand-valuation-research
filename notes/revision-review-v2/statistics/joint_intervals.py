"""Post-hoc simultaneous sensitivity from frozen crossed seed/batch tensors.

This does not create confirmatory data or finite-sample FWER guarantees.
Scales are exact conditional standard deviations of the crossed bootstrap,
not re-studentized per replicate. No production analysis helpers are imported.
"""
from pathlib import Path
import hashlib, itertools, json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
INPUT = ROOT / 'outputs/matched-factorial-ten-seeds-v1-pipeline/analysis'
OUT = Path(__file__).resolve().parent
N = 20000
RNG_SEED = 2026101307

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def scale(a):
    s, b, _ = a.shape
    grand = a.mean(axis=(0, 1))
    row = a.mean(axis=1) - grand
    col = a.mean(axis=0) - grand
    residual = a - grand - row[:, None, :] - col[None, :, :]
    return np.sqrt((row * row).sum(axis=0) / s**2 + (col * col).sum(axis=0) / b**2 + (residual * residual).sum(axis=(0, 1)) / (s * b)**2)

# Independently enumerate the exact two-by-two conditional bootstrap.
toy = np.array([[1., 5.], [3., 2.]])[:, :, None]
values = [toy[list(r)][:, list(c)].mean() for r in itertools.product(range(2), repeat=2) for c in itertools.product(range(2), repeat=2)]
assert np.isclose(scale(toy)[0], np.std(values, ddof=0), atol=1e-12)

done = json.loads((INPUT / 'completion.json').read_text())
for name in ['paired_tensors_and_draws.npz', 'contrast_specifications.json', 'contrasts.csv']:
    assert sha(INPUT / name) == done['files'][name]
metadata = json.loads((INPUT / 'contrast_specifications.json').read_text())
cells = [tuple(c) for c in metadata['cells']]
specs = metadata['contrasts']
metrics = metadata['metrics']
budget_index = metadata['budgets'].index(.1)
npz = np.load(INPUT / 'paired_tensors_and_draws.npz')
saved = pd.read_csv(INPUT / 'contrasts.csv').set_index(['dataset', 'budget', 'contrast', 'metric'])
sources = ['synthetic', 'jucars', 'mucars']
co_primary = ['positive_expected_log_inflation', 'expected_attacked_absolute_error', 'failed_query_probability']
matrices, scales, rows = [], [], []
for source in sources:
    t = npz[source + '__tensor'][budget_index]
    assert t.shape == (10, 10, 24, 8)
    a = np.stack([sum(term['coefficient'] * t[:, :, cells.index(tuple(term['cell'])), mi]
                      for term in spec['terms']) for spec in specs for mi in range(8)], axis=-1)
    matrices.append(a); scales.append(scale(a))
    for spec in specs:
        for metric in metrics:
            j = len(rows) % (len(specs) * 8)
            point = float(a[:, :, j].mean())
            old = saved.loc[(source, .1, spec['id'], metric)]
            assert np.isclose(point, old.difference, atol=2e-10, rtol=1e-9)
            rows.append({'dataset': source, 'contrast': spec['id'], 'family': spec['family'], 'metric': metric,
                         'difference': point, 'conditional_bootstrap_scale': float(scales[-1][j]),
                         'old_unadjusted_lower': old.lower, 'old_unadjusted_upper': old.upper,
                         'core36': spec['family'] == 'feedback' and metric == metrics[0],
                         'co_primary108': spec['family'] == 'feedback' and metric in co_primary})

# Every method/metric contrast shares draws within its source. Sources have
# independent batch resampling and common seed draws in the primary sensitivity.
# Source-wise Bonferroni bands do not require cross-source independence.
rng = np.random.default_rng(RNG_SEED)
seed_indices = rng.integers(0, 10, (N, 10))
seed_weights = np.array([np.bincount(row, minlength=10) for row in seed_indices]) / 10
all_standardized = []
draws = {'common_seed_indices': seed_indices}
for source, a, se in zip(sources, matrices, scales):
    bi = rng.integers(0, 10, (N, 10)); draws[source + '__batch_indices'] = bi
    bw = np.array([np.bincount(row, minlength=10) for row in bi]) / 10
    point = a.mean(axis=(0, 1))
    values = np.empty((N, a.shape[-1]))
    for begin in range(0, N, 500):
        end = min(begin + 500, N)
        values[begin:end] = np.einsum('rs,sbk,rb->rk', seed_weights[begin:end], a, bw[begin:end], optimize=True)
    for k in range(20):
        direct = a[seed_indices[k, :, None], bi[k, None, :]].mean(axis=(0, 1))
        assert np.allclose(values[k], direct, atol=1e-10, rtol=1e-10)
    nonzero = se > 1e-14
    assert np.allclose(values[:, ~nonzero], point[~nonzero], atol=1e-10)
    z = np.zeros_like(values)
    z[:, nonzero] = (values[:, nonzero] - point[nonzero]) / se[nonzero]
    all_standardized.append(z)
    print('RESAMPLED ' + source, flush=True)

frame = pd.DataFrame(rows)
z = np.concatenate(all_standardized, axis=1)
summary = {}
for name in ['core36', 'co_primary108', 'all1536']:
    member = np.ones(len(frame), bool) if name == 'all1536' else frame[name].to_numpy(bool)
    maximum = np.max(abs(z[:, member]), axis=1)
    critical = float(np.quantile(maximum, .95, method='higher'))
    adjusted = np.full(len(frame), np.nan)
    source_critical = np.full(len(frame), np.nan)
    for i, row in frame.iterrows():
        if not member[i]: continue
        se = row.conditional_bootstrap_scale
        adjusted[i] = (1 + np.count_nonzero(maximum >= abs(row.difference / se))) / (N + 1) if se > 1e-14 else 1.
    for source in sources:
        subset = member & (frame.dataset.to_numpy() == source)
        source_max = np.max(abs(z[:, subset]), axis=1)
        source_critical[subset] = np.quantile(source_max, 1 - .05 / 3, method='higher')
    lo = frame.difference.to_numpy() - critical * frame.conditional_bootstrap_scale.to_numpy()
    hi = frame.difference.to_numpy() + critical * frame.conditional_bootstrap_scale.to_numpy()
    frame[name + '_lower'] = np.where(member, lo, np.nan)
    frame[name + '_upper'] = np.where(member, hi, np.nan)
    frame[name + '_adjusted_p_approx'] = adjusted
    frame[name + '_source_bonf_lower'] = frame.difference - source_critical * frame.conditional_bootstrap_scale
    frame[name + '_source_bonf_upper'] = frame.difference + source_critical * frame.conditional_bootstrap_scale
    core = member & frame.core36.to_numpy()
    summary[name] = {'family_size': int(member.sum()), 'critical_95': critical,
                     'core_feedback_upper_below_zero': int((hi[core] < 0).sum()),
                     'core_feedback_source_bonf_upper_below_zero': int((frame.loc[core, name + '_source_bonf_upper'] < 0).sum()),
                     'critical_first_half': float(np.quantile(maximum[:N // 2], .95, method='higher')),
                     'critical_second_half': float(np.quantile(maximum[N // 2:], .95, method='higher'))}

frame.to_csv(OUT / 'simultaneous_primary_contrasts.csv', index=False)
primary = pd.read_csv(INPUT / 'contrasts.csv')
primary = primary[(primary.budget == .1) & (primary.metric == metrics[0]) & primary.inflation_reduction_percent.notna()].copy()
primary.to_csv(OUT / 'continuous_primary_effects.csv', index=False)
gates = []
for inflation_threshold, honest_threshold in itertools.product([0., 5., 10., 15., 20.], [0., 1., 5., 10.]):
    gate = (primary.inflation_reduction_percent >= inflation_threshold) & (primary.honest_mae_increase_percent <= honest_threshold)
    for (source, family), indices in primary.groupby(['dataset', 'family']).groups.items():
        gates.append({'inflation_reduction_threshold_percent': inflation_threshold, 'honest_mae_increase_threshold_percent': honest_threshold,
                      'dataset': source, 'family': family, 'passing_points': int(gate.loc[indices].sum()), 'comparisons': len(indices)})
pd.DataFrame(gates).to_csv(OUT / 'threshold_sensitivity.csv', index=False)
np.savez_compressed(OUT / 'resampling_indices.npz', **draws)
frozen_path = ROOT / 'outputs/minimax-response-full-v1-analysis/contrasts.csv'
frozen_receipt = json.loads((ROOT / 'outputs/minimax-response-full-v1-statistics-check/completion.json').read_text())
assert sha(frozen_path) == frozen_receipt['analysis_files']['contrasts.csv']
frozen = pd.read_csv(frozen_path)
frozen.to_csv(OUT / 'frozen_allocation_continuous_effects.csv', index=False)
frozen_grid = []
for inflation_threshold, honest_threshold in itertools.product([0, 5, 10, 15, 20], [0, 1, 5, 10]):
    for source, group in frozen.groupby('dataset'):
        frozen_grid.append({'inflation_reduction_threshold_percent': inflation_threshold,
                            'honest_mae_increase_threshold_percent': honest_threshold,
                            'dataset': source, 'comparisons': len(group),
                            'passing_points': int(((group.inflation_reduction_percent >= inflation_threshold) & (group.honest_mae_increase_percent <= honest_threshold)).sum())})
pd.DataFrame(frozen_grid).to_csv(OUT / 'frozen_allocation_threshold_sensitivity.csv', index=False)
record = {'status': 'completed', 'resamples': N, 'rng_seed': RNG_SEED, 'fixed_training_records': True,
          'primary_capacity': .1, 'fitting_seeds': 10, 'evaluation_batches': 10, 'results': summary,
          'scope': 'post-hoc approximate simultaneous sensitivity; not confirmatory, finite-sample FWER-certified, or training-population inference',
          'cross_source_assumption': 'shared seed indices, independent source batches; source-wise Bonferroni sensitivity avoids a cross-source dependence assumption',
          'scale': 'exact conditional crossed-bootstrap variance, checked by exhaustive 2x2 enumeration',
          'validation': 'all 1536 points match frozen CSV; 60 weighted/draw-index resamples match independently; all structural zeros retained',
          'input_hashes': {name: sha(INPUT / name) for name in ['completion.json', 'paired_tensors_and_draws.npz', 'contrast_specifications.json', 'contrasts.csv']},
          'frozen_allocation_input_sha256': sha(frozen_path),
          'checker_sha256': sha(Path(__file__)),
          'files': {p.name: sha(p) for p in OUT.iterdir() if p.is_file() and p.name != 'completion.json'}}
(OUT / 'completion.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record))
