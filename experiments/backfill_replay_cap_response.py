"""Integrate audited common-response results into the same editable addendum."""
from pathlib import Path
import hashlib,json
import pandas as pd

root=Path(__file__).resolve().parents[1]
analysis=root/'outputs/replay-cap-response-full-v1-analysis'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
done=json.loads((analysis/'completion.json').read_text());assert done['status']=='completed'
for name,digest in done['files'].items():assert sha(analysis/name)==digest
p=pd.read_csv(analysis/'primary_paired_intervals.csv')
table=[];md=[]
for _,r in p.iterrows():
    table.append(f'{r.dataset} & {r.method} & {r.inflation_reduction_percent:.2f} & {r.attacked_mae_change_percent:+.3f} & {100*r.failed_difference:+.3f} \\\\')
    md.append(f'|{r.dataset}|{r.method}|{r.inflation_reduction_percent:.2f}%|{r.attacked_mae_change_percent:+.3f}%|{100*r.failed_difference:+.3f}|')
section=r'''
\section{Recomputed common responses and multiobjective effects}
\noindent\textbf{Takeaway.} The cap's inflation reductions survive the saved
response heuristic in this study, but attacked error and failed-query rates
can worsen. This is an empirical result, not an extension of the fixed-peer theorem.

We recomputed reports for every source/seed/estimator/capacity/rule cell, using
the original four starts and up to20 sweeps, frozen public scores and unchanged
mixture weights. The uncapped baseline uses the independently audited original
responses. All432 new cells and432,000 listing outcomes were replayed by an
independent full-sort auditor. It checked5,300 supported complete-rule batch
allocations and5,570,112 legal rule--deviation outcomes. The auditor reconstructs
final quotations, currency absolute errors, query failures and remaining unilateral
regret; it does not certify a globally optimal joint response or every search step.

\begin{table}[ht]
\centering\small
\caption{Recomputed common-response comparison at10\% capacity with the robust
estimator, averaged over three seeds. Positive inflation reduction is favorable;
positive attacked-MAE change and failed-query change are unfavorable. Failure
change is percentage points per listing, not the conditional failure/query rate.}
\begin{tabular}{llrrr}\toprule
Source & Rule & \shortstack{Inflation\\reduction (\%)} & \shortstack{MAE\\change (\%)} & \shortstack{Failure\\change (pp)}\\\midrule
__RESPONSE_TABLE__
\bottomrule\end{tabular}
\end{table}

Across all432 paired cells, inflation decreases in279 and is unchanged in153
within numerical tolerance. Attacked MAE decreases in185 cells, is unchanged
in153, and increases in94. Failed-query probability increases in145 cells,
decreases in4, and is unchanged in283. Honest MAE is unchanged throughout.
These cell counts are descriptive; cells share records and fitted models.

Thirty-three capped cells contain at least one batch with remaining unilateral
regret above the convergence tolerance, compared with34 original cells. The
maximum capped regret is0.204423 log units. We retain these cases. In the primary
robust benefit comparison, one synthetic seed has one nonconverged batch, with
maximum regret0.029232; the JUCars and MUCars primary benefit batches pass the
specified local regret check. Therefore no result is described as a certified
market equilibrium.

For the12 primary source/rule contrasts, we compute unadjusted95\% percentile
intervals from1,000 paired resamples of the ten shared batches, first averaging
the three fixed fitted-seed outcomes within each batch. These are conditional
evaluation-batch intervals, not training-population intervals or30 independent
batch replicates. For benefit, the absolute inflation-reduction intervals are
$[0.000388,0.001252]$ (synthetic), $[0.001207,0.001586]$ (JUCars), and
$[0.000842,0.000995]$ (MUCars). The JUCars and MUCars point reductions satisfy
the original10\% inflation/5\% honest-error criterion with a positive conditional
interval, but that criterion does not constrain attacked error or query failures.
In particular, JUCars attacked MAE increases by0.080\%.

Risk had no change in the earlier primary fixed-profile table, but can change
under the newly computed profiles. The comparisons condition on different peer
reports, so these findings are compatible. The existing fixed-profile theorem
must not be used as a common-response or Pareto-dominance guarantee.

Seven additional predetermined training seeds are now scheduled under the
byte-identical original nested protocol. Their live run does not yet provide
ten-seed evidence, matched factorial results or training-population uncertainty.
'''.replace('__RESPONSE_TABLE__','\n'.join(table))
tex=root/'paper/innovation-addendum-v1.tex';original=tex.read_text()
assert '\\section{Recomputed common responses' not in original
old_hash=sha(tex)
new=original.replace('\\section{Claims, limitations and next evidence}',section+'\n\\section{Claims, limitations and next evidence}')
new=new.replace('An exhaustive developmental comparison covers 108 estimator/source/seed/budget\ncases and 2,160,000 entry--method comparisons.',
'''An exhaustive fixed-profile comparison covers 108 estimator/source/seed/budget
cases and 2,160,000 entry--method comparisons. A further432 common-response
cells show279 inflation reductions and153 ties, but94 attacked-error increases
and145 increases in failed-query probability.''')
new=new.replace('verify attacked MAE after the\ncap. The next required experiments recompute seller responses, report honest\nand attacked error, bias, failed-query rates and regret, and implement the\nmatched estimator/acquisition/feedback/allocation design with ten seeds.',
'''establish Pareto dominance after the cap. Audited common-response outcomes now
quantify attacked MAE and query-failure tradeoffs. The next required experiments
implement the matched estimator/acquisition/feedback/allocation design with ten
seeds and complete the separately running original-protocol seed extension.''')
assert new!=original
tex.write_text(new)
report='''# 核验报价上限：共同响应实验已完成

2026-10-07。保留模型、查询评分和原混合权重，重新计算四起点、最多20轮的卖家响应。
全部432个方法单元/432,000条物品结果完成；独立审计核对5,300个实际规则批次分配
和5,570,112个合法规则偏离。收益指标为共同响应下mean positive expected log inflation。

## 10%预算、稳健报价器、三个种子均值

|来源|规则|inflation降幅|attacked MAE变化|失败查询变化（百分点/物品）|
|---|---|---:|---:|---:|
'''+ '\n'.join(md)+'''

## 必须同时保留的反面证据

全部432个单元中：inflation279个下降、153个不变；attacked MAE185个下降、
153个不变、94个上升；失败查询145个上升、4个下降、283个不变。诚实MAE全部不变。
33个capped单元含未通过局部regret收敛检查的批次，原版为34个；最大剩余regret0.204423。
主比较的synthetic/seed2026/benefit有一个批次未收敛，regret0.029232；不能称为已求均衡。

区间：先按相同批次对三个固定模型种子取平均，再对10个共同批次配对bootstrap1000次。
这是未做多重比较校正的条件性95%区间，不是训练总体不确定性或30个独立批次。
benefit绝对inflation降幅区间：synthetic[0.000388,0.001252]，
JUCars[0.001207,0.001586]，MUCars[0.000842,0.000995]。
JUCars/MUCars仅满足原inflation–honest-error操作门槛；这不表示attacked MAE或失败查询无代价。

该机制使用核验历史，属于OQBO核验中性边界之外。固定同伴报告下的定理不推广为
共同响应或多目标优势。文献创新排重仍未完成。

完整明细：outputs/replay-cap-response-full-v1-audit-v2/verified_summary.csv。
配对区间：outputs/replay-cap-response-full-v1-analysis/primary_paired_intervals.csv。
同一论文补充源文件已更新，编译状态见独立receipt。
'''
(root/'notes/replay-cap-response-evidence-2026-10-07-v1.md').write_text(report)
receipt={'old_tex_sha256':old_hash,'new_tex_sha256':sha(tex),'analysis_completion_sha256':sha(analysis/'completion.json'),'compile_status':'pending'}
(root/'notes/innovation-addendum-response-binding-v1.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(tex)
