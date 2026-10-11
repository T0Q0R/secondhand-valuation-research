"""Write a standalone research addendum from independently verified summaries."""
from pathlib import Path
import hashlib,json
import pandas as pd

root=Path(__file__).resolve().parents[1]
cap=root/'outputs/replay-cap-full-v1-audit'
decomp=root/'outputs/mechanism-decomposition-full-v2-audit'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for folder in (cap,decomp):
    completed=json.loads((folder/'completion.json').read_text())
    assert completed['status']=='completed'
    for name,digest in completed['files'].items():assert sha(folder/name)==digest
d=pd.read_csv(cap/'verified_summary.csv')
primary=d[(d.budget==.1)&(d.price=='robust')].groupby(['dataset','method'])[['original_mean','capped_mean']].mean()
primary['relative_reduction']=100*(primary.original_mean-primary.capped_mean)/primary.original_mean
table=[];markdown=[]
for (dataset,method),r in primary.iterrows():
    table.append(f'{dataset} & {method} & {r.original_mean:.6f} & {r.capped_mean:.6f} & {r.relative_reduction:.2f} \\\\')
    markdown.append(f'|{dataset}|{method}|{r.original_mean:.6f}|{r.capped_mean:.6f}|{r.relative_reduction:.2f}%|')
text=r'''\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage{amsmath,amssymb,amsthm,booktabs,hyperref}
\newtheorem{proposition}{Proposition}
\title{Information Limits and Verification-Path Effects\\in Budgeted Valuation}
\author{Research addendum to the audited valuation study}
\date{7 October 2026}
\begin{document}
\maketitle
\begin{abstract}
We extend the existing heterogeneous-results study with a finite public-information
oracle and a diagnostic of verification-path effects. A restricted missingness-alias
family admits a tight honest-precision--incentive frontier. A new decomposition of
360,000 saved-model deviation outcomes separates the initial quote, local recovery
and hard-capacity effects. It identifies partial recovery that can raise a seller's
quote. A verification-history cap weakly reduces every fixed-profile unilateral
gain while preserving truthful quotes under the stated replay semantics.
An exhaustive developmental comparison covers 108 estimator/source/seed/budget
cases and 2,160,000 entry--method comparisons. For the robust benefit rule at
10\% capacity, mean worst unilateral gain decreases by 6.11\%, 7.04\% and 12.49\%
on synthetic, JUCars and MUCars cohorts. These conditional effects do not establish
equilibrium dominance, attacked-error improvement or general methodological novelty.
\end{abstract}

\section{Question and scope}
\noindent\textbf{Takeaway.} Audit information limits and the consequences of
verification, while retaining the original negative and heterogeneous results.

Each batch contains 100 listings, each with four optional fields. Sellers may
withhold at most two available fields. Queries on naturally absent fields fail
and consume budget. Pricing is itemwise and fixed in the present extension;
only query allocation couples a batch. Public scores cannot use latent source
availability. We use the original three seeds (13, 42, 2026), two frozen price
models, six capacities and five saved peer profiles. Three seeds are not ten
seeds, and the saved profiles are not observed market behavior.

Strategic withholding and monotone incentive remedies already have a literature
\cite{withheld}; randomized automated mechanism design under partial verification
also uses established optimization tools \cite{partial}. We do not claim that LP,
randomization or a minimum operator is new. The candidate contribution is the
specific precision frontier, information-consistent audit certificates, and the
empirically diagnosed verification-path effect. Theorem-level novelty review remains
necessary before claiming a first result.

\section{Observable-report oracle and a precision frontier}
\noindent\textbf{Takeaway.} A finite complete oracle can distinguish a policy-library
restriction from the best value achievable under the same public information.

Let $o$ be the complete observable batch signature and $A_B(o)$ its feasible
complete nonadaptive allocations, each spending at most $B$ queries. Allocate
probability $z_{oa}$ to action $a$, sharing the same variables across latent
worlds with the same signature. For each legal deviation $d$, let $G_d(z)$ be
the expected deviated quote minus the truthful quote, with the entire batch
reallocated on both sides. The finite oracle solves
\[
 \min_{z,t} t\quad\text{s.t.}\quad G_d(z)\le t\ (\forall d),\quad
 \sum_{a\in A_B(o)}z_{oa}=1,\quad z_{oa}\ge0,\quad t\ge0.
\]
This is exact only for the declared complete finite world/report/action universe.
Its numerical primal/dual certificate uses tolerance $10^{-8}$. It is not a
guarantee over unseen types or general adaptive query trees.

Consider a separate alias family with an all-natural-missing world and worlds
in which only listing $i$ has a recoverable low-value field, lowering its target
by $\Delta_i>0$. Withholding it produces the same public batch. Require
verification-neutral quotes (same final record, same quote), and uniform
absolute error at most $\eta$ on all specified honest reports. Set
$a_i=(\Delta_i-2\eta)_+$. The attainable worst positive expected gain is
\begin{equation}
T^*(\eta,B)=\min_{0\le p_i\le1,\ \sum_i p_i\le B}\max_i a_i(1-p_i).
\label{eq:frontier}
\end{equation}
For the nonzero interior case, $\sum_{i:a_i>0}(1-T^*/a_i)_+=B$.

\paragraph{Proof sketch and boundaries.}
Couple queries by their private random seed on the all-failure transcript.
Let $p_i$ be the probability of querying $i$. Hard capacity gives
$\sum_i p_i\le B$. Until $i$ is queried, its hidden low-value world has the same
transcript; without recovery, the honest-precision constraint leaves a quote
gap at least $\Delta_i-2\eta$. This proves the lower bound, including adaptive
policies in this single-recoverable family. Choose quote shifts
$e_i=\min(\eta,\Delta_i/2)$ toward one another and marginals
$p_i=(1-T^*/a_i)_+$. Systematic interval sampling realizes these marginals with
at most $B$ queries per draw and attains the bound. This does not follow from
an average MAE bound. It does not imply zero adaptivity benefit for failed-query
counts or multi-field worlds.

A two-mode constructed example at $B=1,\eta=0$ yields $72/17$ for the public
oracle, $72/13$ for the best global mixture of the specified eight rules, and
$8$ for risk ordering. These are artificial linear quote units, not empirical
log-price effects. All 32 budget/precision cases passed a separate auditor.

\section{A nondegenerate mechanism decomposition}
\noindent\textbf{Takeaway.} Freezing truthful queries cannot separate recovery
from capacity in this replay model; use a capacity-relaxed public query instead.

For each fixed peer profile and evaluated mixture, retain its saved maximizing
own report $h^*$. Let $q_0$ be the truthful quote, $q_h$ the unqueried reported
quote, $q_L$ the quote after the same rule's highest-scoring eligible query with
capacity relaxed, and $q_A$ the hard-budget quote. Ineligible or nonpositive
scores still cause no query in the relaxed reference. Then
\begin{align}
E &= q_h-q_0, & R&=\mathbb{E}[q_L]-q_h,\\
C &=\mathbb{E}[q_A]-\mathbb{E}[q_L], & G&=E+R+C.
\end{align}
All components are signed and evaluated at the same $h^*$. Mixture expectation
precedes report maximization. The relaxed query is a diagnostic, not a feasible
deployment policy. The original truthful-query anchor would give zero recovery:
that query targets a naturally absent field, which remains absent when another
field is withheld. Its remaining term would conflate recovery and capacity.

Across all nine source/seed pairs and both price models at 10\% capacity,
360,000 component rows were independently reconstructed by complete stable
sorting of each hypothetical batch. The audit checked 11,343,240 legal
rule--world allocations and rejected four output mutations. Eighty-one saved
winners differed from freshly computed argmax labels only through floating
ties; the largest payoff gap was $6.94\times10^{-18}$. Original winners were
retained. The initial argmax-identity failure is preserved in a separate run.

Positive $R$ can occur: hiding two fields and recovering one can move a
nonmonotone estimator to an intermediate record with a higher quote. This
motivates the following developmental mechanism experiment. It is not evidence
that all original SAV advantages or failures have been causally explained.

\section{Verification-history cap}
\noindent\textbf{Takeaway.} Removing quote increases along the realized recovery
path gives a conditional unilateral-gain guarantee without changing truthful quotes.

For every realized allocation, use
\begin{equation}
 q_{\rm cap}(r,a)=\min\{q(r,\varnothing),q(r,a)\}.
\end{equation}
Apply this operation before averaging over a policy mixture. The underlying
public scores, query budget, model and mixture weights are fixed.

\begin{proposition}
If truthful queries cannot alter the fixed itemwise quote, then for any fixed
peer profile and any fixed policy mixture the cap preserves the truthful quote
and weakly reduces the worst expected unilateral gain over legal own reports.
\end{proposition}
\begin{proof}
Pointwise $q_{\rm cap}(h,a)\le q(h,a)$, whereas
$q_{\rm cap}(0,a)=q(0,a)=q_0$ for every realized action. Subtracting the same
truthful quote, taking expectations and then maximizing over legal $h$ preserves
the inequality. The null deviation yields zero.\end{proof}

The mechanism deliberately uses verification history. It lies outside the
verification-neutral class in Equation~\eqref{eq:frontier}, so it cannot be used
to claim a violation of that bound. Equal final records can have different
prices under the cap. The guarantee concerns fixed peers and scores; a new
seller-response profile can change allocations and outcomes. Lower quotes need
not have lower absolute pricing error.

\begin{table}[ht]
\centering\small
\caption{Primary descriptive comparison: robust frozen estimator, 10\% capacity.
Mean worst unilateral log-quote gain, equally averaging five fixed peer profiles
and three seeds. No confidence interval or practical-threshold pass is asserted.}
\begin{tabular}{llrrr}\toprule
Source & Rule & Original & Capped & Reduction (\%)\\\midrule
__TABLE__
\bottomrule\end{tabular}
\end{table}

The full comparison includes both estimators and all six capacities: 108 cases,
5,671,620 legal report rows and 2,160,000 entry--method comparisons. A separate
auditor reconstructs absolute quotes rather than reusing the signed-gain cap
calculation. All truthful quotes are unchanged and all fixed-profile envelopes
weakly decrease within tolerance $10^{-10}$. Risk has zero improvement in the
primary table and is retained as a strong reference. These are additional
conditional diagnostics, not new ten-seed training experiments.

\section{Claims, limitations and next evidence}
\noindent\textbf{Takeaway.} The strongest defensible story combines bounded theory,
audited mechanisms and honest limits on empirical generalization.

The new evidence supports a recovery-path failure mechanism and a simple
conditional remedy. It does not yet prove novelty relative to all audit or
monotone-prediction mechanisms, explain the complete SAV feedback effect,
establish response-equilibrium improvement, or verify attacked MAE after the
cap. The next required experiments recompute seller responses, report honest
and attacked error, bias, failed-query rates and regret, and implement the
matched estimator/acquisition/feedback/allocation design with ten seeds.
Training-population uncertainty needs actual resampling and refitting.

The scripts, immutable outputs, failed initial run and audit receipts are local
research artifacts. This addendum is not the fully integrated submission
manuscript and has no asserted public DOI or journal acceptance status.

\begin{thebibliography}{9}
\bibitem{withheld} \emph{Classification with Strategically Withheld Data}.
AAAI, 2021. \url{https://ojs.aaai.org/index.php/AAAI/article/download/16694/16501}.
\bibitem{partial} \emph{Automated Mechanism Design for Classification with
Partial Verification}. 2021. \url{https://arxiv.org/abs/2104.05182}.
\end{thebibliography}
\end{document}
'''.replace('__TABLE__','\n'.join(table))
dest=root/'paper/innovation-addendum-v1.tex'
if dest.exists():raise FileExistsError(dest)
dest.write_text(text)
report='''# 新增机制证据与论文创新进展

2026-10-07。当前主张：信息约束的有限最优审计 + 特定别名族的精度紧界 + 核验路径效应。
该组合仍须定理级文献排重；不以缩写、LP或min操作本身声称首创。

## 已完成的真实来源诊断

三个来源×三个种子×两种固定报价器，10%预算下，360,000条机制分解完成。
独立审计重排11,343,240个合法规则—世界批次，四种错误注入均被拒绝。
原“冻结诚实查询”分解的回填项恒为零，已修正为同一公开规则的不限容量查询参照。
分量：初始报价差 + 本地回填变化 + 硬容量差额 = 同一隐瞒行为的总收益。

发现部分回填可提高报价，因此完成核验历史报价上限实验：每次实际抽签下取
min(核验前报价,回填后报价)，再对规则混合取期望。它改变核验中性假设，
不能与OQBO中性机制下界混为一谈。所有模型和分配评分都固定。

## 主描述性比较

稳健报价器、10%预算、五种固定同伴报告等权、三个种子等权。指标是平均最坏
单方log报价收益，不是原论文的共同响应下平均inflation，也不是attacked MAE。

|来源|规则|原值|报价上限后|降幅|
|---|---|---:|---:|---:|
'''+ '\n'.join(markdown)+'''

全部两种报价器、六种预算、108个案例已保留：5,671,620个合法报告行，
2,160,000组逐项方法比较。独立绝对报价回放检查68,059,440个规则报价。
诚实报价不变；固定同伴报告下最坏单方收益均不增加。risk的零改进行不能删除。

## 解释边界

这解释了一个可修复的回填路径现象，尚未解释完整SAV的跨来源差异。
尚未重算加入报价上限后的卖家共同响应，未证明attacked MAE、偏差、
失败查询率或均衡改进。三个固定种子的均值没有训练总体置信区间；
12.49%的点降幅不能自动记为通过10%实际改进门槛。

来源文件：outputs/mechanism-decomposition-full-v2-audit/verified_summary.csv；
outputs/replay-cap-full-v1-audit/verified_summary.csv。
论文补充源稿：paper/innovation-addendum-v1.tex。
下一科学工作：完整响应和误差评估、定理排重、匹配因子与10种子扩展。
'''
(root/'notes/innovation-mechanism-evidence-2026-10-07-v1.md').write_text(report)
receipt={'inputs':{str(p.relative_to(root)):sha(p) for p in [cap/'completion.json',cap/'verified_summary.csv',decomp/'completion.json']},
         'tex_sha256':sha(dest),'source_tables':'verified descriptive means; no novel training or inference',
         'compile_status':'not yet checked'}
(root/'notes/innovation-addendum-v1-binding.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(dest)
