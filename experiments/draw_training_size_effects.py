"""Supplementary paired effects from immutable, independently audited snapshots."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd

from audit_panel_alignment import require_matplotlib_panel_alignment


SOURCES = [('synthetic', 'Synthetic', 'Price units'),
           ('jucars', 'JUCars', 'JOD'), ('mucars', 'MUCars', 'MAD')]
METRICS = [('positive_log_inflation', 'Concealment', 'Millilog gap', 1000.),
           ('clean_absolute_error', 'Honest MAE', '', 1.),
           ('attack_absolute_error', 'Attacked MAE', '', 1.)]
REFERENCES = [('robust_no_feedback', 'Static SUP', '#009E73', 's', '--', -.06),
              ('sav_benefit_head', 'Component BEN', '#0072B2', 'D', '-.', 0.),
              ('robust_benefit_no_feedback', 'Ordinary BEN', '#D55E00', '^', ':', .06)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_snapshot(directory, names, prefix, output):
    receipt_path = directory/'completion.json'
    receipt = json.loads(receipt_path.read_text())
    require(receipt['status'] == 'completed', 'Completed statistics required')
    shutil.copy2(receipt_path, output/f'{prefix}_completion.json')
    frames = []
    for name in names:
        path = directory/name
        require(sha(path) == receipt['files'][name], f'Input checksum: {name}')
        shutil.copy2(path, output/f'{prefix}_{name}')
        frames.append(pd.read_csv(path))
    return receipt, frames


def selected(frame, references):
    mask = (np.isclose(frame.budget, .1) &
            frame.all_scheduled_seeds_complete.eq(True) &
            frame.completed_training_seeds.eq(3) &
            frame.ours.isin(['fixed__sav_val', 'tuned__sav_val']) &
            frame.reference.isin([f'{role}__{ref}' for role in ('fixed', 'tuned')
                                   for ref in references]))
    result = frame.loc[mask].copy()
    require(np.isfinite(result[['difference', 'lower', 'upper']]).all().all(),
            'Finite paired estimates and intervals')
    require((result.lower <= result.difference).all() and
            (result.difference <= result.upper).all(), 'Interval order')
    require((result.clusters == 10).all(), 'Ten common evaluation batches')
    require(not result.duplicated(['dataset', 'train_cap', 'ours', 'reference', 'metric']).any(),
            'Unique source-size-role-reference-metric')
    return result


def draw(frame, counts, role, output, complete=False):
    fig, axes = plt.subplots(3, 3, figsize=(7.2, 7.8))
    fig.subplots_adjust(left=.115, right=.98, bottom=.12, top=.855,
                        wspace=.66, hspace=.68)
    for row, (source, title, units) in enumerate(SOURCES):
        actual = [int(counts.get((source, cap), cap)) for cap in (1000, 2500, 5000)]
        for col, (metric, heading, ylabel, scale) in enumerate(METRICS):
            ax = axes[row, col]
            ax.axhline(0, color='#666666', lw=.8, zorder=0)
            for ref, label, color, marker, line, offset in REFERENCES:
                group = frame[(frame.dataset == source) & (frame.metric == metric) &
                              (frame.ours == f'{role}__sav_val') &
                              (frame.reference == f'{role}__{ref}')].sort_values('train_cap')
                if group.empty:
                    continue  # Pending audited cohorts are absent, never zero-filled.
                x = np.array([counts[(source, int(v))]/1000
                              for v in group.train_cap], dtype=float) + offset
                center = group.difference.to_numpy()*scale
                lower, upper = group.lower.to_numpy()*scale, group.upper.to_numpy()*scale
                ax.errorbar(x, center, yerr=np.vstack([center-lower, upper-center]),
                            label=label, color=color, marker=marker, ls=line, lw=1.2,
                            ms=4, capsize=2, elinewidth=.8, zorder=3)
            ax.set_xlim(.78, 5.22)
            ax.set_xticks(np.array(actual)/1000, [str(v) for v in actual])
            ax.set_xlabel('Training records', labelpad=4)
            ax.set_ylabel(ylabel if col == 0 else units, labelpad=4)
            ax.set_title(f'{title}: {heading}', fontsize=9, loc='left', pad=17)
            ax.text(0, 1.04, chr(97+3*row+col), transform=ax.transAxes,
                    fontsize=9, fontweight='bold', va='bottom', ha='left')
            ax.yaxis.set_major_locator(MaxNLocator(4))
            ax.ticklabel_format(axis='y', style='plain', useOffset=False)
            ax.grid(axis='y', color='#dddddd', lw=.4, zorder=0)
            ax.spines[['top', 'right']].set_visible(False)
        # Honest and attacked errors use the same native scale within a source.
        limits = [axes[row, c].get_ylim() for c in (1, 2)]
        common = (min(v[0] for v in limits), max(v[1] for v in limits))
        for col in (1, 2):
            axes[row, col].set_ylim(common)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(.5, .945),
               ncol=3, frameon=False, fontsize=9, columnspacing=1.1, handlelength=2)
    fig.suptitle(('Equal-budget tuned' if role == 'tuned' else 'Fixed-weight') +
                 ' SAV-Val: reference minus SAV', y=.985, fontsize=11)
    footer=('Positive favors SAV; shared-batch 95% intervals; all scheduled cohorts' if complete
            else 'Positive favors SAV; shared-batch 95% intervals; absent points are pending')
    fig.text(.5, .035, footer,
             ha='center', fontsize=9)
    name = f'training_size_{role}'
    require_matplotlib_panel_alignment(fig, json_out=output/f'{name}.alignment.json',
        overlay_svg=output/f'{name}.alignment.svg', tolerance_pt=1.5,
        gutter_tolerance_pt=1.5, strict=True, require_panel_labels=True)
    fig.savefig(output/f'{name}.pdf')
    fig.savefig(output/f'{name}.svg')
    fig.savefig(output/f'{name}.png', dpi=600)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    for name in ('tuning', 'benefit', 'contract', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    require(not output.exists(), 'Fresh output bundle required')
    output.mkdir(parents=True)
    tuning, (parent, summary) = read_snapshot(args.tuning,
        ['primary_method_contrasts.csv', 'audited_summary.csv'], 'tuning', output)
    benefit, (ordinary,) = read_snapshot(args.benefit, ['primary_contrasts.csv'],
                                       'benefit', output)
    p = selected(parent, ['robust_no_feedback', 'sav_benefit_head'])
    b = selected(ordinary, ['robust_benefit_no_feedback'])
    keys = ['dataset', 'train_cap', 'ours', 'metric', 'budget']
    shared = p[p.reference.str.endswith('robust_no_feedback')].merge(
        b, on=keys, suffixes=('_tuning', '_benefit'))
    require(len(shared) == len(b) and
            np.array_equal(shared.ours_mean_tuning, shared.ours_mean_benefit),
            'Exact common SAV means across independently audited snapshots')
    combined = pd.concat([p, b], ignore_index=True)
    counts = summary.groupby(['dataset', 'train_cap']).actual_train_count.agg(['min', 'max'])
    require((counts['min'] == counts['max']).all(), 'Actual count stable across methods/seeds')
    lookup = counts['min'].to_dict()
    for key, value in lookup.items():
        require(value == (4774 if key == ('jucars', 5000) else key[1]),
                'Prespecified actual training sizes')
    combined['actual_train_count'] = [lookup[(r.dataset, int(r.train_cap))]
                                      for r in combined.itertuples()]
    combined.to_csv(output/'plotted_paired_effects.csv', index=False)
    plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['DejaVu Sans'],
        'font.size': 9, 'axes.labelsize': 9, 'axes.titlesize': 9, 'legend.fontsize': 9,
        'xtick.labelsize': 9, 'ytick.labelsize': 9, 'pdf.fonttype': 42, 'svg.fonttype': 'none'})
    complete=(tuning['all_scheduled_cases_completed'] and
              benefit['all_scheduled_cases_complete'])
    if complete:
        require(tuning['cells']==972 and benefit['reference_cells']==324 and
                len(combined)==162 and len(shared)==54,
                'All nine cohorts and complete role/reference/metric grid')
    for role in ('tuned', 'fixed'):
        draw(combined, lookup, role, output, complete=complete)
    shutil.copy2(args.contract, output/'figure_contract.md')
    for name in (Path(__file__).name, 'audit_panel_alignment.py'):
        shutil.copy2(Path(__file__).parent/name, output/name)
    receipt = {'status': 'rendered_pending_qa', 'tuning_cells': tuning['cells'],
        'benefit_cells': benefit['reference_cells'],
        'all_scheduled_cases_complete': (tuning['all_scheduled_cases_completed'] and
                                        benefit['all_scheduled_cases_complete']),
        'filters': {'predicate': 'budget=0.1; all 3 scheduled seeds; SAV vs named references',
                    'tuning_before': len(parent), 'tuning_after': len(p),
                    'benefit_before': len(ordinary), 'benefit_after': len(b)},
        'points_per_figure': len(combined)//2, 'dimensions_inches': [7.2, 7.8],
        'cross_snapshot_sav_mean_matches': len(shared),
        'horizontal_offset_records': {'Static SUP': -60, 'Component BEN': 0, 'Ordinary BEN': 60},
        'interval_scope': 'Unadjusted conditional paired shared-batch bootstrap; not training-population CI',
        'files': {v.name: sha(v) for v in output.iterdir() if v.is_file()}}
    (output/'render_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'files'}, indent=2))


if __name__ == '__main__':
    main()
