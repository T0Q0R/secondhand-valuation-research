"""Full-grid and paired-selection evidence; no simulated or omitted observations."""
from pathlib import Path
import sys,json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
ROOT=Path(__file__).resolve().parents[2];N=Path(__file__).parent
sys.path.insert(0,str(ROOT/'notes/results-visual-v5'))
from audit_panel_alignment import require_matplotlib_panel_alignment

def main():
    assert json.loads((N/'gap/verification.json').read_text())['status']=='all_candidates_and_selection_checked'
    data=pd.read_csv(N/'gap/all-candidate-cells.csv');selected=pd.read_csv(N/'gap/selected-cells.csv')
    assert len(data)==210 and len(selected)==60
    out=ROOT/'paper/figures/review-v1';out.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['DejaVu Sans'],
      'font.size':8,'axes.titlesize':9,'axes.labelsize':8,'xtick.labelsize':7.5,'ytick.labelsize':7.5,
      'legend.fontsize':8,'legend.frameon':False,'pdf.fonttype':42,'svg.fonttype':'none',
      'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7})
    fig,axes=plt.subplots(2,3,figsize=(7.2,5.7))
    fig.subplots_adjust(left=.095,right=.975,bottom=.16,top=.87,hspace=.70,wspace=.45)
    labels=['Synthetic','JUCars','MUCars'];sources=['synthetic','jucars','mucars'];source_colors=['#0072B2','#D55E00','#009E73']
    colors={'rpl':'#0072B2','gap':'#D55E00'};rows=[];paired=[]
    for col,(source,label) in enumerate(zip(sources,labels)):
        ax=axes[0,col];d=data[data.source==source].copy()
        base=d[d.method=='path-0-gap-0.5'].set_index('seed')
        d['honest_change_pct']=[100*(r.clean_mae/base.loc[r.seed,'clean_mae']-1) for r in d.itertuples()]
        d['inflation_reduction_pct']=[100*(1-r.mean_positive_log_inflation/base.loc[r.seed,'mean_positive_log_inflation']) for r in d.itertuples()]
        rows.extend(d.to_dict('records'))
        for family,weights,marker in [('rpl',[0.,.1,.5,1.],'o'),('gap',[.5,1.,2.,4.],'s')]:
            q=d[d.beta==.5] if family=='rpl' else d[d.path_weight==0]
            key='path_weight' if family=='rpl' else 'beta'
            ax.scatter(q.honest_change_pct,q.inflation_reduction_pct,s=9,c=colors[family],marker=marker,alpha=.16,linewidths=0)
            means=q.groupby(key)[['honest_change_pct','inflation_reduction_pct']].mean().reindex(weights)
            ax.plot(means.honest_change_pct,means.inflation_reduction_pct,color=colors[family],lw=1)
            mean_markers={'rpl':['D','o','^','P'],'gap':['D','s','v','X']}
            for index,(_,r) in enumerate(means.iloc[1:].iterrows(),1):
                ax.scatter([r.honest_change_pct],[r.inflation_reduction_pct],
                   marker=mean_markers[family][index],s=27,c=colors[family],zorder=6)
        ax.scatter([0],[0],c='#333333',marker='D',s=18,zorder=5)
        ax.set_title(label,pad=15);ax.set_xlabel('Honest MAE change (%)')
        ax.axvline(0,color='#cccccc',lw=.5,zorder=0);ax.axhline(0,color='#cccccc',lw=.5,zorder=0)
        ax.grid(axis='y',color='#e3e3e3',lw=.5,zorder=0)
        ax=axes[1,col]
        a=selected[(selected.source==source)&(selected.family=='rpl')].set_index('seed')
        b=selected[(selected.source==source)&(selected.family=='gap')].set_index('seed').reindex(a.index)
        x=100*(b.clean_mae/a.clean_mae-1);y=100*(b.mean_positive_log_inflation/a.mean_positive_log_inflation-1)
        assert len(x)==10 and np.isfinite(x).all() and np.isfinite(y).all()
        for seed in a.index:paired.append(dict(source=source,seed=seed,honest_change_pct=x.loc[seed],inflation_change_pct=y.loc[seed]))
        ax.scatter(x,y,c=source_colors[col],s=20,alpha=.7,linewidths=.3,edgecolors='white')
        ax.scatter([x.mean()],[y.mean()],c='#111111',marker='D',s=32,zorder=5)
        ax.axvline(0,color='#999999',lw=.7,zorder=0);ax.axhline(0,color='#999999',lw=.7,zorder=0)
        ax.set_title('OOF-selected: Gap − RPL',fontsize=8.5,pad=15)
        ax.set_xlabel('Honest MAE change (%)');ax.grid(axis='y',color='#e3e3e3',lw=.5,zorder=0)
    # Common y scales within each inferential row, preserving every data point.
    r=pd.DataFrame(rows);p=pd.DataFrame(paired)
    lo=min(0,r.inflation_reduction_pct.min());hi=max(0,r.inflation_reduction_pct.max())
    margin=.15*(hi-lo)
    for ax in axes[0]:ax.set_ylim(lo-margin,hi+margin);ax.margins(x=.28)
    lo=min(0,p.inflation_change_pct.min());hi=max(0,p.inflation_change_pct.max());margin=.15*max(hi-lo,1)
    for ax in axes[1]:ax.set_ylim(lo-margin,hi+margin);ax.margins(x=.18)
    axes[0,0].set_ylabel('Inflation reduction (%)');axes[1,0].set_ylabel('Inflation change (%)')
    for index,ax in enumerate(axes.ravel()):
        ax.annotate('abcdef'[index],xy=(0,1),xytext=(-13,12),xycoords='axes fraction',
                    textcoords='offset points',ha='left',va='bottom',fontweight='bold',fontsize=10)
    handles=[Line2D([],[],color='#333333',marker='D',ls='none',label='Common: λ 0, β .5')]
    for family,weights,markers in [('rpl',[.1,.5,1],['o','^','P']),('gap',[1,2,4],['s','v','X'])]:
        for weight,marker in zip(weights,markers):
            handles.append(Line2D([],[],color=colors[family],marker=marker,ls='none',
               label=('RPL: λ ' if family=='rpl' else 'Gap-only: β ')+f'{weight:g}'))
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.52,1.0),ncol=4,columnspacing=1.3,fontsize=7.5)
    fig.text(.5,.07,'Top: all ten seeds and candidate means. Bottom: ten paired seeds and mean (black diamond).',ha='center',fontsize=7.5)
    fig.text(.5,.035,'Fixed cohorts, 10% capacity. Full observed scatter; no confidence region or interpolation claim.',ha='center',fontsize=7.5)
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig,json_out=str(out/'gap-tradeoffs.alignment.json'),
       overlay_svg=str(out/'gap-tradeoffs.alignment.svg'),tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
    fig.savefig(out/'gap-tradeoffs.pdf')
    fig.savefig(out/'gap-tradeoffs.svg')
    fig.savefig(out/'gap-tradeoffs.png',dpi=600)
    r.to_csv(out/'gap-tradeoffs-grid.csv',index=False);p.to_csv(out/'gap-tradeoffs-paired.csv',index=False)
    plt.close(fig)

if __name__=='__main__':main()
