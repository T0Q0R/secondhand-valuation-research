"""All-budget common-bank tail contrasts after complete independent audit."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from analyze_nested import conditional_cluster_interval, read, require, sha
from run_all import write_json


METRICS = ('mean_envelope', 'maximum_envelope', 'p95_envelope', 'cvar95_envelope')
REFERENCES = ('risk', 'benefit', 'uniform', 'training_selected_pure')


def main():
    parser = argparse.ArgumentParser()
    for name in ('run', 'audit', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args(); run, audit, output = (p.resolve() for p in (args.run, args.audit, args.output))
    manifest, source_done = read(run/'manifest.json'), read(run/'completion.json')
    done, binding = read(audit/'completion.json'), read(audit/'input_binding.json')
    require(done['status'] == 'completed' and not done['execution_smoke'], 'Full independently audited diagnostics')
    require(done['cells'] == source_done['cells'] == 1512 and done['cases'] == 108, 'Every scheduled case')
    require(sha(run/'completion.json') == binding['completion_sha256'], 'Same audited diagnostic generation')
    require(sha(audit/'input_binding.json') == done['input_binding_sha256'], 'Independent audit binding')
    for folder, receipt in ((run, source_done), (audit, done)):
        for name, digest in receipt['files'].items():
            require(sha(folder/name) == digest, 'Source/audit output hash')
    require(not output.exists(), 'Fresh contrast generation')
    output.mkdir(parents=True); (output/'source_snapshot.py').write_bytes(Path(__file__).read_bytes())
    summary = pd.read_csv(audit/'audited_summary.csv')
    batches = pd.read_csv(run/'batch_summary.csv')
    require(not batches.duplicated(['dataset', 'seed', 'price', 'budget', 'batch', 'method']).any(),
            'Unique shared-batch rows')
    choices = {}
    for case in source_done['case_receipts']:
        d, s, p, b = (case[k] for k in ('dataset', 'seed', 'price', 'budget'))
        folder = run/d/f'seed-{s}'/p/f'budget-{int(round(b*10000)):04d}'
        require(sha(folder/'completion.json') == case['receipt_sha256'], 'Audited case remains unchanged')
        choices[(d, s, p, b)] = read(folder/'input_binding.json')['calibration_selected_pure']
    comparisons = []
    original = read(Path(manifest['source_run'])/'manifest.json')
    repetitions = original['config']['bootstrap_repetitions']
    for (dataset, price, budget), group in batches.groupby(['dataset', 'price', 'budget'], sort=True):
        require(set(group.seed) == {13, 42, 2026}, 'Every scheduled fitting seed')
        for reference in REFERENCES:
            paired = []
            for seed, seed_rows in group.groupby('seed'):
                name = choices[(dataset, seed, price, budget)] if reference == 'training_selected_pure' else reference
                own = seed_rows[seed_rows.method == 'cdm'].set_index('batch')
                ref = seed_rows[seed_rows.method == name].set_index('batch')
                require(set(own.index) == set(ref.index) == set(range(10)), 'Ten shared complete evaluation batches')
                paired.append(pd.DataFrame({'seed': seed, 'batch': own.index,
                              **{f'own_{metric}': own[metric].to_numpy() for metric in METRICS},
                              **{f'ref_{metric}': ref.loc[own.index, metric].to_numpy() for metric in METRICS}}))
            paired = pd.concat(paired, ignore_index=True)
            for metric in METRICS:
                paired['delta'] = paired[f'ref_{metric}']-paired[f'own_{metric}']
                averaged = paired.groupby('batch', as_index=False).delta.mean()
                interval = conditional_cluster_interval(averaged, repetitions, 912012)
                own_mean = float(paired[f'own_{metric}'].mean())
                ref_mean = float(paired[f'ref_{metric}'].mean())
                comparisons.append({'dataset': dataset, 'price': price, 'budget': budget,
                                    'reference': reference, 'metric': metric,
                                    'cdm_mean_batch_measure': own_mean, 'reference_mean_batch_measure': ref_mean,
                                    'relative_reduction_percent': 100*(ref_mean-own_mean)/ref_mean if ref_mean > 0 else None,
                                    'completed_training_seeds': 3, **interval,
                                    'scope': 'batch-level common-bank measure; conditional on three fitted models; '
                                             'seed-averaged contrasts, ten shared batches, unadjusted exploratory'})
    pd.DataFrame(comparisons).to_csv(output/'paired_batch_contrasts.csv', index=False)
    pd.DataFrame(comparisons).query('budget == .1').to_csv(output/'primary_batch_contrasts.csv', index=False)
    aggregate = summary.groupby(['dataset', 'price', 'budget', 'method'])[list(METRICS)].agg(['mean', 'std'])
    aggregate.columns = ['_'.join(column) for column in aggregate.columns]
    aggregate.reset_index().to_csv(output/'whole_case_seed_summary.csv', index=False)
    write_json(output/'completion.json', {'status': 'completed', 'execution_smoke': False,
               'cells': 1512, 'cases': 108, 'paired_batch_contrasts': len(comparisons),
               'audit_completion_sha256': sha(audit/'completion.json'),
               'diagnostic_completion_sha256': sha(run/'completion.json'),
               'source_sha256': sha(Path(__file__)),
               'paired_statistics_sha256': sha(Path(__file__).with_name('analyze_nested.py')),
               'files': {p.name: sha(p) for p in output.iterdir() if p.is_file()},
               'scope': 'every original method and budget; whole-case seed mean/SD descriptive, '
                        'intervals only for batch-level measures; primary mean-inflation conclusions unchanged'})
    print('COMPLETED COMMON-PROFILE DEVIATION CONTRASTS', flush=True)


if __name__ == '__main__':
    main()
