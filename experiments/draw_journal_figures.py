"""Journal-width vector figures from complete, independently audited evidence."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
import pandas as pd

from analyze_nested import read, require, sha
from run_all import write_json


SOURCES = {'synthetic': 'Synthetic', 'jucars': 'JUCars', 'mucars': 'MUCars'}
BUDGETS = np.array([0, .01, .05, .1, .2, .3])


def save(fig, output, name):
    for extension in ('pdf', 'svg', 'png'):
        fig.savefig(output/f'{name}.{extension}', dpi=200)
    plt.close(fig)


def finish_axis(ax):
    ax.set(xlim=(-1, 31), xticks=[0, 5, 10, 20, 30], xlabel='Query capacity (%)')
    ax.axvline(10, color='#888888', lw=.7, ls=':', zorder=0)
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(axis='y', color='#dddddd', lw=.4)
    ax.ticklabel_format(axis='y', style='plain', useOffset=False)
    ax.yaxis.set_major_locator(plt.MaxNLocator(4))


def legend(fig, axes):
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=2, frameon=False,
               bbox_to_anchor=(.5, .99), columnspacing=1.3, handlelength=2)
    fig.subplots_adjust(left=.205, right=.975, bottom=.075, top=.88, wspace=.8, hspace=.82)


def plots(main, paired, cdm, output):
    styles = {'masking_benefit': ('Mask + benefit', '#E69F00', '^', ':'),
              'robust_no_feedback': ('Robust, no feedback', '#009E73', 's', '--'),
              'sav_benefit_head': ('SAV + benefit output', '#0072B2', 'D', '-.'),
              'sav_val': ('SAV-Val', '#000000', 'o', '-')}
    fig, axes = plt.subplots(3, 2, figsize=(5.15, 7.2))
    for row, (dataset, title) in enumerate(SOURCES.items()):
        left, right = axes[row]
        for method, (label, color, marker, line) in styles.items():
            values = main[(main.dataset == dataset)&(main.method == method)].sort_values('budget')
            require(len(values) == 6 and np.allclose(values.budget, BUDGETS), 'All preset SAV capacities')
            left.errorbar(values.budget*100, values.mean_inflation, yerr=values.seed_sd_inflation,
                          label=label, color=color, marker=marker, ls=line, lw=1.1,
                          ms=4, capsize=2, elinewidth=.65)
        values = paired[(paired.dataset == dataset)&(paired.reference == 'robust_no_feedback')&
                        (paired.metric == 'positive_log_inflation')].sort_values('budget')
        require(len(values) == 6 and values.all_scheduled_seeds_complete.all(), 'Complete paired SAV evidence')
        require(np.allclose(values.budget, BUDGETS), 'All paired budgets')
        right.axhline(0, color='#666666', lw=.7)
        right.errorbar(values.budget*100, values.difference,
                       yerr=np.stack([values.difference-values.lower, values.upper-values.difference]),
                       color='black', marker='o', ms=4, lw=1.1, capsize=2)
        left.set_title(f'({chr(97+row*2)}) {title}: inflation', loc='left')
        right.set_title(f'({chr(98+row*2)}) {title}: contrast', loc='left')
        left.set_ylabel('Mean positive\nlog-quote gap')
        right.set_ylabel('Robust minus SAV\nlog-quote gap')
        for ax in (left, right): finish_axis(ax)
    legend(fig, axes); save(fig, output, 'capacity_frontiers')
    styles = {'risk': ('Risk priority', '#D55E00', 's', '--'),
              'benefit': ('Benefit priority', '#009E73', '^', '-.'),
              'uniform': ('Uniform mixture', '#666666', 'D', ':'),
              'cdm': ('CDM', '#0072B2', 'o', '-')}
    fig, axes = plt.subplots(3, 2, figsize=(5.15, 7.2))
    for row, (dataset, title) in enumerate(SOURCES.items()):
        for col, price in enumerate(('masking', 'robust')):
            ax = axes[row, col]
            for method, (label, color, marker, line) in styles.items():
                group = cdm[(cdm.dataset == dataset)&(cdm.price == price)&(cdm.method == method)]
                require(len(group) == 18 and set(group.seed) == {13, 42, 2026}, 'All CDM budgets/seeds')
                values = group.groupby('budget').mean_positive_expected_log_inflation.agg(['mean', 'std']).reindex(BUDGETS)
                require(not values.isna().any().any(), 'Complete CDM curve')
                ax.errorbar(BUDGETS*100, values['mean'], yerr=values['std'], label=label,
                            color=color, marker=marker, ls=line, lw=1.1, ms=4, capsize=2, elinewidth=.65)
            ax.set_title(f'({chr(97+row*2+col)}) {title}: '+('mask' if col == 0 else 'robust'), loc='left')
            ax.set_ylabel('Positive expected\nlog-quote gap'); finish_axis(ax)
    legend(fig, axes); save(fig, output, 'cdm_capacity_frontiers_full')


def box(ax, x, y, w, h, title, body, color='#666666', fill='#f6f6f6'):
    ax.add_patch(FancyBboxPatch((x-w/2, y-h/2), w, h,
                boxstyle='round,pad=.03,rounding_size=.04', ec=color, fc=fill, lw=.9))
    ax.text(x, y+h*.23, title, fontsize=8.5, weight='bold', va='center', ha='center', linespacing=1.2)
    ax.text(x, y-h*.17, body, fontsize=8.5, va='center', ha='center', linespacing=1.2)


def arrow(ax, a, b):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle='-|>', mutation_scale=9, lw=.8, color='#333333'))


def diagrams(output):
    fig, ax = plt.subplots(figsize=(5.15, 3.3)); fig.subplots_adjust(left=.025, right=.975, bottom=.04, top=.94)
    ax.set(xlim=(-.65, 7.8), ylim=(-2, 2)); ax.axis('off')
    box(ax, .35, .85, 1.85, 1.25, 'A: withheld', '140,000 km\nrecorded', '#B46B00', '#fff7e8')
    box(ax, .35, -.85, 1.85, 1.25, 'B: unavailable', 'No mileage\nrecorded')
    box(ax, 2.5, 0, 1.65, 1.7, 'Same public\nreport', 'Mileage absent\nFixed ID / peers', '#0072B2', '#f1f7fc')
    box(ax, 4.6, 0, 1.65, 1.7, 'Same query\ndecision', 'Public inputs\nOne slot / query')
    box(ax, 6.75, .85, 1.6, 1.25, 'A: succeeds', '140,000 km\nrestored', '#0072B2', '#f1f7fc')
    box(ax, 6.75, -.85, 1.6, 1.25, 'B: fails', 'Still absent\nSlot consumed')
    for a,b in [((1.34,.85),(1.64,.4)),((1.34,-.85),(1.64,-.4)),((3.36,0),(3.74,0)),
                ((5.46,.4),(5.91,.85)),((5.46,-.4),(5.91,-.85))]:arrow(ax,a,b)
    ax.text(3.55,1.78,'Alternative hidden states; identical public inputs',ha='center',fontsize=9)
    ax.text(3.55,-1.73,'Illustrative record replay; no physical inspection',ha='center',fontsize=8.5)
    save(fig, output, 'missingness_example')
    fig, ax = plt.subplots(figsize=(5.15, 5.0)); fig.subplots_adjust(left=.035, right=.965, bottom=.025, top=.975)
    ax.set(xlim=(-.35, 6.35), ylim=(-.8, 7.8)); ax.axis('off')
    blue = {'color':'#0072B2', 'fill':'#f1f7fc'}
    for x,y,title,body in [(.85,6.65,'Nested target\ngeneration','Outer teacher\nInner 70/30 split'),
                           (3,6.65,'Policy-aware\nfeedback','Backbone + residual\nGuidance / response'),
                           (5.15,6.65,'Suppression\ntargets','Outer held-out quotes\nThen use outcomes'),
                           (.85,4.05,'Deployment\nvaluation','Full training cohort\nOwn 70/30 split'),
                           (3,4.05,'Deployment\naction head','Outer targets\nPublic input scores')]:
        box(ax,x,y,1.95,1.7,title,body,**blue)
    ax.text(5.15,4.05,'Offline only:\nrecorded values\nand outcomes\nform targets',ha='center',va='center',fontsize=8.5)
    for a,b in [((1.87,6.65),(1.98,6.65)),((4.02,6.65),(4.13,6.65)),
                ((1.87,4.05),(1.98,4.05)),((.85,3.17),(.85,1.73)),((3,3.17),(3,1.73))]:arrow(ax,a,b)
    ax.plot([5.15,5.15,3],[5.77,5.28,5.28],lw=.8,color='#333333');arrow(ax,(3,5.28),(3,4.93))
    ax.axhline(2.6, color='#777777', ls='--', lw=.7)
    for x,title,body in [(.85,'Public listing','Reported fields\nCurrent log quote'),
                         (3,'Budget allocation','Best missing field\nTop positive scores'),
                         (5.15,'Query / quote','Recorded-value replay\nFailed slot is spent')]:
        box(ax,x,.85,1.95,1.7,title,body)
    arrow(ax,(1.87,.85),(1.98,.85));arrow(ax,(4.02,.85),(4.13,.85))
    ax.text(3,-.49,'Deployment excludes hidden masks, source values and outcomes',ha='center',fontsize=8.5)
    save(fig,output,'sav_val_overview')


def main():
    parser=argparse.ArgumentParser()
    for name in ('main-audit','cdm-audit','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args(); a,c,o=args.main_audit.resolve(),args.cdm_audit.resolve(),args.output.resolve()
    main_done,cdm_done=read(a/'analysis_completion.json'),read(c/'completion.json')
    require(main_done['run_complete'] and cdm_done['status']=='completed' and cdm_done['cells']==1512,
            'Complete audited scientific inputs')
    inputs=[(a/'method_seed_summary.csv',main_done['outputs']['method_seed_summary.csv']),
            (a/'paired_capacity_frontiers.csv',main_done['outputs']['paired_capacity_frontiers.csv']),
            (c/'audited_summary.csv',cdm_done['files']['audited_summary.csv'])]
    for path,digest in inputs:require(sha(path)==digest,'Unchanged audited figure data')
    require(not o.exists(),'Fresh immutable journal figures');o.mkdir(parents=True)
    for path,_ in inputs:shutil.copy2(path,o/path.name)
    plt.rcParams.update({'font.family':'DejaVu Serif','font.size':9,'axes.labelsize':9,'axes.titlesize':9,
        'legend.fontsize':9,'xtick.labelsize':9,'ytick.labelsize':9,'pdf.fonttype':42,'svg.fonttype':'none'})
    plots(*(pd.read_csv(path) for path,_ in inputs),o);diagrams(o)
    shutil.copy2(Path(__file__),o/Path(__file__).name)
    write_json(o/'figure_receipt.json',{'status':'completed','journal_width_inches':5.15,
        'minimum_body_tick_font_points':8.5,'main_audit_completion_sha256':sha(a/'analysis_completion.json'),
        'cdm_audit_completion_sha256':sha(c/'completion.json'),
        'audited_inputs':{str(path):digest for path,digest in inputs},
        'files':{p.name:sha(p) for p in o.iterdir() if p.is_file()},
        'scope':'Every source/seed/capacity preserved; two-column capacity panels at journal width; '
                'all means, sample SD and paired intervals unchanged; illustrative diagrams do not depict empirical fraud.'})
    print('Exported four journal-width vector figures and exact audited input snapshots.',flush=True)


if __name__=='__main__':main()
