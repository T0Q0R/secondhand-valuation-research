"""Four source-bound results figures; all observations, no training or new CIs."""
from pathlib import Path
import sys,json,hashlib,itertools
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;OUT=ROOT/'paper/figures/results-visual-v5'
sys.path.insert(0,str(HERE))
from audit_panel_alignment import require_matplotlib_panel_alignment
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['DejaVu Sans'],'font.size':9,'axes.titlesize':10,'axes.labelsize':9,'xtick.labelsize':9,'ytick.labelsize':9,'legend.fontsize':8,'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.right':False,'axes.spines.top':False,'axes.linewidth':.7,'legend.frameon':False,'savefig.facecolor':'white'})
BLUE='#41698A';ORANGE='#BE702C';GRAY='#9A9D9F';LIGHT='#D6DEE5';SEED=['#41698A','#BE702C','#61666B'];bindings={};receipts=[]
def read(path):
    p=ROOT/path;bindings[path]=hashlib.sha256(p.read_bytes()).hexdigest();return pd.read_csv(p)
def save(fig,name):
    fig.canvas.draw();alignment=require_matplotlib_panel_alignment(fig,json_out=OUT/(name+'.alignment.json'),overlay_svg=OUT/(name+'.alignment.svg'),tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
    fig.savefig(OUT/(name+'.pdf'))
    fig.savefig(OUT/(name+'.svg'))
    fig.savefig(OUT/(name+'.png'),dpi=600)
    receipts.append(dict(name=name,panels=len(fig.axes),dimensions_inches=fig.get_size_inches().tolist(),alignment=alignment['verdict'] if 'verdict' in alignment else alignment.get('status'),minimum_configured_text_pt=8))
    plt.close(fig)
def grid(ax):ax.set_axisbelow(True);ax.grid(axis='y',color='#E6E8EB',lw=.5)
def title(ax,text):ax.set_title(text,loc='left',pad=15)
# Cap: all 72 paired raw summary rows -> 12 source/rule means.
f=read('outputs/replay-cap-response-full-v1-audit-v2/verified_summary.csv');p=f[(f.price=='robust')&np.isclose(f.budget,.1)]
keys=['dataset','method','seed'];o=p[p.variant=='original'].set_index(keys);c=p[p.variant=='capped'].set_index(keys);assert len(o)==len(c)==36
rows=[]
for (dataset,method),g in o.groupby(level=[0,1]):
    a=g.mean(numeric_only=True);b=c.loc[g.index].mean(numeric_only=True)
    rows.append(dict(dataset=dataset,method=method,inflation_reduction_percent=100*(a.inflation-b.inflation)/a.inflation,attacked_mae_change_percent=100*(b.attacked_mae-a.attacked_mae)/a.attacked_mae,failed_change_pp=100*(b.failed-a.failed)))
cap=pd.DataFrame(rows);cap.to_csv(OUT/'cap-tradeoffs-source.csv',index=False);assert len(cap)==12
fig,axes=plt.subplots(1,2,figsize=(6.3,3.5));fig.subplots_adjust(left=.10,right=.98,bottom=.28,top=.82,wspace=.32)
colors={'synthetic':BLUE,'jucars':ORANGE,'mucars':'#508273'};markers={'suppression':'o','benefit':'s','risk':'^','cdm':'D'}
for ax,metric,heading in zip(axes,['attacked_mae_change_percent','failed_change_pp'],['a  Attacked-MAE change (%)','b  Failed-query change (pp)']):
    ax.axhline(0,color='#7C8288',lw=.8,ls='--');grid(ax)
    for r in cap.itertuples():ax.scatter(r.inflation_reduction_percent,getattr(r,metric),s=40,marker=markers[r.method],c=colors[r.dataset],edgecolors='white',linewidths=.5,zorder=3)
    ax.set_xlim(0,14);ax.set_xticks([0,5,10]);ax.set_xlabel('Inflation reduction (%)');title(ax,heading)
axes[0].set_ylim(-.18,.12);axes[0].set_yticks([-.15,-.1,-.05,0,.05,.1]);axes[1].set_ylim(-.06,.9);axes[1].set_yticks([0,.2,.4,.6,.8])
handles=[Line2D([],[],color=col,marker='o',ls='',label={'synthetic':'Synthetic','jucars':'JUCars','mucars':'MUCars'}[d]) for d,col in colors.items()]
handles += [Line2D([],[],color='#333333',marker=m,ls='',label={'suppression':'Suppression','benefit':'Benefit','risk':'Risk','cdm':'CDM'}[d]) for d,m in markers.items()]
fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,.01),ncol=4,columnspacing=1.25,handletextpad=.4)
save(fig,'cap-tradeoffs')
# Cost: retain all four scenarios, three fixed seeds and both feedback modes.
cost=read('notes/revision-mechanisms-v3/cost_mechanism_means.csv');seeds=read('outputs/review-cost-sensitivity-v2-analysis/all_seed_cells.csv')
scenarios=['zero','uniform005','uniform020','heterogeneous020'];tick=['0','0.005','0.020','Hetero.'];cc=cost.query("dataset=='synthetic' and allocation=='top_b'");assert len(cc)==8
cc.to_csv(OUT/'cost-bounds-source.csv',index=False)
s=seeds.query("dataset=='synthetic' and allocation=='top_b'");values=[]
for scenario in scenarios:
    ss=s[s.scenario==scenario].set_index(['seed','feedback'])
    for seed in [13,42,2026]:values.append(dict(scenario=scenario,seed=seed,inflation_improvement=ss.loc[(seed,'none'),'inflation']-ss.loc[(seed,'policy'),'inflation']))
diff=pd.DataFrame(values);diff.to_csv(OUT/'cost-paired-source.csv',index=False)
fig,axes=plt.subplots(1,2,figsize=(6.3,3.5));fig.subplots_adjust(left=.10,right=.98,bottom=.21,top=.80,wspace=.32)
for fb,color,marker,offset in [('none',BLUE,'o',-.10),('policy',ORANGE,'s',.10)]:
    for i,scenario in enumerate(scenarios):
        r=cc[(cc.feedback==fb)&(cc.scenario==scenario)].iloc[0];lo,hi=r.hidden_lower,r.hidden_upper
        axes[0].errorbar(i+offset,(lo+hi)/2,yerr=(hi-lo)/2,fmt='none',capsize=4,lw=2,color=color)
        if scenario=='zero':axes[0].scatter(i+offset,lo,c=color,marker=marker,s=32,zorder=3)
axes[0].legend(handles=[Line2D([],[],c=BLUE,marker='o',ls='',label='No feedback'),Line2D([],[],c=ORANGE,marker='s',ls='',label='Feedback')],loc='upper right')
axes[0].set_ylim(0,1.18);axes[0].set_yticks([0,.25,.5,.75,1]);title(axes[0],'a  Hidden fields per listing')
for j,seed in enumerate([13,42,2026]):
    a=diff[diff.seed==seed].set_index('scenario').reindex(scenarios)
    axes[1].scatter(np.arange(4)+(j-1)*.14,a.inflation_improvement*1000,c=SEED[j],marker=['o','s','^'][j],s=30,label=f'Seed {seed}',zorder=3)
for i,scenario in enumerate(scenarios):
    mean=diff[diff.scenario==scenario].inflation_improvement.mean()*1000;axes[1].plot([i-.26,i+.26],[mean,mean],color='#242424',lw=1.3)
axes[1].axhline(0,c='#7C8288',ls='--',lw=.8);axes[1].legend(loc='lower right',fontsize=8);title(axes[1],'b  Inflation improvement (x1000)')
for ax in axes:ax.set_xticks(range(4),tick);ax.set_xlim(-.5,3.5);ax.set_xlabel('Cost scenario')
save(fig,'cost-mechanism')
# Absolute variance decomposition, not just shares.
v=read('notes/revision-mechanisms-v3/variance_components.csv');v=v.query("dataset=='mucars' and initial_objective=='masking' and score=='suppression'")
order=[('top_b','capped'),('top_b','uncapped'),('minimax','capped'),('minimax','uncapped')]
v=v.set_index(['allocation','coverage']).loc[order].reset_index();v.to_csv(OUT/'variance-source.csv',index=False)
fig,ax=plt.subplots(figsize=(6.3,3.1));fig.subplots_adjust(left=.24,right=.93,bottom=.22,top=.77);left=np.zeros(4)
for column,color,label in [('seed_variance',BLUE,'Fitting seed'),('batch_variance',ORANGE,'Evaluation batch'),('interaction_variance',GRAY,'Interaction')]:
    value=v[column].to_numpy()*1e8;ax.barh(np.arange(4),value,left=left,color=color,height=.56,label=label,edgecolor='white',linewidth=.4);left+=value
for i,r in enumerate(v.itertuples()):ax.text(left[i]+.07,i,f'{r.seed_share*100:.2f}%',va='center',fontsize=9)
ax.set_yticks(range(4),['Top-B  capped','Top-B  uncapped','Minimax  capped','Minimax  uncapped']);ax.invert_yaxis();ax.set_xlim(0,5.25);ax.set_xticks([0,1,2,3,4,5]);ax.set_xlabel('Conditional variance (x 10^-8)');ax.spines['left'].set_visible(False)
ax.legend(loc='upper left',bbox_to_anchor=(-.18,1.37),ncol=3,columnspacing=1.3,fontsize=9);ax.set_title('Seed-main share shown at right',loc='left',pad=14,fontsize=9)
save(fig,'uncertainty-components')
# Coverage boundary and within-source MAE concentration (no currency pooling).
pilot=read('notes/revision-mechanisms-v3/final_record_pilot.csv');cover=read('notes/teacher-review-v4/price_and_singleton_diagnostics.csv');support=cover.drop_duplicates('dataset')[['dataset','covered','singletons','natural_missing']].copy();support['abstained']=1000-support.covered;support.to_csv(OUT/'envelope-coverage-source.csv',index=False)
mu=pilot.query("dataset=='mucars'").copy();mu.to_csv(OUT/'envelope-error-source.csv',index=False)
fig,axes=plt.subplots(1,2,figsize=(6.3,3.5));fig.subplots_adjust(left=.10,right=.98,bottom=.32,top=.80,wspace=.32)
left=np.zeros(2)
for col,color,label in [('singletons',BLUE,'Complete'),('natural_missing',ORANGE,'Natural missing'),('abstained',LIGHT,'Abstain')]:
    vals=support[col].to_numpy();axes[0].barh([0,1],vals,left=left,color=color,height=.42,label=label,edgecolor='white',linewidth=.3);left+=vals
for i,r in enumerate(support.itertuples()):axes[0].text(r.singletons/2,i,str(r.singletons),ha='center',va='center',color='white',fontsize=10)
axes[0].set_yticks([0,1],['JUCars','MUCars']);axes[0].invert_yaxis();axes[0].set_xlim(0,1000);axes[0].set_xticks([0,500,1000]);axes[0].set_xlabel('Validation listings');title(axes[0],'a  Coverage among 1,000 listings')
axes[0].set_ylim(1.65,-.65);fig.legend(*axes[0].get_legend_handles_labels(),loc='lower center',bbox_to_anchor=(.5,.015),ncol=3,fontsize=8)
for j,seed in enumerate([13,42,2026]):
    a=mu[mu.seed==seed].set_index('subset').loc[['covered','covered_with_missing_category']]
    axes[1].plot(np.arange(2)+(j-1)*.04,a.mae_change,c=SEED[j],marker=['o','s','^'][j],ls=['-','--',':'][j],lw=1,label=f'Seed {seed}',markersize=5)
axes[1].set_xlim(-.28,1.28);axes[1].set_ylim(-25,1000);axes[1].set_yticks([0,250,500,750,1000]);axes[1].set_xticks([0,1],['Covered\nn=999','Natural missing\nn=28']);axes[1].set_xlabel('MUCars evaluation support');title(axes[1],'b  Honest-MAE increase (currency)');axes[1].legend(loc='upper left',fontsize=8)
save(fig,'envelope-boundary')
(HERE/'figure-completion.json').write_text(json.dumps(dict(status='rendered_pending_pdf_and_visual_qa',figure_count=4,training_runs=0,input_sha256=bindings,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),figures=receipts),indent=2)+'\n')
print(json.dumps(receipts,indent=2))
