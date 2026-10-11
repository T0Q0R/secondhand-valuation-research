"""Bind every complete three-seed benefit-reference cohort to manuscript text."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from analyze_nested import read, require, sha
from run_all import write_json


def main():
    parser = argparse.ArgumentParser()
    for name in ('statistics', 'paper', 'receipt'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    statistics, paper, receipt = (p.resolve() for p in
                                  (args.statistics, args.paper, args.receipt))
    require(not receipt.exists(), 'Fresh evidence receipt required')
    done = read(statistics / 'completion.json')
    require(done['status'] == 'completed' and not done['execution_smoke'],
            'Completed non-smoke statistics required')
    for name, digest in done['files'].items():
        require(sha(statistics / name) == digest, 'Statistical artifact binding')
    data = pd.read_csv(statistics / 'primary_contrasts.csv')
    require((data.budget == .1).all(), 'Prespecified primary capacity')
    source_names = {'synthetic': 'Synthetic', 'jucars': 'JUCars', 'mucars': 'MUCars'}
    rows, evidence, cohorts, incomplete, narrative = [], [], [], [], []
    for (dataset, cap), group in data.groupby(['dataset', 'train_cap'], sort=True):
        cap = int(cap)
        if not group.all_scheduled_seeds_complete.all():
            incomplete.append([dataset, cap])
            continue
        require((group.completed_training_seeds == 3).all(), 'Three fitted seeds')
        if cohorts:
            rows.append(r'\midrule')
        cohorts.append([dataset, cap])
        for index, role in enumerate(('fixed', 'tuned')):
            pair = group[(group.ours == f'{role}__sav_val') &
                         (group.reference == f'{role}__robust_benefit_no_feedback')]
            metrics = ('positive_log_inflation', 'clean_absolute_error',
                       'attack_absolute_error')
            require(len(pair) == 3 and set(pair.metric) == set(metrics),
                    'Exactly one primary contrast per metric')
            values = {metric: pair[pair.metric == metric].iloc[0] for metric in metrics}
            inflation, honest, attacked = (values[metric] for metric in metrics)
            require(honest.reference_mean > 0 and attacked.reference_mean > 0,
                    'Nonzero error reference')
            honest_change = -honest.relative_reduction_percent
            attack_change = -attacked.relative_reduction_percent
            label = source_names[dataset] if index == 0 else ''
            size = str(cap) if index == 0 else ''
            rows.append(
                f'{label} & {size} & {role.capitalize()} & '
                f'{inflation.ours_mean:.5f} & {inflation.reference_mean:.5f} & '
                f'{inflation.relative_reduction_percent:+.2f} & '
                f'$[{inflation.lower:.5f},{inflation.upper:.5f}]$ & '
                f'{honest_change:+.2f} & {attack_change:+.2f}' + r'\\')
            for metric, value in values.items():
                evidence.append({'dataset': dataset, 'train_cap': cap, 'role': role,
                                 'metric': metric, 'budget': .1,
                                 **{key: float(value[key]) for key in
                                    ('ours_mean', 'reference_mean',
                                     'relative_reduction_percent', 'difference', 'lower', 'upper')}})
            if role == 'tuned':
                reduction = inflation.relative_reduction_percent
                direction = 'lower' if reduction >= 0 else 'higher'
                interpretation = ('favors SAV-Val' if inflation.lower > 0 else
                                  'favors the reference' if inflation.upper < 0 else
                                  'crosses zero')
                narrative.append(
                    f'At {source_names[dataset]} cap {cap:,}, tuned SAV-Val has '
                    f'{abs(reduction):.2f}\\% {direction} inflation than the tuned '
                    f'ordinary-benefit robust reference; the reference-minus-SAV '
                    f'interval {interpretation}.')
    require(cohorts, 'At least one complete source/size cohort')
    full_scope=(done['all_scheduled_cases_complete'] and
                done['reference_cells']==324 and len(cohorts)==9 and not incomplete)
    completion_text=('All nine scheduled source/cap cohorts and all 324 reference '
                     'cells are independently audited, with a matching full 972-cell '
                     'tuning-parent audit. ' if full_scope else
                     'These completed cohorts do not establish completion of the scheduled\n'
                     '324-cell extension or its 972-cell tuning parent. ')
    text = r'''\subsection{Ordinary-benefit reference with equal selection allowances}
The separate extension evaluates ordinary-benefit acquisition with a static
robust estimator at the same three gap-weight trials and twelve residual
epochs. Static candidate price fits can be shared with the suppression-output
control, but the ordinary-benefit validation objective is recomputed and its
selected weight is refitted when necessary. Its outer predictions and final
action head follow its own selections. The comparison therefore does not
relabel a suppression-output policy or select a reference on evaluation data.

\begin{table*}[t]
\centering
\caption{Every fully completed three-seed source/cap cohort in the audited
ordinary-benefit allowance extension, at 10\% capacity. BEN is the static robust
predictor with ordinary-benefit acquisition. Gain is $100(\Phi_{BEN}-\Phi_{SAV})/
\Phi_{BEN}$. Error changes are SAV relative to BEN; positive values mean larger
MAE. Intervals concern the paired reference-minus-SAV inflation difference,
averaged over seeds before resampling ten shared batches. Fixed means
$\beta=0.5$; tuned selects from the same three training-internal trials.}
\label{tab:equal_benefit_reference}
\small
\begin{tabular}{lrlrrrrrr}
\toprule
Source & Cap & Role & SAV $\Phi$ & BEN $\Phi$ & Gain (\%) & Difference interval & Honest $\Delta$ (\%) & Attack $\Delta$ (\%)\\
\midrule
''' + '\n'.join(rows) + r'''
\bottomrule
\end{tabular}
\end{table*}

''' + '\n'.join(narrative) + r'''

Both roles and all preset capacities remain in the associated statistics.
''' + completion_text + r'''The conditional,
unadjusted intervals concern the fitted models and historical validation
cohorts; they are not guarantees for new markets or seller behavior.
'''
    target = paper / 'sections/equal_benefit_reference_results.tex'
    target.write_text(text)
    write_json(receipt, {'statistics_completion_sha256': sha(statistics / 'completion.json'),
                         'source_sha256': sha(Path(__file__)),
                         'section_sha256': sha(target), 'section': str(target),
                         'completed_source_caps': cohorts,
                         'incomplete_captured_source_caps': incomplete,
                         'reference_cells_in_statistics': done['reference_cells'],
                         'all_scheduled_reference_cases_in_manuscript':full_scope,
                         'evidence': evidence,
                         'scope': 'Every complete captured three-seed cohort, both roles; '
                                  'three paired primary metrics, no evaluation-best selection'})
    print(f'Bound {2 * len(cohorts)} equal-benefit table rows.', flush=True)


if __name__ == '__main__':
    main()
