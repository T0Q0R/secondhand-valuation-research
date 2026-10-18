"""Build self-contained formal review supplement from checked aggregate files."""
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
N=Path(__file__).parent

def table(caption,cols,headers,rows):
    return '\n'.join([r'\begin{table}[htbp]\centering\small',r'\caption{'+caption+'}',
      r'\begin{tabular}{'+cols+r'}\toprule',' & '.join(headers)+r'\\\midrule',
      *[' & '.join(map(str,row))+r'\\' for row in rows],r'\bottomrule\end{tabular}\end{table}'])

def build():
    flow=pd.read_csv(N/'data-construction/sample-flow.csv').set_index('source')
    missing=pd.read_csv(N/'data-construction/field-missingness.csv')
    reports=pd.read_csv(N/'data-construction/legal-report-distribution.csv')
    edges=pd.read_csv(N/'mechanisms/edge-source-means.csv')
    quotes=pd.read_csv(N/'mechanisms/quote-and-query-source-means.csv')
    paired=pd.read_csv(N/'mechanisms/paired-contrasts.csv')
    decomp=pd.read_csv(N/'mechanisms/decomposition-source-means.csv')
    labels={'synthetic':'Synthetic','jucars':'JUCars','mucars':'MUCars'}
    s=r'''\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage{amsmath,amssymb,booktabs,longtable,array,graphicx,xcolor,hyperref}
\graphicspath{{images/}}
\renewcommand{\thefigure}{S\arabic{figure}}
\newcommand{\AuditVector}[1]{\ifdefined\pdfliteral\pdfliteral{#1}\else\special{pdf:bcontent}\special{pdf:literal direct #1}\special{pdf:econtent}\fi}
\hypersetup{hidelinks}
\setlength{\emergencystretch}{2em}
\renewcommand{\thesection}{S\arabic{section}}
\renewcommand{\thetable}{S\arabic{table}}
\title{Supplement to When Does Verification Help?\\Recovery-Path Regularization for Strategy-Aware Valuation}
\author{Yuchen Tang \quad Fengqin You\textsuperscript{*} \quad Junxiang Gu \quad Xin Pang\\[.5em]
\small School of Computer and Artificial Intelligence\\
\small Nanjing University of Science and Technology Zijin College\\
\small Nanjing, China\\[.4em]
\small \textsuperscript{*}Corresponding author: \texttt{irisyou@njust.edu.cn}}
\date{}
\begin{document}\maketitle
This supplement reports additional fixed-design diagnostics and the matched
stronger-gap comparison. It preserves the distinction between new training,
new diagnostics from existing models, and the earlier four-stage audit.
It does not establish new-market effectiveness or repair the retained strict
cross-machine numerical failure. All models and per-listing artifacts remain
local; released tables contain source-, seed- or batch-level aggregates.

\section{Data construction and operational assumptions}
\paragraph{Sample flow.}
Historical construction receipts bind the input versions and every split
checksum. Joint filtering precedes non-price fingerprint deduplication;
individual exclusion flags overlap and must not be added. The counts below
reconcile all retained records, including calibration and test partitions.
Only train and validation enter the reported fixed-cohort experiments;
calibration and test are not newly evaluated here. Sealed test labels were
hashed as bytes for integrity, not parsed for this revision.
'''
    s+=table('Construction counts. Filtered counts are joint exclusions; deduplication follows filtering.',
      'lrrrrr',['Source','Raw','Filtered','Duplicates','Retained','Used train/eval'],
      [[labels[k],int(r.raw),int(r.joint_filter_removed),int(r.duplicates_removed),int(r.retained),f'{int(r.used_training)}/{int(r.used_evaluation)}'] for k,r in flow.iterrows()])
    s+=table('Partitions before label-independent experimental truncation. Synthetic validation denotes its separately generated evaluation population.',
      'lrrrr',['Source','Train','Validation','Calibration','Test'],
      [[labels[k],int(r.train),int(r.validation),int(r.calibration),int(r.test)] for k,r in flow.iterrows()])
    s+=r'''
JUCars retains used-condition records with positive finite JOD price and
model year 1980--2026. MUCars excludes records labeled New, restricts advertised
MAD price to [5,000,2,000,000], and model year to 1980--2025. These are inherited
quality filters, not a claim of full-source representativeness. Split buckets
use the first eight hexadecimal digits of a non-price fingerprint hash modulo
100: 0--54 train, 55--69 validation, 70--84 calibration, 85--99 test.
No original advertisement ID or verified vehicle identity is available.
Identical non-price fingerprints may over-collapse different vehicles.
Training and evaluation are separately hash-ranked before the 5,000/1,000
caps. The same fixed populations and batches are shared by fitting seeds.

\paragraph{Field mapping and missingness.}
JUCars uses its mileage\_km, transmission, fuel\_type and feat\_body\_condition
fields. MUCars maps Mileage, Gearbox, Fuel and Condition to these four fields;
mileage bands use numeric midpoints, or the stated bound for a one-ended band.
Missingness means unavailable in the processed source record. Its actual cause
is unknown: it may reflect collection, inapplicability or earlier concealment.
Unrecoverability is a simulation stipulation, not an empirical diagnosis of
those causes. Numeric inputs use training medians, missing indicators and
scaling; mileage is log-transformed. Categorical missing tokens and training-fit
one-hot encodings retain unknown-category handling. Targets, IDs, source
indices and declared reveal aliases are excluded from predictor inputs.
'''
    rows=[]
    for source in labels:
        for cohort in ['used_training','used_evaluation']:
            q=missing[(missing.source==source)&(missing.cohort==cohort)].set_index('field')
            rows.append([labels[source],cohort.replace('used_',''),int(q.n.iloc[0]),*[f'{100*q.loc[k,"missing_rate"]:.3f}' for k in ['mileage_km','transmission','fuel_type','feat_body_condition']]])
    s+=table('Unavailable fields in the actual experimental cohorts (percent of records). Full retained and pre-cap split counts are also released in field-missingness.csv.',
       'llrrrrr',['Source','Cohort','$n$','Mileage','Gearbox','Fuel','Condition'],rows)
    rows=[]
    for source in labels:
        for cohort in ['used_training','used_evaluation']:
            q=reports[(reports.source==source)&(reports.cohort==cohort)].set_index('legal_reports')
            rows.append([labels[source],cohort.replace('used_',''),*[f'{100*q.loc[k,"fraction"]:.2f}' if k in q.index else '0.00' for k in [1,2,4,7,11]]])
    s+=table(r'Distribution of legal report counts (percent of records). With $m$ available fields, the count is $1+m+\binom m2$; legal concealed-field recovery edges number $m^2$.',
       'llrrrrr',['Source','Cohort','1','2','4','7','11'],rows)
    s+=r'''
Sellers can conceal at most two available fields, each record receives at most
one unit-cost query, failed queries spend capacity, and the primary concealment
cost is zero. Extra absence or positive-cost tests of earlier models are not
relabeled as RPL robustness tests.

\paragraph{Synthetic generator.}
Draw make $M\sim U\{0,\ldots,4\}$, variant $V\sim U\{0,\ldots,3\}$ and
age $A\sim U\{1,\ldots,18\}$. Mileage is
$K=\max(100,A\exp Z)$ with $Z\sim N(\log15000,.4^2)$.
Condition $C\in\{0,1,2,3\}$ has probabilities $(.12,.28,.42,.18)$.
Automatic transmission $T\sim\mathrm{Bernoulli}(.45+.06\mathbf1[M>2])$,
diesel $D\sim\mathrm{Bernoulli}(.4)$ and fiscal power
$P=4+M+2V+U\{0,1,2\}$. Log target is
\begin{align*}
y={}&10.3+.23M+.1V-.072A-.20\log(1+K/50000)\\
 &+.12C+.08T+.04D+.02P-.06\mathbf1[C=0,A>10]+\epsilon,
 \quad\epsilon\sim N(0,.1^2).
\end{align*}
Year is $2024-A$, model identifies make/variant, and location is uniform over
three labels. Four action fields are independently made unavailable with
probability .04 after target generation. Shared latent attributes create
feature correlations. Seeds 73101/73102 generate 6,000/1,500 train/evaluation
records. This is a stipulated generator, not inferred seller behavior.

\paragraph{Training schedules by experiment family.}
The inherited backbone has 250 boosting iterations and no fitted neural
residual when branches start. The earlier manuscript's six-initial-epoch and
two-three-epoch description was incorrect; the bound production config and
training receipts specify twelve residual epochs as shown below. No model or
result was changed to match the corrected description.
'''
    s+=table('Residual update schedules. Optimizer state resets at each update call; epochs and report-search sweeps are different quantities.',
       r'p{.32\linewidth}p{.28\linewidth}p{.28\linewidth}',
       ['Experiment family','Residual calls','Training response'],[
       ['Original feedback factorial','Two calls of six epochs','One start/two sweeps, fixed epoch scores'],
       ['Original static no-feedback','One call of twelve epochs','No query'],
       ['Matched RPL, gap controls and loss ablation','Two calls of six epochs','No query; common report maximization'],
       ['Search-strength intervention','Two calls of six epochs','One/two versus four/twenty; epoch/batch refresh'],
       ['Parameter/stability variants','Explicit per-variant settings','Declared variant; no transfer of scope'],
       ['RPL by five acquisition families','No new price-model fitting','Reused predictors; new evaluation responses']])
    s+=r'''
\section{Ten-seed recovery geometry, quotes and budget interaction}
\paragraph{All-edge diagnostics.}
We infer all eleven report-state quotes from each of sixty existing deployment
models (three sources, ten fitting seeds, $\lambda=0,1$ at $\beta=.5$).
For every legal concealed-field recovery edge, compute
$[g(T(s,a))-g(s)]_+$ with $g(s)=[q(s)-q(H)]_+$.
Reported rates use threshold $10^{-8}$ and all legal edges as denominator.
Quantiles below first include zero increments within each model and are then
averaged across seeds. They are not pooled-population quantiles or confidence
limits. Full per-model values, including maxima, are in edge-60-models.csv.
'''
    rows=[]
    for source in labels:
        for w in [0,1]:
            r=edges[(edges.source==source)&(edges.path_weight==w)].iloc[0]
            rows.append([labels[source],w,f'{100*r.gain_violating_rate:.2f}',f'{100*r.raw_quote_raising_rate:.2f}',f'{r.positive_increment_mean:.6f}',f'{r.increment_q95:.6f}',f'{r.increment_q99:.6f}'])
    s+=table(r'Ten-seed recovery diagnostics: positive-gain violations, raw quote increases and positive increment magnitudes (log units). Median and 90th percentile are zero in these source-level means except synthetic $\lambda=0$ has mean 90th percentile .004806.',
      'lrrrrrr',['Source',r'$\lambda$',r'Gain viol. (\%)',r'Quote up (\%)','Mean','95th','99th'],rows)
    s+=r'''
Every edge ending at $H$ has zero penalty because $g(H)=0$ and $g(s)\ge0$.
Thus the regularizer targets intermediate recovery states. An improved
positive-gain graph need not lower the raw quote on every recovery edge and
does not establish truthfulness or a fixed honest anchor.

\paragraph{Quote and query outcomes.}
Predicted log quotes are compared with the same log target records; currency
MAE is a separate metric. The MUCars honest/attacked biases move upward despite
decreasing MAE. The conditional intervals on their paired shifts include zero;
this is not evidence of deliberate anchor manipulation.
'''
    rows=[]
    for source in labels:
        for w in [0,1]:
            r=quotes[(quotes.source==source)&(quotes.path_weight==w)&(quotes.budget==.1)].iloc[0]
            rows.append([labels[source],w,*[f'{r[k]:.6f}' for k in ['honest_quote','attacked_quote','honest_bias','attacked_bias']],f'{100*r.actual_query_rate:.2f}',f'{100*r.failed_per_attempt:.1f}'])
    s+=table(r'Ten-seed mean log quotes and signed log biases at 10\% capacity. Queries are per all listings; failures in the last column are per attempted query.',
      'lrrrrrrr',['Source',r'$\lambda$','$q^H$','$q^A$','Honest bias','Attack bias',r'Query (\%)',r'Fail (\%)'],rows)
    s+=r'''
For JUCars $\lambda=1$, queries cover 10\% of all listings, failures 6.17\%
and successes 3.83\%; conditional failure is 61.7\%. A small change in the
per-listing failure rate need not imply a small operational failure fraction.
Positive log inflation is relative to the model's own honest quote; its
percentage reduction is neither a percentage price cut nor realized
overpayment avoided. No transaction-price outcome is observed.

\paragraph{Paired budget interaction.}
Let $D_b=I_{0,b}-I_{1,b}$ at fixed gap .5. We report $D_{.1}-D_0$ without
interpreting it as a causal mediation effect: sellers can change their reports
between budgets. Intervals independently resample ten common fitting seeds
and ten common batches 5,000 times, preserving all weight/budget pairings.
These post-hoc marginal percentile intervals are conditional on fixed cohorts
and do not cover development-selection uncertainty or guarantee simultaneous
coverage. They are distinct from the original studentized simultaneous bands.
'''
    rows=[]
    for source in labels:
        q=paired[paired.source==source].set_index('contrast');r=q.loc['budget_interaction']
        rows.append([labels[source],f'{q.loc["zero_query_improvement","mean"]:.6f}',f'{q.loc["capacity_10_improvement","mean"]:.6f}',f'{r["mean"]:.6f}',f'[{r.low:.6f}, {r.high:.6f}]'])
    s+=table('Budget interaction in positive log inflation. Real-source intervals include zero.',
      'lrrrr',['Source','$D_0$','$D_{.1}$','Interaction',r'Marginal 95\% interval'],rows)
    s+=r'''
Zero-query improvements are 98.3\% and 97.1\% of the 10\% improvements on
JUCars/MUCars. These are descriptive ratios, not causal contribution shares.
The evidence supports recovery-graph-inspired regularization with estimator
effects; it does not attribute most real-source improvement to verification.
For synthetic, changing primary inflation to the fixed-peer unilateral
envelope changes the paired reduction from .006267693 to .006266569, a
difference of $1.125\times10^{-6}$. This bounds that mean sensitivity without
certifying a joint equilibrium.

\section{Fixed reports versus reselected responses}
For each source/seed, retain the $\lambda=0$, 10\%-capacity report profile.
Recompute both models' quotes and their own scores/allocations at this fixed
profile. Separately evaluate each model's saved, endogenously selected profile.
For pre-query quote $q_0$, highest positive-score query without capacity $q_L$,
hard-capacity quote $q_A$ and honest quote $q_H$, report signed
$E=q_0-q_H$, $R=q_L-q_0$, $C=q_A-q_L$, $G=q_A-q_H$.
All 120 source/seed/weight/profile identities satisfy $E+R+C=G$ to numerical
tolerance. A negative mean $G$ can coexist with positive mean $[G]_+$.
'''
    rows=[]
    for source in labels:
        for w,mode,label in [(0,'own_response','Reference'),(1,'fixed_lambda0_response','Fixed report'),(1,'own_response','Reselected')]:
            r=decomp[(decomp.source==source)&(decomp.path_weight==w)&(decomp.report_mode==mode)].iloc[0]
            rows.append([labels[source],w,label,*[f'{r[k]:.6f}' for k in ['E','R','C','G','positive_G']]])
    s+=table(r'Ten-seed mean signed decomposition and positive gain, log units. The reference profile is common to the two $\lambda=0$ report modes.',
      'lrlrrrrr',['Source',r'$\lambda$','Profile','$E$','$R$','$C$','$G$','$[G]_+$'],rows)
    s+=r'''
Fixed reports remove report reselection but do not hold the predictor or
acquisition head fixed. These are diagnostic identities, not isolated causal
interventions. In particular, the real-source $R$ term does not consistently
decrease under RPL; a reduction in total positive gain must not be relabeled
as a direct reduction of that component.

\section{Matched stronger-gap comparison}
'''
    gap=N/'gap-supplement.tex'
    s+=gap.read_text() if gap.exists() else 'The new matched comparison is still running; no scientific result is asserted in this working supplement.\n'
    s+=r'''
\section{Numerical portability and retained failure}
An independently operated Mac completed the original six synthetic/seed-13
cells. Strict numerical reproduction failed under the original tolerances;
that verdict is retained. The ten-percent paired absolute improvement is
about .008024 locally and .008823 externally (53.97\% versus 57.54\%).
Direction agreement in one seed is supportive, but response quality differs:
$\lambda=1$ maximum regret changes from .0002041 to .0219727 at 10\% capacity.
The table distinguishes outcome direction from numerical equivalence.
'''
    s+=(ROOT/'notes/external-reproduction-synthetic-v1/numerical-difference-table-v1/table.tex').read_text()
    s+=r'''
Inputs and tree backbones matched; residual parameters differed. Each machine
was internally repeatable in the recorded repeats and thread comparisons.
The first recorded difference was an output-layer gradient; hidden forward
activations were not captured, so no underlying operator is causally isolated.
An isolated float64 candidate is not adopted or validated for scientific
performance. We neither relax tolerances nor retroactively substitute a new
scientific-equivalence criterion. No new external real-source comparison is
claimed. A stronger transportability claim requires a future locked protocol
and actual independent environment, including effect and regret checks.

The public \texttt{reproduction/macos-core-v2} and
\texttt{reproduction/windows-core-v1} directories contain minimal core training
procedures and data routes. The archived software excludes model weights and
listing-level outputs; it is not a self-contained binary model package.

\section{Version and evidence map}
The immutable software ZIP at
\href{https://doi.org/10.5281/zenodo.23447567}{10.5281/zenodo.23447567}
is version 1.0.0 from source \texttt{89ad56e}. It includes the earlier
90-cell crossing and external difference tables; it excludes manuscripts,
large weights, raw data and listing-level outcomes. Later paper revisions
and the present diagnostics are not retroactively inside that archive.
Current repository citation metadata follows the author order explicitly
confirmed by the authors: Tang, You (corresponding), Gu, Pang.

\begin{itemize}
\item Pre-review integrated paper: commit \texttt{45c2aef}; this is the earlier
28-page manuscript with the five-family crossing in its main text.
\item Matched gap runner and engineering replay: commit \texttt{5fb3437};
\path{experiments/run_review_gap_controls_v1.py} and its immutable manifest.
\item Mechanisms and cohort construction: commit \texttt{00eb579};
\path{notes/review-improvement-v1/}. Sixty models and 180 existing outcome
cells are newly diagnosed, not newly trained.
\item Current artifact hashes: \path{notes/review-improvement-v1/qa.json}.
They bind saved files; they do not establish scientific validity.
\end{itemize}
The main text and this supplement bound claims to the observed fixed
populations and declared response procedure. Fitting seeds do not sample
new training populations, and independent new-market effectiveness remains
unestablished.
\end{document}
'''
    legacy=N/'legacy-extended-appendix.tex'
    if legacy.exists():s=s.replace(r'\end{document}',legacy.read_text()+r'\end{document}')
    Path('/tmp/review-supplement-source.tex').write_text(s)
    return s

if __name__=='__main__':build()
