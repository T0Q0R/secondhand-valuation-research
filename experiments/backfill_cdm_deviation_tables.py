"""Bind every primary common-profile deviation contrast to a supplementary table."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from analyze_nested import read, require, sha
from run_all import write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--statistics', type=Path, required=True)
    parser.add_argument('--paper', type=Path, default=Path('paper'))
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    stats = args.statistics.resolve(); done = read(stats/'completion.json')
    require(done['status'] == 'completed' and done['cells'] == 1512
            and done['paired_batch_contrasts'] == 576, 'Complete independently audited study')
    for name, digest in done['files'].items():
        require(sha(stats/name) == digest, 'Unchanged statistics')
    data = pd.read_csv(stats/'primary_batch_contrasts.csv')
    require(len(data) == 96, 'Six source/price settings, four references, four metrics')
    metrics = ('mean_envelope', 'maximum_envelope', 'p95_envelope', 'cvar95_envelope')
    names = {'synthetic': 'Synthetic', 'jucars': 'JUCars', 'mucars': 'MUCars'}
    references = {'risk': 'Risk', 'benefit': 'Benefit', 'uniform': 'Uniform',
                  'training_selected_pure': 'Chosen pure'}
    rows, evidence = [], []
    for dataset in ('synthetic', 'jucars', 'mucars'):
        for price in ('masking', 'robust'):
            for reference in references:
                subset = data[(data.dataset == dataset) & (data.price == price)
                              & (data.reference == reference)].set_index('metric')
                require(set(subset.index) == set(metrics), 'All metrics for every reference')
                reductions = [f"{subset.loc[m, 'relative_reduction_percent']:.2f}" for m in metrics]
                tail = subset.loc['cvar95_envelope']
                interval = f"${tail.difference:.5f}\\;[{tail.lower:.5f},{tail.upper:.5f}]$"
                rows.append(' & '.join([names[dataset], price.title(), references[reference],
                                        *reductions, interval])+r'\\')
                for metric in metrics:
                    record = subset.loc[metric].to_dict()
                    evidence.append({'dataset': dataset, 'price': price, 'reference': reference,
                                     'metric': metric, **record})
    text = r'''\section{Common-profile deviation generalization}
\label{sec:cdm_deviation_generalization}
This exploratory diagnostic was specified after the original CDM outcomes
were available and before its own tail summaries were opened. It neither
refits the price estimator nor changes the primary positive-inflation
endpoint. All 108 source/seed/price/capacity cases and 1,512 method cells
are retained. For each held-out batch, every method faces the same five
peer-report profiles: truthful, no-query maximizing, fixed-seed random,
suppression-response and benefit-response. These constructions match the
calibration profile types but use held-out listings; they do not cover
all possible peer configurations.

For listing $i$ and peer profile $p$, we evaluate every legal report $h$,
reallocate the complete batch under both $h$ and the truthful report, and
compute the signed log-quote difference under each rule $k$, denoted
$D_{i,p,h,k}$. Given rule probabilities $\alpha$, the envelope is
\begin{equation}
 e_{i,p}(\alpha)=\max\{0,\max_h\sum_k\alpha_kD_{i,p,h,k}\}.
\label{eq:common_profile_envelope}
\end{equation}
The rule expectation in Eq.~\eqref{eq:common_profile_envelope} precedes
report maximization. Listings and profiles
receive equal weight, irrespective of how many reports are legal. We
retain the mean, maximum, 95th percentile and exact upper 5\% probability
mass mean (conditional value at risk, CVaR), using fractional boundary mass
where necessary. Whole-case
tails have descriptive seed means and standard deviations. The intervals
in Table~\ref{tab:cdm_deviation_generalization} apply instead to batch-level
measures: paired seed contrasts are averaged before resampling the ten
shared batches. They are conditional on the three fitted models and are
unadjusted exploratory intervals. ``Chosen pure'' is selected on calibration
rows, never on these held-out summaries. The complete exported contrasts
retain all four references and all six capacities.

With robust pricing at 10\% capacity, CDM reduces batch CVaR relative to
the calibration-selected pure rule by 7.34\% on Synthetic, 2.86\% on JUCars
and 6.81\% on MUCars, with positive conditional intervals. Its batch maxima
also have positive intervals against this reference on Synthetic and MUCars;
the JUCars interval includes zero. These gains do not establish superiority
over risk: its CVaR intervals against risk include zero on all three robust
cohorts, and mean envelopes are higher on Synthetic and MUCars. With
mask-aware pricing on MUCars, mean, 95th-percentile and CVaR envelopes are
higher than risk, with intervals excluding zero. Thus finite-profile mixing
has a bounded effect against its training-selected pure reference, while
the original absence of a consistent risk-rule advantage remains.

\begin{table*}[t]
\centering
\caption{Complete common-profile deviation diagnostic at 10\% capacity.
Columns report relative reductions in batch measures (\%); positive values
favor CDM. The final column is reference minus CDM batch CVaR, in log-quote
units, with its conditional 95\% interval. Chosen pure is selected on
calibration data. Every source, estimator and reference is retained.}
\label{tab:cdm_deviation_generalization}
\setlength{\tabcolsep}{3pt}
\begin{tabular}{lllrrrrl}
\toprule
Source & Pricing & Reference & Mean & Maximum & P95 & CVaR & CVaR difference [interval]\\
\midrule
'''+'\n'.join(rows)+r'''
\bottomrule
\end{tabular}
\end{table*}
'''
    section = args.paper.resolve()/'sections/cdm_deviation_generalization.tex'
    require(not args.receipt.exists(), 'Fresh evidence receipt')
    section.write_text(text)
    write_json(args.receipt, {'status': 'completed', 'section': str(section),
               'section_sha256': sha(section), 'statistics_completion_sha256': sha(stats/'completion.json'),
               'builder_sha256': sha(Path(__file__)), 'entries': evidence, 'table_rows': len(rows),
               'scope': 'complete exploratory primary-capacity tail diagnostic; original endpoint unchanged'})
    print('Bound all 96 primary contrasts to 24 table rows.', flush=True)


if __name__ == '__main__':
    main()
