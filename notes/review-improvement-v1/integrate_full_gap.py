"""Integrate checked complete controls, preserving the original scientific blocks."""
from pathlib import Path
import json, shutil
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
N=Path(__file__).parent
P=ROOT/'paper/innovation-addendum-v1.tex'
LABELS={'synthetic':'Synthetic','jucars':'JUCars','mucars':'MUCars'}

def selected_table(data):
    lines=[r'\begin{table}[htbp]\centering\small',
      r'\caption{Matched training-only selection at 10\% capacity. Each family has four candidates; each row averages ten selected fitting-seed outcomes. Inflation is positive log gain, MAE is in source currency, and failures are percent of all listings. These are selected families, not the fixed endpoints in Table~\ref{tab:rpl_primary}.}',
      r'\label{tab:stronger_gap}',r'\begin{tabular}{llrrrr}\toprule',
      r'Source & Family & Inflation & Honest MAE & Attacked MAE & Failed (\%)\\\midrule']
    for source,label in LABELS.items():
        for family,display in [('rpl','RPL'),('gap','Gap-only')]:
            r=data[(data.source==source)&(data.family==family)].iloc[0]
            lines.append(f'{label} & {display} & {r.mean_positive_log_inflation:.6f} & {r.clean_mae:.2f} & {r.attack_mae:.2f} & {100*r.failed_query_fraction:.2f}'+r'\\')
        if source!='mucars':lines.append(r'\midrule')
    return '\n'.join(lines+[r'\bottomrule\end{tabular}\end{table}'])

def main():
    verify=json.loads((N/'gap/verification.json').read_text())
    assert verify['status']=='all_candidates_and_selection_checked'
    assert verify['unique_cells']==210 and verify['new_fit_receipts_checked']==360
    means=pd.read_csv(N/'gap/selected-means.csv')
    grid=pd.read_csv(N/'gap/all-candidate-means.csv')
    effects=pd.read_csv(N/'gap/selected-paired-effects.csv')
    backup=N/'before-full-gap-integration.tex'
    if not backup.exists():shutil.copy2(P,backup)
    s=backup.read_text()
    abstract=r'''Recovering withheld information can increase a seller's predicted price when the valuation model is nonmonotone. We study this failure under natural missingness, charged failed queries and shared verification capacity. A recovery-path decomposition motivates a regularizer that penalizes increases in positive concealment gain along legal recovery edges. At 10\% query capacity, ten-seed unit-weight RPL reduces mean positive log inflation by 50.41\%, 26.58\% and 23.81\% on synthetic, JUCars and MUCars relative to same-gap zero-path controls. These improvements do not establish the advantage of the path loss. With equal four-candidate training-only selection, stronger gap-only regularization has lower inflation in all thirty source--seed pairs: source means are 34.55\%, 63.37\% and 30.23\% lower than selected RPL. Its honest error is higher on synthetic but lower on both real sources. Most real-source RPL improvement is already present without queries, limiting a verification-mechanism interpretation. A separate three-seed, 90-cell crossing lowers inflation in all 45 pairs when RPL is combined with five task-adapted acquisition families at fixed gap weight. Stronger response search also qualifies earlier feedback-failure results. Retrospective cohorts, finite-response regret and failed strict cross-machine numerical reproduction bound these findings. The contribution is a recovery-graph formulation and controlled evidence of its benefits and limits, rather than a generally superior valuation method.'''
    a=s.index(r'\begin{abstract}')+len(r'\begin{abstract}');b=s.index(r'\end{abstract}',a)
    s=s[:a]+'\n'+abstract+'\n'+s[b:]
    s=s.replace('families, including native-head references and prediction/query costs.\nComponent removals, budget variation and computational checks bound both studies.',
      'families, including native-head references and prediction/query costs.\nA matched stronger-gap control gives each family four candidates and uses only\ntraining-fold predictions for selection. Component removals, budget variation\nand computational checks bound these studies.')
    a=s.index('The evidence supports conditional use.');b=s.index(r'\section{Related work}',a)
    s=s[:a]+r'''The stronger control changes the practical conclusion. RPL improves on the
fixed-gap reference, but training-selected gap-only regularization has lower
inflation in all thirty source--seed pairs and lower mean honest and attacked
error on both real sources. Synthetic results retain a prediction--incentive
trade-off. Most real-source RPL improvement is already present without queries.
Thus the recovery graph provides a useful diagnostic and training target,
while the present experiments do not justify choosing RPL over a tuned gap
penalty. A deployment choice must compare the complete predictor--policy pair
on incentives, prediction and verification costs.

'''+s[b:]
    s=s.replace(r'RPL evaluation query capacities & $0,0.1,0.3$\\',r'RPL evaluation query capacities & $0,0.1,0.3$\\'+'\n'+r'Stronger-gap candidates / evaluation capacity & $0.5,1,2,4$ / $0.1$\\')
    old='fit/statistics-audit upgrade.\n\nThe checks reconstruct'
    new='''fit/statistics-audit upgrade. The stronger-gap control adds 90 evaluations
and 360 residual fitting stages (three outer folds plus deployment for each
source/seed/weight); tree backbones are reused. Together with 120 reused RPL
candidate evaluations, it yields 210 unique candidates and 60 selected rows.
Model/fit/checkpoint/outcome/selection bindings and independent metric
reaggregation are checked; a separate scalar-score implementation checks
all sixty training-only choices. This is not a new full four-stage chain.

The checks reconstruct'''
    assert old in s;s=s.replace(old,new)
    old=r'Remaining completion-study support & Hash bindings, utility checks and recorded summaries & No whole-study four-stage upgrade of all 1,719 cells\\'
    new=r'Matched stronger-gap control: 90 new cells, 360 fit stages & Fit/checkpoint/outcome bindings, independent metric reaggregation and scalar selection check; 120 candidates reused & Training-only retrospective selection; no new complete four-stage chain\\'+'\n'+old
    assert old in s;s=s.replace(old,new)
    anchor=r'\paragraph{Predictive and verification costs.}'
    insertion=r'''\paragraph{Matched stronger-gap control.}
To test whether the path term adds value beyond a stronger existing penalty,
we compare RPL $(\lambda\in\{0,.1,.5,1\},\beta=.5)$ with gap-only
$(\beta\in\{.5,1,2,4\},\lambda=0)$. Folds, tree backbones, residual updates,
no-feedback response search and final head construction are matched.
For each source/seed/family, training-only three-fold out-of-fold (OOF)
predictions select the smallest mean maximum legal no-query positive gain,
subject to honest currency MAE at most 1.05 times the common reference.
The rule was fixed before new training and reads no evaluation outcomes;
it is a retrospective comparison on previously studied populations.

All sixty selected models meet the OOF constraint. Gap-only selects $\beta=4$
in all thirty pairs; RPL selects $\lambda=1$ in 28 and $.5$ in two JUCars pairs.
Gap-only inflation is lower in all thirty pairs, with ratios of source means
34.55\%, 63.37\% and 30.23\% below selected RPL
(Table~\ref{tab:stronger_gap}). Its mean honest MAE changes by $+1.98\%$,
$-1.29\%$ and $-2.27\%$; attacked MAE and failed-query means also favor
gap-only on both real sources. Honest and attacked error improve in nine of
ten seeds on each real source, whereas both errors increase in all synthetic
seeds. These results support a synthetic trade-off and reject a claim of
general empirical superiority of RPL over the tested stronger-gap control.
Supplement S4 reports every candidate, paired intervals, selection details
and the complete trade-off figure. Neither largest weight is an established
optimum; both lie at the boundary of their respective finite grids.

'''+selected_table(means)+'\n\n'
    assert s.count(anchor)==1;s=s.replace(anchor,insertion+anchor)
    old='Synthetic honest-error and failed-query increases, together with finite\nresponse regret, preclude a universal dominance claim. The matched crossing'
    new='''The stronger-gap comparison further limits the method claim: with matched
four-candidate training-only selection, gap-only lowers inflation in all
thirty pairs and lowers mean honest/attacked error on both real sources.
On synthetic, it trades higher prediction error for lower inflation. The
path loss is therefore an interpretable recovery-graph intervention whose
incremental practical advantage over a tuned gap penalty is not established.
The matched crossing'''
    assert old in s;s=s.replace(old,new)
    s=s.replace('decision specific to the complete predictor--policy pair.',
      'decision specific to the complete predictor--policy pair. That crossing\nkeeps $\\beta=.5$ and does not test stronger-gap stacking with the five families.')
    s=s.replace(r'\paragraph{Predictive and verification costs.}',r'\paragraph{Fixed-gap predictive and verification costs.}')
    s=s.replace(r'\paragraph{Budget boundary.}',r'\paragraph{Fixed-gap budget boundary.}')
    s=s.replace('''OpenAI Codex assisted implementation, orchestration, analysis, literature
checks, data-derived figures and drafting. Figures use saved empirical
results, not invented images. Authors retain responsibility for interpretation
and approval. Yuchen Tang drafted the manuscript. Fengqin You provided supervision as advisor, and Junxiang Gu provided guidance on manuscript writing.''',
      '''OpenAI Codex assisted implementation, orchestration, analysis, literature
checks, figures and drafting. Figures use saved empirical results. Authors
retain responsibility for interpretation and approval. Yuchen Tang wrote the
manuscript; Fengqin You supervised as advisor; Junxiang Gu guided manuscript writing.''')
    P.write_text(s)
    si=r'''\paragraph{Protocol and training-only selection.}
The fixed protocol precedes the new fits. RPL uses
$\lambda\in\{0,.1,.5,1\},\beta=.5$; gap-only uses
$\beta\in\{.5,1,2,4\},\lambda=0$. The common $(0,.5)$ point is shared:
seven unique candidates per source/seed, or 210 evaluations. Ninety new
gap cells require 360 residual fits (three outer folds and deployment),
reusing existing tree backbones. The other 120 candidate cells reuse the
ten-seed RPL experiment at 10\% capacity. All models use the same no-feedback
schedule, folds, minibatch orders, optimizer resets and final OOF head
construction. Matching candidate counts and update schedules does not imply
equal wall-clock cost. An engineering optimization omits unused intermediate
guidance heads in no-feedback training, retaining the final OOF head;
a complete JUCars/seed-13 fold replay matched residual parameters,
all 1,000-by-11 quotes and training logs exactly.

For each source/seed/family, choose the smallest training OOF mean maximum
legal no-query positive log gain, subject to OOF honest currency MAE at most
1.05 times the common $(0,.5)$ reference. Ties use honest MAE then candidate
order. With no feasible candidate, choose smallest honest MAE, then gain,
then order, and mark constraint failure. The scalar scores and selection
receipts are fixed before evaluation; no evaluation metric enters selection.
All sixty choices meet the constraint, with no fallback. Gap-only selects
$\beta=4$ thirty times. RPL selects $\lambda=1$ for ten synthetic, eight
JUCars and ten MUCars seeds; JUCars seeds with the other two choices select
$\lambda=.5$. OOF feasibility need not imply the same constraint on unseen
populations. The original cohorts had been used in development, so this is
not independent confirmation or an expanded-population test.

\paragraph{All candidates and numerical response quality.}
Table~\ref{tab:gap_all} retains the complete grid, including failed queries
and finite-response quality. $\rho_{\max}$ is the worst observed regret over
all ten seeds and all batches, not a mean of seed maxima; NC is the percentage
of all seed--batch responses that did not meet the response criterion.
All ninety new gap cells have zero remaining regret and zero nonconverged
batches. Reused RPL candidates retain eight nonconverged batches: seven
synthetic and one JUCars, with worst regret .023513. Among selected RPL
models only two synthetic batches remain nonconverged (2/100, worst .011042);
selected real-source RPL responses have zero regret. No failed batch or
unfavorable candidate is removed.
\begin{table}[htbp]\centering\small
\setlength{\tabcolsep}{4pt}
\caption{Complete ten-seed means at 10\% capacity. $I$ is positive log inflation;
$H,A$ are honest/attacked MAE in source currency; $F$ is failed attempts per
all listings (percent), and NC is percent of seed--batches. The shared
$(\lambda,\beta)=(0,.5)$ baseline appears once per source.}
\label{tab:gap_all}
\begin{tabular}{lrrrrrrrr}\toprule
Source & $\lambda$ & $\beta$ & $I$ & $H$ & $A$ & $F$ & $\rho_{\max}$ & NC\\\midrule
'''
    for source,label in LABELS.items():
        q=grid[grid.source==source].sort_values(['beta','path_weight'])
        for r in q.itertuples():
            si+=f'{label} & {r.path_weight:g} & {r.beta:g} & {r.mean_positive_log_inflation:.6f} & {r.clean_mae:.2f} & {r.attack_mae:.2f} & {100*r.failed_query_fraction:.2f} & {r.max_remaining_response_regret:.6f} & {100*r.nonconverged_batch_fraction:.1f}'+r'\\'+'\n'
        if source!='mucars':si+=r'\midrule'+'\n'
    si+=r'''\bottomrule\end{tabular}\end{table}
\paragraph{Selected comparison and uncertainty.}
Gap-only has lower positive log inflation in 30/30 paired seeds.
Selected means are reported in the main table. Its source-level honest
MAE changes relative to selected RPL are $+1.98\%,-1.29\%,-2.27\%$
(ratios of source means). Both honest and attacked MAE improve in 9/10
paired seeds on each real source, but worsen in all ten synthetic seeds.
Average failures decrease on all three sources. These are distinct outcomes,
not evidence of a scalar welfare optimum. The largest weights are boundary
points of the tested grids, not validated optima or recommended defaults.

Table~\ref{tab:gap_paired} independently resamples ten paired fitting seeds
10,000 times (analysis RNG seed 20261019). Marginal percentile intervals are
post-hoc, conditional on fixed records and the chosen selection rule. They
include selection's observed training randomness, but do not cover the
development process, new populations or simultaneous multiple comparisons.
No independent confirmation claim follows from excluding zero.
\begin{table}[htbp]\centering\small
\caption{Paired selected gap-minus-RPL mean differences and marginal 95\%
intervals. Negative values favor gap-only. Error differences use source
currency; inflation differences are log units.}
\label{tab:gap_paired}
\begin{tabular}{llrr}\toprule
Source & Outcome & Mean difference & Marginal interval\\\midrule
'''
    for source,label in LABELS.items():
        for metric,display in [('mean_positive_log_inflation','Inflation'),('clean_mae','Honest MAE'),('attack_mae','Attacked MAE')]:
            r=effects[(effects.source==source)&(effects.metric==metric)].iloc[0]
            fmt='.6f' if metric=='mean_positive_log_inflation' else '.2f'
            si+=f'{label} & {display} & {r.gap_minus_rpl:{fmt}} & [{r.low:{fmt}}, {r.high:{fmt}}]'+r'\\'+'\n'
        if source!='mucars':si+=r'\midrule'+'\n'
    si+=r'''\bottomrule\end{tabular}\end{table}
\begin{figure}[htbp]\centering
\includegraphics[width=\textwidth]{figures/review-v1/gap-tradeoffs.pdf}
\caption{Complete candidate and selected trade-offs at 10\% capacity.
(a--c) All seven unique candidates over ten fitting seeds. Pale points are
individual fits; colored symbols are means of same-seed percentage changes
relative to the common $(\lambda,\beta)=(0,.5)$ control. The common point
coincides at the origin; connecting lines only guide the candidate order.
Higher inflation reduction and lower honest-error change are favorable.
(d--f) Ten same-seed percentage changes from selected RPL to selected gap-only;
black diamonds are their means. Lower values on both axes are favorable.
These means of seed ratios differ from the ratios of source means in the
main text. Full observed scatter represents fitting variation, with no
confidence region or population extrapolation. Synthetic trades lower
inflation for higher error; the real-source means improve on both axes.}
\label{fig:stronger_gap_tradeoffs}
\end{figure}
\paragraph{Evidence and interpretation.}
Model, checkpoint, outcome and training-selection hashes bind the comparisons;
new-cell inflation and both MAE metrics are independently reaggregated from
saved outcomes. All 360 fit-stage records retain the two six-epoch updates
and declared gap/path settings. A separate implementation imports no runner
and independently checks the candidate sets, constraints and sixty choices
from saved OOF scalar scores; it does not regenerate OOF predictions.
This is a bounded computational check, not a new complete four-stage audit.
The complete grid, scores, selected cells and paired contrasts are released
under \path{notes/review-improvement-v1/gap/}. Scalar receipts are archived
separately, excluding weights, arrays and listing-level outcomes.

The comparison does not support practical superiority of RPL over a tuned
gap penalty on these cohorts. It also does not test stronger-gap combinations
with the five acquisition families: that separate 90-cell crossing holds
$\beta=.5$ and tests a different question. The graph loss remains a concrete
recovery-targeted formulation; its incremental benefit beyond stronger
gap regularization is unestablished under the present selection protocol.
'''
    (N/'gap-supplement.tex').write_text(si)
    b=N/'build_supplement.py';bs=b.read_text()
    anchor=r'\item Current artifact hashes:'
    if '2638dee' not in bs:
        bs=bs.replace(anchor,r'''\item Equivalent no-feedback optimization: commit \texttt{7d870c2};
\path{experiments/run_review_gap_controls_v2.py}. The v1 checkpoints remain
bound and reusable; the engineering equivalence check precedes continuation.
\item Complete stronger-gap analysis and independent selection check:
commit \texttt{c7a577a}; all 90 new cells, 360 fit records and 210 candidates.
The complete trade-off figure and its rendered checks are in \texttt{2638dee}.
'''+anchor)
        b.write_text(bs)
    dest=ROOT/'paper/review-supplement-v1/images/figures/review-v1';dest.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'paper/figures/review-v1/gap-tradeoffs.pdf',dest/'gap-tradeoffs.pdf')
    print('Main and S4 source integrated; build supplement before compiling.')

if __name__=='__main__':main()
