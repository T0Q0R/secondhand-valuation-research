"""All-budget synthetic CDM figure from audited three-seed evidence."""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analyze_nested import read,require,sha
from run_all import write_json


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--audit',type=Path,required=True)
    parser.add_argument('--contrasts',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    audit,contrasts,output=args.audit.resolve(),args.contrasts.resolve(),args.output.resolve()
    done,comparison=read(audit/'completion.json'),read(contrasts/'completion.json')
    require(done['status']==comparison['status']=='completed','Completed audited evidence required')
    require(comparison['audit_completion_sha256']==sha(audit/'completion.json'),'Contrast audit binding')
    require(not comparison['execution_smoke'],'Software smoke is not a source figure')
    rows=pd.read_csv(audit/'audited_summary.csv')
    paired=pd.read_csv(contrasts/'paired_contrasts.csv')
    selected=rows[rows.dataset=='synthetic']
    require(set(selected.seed)=={13,42,2026},'Complete synthetic seed set required')
    require(not output.exists(),'Fresh figure output required')
    output.mkdir(parents=True)
    plt.rcParams.update({'font.family':'DejaVu Serif','font.size':8.5,'axes.labelsize':8.5,
                         'axes.titlesize':9,'legend.fontsize':8.5,'xtick.labelsize':8.5,
                         'ytick.labelsize':8.5,'pdf.fonttype':42,'ps.fonttype':42})
    fig,axes=plt.subplots(2,2,figsize=(7.1,4.1),gridspec_kw={'width_ratios':[1.15,1]},squeeze=False)
    styles={'cdm':('CDM','#0072B2','o','-'),'risk':('Risk priority','#D55E00','s','--'),
            'benefit':('Benefit priority','#009E73','^','-.'),'uniform':('Uniform mixture','#666666','D',':')}
    budgets=np.array([0,.01,.05,.1,.2,.3])
    for index,price in enumerate(['masking','robust']):
        left,right=axes[index]
        for method,(label,color,marker,line) in styles.items():
            group=selected[(selected.price==price)&(selected.method==method)]
            aggregate=group.groupby('budget').mean_positive_expected_log_inflation.agg(['mean','std']).reindex(budgets)
            require(not aggregate.isna().any().any(),'Full budget/seed curve required')
            left.errorbar(budgets*100,aggregate['mean'],yerr=aggregate['std'],label=label,
                          color=color,marker=marker,linestyle=line,linewidth=1.1,markersize=3.4,capsize=2)
        difference=paired[(paired.dataset=='synthetic')&(paired.price==price)&
                          (paired.reference=='risk')&(paired.metric=='positive_expected_log_inflation')].sort_values('budget')
        require(np.allclose(difference.budget,budgets),'Complete paired risk curve')
        x=difference.budget.to_numpy()*100
        right.plot(x,difference.paired_improvement,color='#0072B2',marker='o',markersize=3.4,linewidth=1.1)
        right.fill_between(x,difference.lower,difference.upper,color='#0072B2',alpha=.16)
        right.axhline(0,color='black',linewidth=.7)
        left.set_title('Mask-aware estimator' if price=='masking' else 'Robust estimator')
        right.set_title('Risk minus CDM; positive favors CDM')
        left.set_ylabel('Mean positive uplift\n(expected-log units)')
        right.set_ylabel('Paired uplift difference')
        for ax in (left,right):
            ax.axvline(10,color='#888888',linestyle=':',linewidth=.8)
            ax.set_xticks([0,10,20,30])
            ax.set_xlim(-1,31)
            ax.grid(axis='y',alpha=.2,linewidth=.5)
            ax.spines[['top','right']].set_visible(False)
            ax.set_xlabel('Verification capacity (%)')
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.94),ncol=4,frameon=False)
    fig.suptitle('Synthetic development: all three fitted seeds',fontsize=10,y=.995)
    fig.subplots_adjust(left=.10,right=.985,bottom=.105,top=.79,wspace=.39,hspace=.68)
    files=[]
    for extension in ['pdf','svg','png']:
        path=output/f'cdm_capacity_frontiers.{extension}'
        fig.savefig(path,dpi=200)
        files.append(path)
    plt.close(fig)
    write_json(output/'receipt.json',{'audit_completion_sha256':sha(audit/'completion.json'),
               'audited_summary_sha256':sha(audit/'audited_summary.csv'),
               'contrast_completion_sha256':sha(contrasts/'completion.json'),
               'contrast_csv_sha256':sha(contrasts/'paired_contrasts.csv'),'source_sha256':sha(Path(__file__)),
               'files':{p.name:sha(p) for p in files},
               'scope':'synthetic only; all six capacities; prespecified risk/benefit/uniform/CDM references; mean expected transformed uplift',
               'left_uncertainty':'sample SD over three fitted seeds; not CI',
               'right_uncertainty':'unadjusted conditional shared-batch paired bootstrap 95% interval',
               'primary_capacity':.1,'normal_mae_constraint_rule_variation':False})
    print(f'EXPORTED AUDITED CDM FIGURE {output}',flush=True)


if __name__=='__main__':main()
