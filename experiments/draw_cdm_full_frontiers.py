"""All three-source CDM capacity curves from complete hash-bound audits."""
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
    for name in ('audit','contrasts','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();audit,contrasts,output=[getattr(args,n).resolve() for n in ('audit','contrasts','output')]
    done,stats=read(audit/'completion.json'),read(contrasts/'completion.json')
    require(done['status']==stats['status']=='completed' and done['cells']==1512,'Complete audited CDM matrix')
    require(done['all_scheduled_pairs_completed'] and stats['all_scheduled_pairs_completed'],'All nine pairs')
    require(stats['audit_completion_sha256']==sha(audit/'completion.json'),'Statistics audit binding')
    require(sha(audit/'audited_summary.csv')==done['files']['audited_summary.csv'],'Audited source summary')
    require(sha(contrasts/'paired_contrasts.csv')==stats['files']['paired_contrasts.csv'],'Statistics binding')
    require(not output.exists(),'Fresh immutable figure');output.mkdir(parents=True)
    rows=pd.read_csv(audit/'audited_summary.csv');sources={'synthetic':'Synthetic','jucars':'JUCars','mucars':'MUCars'}
    plt.rcParams.update({'font.family':'DejaVu Serif','font.size':7.5,'axes.labelsize':7.5,'axes.titlesize':8,
        'legend.fontsize':8,'xtick.labelsize':7,'ytick.labelsize':7,'pdf.fonttype':42,'svg.fonttype':'none'})
    fig,axes=plt.subplots(2,3,figsize=(7.1,5.6),squeeze=False)
    styles={'risk':('Risk priority','#D55E00','s','--'),'benefit':('Benefit priority','#009E73','^','-.'),
            'uniform':('Uniform mixture','#666666','D',':'),'cdm':('CDM','#0072B2','o','-')}
    budgets=np.array([0,.01,.05,.1,.2,.3])
    for j,(dataset,title) in enumerate(sources.items()):
        for i,price in enumerate(('masking','robust')):
            ax=axes[i,j]
            for method,(label,color,marker,line) in styles.items():
                own=rows[(rows.dataset==dataset)&(rows.price==price)&(rows.method==method)]
                require(len(own)==18 and set(own.seed)=={13,42,2026},'All budgets and source seeds')
                values=own.groupby('budget').mean_positive_expected_log_inflation.agg(['mean','std']).reindex(budgets)
                require(not values.isna().any().any(),'Complete curve')
                ax.errorbar(100*budgets,values['mean'],yerr=values['std'],label=label,color=color,marker=marker,
                            ls=line,lw=1.,ms=3.3,capsize=1.7,elinewidth=.6)
            ax.set_title(f'({chr(97+i*3+j)}) {title}: '+('mask' if i==0 else 'robust'),loc='left')
            ax.set(xlim=(-1,31),xticks=[0,5,10,20,30],xlabel='Query capacity (%)')
            if j==0:ax.set_ylabel('Positive expected-log uplift')
            ax.axvline(10,color='#888888',lw=.7,ls=':');ax.grid(axis='y',alpha=.25,lw=.5)
            ax.spines[['top','right']].set_visible(False)
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='upper center',ncol=2,frameon=False,bbox_to_anchor=(.5,.99))
    fig.subplots_adjust(left=.12,right=.98,bottom=.105,top=.82,wspace=.65,hspace=.65)
    for extension in ('pdf','svg','png'):fig.savefig(output/f'cdm_capacity_frontiers.{extension}',dpi=220)
    plt.close(fig);(output/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    write_json(output/'receipt.json',{'audit_completion_sha256':sha(audit/'completion.json'),
        'contrast_completion_sha256':sha(contrasts/'completion.json'),
        'inputs':{'audited_summary.csv':sha(audit/'audited_summary.csv'),'paired_contrasts.csv':sha(contrasts/'paired_contrasts.csv')},
        'files':{p.name:sha(p) for p in output.iterdir() if p.is_file()},
        'scope':'all three sources, two fixed estimators, all six capacities, risk/benefit/uniform/CDM; three-seed means and sample SD; primary capacity 10%'})
    print('Exported complete audited CDM capacity curves.',flush=True)

if __name__=='__main__':main()
