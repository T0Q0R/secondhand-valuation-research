from pathlib import Path
import sys,json,hashlib,string
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
sys.path.insert(0,'/Users/tqr/.codex/skills/nature-figure/scripts')
from audit_panel_alignment import require_matplotlib_panel_alignment
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'paper/figures/postcompute-v1';DATA=Path(__file__).parent;OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['DejaVu Sans'],'font.size':8,'axes.titlesize':9,'axes.labelsize':8,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7})
SOURCES=['synthetic','jucars','mucars'];LABELS=['Synthetic','JUCars','MUCars'];COLORS=['#0072B2','#D55E00','#009E73'];M='mean_positive_log_inflation';FILES=[]
def style(ax,label,title):
 ax.set_title(title,pad=11);ax.text(-.1,1.07,label,transform=ax.transAxes,fontweight='bold',fontsize=10);ax.grid(axis='y',color='#dddddd',lw=.4,zorder=0)
def save(fig,name,data):
 fig.canvas.draw();require_matplotlib_panel_alignment(fig,json_out=str(DATA/f'{name}.alignment.json'),tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
 fig.savefig(OUT/f'{name}.pdf')
 fig.savefig(OUT/f'{name}.svg')
 fig.savefig(OUT/f'{name}.png',dpi=600)
 data.to_csv(DATA/f'{name}.source.csv',index=False);FILES.append(name);plt.close(fig)
def curve(ax,df,x,y,color,label,marker='o',ls='-'):
 g=df.groupby(x)[y].agg(['mean','min','max']).sort_index();xx=g.index.to_numpy(float);ax.plot(xx,g['mean'],color=color,marker=marker,ms=3,lw=1.2,label=label,ls=ls);ax.fill_between(xx,g['min'],g['max'],color=color,alpha=.09,lw=0)
# Paired changes, not marginal ratios of means.
r=pd.read_csv(ROOT/'notes/postcompute-review-v1/rpl_paired_changes.csv');r=r[(r.beta==.5)&(r.budget==.1)].copy();r['inflation_reduction_pct']=-100*r[M+'_relative_change'];r['honest_change_pct']=100*r.clean_mae_relative_change;r['failed_change_pp']=100*r.failed_query_fraction_change
fig,axs=plt.subplots(1,3,figsize=(7.2,2.8));fig.subplots_adjust(left=.09,right=.98,bottom=.27,top=.78,wspace=.48)
for i,(y,title) in enumerate([('inflation_reduction_pct','Inflation reduction (%)'),('honest_change_pct','Honest MAE change (%)'),('failed_change_pp','Failed queries change (pp)')]):
 ax=axs[i];style(ax,string.ascii_lowercase[i],title);ax.axhline(0,color='#777777',lw=.6,ls='--')
 for source,color,label in zip(SOURCES,COLORS,LABELS):curve(ax,r[r.dataset==source],'path_weight',y,color,label)
 ax.set_xticks([.1,.5,1]);ax.set_xlabel('Path weight')
fig.legend(*axs[0].get_legend_handles_labels(),loc='lower center',ncol=3,bbox_to_anchor=(.5,.01),frameon=False);save(fig,'rpl_tradeoffs',r)
# Mechanism: all individual seeds plus source-specific means.
d=pd.read_csv(ROOT/'outputs/completion-mechanisms-v1/summary.csv');d=d[d.budget==.1].copy();methods=['feedback-off','epoch-weak','batch-weak','epoch-strong','batch-strong'];short=['Off','Epoch\nweak','Batch\nweak','Epoch\nstrong','Batch\nstrong'];fig,axs=plt.subplots(1,3,figsize=(7.2,2.9));fig.subplots_adjust(left=.09,right=.98,bottom=.25,top=.79,wspace=.48)
for i,(source,color,label) in enumerate(zip(SOURCES,COLORS,LABELS)):
 ax=axs[i];style(ax,string.ascii_lowercase[i],label)
 for seed,marker in zip([13,42,2026],['o','s','^']):
  vals=d[(d.dataset==source)&(d.seed==seed)].set_index('method').loc[methods,M];ax.plot(range(5),vals,color=color,alpha=.4,lw=.65,marker=marker,ms=3)
 means=d[d.dataset==source].groupby('method')[M].mean().loc[methods];ax.plot(range(5),means,color=color,lw=1.5,marker='D',ms=3);ax.set_xticks(range(5),short,fontsize=7);ax.set_ylabel('Positive log inflation')
save(fig,'mechanism_search',d)
# Seven acquisition curves on each fixed backend; comparator data stay intact.
d=pd.read_csv(ROOT/'notes/postcompute-review-v1/recent_and_simple_controls.csv');methods=['aco','sefa','gdfs','dime','efa','masking_risk','masking_benefit'];names=['ACO (k=25)','SEFA','GDFS','DIME','Explainability AFA','Risk','Benefit'];colors=['#555555','#0072B2','#56B4E9','#D55E00','#CC79A7','#009E73','#777700'];fig,axs=plt.subplots(2,3,figsize=(7.2,5.2));fig.subplots_adjust(left=.09,right=.98,bottom=.2,top=.9,hspace=.55,wspace=.48)
used=[]
for row,backend in enumerate(['masking_suppression','robust_no_feedback']):
 for col,source in enumerate(SOURCES):
  ax=axs[row,col];style(ax,string.ascii_lowercase[row*3+col],LABELS[col]+(' / Mask-aware' if row==0 else ' / Robust'))
  for k,(method,label,color) in enumerate(zip(methods,names,colors)):
   part=d[(d.dataset==source)&(d.price_backend==backend)&(d.recent_family==method)]
   # Risk/benefit have no matching robust-backend acquisition artifact.
   if len(part)==0:continue
   curve(ax,part,'budget',M,color,label,marker=['o','s','^','v','D','x','+'][k],ls='--' if k>=5 else '-');used.append(part)
  ax.set_xlabel('Query capacity');ax.set_ylabel('Positive log inflation');ax.set_xticks([0,.1,.2,.3])
handles,labels=axs[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',ncol=4,bbox_to_anchor=(.5,.01),frameon=False);save(fig,'recent_budget_curves',pd.concat(used))
# All factorial combinations vs full configuration.
d=pd.read_csv(ROOT/'outputs/completion-ablation-v6/summary.csv');d=d[d.budget==.1].copy();ms=sorted(d.method.unique());rows=[]
for (source,seed),g in d.groupby(['dataset','seed']):
 ref=g[g.method=='S1F1G1'][M].iloc[0]
 for _,v in g.iterrows():rows.append(dict(dataset=source,seed=seed,method=v.method,inflation_difference=v[M]-ref))
p=pd.DataFrame(rows);fig,axs=plt.subplots(1,3,figsize=(7.2,3.4));fig.subplots_adjust(left=.14,right=.98,bottom=.2,top=.83,wspace=.5)
for i,(source,color,label) in enumerate(zip(SOURCES,COLORS,LABELS)):
 ax=axs[i];style(ax,string.ascii_lowercase[i],label);ax.axvline(0,color='#777777',lw=.7,ls='--')
 for j,method in enumerate(ms):
  v=p[(p.dataset==source)&(p.method==method)].inflation_difference.to_numpy();ax.plot(v,np.full(3,j)+np.array([-.13,0,.13]),'o',color=color,ms=3,alpha=.55);ax.plot(v.mean(),j,'D',color=color,ms=4)
 ax.set_yticks(range(8),ms,fontsize=7);ax.invert_yaxis();ax.set_xlabel('Inflation minus S1F1G1')
save(fig,'factorial_ablations',p)
# Core hyperparameters including matched default points.
d=pd.read_csv(ROOT/'outputs/completion-parameters-v6/summary.csv');fig,axs=plt.subplots(2,3,figsize=(7.2,4.8));fig.subplots_adjust(left=.1,right=.98,bottom=.19,top=.88,hspace=.63,wspace=.48);parts=[]
for row,budget in enumerate([.1,.3]):
 for col,(axis,x,title) in enumerate([('gap_weight','beta','Gap weight'),('tolerance','tolerance','Gap tolerance'),('feedback_schedule','rounds','Feedback rounds')]):
  part=d[(d.budget==budget)&(d.axis==axis)&d.feedback].copy()
  if col in [1,2]:part=pd.concat([part,d[(d.budget==budget)&(d.method=='beta-0.5')]],ignore_index=True)
  ax=axs[row,col];style(ax,string.ascii_lowercase[row*3+col],title)
  for source,color,label in zip(SOURCES,COLORS,LABELS):curve(ax,part[part.dataset==source],x,M,color,label)
  ax.set_xlabel(title);ax.set_ylabel(f'Log inflation (B={budget:g})');parts.append(part)
fig.legend(*axs[0,0].get_legend_handles_labels(),loc='lower center',ncol=3,bbox_to_anchor=(.5,.01),frameon=False);save(fig,'parameter_sensitivity',pd.concat(parts))
# Remaining hyperparameters, paired normalization to unchanged matched default.
d=pd.read_csv(ROOT/'outputs/completion-stability-v6/summary.csv');base=pd.read_csv(ROOT/'outputs/completion-ablation-v6/summary.csv');base=base[(base.method=='S1F1G1')&(base.budget==.1)];settings=[('anchor_weight',.25,'Anchor weight'),('attack_loss_weight',.5,'Attack loss weight'),('learning_rate',.001,'Learning rate'),('residual_epochs',12,'Residual epochs'),('head_trees',160,'Head trees'),('residual_hidden_width',64,'Hidden width')];rows=[];fig,axs=plt.subplots(2,3,figsize=(7.2,4.8));fig.subplots_adjust(left=.1,right=.98,bottom=.19,top=.88,hspace=.63,wspace=.48)
for i,(axis,default,title) in enumerate(settings):
 part=d[d.axis==axis];points=[]
 for _,v in part.iterrows():
  ref=base[(base.dataset==v.dataset)&(base.seed==v.seed)].iloc[0][M];points.append(dict(dataset=v.dataset,seed=v.seed,setting=float(v.method.removeprefix(axis+'-')),inflation_ratio=v[M]/ref))
 for _,v in base.iterrows():points.append(dict(dataset=v.dataset,seed=v.seed,setting=default,inflation_ratio=1.))
 p=pd.DataFrame(points);p['parameter']=axis;rows.append(p);ax=axs.flat[i];style(ax,string.ascii_lowercase[i],title)
 for source,color,label in zip(SOURCES,COLORS,LABELS):curve(ax,p[p.dataset==source],'setting','inflation_ratio',color,label)
 if axis=='learning_rate':
  from matplotlib.ticker import NullLocator
  assert (p.setting>0).all()
  ax.set_xscale('log');ax.set_xticks([.0003,.001,.003],['0.0003','0.001','0.003']);ax.xaxis.set_minor_locator(NullLocator())
 ax.set_xlabel(title);ax.set_ylabel('Inflation / Default')
fig.legend(*axs[0,0].get_legend_handles_labels(),loc='lower center',ncol=3,bbox_to_anchor=(.5,.01),frameon=False);save(fig,'implementation_stability',pd.concat(rows))
(DATA/'figure-index.json').write_text(json.dumps(dict(figures=FILES,source_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),seed_ranges_not_CIs=True),indent=2)+'\n')
