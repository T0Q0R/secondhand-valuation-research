"""Produce descriptive report and figures solely from the audited analysis."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
PIPE=ROOT/'outputs/matched-factorial-ten-seeds-v1-pipeline'
OUT=ROOT/'notes/factorial-final'
FIG=ROOT/'paper/figures/factorial-final'
OUT.mkdir(exist_ok=True); FIG.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
receipt=json.loads((PIPE/'completion.json').read_text());assert receipt['status']=='completed'
for stage,digest in receipt['stage_completion_hashes'].items():
 assert sha(PIPE/stage/'completion.json')==digest
analysis=json.loads((PIPE/'analysis/completion.json').read_text())
for name,digest in analysis['files'].items():assert sha(PIPE/'analysis'/name)==digest
contrasts=pd.read_csv(PIPE/'analysis/contrasts.csv')
primary=contrasts[contrasts.budget.eq(.1)].copy()
primary.to_csv(OUT/'primary_contrasts.csv',index=False)
primary_components=pd.read_csv(PIPE/'analysis/contrast_components.csv')
primary_components=primary_components[primary_components.budget.eq(.1)]
primary_components.to_csv(OUT/'primary_components.csv',index=False)
inflation=primary[primary.metric.eq('positive_expected_log_inflation')]
rows=[]
for (dataset,family),g in inflation.groupby(['dataset','family']):
 rows.append({'dataset':dataset,'family':family,'contrasts':len(g),'favorable_points':int(g.difference.gt(0).sum()),'favorable_unadjusted_intervals':int(g.lower.gt(0).sum()),'unfavorable_unadjusted_intervals':int(g.upper.lt(0).sum()),'point_gates_passed':int(g.point_gate.eq(True).sum())})
counts=pd.DataFrame(rows);counts.to_csv(OUT/'primary_family_counts.csv',index=False)
feedback=inflation[inflation.family.eq('feedback')]
assert len(feedback)==36 and feedback.difference.lt(0).all() and feedback.upper.lt(0).sum()==34
joint=inflation[inflation.family.eq('joint_policy')]
assert len(joint)==18 and joint.point_gate.eq(True).sum()==0
mucars=inflation[inflation.dataset.eq('mucars')&inflation.family.eq('initial_objective')]
assert len(mucars)==12 and mucars.difference.gt(0).all() and mucars.point_gate.eq(True).all()

plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['DejaVu Sans'],'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none','axes.linewidth':.7})
colors={'synthetic':'#536F8C','jucars':'#C17E4B','mucars':'#638C72'}
def forest(family,name,heading,definition,terms):
 data=inflation[inflation.family.eq(family)&inflation.contrast.isin(terms)].copy()
 order=[(d,t) for d in ['synthetic','jucars','mucars'] for t in terms]
 data=data.set_index(['dataset','contrast']).loc[order].reset_index()
 labels=[]
 for row in data.itertuples():
  words=row.contrast.split('__')[1:]
  words=[{'masking':'Mask','robust':'Robust','none':'No feedback','top_b':'Top-B','minimax':'Minimax','suppression':'Suppression'}.get(w,w) for w in words]
  # Acquisition is fixed to suppression; avoid repeating it in every label.
  words=[w for w in words if w not in ['Suppression','No feedback']]
  labels.append({'synthetic':'Synthetic','jucars':'JUCars','mucars':'MUCars'}[row.dataset]+' / '+' / '.join(words))
 fig,ax=plt.subplots(figsize=(7.08,4.3))
 fig.subplots_adjust(left=.43,right=.97,bottom=.17,top=.96)
 for j,row in enumerate(data.itertuples()):
  ax.errorbar(row.difference,j,xerr=[[row.difference-row.lower],[row.upper-row.difference]],fmt='o',color=colors[row.dataset],markersize=4,capsize=2,lw=1)
 ax.axvline(0,color='#777777',lw=.7,ls='--');ax.set_yticks(range(len(data)),labels);ax.invert_yaxis()
 ax.set_xlabel('Inflation difference (no feedback - policy feedback)' if family=='feedback' else 'Inflation difference (mask - robust)');# The journal caption contains the heading; preserve plot-only artwork.
 ax.tick_params(axis='y',length=0,pad=8)
 if family=='initial_objective':ax.set_xticks([-.003,0,.003])
 data.to_csv(FIG/(name+'.source.csv'),index=False)
 fig.savefig(FIG/(name+'.pdf'));fig.savefig(FIG/(name+'.svg'));fig.savefig(FIG/(name+'.png'),dpi=300)
 plt.close(fig)
forest('feedback','feedback-suppression','Feedback increased inflation in every suppression cell','No feedback − policy feedback (positive favors feedback)',[f'feedback__{i}__suppression__{a}' for i in ['masking','robust'] for a in ['top_b','minimax']])
forest('initial_objective','initial-objective','Initial-objective effects differed across sources','Mask objective − robust objective (positive favors robust)',[f'initial_objective__suppression__none__{a}' for a in ['top_b','minimax']])
report='''# 已审计的匹配因子实验：结果解读

完整四阶段流水线已通过：30个来源/种子组合、4320实验单元、432万条结果；训练审计独立重建420个估值头，结果审计核验45372960个合法单边偏离。统计检查覆盖9216条指标对比。

## 核心结果（预设10%预算）

1. 反馈训练：36/36个对比的平均inflation均变差，34/36个95%未校正区间完全位于不利方向。两个跨零例外是MUCars、mask初始目标、suppression查询下的两种分配。反馈失败限于本次实现和固定训练预算，不能推出所有反馈学习都失败。
2. MUCars初始目标：12/12个robust相对mask对比降低inflation，且均通过“inflation至少降低10%、honest MAE增加不超过5%”的点估计门槛；降幅12.43%至33.40%。这个初始目标因子是新实验干预，不是原SAV/静态robust模型的重新命名。
3. 联合干预：从无反馈top-B切换到有反馈minimax，18个对比无一通过门槛。MUCars三个小幅正点估计区间均跨零。不能将正交互解释成方法优势。
4. 交互反例：synthetic、mask、suppression的反馈×分配交互为0.004917（未校正95%区间0.002378至0.007586），但两种分配的反馈都使inflation恶化：top-B增加0.008097，minimax增加0.003181。这是“少受损”而非“改善”。

## 解释与边界

本次可支持训练目标、反馈与分配的受控对比；无法直接解释原SAV来源异质性。反馈导致恶化的具体机制尚未识别，训练与评估响应搜索强度不同、score冻结及固定10%训练预算只是待检验解释。不可追加调参后声称同一预设实验成功。

1000次种子×共享批次交叉bootstrap仅覆盖拟合随机性与这批固定评估样本的批次波动，不覆盖新训练总体，也不做多重比较校正。1000个listing重复用于10个seed和各方法，432万条输出不是432万个独立样本。所有容量与对比保留，10%是预设主容量，其他容量是迁移诊断。非收敛响应保留，不宣称均衡。

## 图表与数据

两幅单图提供suppression反馈对比和无反馈初始目标对比的效应及区间；图中未显示的其他查询规则在完整CSV中保留。图不是通用排行榜。相关图源CSV逐行来自已审计contrasts.csv，核心计数见primary_family_counts.csv。
'''
(OUT/'RESULTS.zh.md').write_text(report)
(OUT/'report_provenance.json').write_text(json.dumps({'pipeline_completion_sha256':sha(PIPE/'completion.json'),'analysis_completion_sha256':sha(PIPE/'analysis/completion.json'),'source_contrasts_sha256':sha(PIPE/'analysis/contrasts.csv'),'source_components_sha256':sha(PIPE/'analysis/contrast_components.csv'),'new_training':False,'multiple_testing_adjusted':False,'figure_contract':{'archetype':'single-panel paired-effect forest plots','dimensions_inches':[7.08,4.3],'backend':'python','uncertainty':'95% unadjusted seed-by-batch crossed bootstrap, fixed training records','alignment':'not applicable: each figure has one plotting axis'}},indent=2)+'\n')
print(counts.to_string(index=False))
