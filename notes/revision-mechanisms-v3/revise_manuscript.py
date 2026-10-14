"""Backfill verified v3 diagnostics into the existing manuscript in place."""
from pathlib import Path
import json,re,hashlib,difflib
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
baseline=HERE/'baseline-reviewed-source.tex';s=baseline.read_text()
assert hashlib.sha256(baseline.read_bytes()).hexdigest()=='9560dbc977cbf14e92ea8c07080560453837cdf36dc899e1d81c9b3eb6da4d2e'
variance=pd.read_csv(HERE/'variance_components.csv');pilot=pd.read_csv(HERE/'final_record_pilot.csv');cost=pd.read_csv(HERE/'cost_mechanism_means.csv')
abstract=r'''Verification can recover withheld information without reducing a seller's
valuation gain. We study secondhand-price prediction with natural missingness,
charged failed queries and batch capacity. A restricted information frontier
bounds verification under uniform honest precision; recovery-path analysis
instead diagnoses actual learned models. Exhaustive prediction tables show
gain-increasing partial recoveries on all three cohorts.
A ten-seed factorial study separates initial objective, acquisition, feedback
and allocation across 4,320 cells and 4.32 million repeated records. At 10\%
capacity, all 36 zero-cost feedback contrasts worsen inflation; a post-hoc
simultaneous sensitivity retains 31 adverse intervals for that family.
Removing both real-source evaluation caps preserves all 24 adverse directions,
with 22 unadjusted intervals excluding zero. For the two crossing-zero MUCars
contrasts, fitting-seed main effects explain over 98\% of conditional bootstrap
variance; this neither establishes equivalence nor measures training-population
uncertainty. Ordinary-benefit and acquisition-conditioned controls also outperform
the original SAV candidate on synthetic and JUCars inflation. A history cap
can worsen attacked error or query failures after responses change. Positive
costs reverse a synthetic subset ranking alongside sharply reduced concealment
and high query failure, limiting its interpretation as better feedback.
A restricted final-record envelope illustrates honest-error and coverage costs.
We deliver an explicit audit contract and validator, disclose shared audit
primitives, and add an exhaustive state-transition oracle. The contribution is
a controlled audit, a recovery failure diagnostic and explicit information
and deployment boundaries, without a universal method advantage.'''
s=re.sub(r'\\begin\{abstract\}.*?\\end\{abstract\}',lambda _:r'\begin{abstract}'+'\n'+abstract+'\n'+r'\end{abstract}',s,count=1,flags=re.S)
count=len(re.findall(r"\S+",abstract));assert count<=250,count
old='''excluding zero adversely. A joint gate compares no feedback/top-$B$ with'''
new='''excluding zero adversely for the capped primary evaluation. The uncapped
MUCars sensitivity also excludes zero in 10/12 intervals
(Section~\\ref{sec:full_validation}). A joint gate compares no feedback/top-$B$ with'''
assert old in s;s=s.replace(old,new,1)
old='''an explicitly uncertified fallback. It is an analytical alternative, not an
empirically evaluated replacement in the present comparisons.'''
new=r'''an explicitly uncertified fallback. A three-seed categorical-domain pilot
quantifies one limited honest-error cost: MUCars shared-support MAE increases
by 10.49--23.87 currency units, concentrated among 28 naturally incomplete
records. Mileage is observed and fixed, so this is not a tested four-field
replacement (Appendix~\ref{app:mechanism_diagnostics}).'''
assert old in s;s=s.replace(old,new,1)
anchor='''JUCars and MUCars retain adverse mean inflation directions for both allocators'''
addition=r'''The reversal accompanies strong concealment deterrence. At uniform cost
0.02, synthetic top-$B$ mean hidden-field counts are bounded by
$[0.130,0.165]$ without feedback and $[0.130,0.181]$ with it, versus directly
observed zero-cost means 0.996 and 0.957. These bounds retain nonconverged
profiles rather than treating the inflation--net-deviation gap as exact cost.
The legal net-deviation envelope falls by 77.5\% and 81.1\%, respectively.
Failed queries reach 9.47\% and 9.40\% per listing; at 10\% capacity, at least
94.7\% and 94.0\% of actual queries fail. Thus the local ranking reversal
coexists with suppressed concealment and predominantly unsuccessful
verification; it does not isolate improved feedback quality as its cause.
Appendix~\ref{app:mechanism_diagnostics} gives the utility-based bounds.

'''
assert anchor in s;s=s.replace(anchor,addition+anchor,1)
s=s.replace(r'\subsection{Full-validation evaluation coverage}',r'\subsection{Full-validation evaluation coverage}\label{sec:full_validation}',1)
s=s.replace('''responses. The original 1,000-record prefixes are reproduced and reused;
no model is retrained.''','''responses. The first ten batches reuse the original prediction/outcome bytes
through symlinks, with original receipt provenance retained in the extended
bindings; only the remaining batches are newly evaluated. No model is retrained.''',1)
anchor='''The original capped factorial remains the declared primary comparison.'''
addition=r'''

An exact conditional seed/batch variance decomposition, including weighted
partial batches, attributes 98.39\% and 98.28\% to fitting-seed main effects
for the uncapped MUCars masking/suppression top-$B$ and minimax contrasts.
Their capped shares are 90.97\% and 87.42\%; interval-width ratios alone do
not identify these components. Under the empirical conditional design,
thirty instead of ten independent fitting seeds would project standard
deviations to approximately 58\% of their current values, while eliminating
only batch resampling noise leaves approximately 99\%. These are design
projections, not newly trained results. The stable small estimates and
crossing-zero intervals establish neither zero effect nor equivalence;
fitting randomness on fixed training records also does not quantify
training-population uncertainty. Details are in
Appendix~\ref{app:mechanism_diagnostics}.'''
assert anchor in s;s=s.replace(anchor,anchor+addition,1)
# Keep the conclusion's exception coupled to its diagnostic qualification.
s=s.replace('''A three-seed positive-cost sensitivity reverses the synthetic top-$B$ feedback ranking, further limiting generalization.''','''A three-seed positive-cost sensitivity reverses the synthetic top-$B$ feedback ranking alongside sharply reduced concealment and high query failure, further limiting generalization.''')
# The availability section is the smallest stable place to identify the actual protocol product.
anchor='''\\appendix'''
assert anchor in s
# Place a brief protocol pointer before Discussion instead of adding another results subsection.
protocol=r'''
The accompanying \path{audit-protocol/} artifact provides a machine-readable
worked contract, an execution protocol and a standard-library validator of
six directly bound evidence files. Six invalid-contract controls are rejected.
It is an explicit post-hoc protocol, not preregistration or a certificate of
scientific validity or independent end-to-end reproduction.

'''
s=s.replace(r'\section{Discussion}',protocol+r'\section{Discussion}',1)
# Detailed supplementary methods and a compact cost table.
appendix=r'''
\section{Conditional uncertainty and mechanism diagnostics}\label{app:mechanism_diagnostics}
\subsection{Exact conditional crossed-bootstrap variance}
Let $Y$ be a paired-difference matrix with $S$ fitting seeds and $K$ batches.
Independent bootstrap seed weights $U$ and record-normalized batch weights
$V$ give $U^\top YV$. Write $m=\mathbb E[V]$, $C=\operatorname{Cov}(V)$,
$r=Ym-\mathbf1\,\operatorname{mean}(Ym)$,
$z=\operatorname{mean}_{s}(Y)$ and
$R=Y-\mathbf1z^\top-r\mathbf1^\top$. The conditional variance decomposes as
\[
 \frac{\|r\|^2}{S^2}+z^\top Cz+
 \frac{1}{S^2}\sum_s R_s^\top C R_s.
\]
These are seed-main, batch-main and interaction terms. Batch-weight moments
are calculated by conditioning on the multinomial count of the single
partial batch, retaining ratio normalization. Exhaustive balanced and
unequally weighted $2\times2$ resampling independently checks the formula.
All 48 capped/full real-source feedback decompositions are retained.
Thirty-seed projections divide seed and interaction terms by three; the
batch-noise-free projection holds the empirical batch distribution fixed.
Neither supplies new training runs, equivalence evidence or population coverage.

\subsection{Concealment identification from saved utility summaries}
For one listing let $C_i=c_i k_i$ be concealment cost, $G_i$ positive expected
quote inflation, $N_i$ the positive best-legal-utility gain over truth, and
$\rho_i$ remaining unilateral regret. Since truthful utility is its honest
quote,
\[
 C_i-\rho_i\le G_i-N_i\le C_i.
\]
Thus $\max(\overline G-\overline N,0)$ bounds mean cost below; adding
$\max_i\rho_i$ and capping by $2\overline c$ bounds it above. Uniform-cost
hidden-field bounds divide by $c$; heterogeneous costs in $[.01,.03)$ give
bounds using .03 and .01, respectively. Dividing by mean heterogeneous cost
would not identify mean hidden fields. Positive-cost states were not saved;
all 20 nonconverged batches remain in the bounds. The inequality passes
768 exhaustive toy utility/returned-state checks. The paired zero-cost
concealment counts use saved states directly. Neither co-occurrence nor this
accounting identity identifies a causal mediation effect.

\subsection{Restricted final-record honest-error pilot}
Three frozen robust/no-feedback models per real source (seeds 13, 42 and
2026) enumerate completions of transmission, fuel and body condition from
their training-encoder vocabularies, including missing tokens. Mileage must
be observed and fixed; other covariates stay fixed. Unsupported observed
categories and missing mileage abstain. The same original 1,000 records per
source are used without tuning or retraining. Current records are included
in the minima; singleton sets preserve their original quotes exactly.
Shared-support errors and abstentions are reported separately.

\begin{table}[htbp]\centering\small
\begin{tabular}{llrrr}\toprule
Source & Support & Records & Honest-MAE change & Mean quote reduction\\\midrule
JUCars & Covered & 801 & 0 & 0\\
JUCars & Missing category & 1 & 0 & 0\\
MUCars & Covered & 999 & 10.49--23.87 & 200.21--240.51\\
MUCars & Missing category & 28 & 374.24--851.51 & 7,143.33--8,581.21\\
\bottomrule\end{tabular}
\caption{Final-record categorical-envelope pilot. Entries are per-source
three-seed ranges, not uncertainty intervals; positive MAE changes are worse.
Price quantities use source currency units. Missing-category rows are subsets
of covered rows, not additional observations. JUCars abstains on 199 records,
MUCars on one, all for missing mileage.}\label{tab:final_record_pilot}
\end{table}

Each JUCars model evaluates 806 completions; each MUCars model evaluates
1,139. All baseline quotes match saved predictions within $5\times10^{-6}$
in log quote; sampled completions also match the production all-state
inference route within that tolerance. Predictor primitives are shared.
Only one covered JUCars and 28 covered MUCars records have a naturally missing
category, explaining the concentration of effects. The guarantee covers only
the declared categorical domain with fixed observed mileage. It does not
cover mileage concealment, unseen values or the original full four-field
game, and this pilot supplies no confirmatory or universal method advantage.

'''
s=s.replace(r'\begin{thebibliography}',appendix+r'\begin{thebibliography}',1)
# Make the qualitative matrix carry the mechanism qualifier too.
s=s.replace('''Positive costs reverse one subset ranking.''','''Positive costs reverse one subset ranking alongside strong concealment deterrence.''')
s=s.replace(r'\addlinespace'+'\n'+r'\bottomrule',r'\bottomrule')
target=ROOT/'paper/innovation-addendum-v1.tex';target.write_text(s)
(HERE/'manuscript-changes.patch').write_text(''.join(difflib.unified_diff(baseline.read_text().splitlines(True),s.splitlines(True),fromfile='reviewed-source',tofile='revised-source')))
inputs=[baseline,HERE/'variance_components.csv',HERE/'cost_mechanism_means.csv',HERE/'final_record_pilot.csv']
receipt={'status':'source_backfilled_pending_compile_and_layout','abstract_words':count,'source_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'inputs':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
(HERE/'manuscript-revision-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
# Exact excerpts for the response skill correspondence checker.
excerpts=[addition.strip(),protocol.strip(),r'''The reversal accompanies strong concealment deterrence.''']
(HERE/'response-excerpts.tex').write_text('% Internal exact correspondence excerpts; not a submitted response letter.\n'+'\n\n'.join('\\RevisedExcerpt{'+x+'}' for x in excerpts)+'\n')
print(json.dumps(receipt,indent=2))
