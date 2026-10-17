"""Claim-directed figures from audited results. No fitting or new inference.

Build anew for ten-seed evidence; inherit project typography and colors only.
Existing three-seed parameter source tables retain their original scope.
"""
from pathlib import Path
import os
for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']:
    os.environ[key] = '1'
os.nice(10)
import hashlib, json, string, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.colors import TwoSlopeNorm
from matplotlib.ticker import NullLocator, FuncFormatter

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).parent
OUT = ROOT / 'paper/figures/ten-seed-v1'
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / 'notes/results-visual-v5'))
from audit_panel_alignment import require_matplotlib_panel_alignment

plt.rcParams.update({'font.family':'sans-serif', 'font.sans-serif':['DejaVu Sans'],
    'font.size':8, 'axes.titlesize':9, 'axes.labelsize':8, 'xtick.labelsize':7,
    'ytick.labelsize':7, 'legend.fontsize':7.5, 'legend.frameon':False, 'pdf.fonttype':42, 'svg.fonttype':'none',
    'axes.spines.top':False, 'axes.spines.right':False, 'axes.linewidth':.7})
SOURCES = ['synthetic', 'jucars', 'mucars']
LABELS = ['Synthetic', 'JUCars', 'MUCars']
SOURCE_COLORS = ['#0072B2', '#D55E00', '#009E73']
WEIGHTS = [0., .1, .5, 1.]
COLORS = ['#777777', '#56B4E9', '#0072B2', '#D55E00']
MARKERS = ['o', 's', '^', 'D']
METHODS = [f'path-{w:g}-gap-0.5' for w in WEIGHTS]
M = 'mean_positive_log_inflation'
STAGE = ROOT / 'outputs/core-evidence-audit-v2/analysis'
cells = pd.read_csv(STAGE / 'rpl10/audited_cell_summaries.csv')
contrasts = pd.read_csv(STAGE / 'rpl10/paired_contrasts.csv')
paired = pd.read_csv(DATA / 'paired_seed_changes.csv')
INDEX = []


def frame(rows, cols, height, bottom=.19, left=.105, wspace=.58, hspace=.64):
    fig, axes = plt.subplots(rows, cols, figsize=(7.2, height), squeeze=False)
    fig.subplots_adjust(left=left, right=.98, bottom=bottom, top=.88, wspace=wspace, hspace=hspace)
    return fig, axes


def decorate(ax, number, title):
    ax.set_title(title, pad=12)
    ax.text(-.11, 1.07, string.ascii_lowercase[number], transform=ax.transAxes,
            fontsize=10, weight='bold')
    ax.grid(axis='y', color='#e2e2e2', lw=.45, zorder=0)


def footer(fig, text):
    fig.text(.5, .024, text, ha='center', va='bottom', fontsize=7)


def save(fig, name, source, caption, n, role):
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig, json_out=str(DATA / f'{name}.alignment.json'),
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, strict=True)
    fig.savefig(OUT / f'{name}.pdf')
    fig.savefig(OUT / f'{name}.svg')
    fig.savefig(OUT / f'{name}.png', dpi=600)
    fig.savefig(OUT / f'{name}.tiff', dpi=600, pil_kwargs={'compression':'tiff_lzw'})
    source.to_csv(DATA / f'{name}.source.csv', index=False)
    INDEX.append(dict(name=name, panels=len([a for a in fig.axes if not a.get_label().startswith('<colorbar')]),
        fitting_seeds=n, role=role, caption=caption, source_rows=len(source),
        pdf_sha256=hashlib.sha256((OUT/f'{name}.pdf').read_bytes()).hexdigest()))
    plt.close(fig)


def curve(ax, part, x, y, color, marker, label, ls='-'):
    grouped = part.groupby(x)[y].agg(['mean','min','max']).sort_index()
    xx = grouped.index.to_numpy(float)
    ax.fill_between(xx, grouped['min'], grouped['max'], color=color, alpha=.075, lw=0)
    ax.plot(xx, grouped['mean'], color=color, marker=marker, ms=3.3, lw=1.3, label=label, ls=ls)


def shared_weight_legend(fig, gap_zero=False, show_zero=True):
    handles = [Line2D([], [], color=c, marker=m, lw=1.2, ms=4, label=f'λ={w:g}')
               for w,c,m in zip(WEIGHTS,COLORS,MARKERS)]
    if not show_zero:
        handles=handles[1:]
    if gap_zero:
        handles.extend([Line2D([],[],color='#777777',ls=':',label='λ=0, β=0'),
                        Line2D([],[],color='#009E73',ls='--',label='λ=0.5, β=0')])
    fig.legend(handles=handles, loc='lower center', bbox_to_anchor=(.5,.065), ncol=3 if gap_zero else 4)


# 1. Four paired comparisons: inference for inflation, without a false ratio CI.
fig, ax = frame(1,3,3.5,bottom=.24,left=.12,wspace=.8)
candidates = ['path-0.1-gap-0.5','path-0.5-gap-0.5','path-1-gap-0.5','path-0.5-gap-0']
labels = ['λ=0.1','λ=0.5','λ=1','λ=0.5; β=0']
part = contrasts[(contrasts.budget==.1)&(contrasts.metric==M)].copy()
for j,(source,color) in enumerate(zip(SOURCES,SOURCE_COLORS)):
    a=ax[0,j];decorate(a,j,LABELS[j]);a.axvline(0,color='#888888',ls='--',lw=.7)
    z=part[part.dataset==source].set_index('candidate').loc[candidates]
    for i,(_,v) in enumerate(z.iterrows()):
        a.plot(1000*np.array([v.simultaneous_lower,v.simultaneous_upper]),[i,i],color=color,alpha=.35,lw=4)
        a.plot(1000*np.array([v.lower,v.upper]),[i,i],color=color,lw=1.6)
        a.plot(v.reference_minus_candidate*1000,i,'o',color=color,ms=4)
    a.set_yticks(range(4),labels);a.set_ylim(3.5,-.5)
    a.set_xlabel('Inflation improvement\n(0.001 log units)')
footer(fig,'Positive favors RPL. Thin: marginal 95% interval; pale: exploratory simultaneous band.\n10 fitting seeds × 10 fixed batches; all responses retained.')
save(fig,'ten_seed_primary',part,
    'Matched inflation improvement at10% query capacity, reference minus candidate. Each β=0.5 branch uses λ=0,β=0.5; the β=0 branch uses its own zero-weight control. Points are paired means. Thin segments are saved marginal percentile intervals; pale segments are saved exploratory max-deviation bands over216 metric contrasts. Ten fitting seeds share fixed populations and ten evaluation batches. Bands do not certify finite-sample FWER or new-population coverage.',10,'Primary inference and matched gap control')


# 2. All seed-level paired trade-offs, with both honest and attacked error.
z=paired[(paired.budget==.1)&(paired.gap_weight==.5)&(paired.path_weight>0)].copy()
fig, ax=frame(2,3,5.3,bottom=.19,left=.105,wspace=.58,hspace=.67)
for col,source in enumerate(SOURCES):
    for row,(metric,title) in enumerate([('honest_mae_change_pct','Honest MAE change (%)'),('attacked_mae_change_pct','Attacked MAE change (%)')]):
        a=ax[row,col];decorate(a,row*3+col,LABELS[col]);a.axhline(0,color='#aaaaaa',lw=.6);a.axvline(0,color='#aaaaaa',lw=.6)
        for weight,color,marker in zip(WEIGHTS[1:],COLORS[1:],MARKERS[1:]):
            v=z[(z.dataset==source)&(z.path_weight==weight)]
            assert len(v)==10
            a.scatter(v[metric],v.inflation_reduction_pct,s=16,marker=marker,color=color,alpha=.6,linewidths=.4)
            a.scatter(v[metric].mean(),v.inflation_reduction_pct.mean(),s=48,marker=marker,
                color=color,edgecolor='#222222',linewidths=.8,zorder=5)
        a.set_xlabel(title);a.set_ylabel('Inflation reduction (%)')
shared_weight_legend(fig,show_zero=False)
footer(fig,'Small: all 10 paired seed changes; outlined: their mean. Upper-left is favorable.\n10% capacity, β=0.5. Seed ratios differ from the headline ratio of means.')
save(fig,'ten_seed_tradeoffs',z,
    'Inflation reduction against honest and attacked MAE changes at10% capacity, all paired fitting seeds for λ0.1/0.5/1 and β0.5. Each point uses its own zero-weight seed control. Larger outlined markers are means of seed ratios, not ratios of cohort means. All30 source-seed pairs are retained at each weight. Raw points supply the variability display; no confidence region or independent replications beyond fitting seeds is claimed.',10,'Multiobjective deployment costs')


# 3. The actual budget grid, including zero queries. No interpolated settings.
z=cells[cells.method.isin(METHODS)].copy()
fig, ax=frame(2,3,5.2,bottom=.19,left=.105)
for col,source in enumerate(SOURCES):
    for row,(metric,title) in enumerate([(M,'Positive log inflation'),('failed_query_fraction','Failed queries / listings')]):
        a=ax[row,col];decorate(a,row*3+col,LABELS[col])
        for method,weight,color,marker in zip(METHODS,WEIGHTS,COLORS,MARKERS):
            v=z[(z.dataset==source)&(z.method==method)]
            curve(a,v,'budget',metric,color,marker,f'λ={weight:g}')
        a.set_xlabel('Query capacity');a.set_xticks([0,.1,.3],['0','10%','30%']);a.set_ylabel(title)
shared_weight_legend(fig)
footer(fig,'Lines: 10-seed means; shading: full seed range, not a confidence interval.\nβ=0.5; zero-query differences are estimator effects.')
save(fig,'budget_response',z,
    'Actual budget grid0/10/30%, four path weights at β0.5. Lines show seed means and shading the full ten-seed range, which is not a CI. Top panels measure strategic gain, bottom panels failed attempts per all listings, not per query. Zero-query changes must be attributed to the estimator. Straight segments connect evaluated settings only.',10,'Budget boundary and charged-failure costs')


# 4. A matched2×2 ablation complements the older eight-switch experiment.
methods=['path-0-gap-0','path-0-gap-0.5','path-0.5-gap-0','path-0.5-gap-0.5']
z=cells[(cells.budget==.1)&cells.method.isin(methods)].copy()
fig, ax=frame(1,3,3.4,bottom=.27,left=.105,wspace=.52)
for col,(source,color) in enumerate(zip(SOURCES,SOURCE_COLORS)):
    a=ax[0,col];decorate(a,col,LABELS[col])
    p=z[z.dataset==source].pivot(index='seed',columns='method',values=M)[methods]
    for seed,v in p.iterrows():a.plot(range(4),v,color=color,alpha=.2,lw=.65)
    for j,method in enumerate(methods):
        v=p[method].to_numpy();a.scatter(j+np.linspace(-.08,.08,10),v,s=12,color=color,alpha=.5)
        a.plot(j,v.mean(),'D',color='#222222',ms=4)
    a.set_xticks(range(4),['0 / 0','0 / .5','.5 / 0','.5 / .5']);a.set_xlabel('Path λ / Gap β');a.set_ylabel('Positive log inflation')
footer(fig,'10% capacity. Lines connect the same seed; dots retain all seeds; black diamonds show means.\nPath and gap terms change together only where the label explicitly says so.')
save(fig,'gap_ablation',z,
    'Matched path-by-gap2×2 intervention at10% capacity, ten seeds in each source. Each line connects one seed across four configurations. Dots retain all seed observations and black diamonds are means. This isolates the path term from the existing gap term at the tested weights; it does not assign three separate innovation claims to the earlier switch ablations.',10,'Control for the existing gap penalty')


# 5. All seeds, including weak/reversed effects, at the primary budget.
methods=['path-0.1-gap-0.5','path-0.5-gap-0.5','path-1-gap-0.5','path-0.5-gap-0']
z=paired[(paired.budget==.1)&paired.method.isin(methods)].copy()
fig, ax=frame(1,3,4.1,bottom=.22,left=.08,wspace=.35)
fig.subplots_adjust(right=.89)
limit=max(10,float(np.ceil(abs(z.inflation_reduction_pct).max()/10)*10))
normal=TwoSlopeNorm(vmin=-limit,vcenter=0,vmax=limit)
for col,source in enumerate(SOURCES):
    a=ax[0,col];decorate(a,col,LABELS[col])
    p=z[z.dataset==source].pivot(index='seed',columns='method',values='inflation_reduction_pct').sort_index()[methods]
    image=a.imshow(p.to_numpy(),aspect='auto',cmap='RdBu',norm=normal,interpolation='nearest')
    for row in range(10):
        for k in range(4):
            value=p.iloc[row,k];label=f'{value:.1f}' if abs(value)<1 else f'{value:.0f}'
            a.text(k,row,label,ha='center',va='center',fontsize=7,
                color='white' if abs(value)>limit*.65 else '#202020')
    a.set_xticks(range(4),['.1/.5','.5/.5','1/.5','.5/0']);a.set_xlabel('Path λ / Gap β')
    a.set_yticks(range(10),[str(s) for s in p.index]);a.set_ylabel('Fitting seed');a.grid(False)
bar=fig.colorbar(image,ax=list(ax.flat),fraction=.02,pad=.025);bar.ax.tick_params(labelsize=7)
bar.set_label('Inflation reduction (%)',fontsize=8)
footer(fig,'10% capacity. Each cell is a paired seed ratio against its same-gap zero-path control.\nPositive: lower inflation; negative: higher. No seed or nonconverged result is removed.')
save(fig,'seed_consistency',z,
    'Complete seed heterogeneity at10% capacity. Four nonzero path/gap configurations each use the same-gap λ0 control. All ten fitting seeds are shown per source, and positive percentages mean lower inflation. Zero-weight controls are omitted from the heatmap because their paired self-change is identically zero; the full paired source table includes them. Display labels are rounded, retaining one decimal for magnitudes below1%, with unrounded data in CSV.',10,'Heterogeneity rather than a mean-only claim')


# 6. Full response convergence boundary. All540 cells remain in the source.
z=cells.copy();fig, ax=frame(2,3,5.5,bottom=.23,left=.105,hspace=.68)
settings=list(zip(METHODS,COLORS,MARKERS,['-']*4))+[
    ('path-0-gap-0','#777777','x',':'),('path-0.5-gap-0','#009E73','+','--')]
for col,source in enumerate(SOURCES):
    for row,(metric,title) in enumerate([('nonconverged_batch_fraction','Nonconverged batches (%)'),('max_remaining_response_regret','Max regret within cell (log)')]):
        a=ax[row,col];decorate(a,row*3+col,LABELS[col])
        for method,color,marker,ls in settings:
            v=z[(z.dataset==source)&(z.method==method)].copy()
            if row==0:v[metric]*=100
            curve(a,v,'budget',metric,color,marker,method,ls)
        if row==1:
            a.set_yscale('symlog',linthresh=.0001)
            a.yaxis.set_major_formatter(FuncFormatter(lambda value,_:f'{value:g}'))
        a.set_ylim(bottom=0)
        if (z.loc[z.dataset==source,metric]==0).all():
            if row==0:
                a.set_ylim(0,1)
                a.text(.5,.6,'0 / 1800 batch replays\nnonconverged',transform=a.transAxes,
                    ha='center',va='center',fontsize=8,color='#555555')
            else:
                a.set_ylim(0,.0001)
                a.text(.5,.6,'Maximum observed\nregret = 0',transform=a.transAxes,
                    ha='center',va='center',fontsize=7.5,color='#555555')
        a.set_xlabel('Query capacity');a.set_xticks([0,.1,.3],['0','10%','30%']);a.set_ylabel(title)
shared_weight_legend(fig,gap_zero=True)
footer(fig,'All 540 cells retained. Means and full seed ranges; lower panels use a symmetric-log axis.\nMean of cell maxima is not the worst observed regret; the full worst case remains in the source.')
save(fig,'response_convergence',z,
    'Convergence boundary for all540 RPL cells and six configurations. Top panels show nonconverged batch percentages within each cell; bottom panels the maximum unilateral regret within that cell on a symmetric-log axis with linear threshold0.0001. Curves average ten cell-level values and bands span their full range; they are not CIs. All51 cells containing nonconverged batches remain, including89 such batch replays out of5400. Worst observed regret0.143721log is not hidden by the mean-of-maxima curves.',10,'Finite-response failure boundary')


# 7. Match the strengthened-search intervention to its audited contrast family.
z=pd.read_csv(STAGE/'mechanisms/paired_contrasts.csv')
z=z[(z.budget==.1)&(z.metric==M)].copy()
methods=['epoch-weak','batch-weak','epoch-strong','batch-strong']
labels=['Epoch weak','Batch weak','Epoch strong','Batch strong']
fig, ax=frame(1,3,3.5,bottom=.24,left=.14,wspace=.8)
for col,(source,color) in enumerate(zip(SOURCES,SOURCE_COLORS)):
    a=ax[0,col];decorate(a,col,LABELS[col]);a.axvline(0,color='#888888',lw=.7,ls='--')
    p=z[z.dataset==source].set_index('candidate').loc[methods]
    for j,(_,v) in enumerate(p.iterrows()):
        a.plot(1000*np.array([v.simultaneous_lower,v.simultaneous_upper]),[j,j],color=color,lw=4,alpha=.3)
        a.plot(1000*np.array([v.lower,v.upper]),[j,j],color=color,lw=1.6)
        a.plot(v.reference_minus_candidate*1000,j,'o',color=color,ms=4)
    a.set_yticks(range(4),labels);a.set_ylim(3.5,-.5)
    a.set_xlabel('Inflation improvement\n(0.001 log units)')
footer(fig,'Reference: no feedback. Positive favors feedback. Three fitting seeds, 10% capacity.\nThin: marginal 95% interval; pale: exploratory simultaneous band. These are not ten-seed results.')
save(fig,'mechanism_search_audited',z,
    'Training-response search and score refresh relative to the matched feedback-off control at10% capacity. Points are paired mean reference-minus-candidate differences; saved marginal and exploratory simultaneous intervals are shown as in the RPL primary figure. This separate intervention retains three fitting seeds and fixed populations. Stronger search can remove mean damage in some sources, but intervals and multiobjective costs prevent a universal benefit claim.',3,'Distinguish implementation-dependent feedback effects')


# 8. Explicitly mark defaults on the original parameter scans; preserve n=3.
z=pd.read_csv(ROOT/'notes/postcompute-figures-v1/parameter_sensitivity.source.csv')
fig, ax=frame(2,3,6.2,bottom=.26,left=.105,hspace=.9)
scans=[('gap_weight','beta','Gap weight',.5),('tolerance','tolerance','Gap tolerance',.02),
       ('feedback_schedule','rounds','Feedback rounds',2)]
for row,budget in enumerate([.1,.3]):
    for col,(axis,x,title,default) in enumerate(scans):
        a=ax[row,col];decorate(a,row*3+col,title)
        p=z[(z.budget==budget)&(z.axis==axis)&z.feedback].copy()
        if col in [1,2]:p=pd.concat([p,z[(z.budget==budget)&(z.method=='beta-0.5')]],ignore_index=True)
        p=p.drop_duplicates(['dataset','seed',x])
        for source,color,label in zip(SOURCES,SOURCE_COLORS,LABELS):
            curve(a,p[p.dataset==source],x,M,color,'o',label)
        assert default in p[x].unique()
        a.axvline(default,color='#555555',ls=':',lw=.8)
        values=sorted(p[x].unique())
        if col in [0,1]:
            positive=[v for v in values if v>0]
            a.set_xscale('symlog',linthresh=min(positive)/2,linscale=.2)
            a.xaxis.set_minor_locator(NullLocator())
            a.set_xlim(-min(positive)*.05,max(values)*1.15)
        a.set_xticks(values,[f'{v:g}' for v in values])
        if col in [0,1]:
            for tick in a.get_xticklabels():
                tick.set_rotation(90)
                tick.set_rotation_mode('anchor')
                tick.set_horizontalalignment('right')
        a.set_xlabel(f'{title}\nDefault = {default:g}')
        a.set_ylabel(f'Log inflation ({budget:.0%} capacity)')
fig.legend(*ax[0,0].get_legend_handles_labels(),loc='lower center',bbox_to_anchor=(.5,.065),ncol=3)
footer(fig,'Dotted: design default. Gap-weight/tolerance axes: symmetric log; all settings are ticked.\nThree-seed means and full ranges, not CIs; this does not establish an optimal default.')
save(fig,'parameter_defaults',z,
    'Existing original-feedback scans of gap weight, tolerance and feedback rounds at10/30% capacity. Vertical dotted lines explicitly mark the declared design values0.5,0.02 and2. Gap-weight and tolerance axes use symmetric-log coordinates with a linear threshold equal to half the smallest positive setting; all actual scan values are ticked. Matching default rows are included from the existing baseline. Means and full ranges use three fitting seeds. These scans do not retune RPL or prove the design values optimal.',3,'Explain defaults without test-set optimization')


# 9. The remaining six implementation settings, with declared defaults visible.
z=pd.read_csv(ROOT/'notes/postcompute-figures-v1/implementation_stability.source.csv')
fig, ax=frame(2,3,6.2,bottom=.26,left=.105,hspace=.9)
scans=[('anchor_weight',.25,'Anchor weight'),('attack_loss_weight',.5,'Attack loss weight'),
       ('learning_rate',.001,'Learning rate'),('residual_epochs',12,'Residual epochs'),
       ('head_trees',160,'Head trees'),('residual_hidden_width',64,'Hidden width')]
for j,(parameter,default,title) in enumerate(scans):
    a=ax.flat[j];decorate(a,j,title);p=z[z.parameter==parameter]
    assert (p.setting==default).any() and np.isfinite(p.inflation_ratio).all()
    for source,color,label in zip(SOURCES,SOURCE_COLORS,LABELS):
        curve(a,p[p.dataset==source],'setting','inflation_ratio',color,'o',label)
    a.axvline(default,color='#555555',ls=':',lw=.8);a.axhline(1,color='#bbbbbb',lw=.6)
    if parameter=='learning_rate':
        assert (p.setting>0).all(), 'A logarithmic scan needs strictly positive settings'
        a.set_xscale('log');a.xaxis.set_minor_locator(NullLocator())
    values=sorted(p.setting.unique());a.set_xticks(values,[f'{v:g}' for v in values])
    if j in [0,1]:
        for tick in a.get_xticklabels():
            tick.set_rotation(90)
            tick.set_rotation_mode('anchor')
            tick.set_horizontalalignment('right')
    a.set_xlabel(f'{title}\nDefault = {default:g}');a.set_ylabel('Inflation / Matched default')
fig.legend(*ax[0,0].get_legend_handles_labels(),loc='lower center',bbox_to_anchor=(.5,.065),ncol=3)
footer(fig,'10% capacity. Dotted lines mark defaults; ticks show all evaluated settings.\nThree-seed means and full ranges, not CIs. All ratios use the same-seed baseline.')
save(fig,'implementation_defaults',z,
    'Existing sensitivity to six implementation settings,10% capacity. Dotted vertical lines mark declared defaults; all evaluated settings are ticked, with learning rate on a logarithmic axis after a strict positivity check. Each seed ratio uses its unchanged matched default, which is included exactly at ratio1. Curves and ranges describe three fitting seeds, not the ten-seed RPL expansion. No default is selected by validation ranking.',3,'Complete parameter transparency')

(DATA/'figure-index.json').write_text(json.dumps(dict(figures=INDEX,
    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    manuscript_modified=False, old_figures_overwritten=False, new_training=False),indent=2)+'\n')
(DATA/'CAPTIONS.md').write_text('\n\n'.join(f"## {x['name']}\n\n{x['caption']}" for x in INDEX)+'\n')
print(json.dumps([dict(name=x['name'],panels=x['panels']) for x in INDEX],indent=2))
