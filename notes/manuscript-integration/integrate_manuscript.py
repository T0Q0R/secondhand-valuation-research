"""Integrate already audited sections into the current standalone manuscript."""
from pathlib import Path
import re,json,hashlib
ROOT=Path(__file__).resolve().parents[2]
source=ROOT/'paper/innovation-addendum-v1.tex'
old=(ROOT/'notes/manuscript-integration/pre-integration-source.tex').read_text()
parts=re.split(r'(?=\\section\{)',old)
blocks={}
for part in parts[1:]:
 title=re.match(r'\\section\{([^}]+)\}',part).group(1)
 blocks[title]=part
last=blocks['Claims and evidence'];bib=last[last.index(r'\begin{thebibliography}'):]

def body(name):return re.sub(r'^\\section\{[^}]+\}\n','',blocks[name],count=1)
intro=r'''\section{Introduction}\label{sec:introduction}
Secondhand valuation must use incomplete seller-provided descriptions while
allowing for deliberate withholding. A vehicle with no recorded mileage and a
vehicle whose mileage was suppressed can present the same public report. A
platform may request additional evidence, but available verification capacity
is finite and a naturally absent field may remain unavailable after a paid
attempt. This study models the resulting interaction between an itemwise price
predictor and a batch-coupled verification policy. The outcome is an advertised
price prediction, rather than a transaction price or a transfer mechanism.

A query need not reduce the incentive created by an incomplete report. Consider
an illustrative nonmonotone predictor whose quotes are 10 for a truthful record,
12 after two fields are withheld, and 14 after only one is recovered. Successful
partial recovery then raises the quote. These illustrative quote units are not
empirical measurements. They expose a distinction between obtaining information
and using the recovered record to reduce a seller's expected gain. Moreover,
changing one report can displace another listing from a hard-capacity query set.
Information value evaluated in isolation does not capture that competition.

Strategic withholding has established regression and classification treatments
\cite{smi,withheld}. Audits and partial-verification mechanism design likewise
have established incentive guarantees under their respective action and outcome
models \cite{audits,partial}. These results motivate verification, but they do
not imply that an error-reduction acquisition score, a fixed library of query
rules, or a finite-round feedback-training implementation will improve
continuous valuation after failed-but-charged recovery. Ordinary active feature
acquisition also targets predictive information rather than this strategic
quotation objective \cite{activeoracle}.

We study two complementary questions. First, how does a uniform honest-precision
requirement limit the strategic gain that a hard verification budget can remove
when natural and strategic absence are observationally identical? Second, which
implemented training and allocation choices actually account for changes in
valuation outcomes?

A finite oracle enforces common decisions for identical
public reports. A recovery-path decomposition separates the initial report,
local recovery and capacity competition. A history-dependent cap provides a
restricted unilateral-gain guarantee. A matched factorial experiment separates
initial objective, acquisition score, policy feedback and allocation.

The contribution is a set of bounded analytical and empirical findings.
Section~\ref{sec:information} characterizes a tight precision--incentive frontier
in a single-recoverable-field family and supplies an implementable marginal
reference. Section~\ref{sec:recovery} identifies a recovery-path failure and
states the cap's fixed-peer guarantee. Sections~\ref{sec:experiment_setup}
and~\ref{sec:factorial_results} report a fully audited, ten-seed, three-source
factorial study. At its prespecified 10\% capacity, all 36 feedback comparisons
increase mean inflation; a robust initial objective instead helps consistently
on MUCars. Positive interaction effects can represent less harm rather than
improvement. These contributions concern the stated information boundary and
implementation; they do not claim a new general linear-programming method,
universal method superiority or a market-equilibrium guarantee.

'''
related=r'''\section{Related work}\label{sec:related}
\subsection{Strategic withholding and predictive missingness}
Zhang et al. studied strategic missingness in regression through support-margin
imputation \cite{smi}. Krishnaswamy et al. characterized truthful classifiers
and constructed predictors resistant to feature withholding \cite{withheld}.
These works already establish that natural absence and deliberate concealment
can have the same report. We therefore do not claim that continuous prediction
or ambiguous missingness defines a new problem. Our analytical question adds a
uniform honest-quote error constraint and a hard query budget. Removing the
incentive by changing predictions may violate that precision constraint, which
is distinct from average mean absolute error.

\subsection{Verification, randomization and information acquisition}
Estornell et al. minimize incentives through budgeted audits, including threshold
and top-$k$ settings \cite{audits}. Zhang et al. study automated classification
mechanisms with partial verification, including randomized decisions and
combinatorial costs \cite{partial}. Marginal-probability representations are
established in security-game optimization \cite{marginals}. The finite oracle
here specializes those tools to public report classes and continuous quote
recovery, with failed queries charged against capacity. Its complete finite
coverage is a certificate within the declared world universe, not a guarantee
for unseen types. Active feature acquisition addresses budgeted information
selection \cite{activeoracle}; its predictive objective differs from the signed
unilateral quotation difference audited here.

\subsection{Strategic feedback and contextual policy classes}
Performative prediction analyzes retraining when deployment changes the data
\cite{performative}; strategic empirical risk minimization differentiates through
modeled user responses \cite{serm}. Contextual games use public side information
to condition decisions \cite{contextual}. Joint score and audit design is also
explicit in recent audit-risk work \cite{auditrisk}. We do not transfer their
convergence conditions to our nonconvex, finite-round training loop or introduce
randomization as a new technique. Instead, we test a frozen-policy implementation
under matched fitting budgets. Our constructed policy-library separation also
includes a stronger small context-aware comparator that closes the gap. This
prevents a restricted library from being mistaken for evidence that dynamic
weights or an LP solver are intrinsically necessary.

'''
problem=r'''\section{Problem formulation}\label{sec:problem}
\subsection{Reports, queries and seller utility}
A batch contains $n=100$ listings. Listing $i$ has a latent recorded feature
vector $x_i$, including four optional action fields: mileage, transmission,
fuel type and body condition. Let $M_i$ be its naturally absent fields. A seller
chooses a concealment set $s_i$ containing at most two available action fields.
Its public report $r_i(s_i)$ replaces fields in $M_i\cup s_i$ with missing values.
Available values cannot be fabricated, changed or recovered from public
identifiers. A missingness indicator does not disclose membership in $M_i$.

The platform observes the whole report batch $r=(r_1,\ldots,r_n)$, locks the
reports and chooses a possibly randomized allocation. It may query at most one
publicly missing field per selected listing, with at most $B=\lfloor bn\rfloor$
queries on every realized draw. A query of a concealed recorded field recovers
that value; a query of a naturally absent field fails. Both spend one unit.
A fixed itemwise model produces log quotes before and after the selected query.
Scores and allocations at deployment may use public reports and model outputs,
but not the latent recoverability indicator or the advertised target.

Seller utility is the expected log quote minus concealment cost. Main empirical
costs are zero; all randomization occurs after reports are locked. Evaluation
uses finite response search and explicitly checks every legal single-seller
report against fixed peer reports, reallocating the batch each time. A returned
profile with small remaining regret is a local deviation diagnostic, not a
certificate of a globally selected market equilibrium. Predictions do not set a
transaction price, and buyer preferences and bilateral trade are outside the model.

\subsection{Predictors, public scores and comparator identity}
Suppression-aware valuation (SAV) combines an augmented price predictor,
a suppression acquisition head and simulated query-feedback training. The
original static-robust comparator changes the prediction training objective
without that feedback procedure. Counterfactual deviation-constrained mixture
verification (CDM) instead fixes the price model and calibrates probabilities
over complete budget-feasible query rules. Its calibration objective constrains
stored own-report/peer-profile rows, not all unseen types. The original library
contains twelve rules and five calibration peer-profile families; expanding the
finite library does not itself establish out-of-sample incentive compatibility.
These original candidates provide the context for the matched experiment,
whose newly trained initial-objective factor must not be renamed SAV or static robust.

For training targets, let $q_s$ be a cross-fitted quote under report state $s$,
$q_{s\setminus f}$ the quote after recovering field $f$, $q^H$ the honest quote,
and $y$ the log advertised price. The three target quantities are
\[
 v_{sf}^{\rm sup}=[q_s-q^H]_+-[q_{s\setminus f}-q^H]_+,
 \quad v_{sf}^{\rm ben}=(q_s-y)^2-(q_{s\setminus f}-y)^2,
 \quad v_{sf}^{\rm risk}=(q_s-y)^2.
\]
A common multioutput ExtraTrees head learns these quantities from encoded
public inputs \cite{extratrees}. Honest records and targets construct training
labels only; deployment does not directly substitute them into the scores.
Each policy chooses its highest-scoring publicly eligible field and queries
only positive scores. Top-$B$ ranks these per-listing scores, using the declared
stable tie rule. The score-minimax control instead balances positive residual
scores through query marginals. It solves a score surrogate, not the true
unilateral incentive problem.

'''
abstract='''Strategically missing fields complicate secondhand valuation when verification
is budgeted and naturally absent information may remain unavailable after a
charged query. We study the limits and effects of verification under this
public-information boundary. In a single-recoverable-field family, we derive
a tight trade-off between uniform honest precision, query capacity and worst
expected concealment gain. An implementable marginal oracle supplies a finite
reference, while a context-aware comparator prevents restricted policy libraries
from creating an artificial solver advantage. A recovery-path decomposition
shows how partial recovery can raise a nonmonotone predictor's quote. A
verification-history cap preserves truthful quotes and weakly reduces unilateral
gain for fixed peer reports, but it can worsen attacked error or query failures
after responses are recomputed. We then separate initial objective, acquisition,
feedback and allocation in a ten-seed experiment on one synthetic and two
advertised vehicle-price cohorts. Independent audits cover 4,320 experimental
cells, 4.32 million repeated outcome records and reconstructed statistical
contrasts. At the prespecified 10% capacity, all 36 feedback comparisons increase
mean inflation; 34 unadjusted intervals exclude zero adversely. A robust initial
objective improves all twelve MUCars inflation comparisons, whereas no joint
feedback--allocation intervention passes the declared improvement gate. These
results support information-consistent, multiobjective auditing rather than a
universal valuation-method advantage. The intervals condition on fixed training
records, and no equilibrium or training-population guarantee is asserted.'''
assert 150<=len(abstract.split())<=250
abstract=abstract.replace('10%','10\\%')
preamble=r'''\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage{amsmath,amssymb,amsthm,booktabs,longtable,graphicx,array,hyperref}
\hypersetup{hidelinks}
\setlength{\emergencystretch}{2em}
\newcommand{\AuditVector}[1]{\ifdefined\pdfliteral\pdfliteral{#1}\else\special{pdf:bcontent}\special{pdf:literal direct #1}\special{pdf:econtent}\fi}
\newtheorem{proposition}{Proposition}
\title{Budgeted Verification for Secondhand Valuation:\\Information Limits, Recovery-Path Effects and Audited Evidence}
\author{}
\date{}
\begin{document}
\maketitle
\begin{abstract}
'''
metrics=body('Data and evaluation quantities')
metrics=metrics.replace('let $h$ be','let $q^H$ be').replace('[\\mu-h]','[\\mu-q^H]').replace('[q_0-h]','[q_0-q^H]').replace('[q_1-h]','[q_1-q^H]').replace('\\exp(h)','\\exp(q^H)')
# Separate data provenance from mathematical metrics.
marker='For one returned report,'
data,metrictext=metrics.split(marker,1)
problem+=r'\subsection{Evaluation quantities}'+'\n'+marker+metrictext
information=body('Observable-report oracle and a precision frontier')
information=information.replace(r'\paragraph{Proof sketch and boundaries.}',r'\paragraph{Proof and boundaries.}')
information=information.replace('Consider a separate alias family', 'For the frontier, we optimize both verification and the itemwise quote function subject to the precision constraint; a fixed empirical predictor need not attain the bound. Consider a separate alias family')
information=information.replace('Until $i$ is queried', 'By verification neutrality and the fixed itemwise quotation rule, unsuccessful queries do not change the quote. Until $i$ is queried')
information=information.replace('intervals containing some $U+k$', 'half-open intervals containing some $U+k$')
compact=body('Compact marginals and a fixed-mixture separation')
compact_core,rest=compact.split(r'\paragraph{A capacity-related global-mixture gap.}',1)
gap,old_literature=rest.split(r'\paragraph{Closest-work boundary.}',1)
compact_core=compact_core.replace('intervals containing some $U+k$','half-open intervals containing some $U+k$').replace('Conditional on selection, draw its field', 'For $p_i>0$, conditional on selection, draw its field')
info=r'\section{Information limits and finite reference mechanisms}\label{sec:information}'+'\n'+r'\subsection{Public-information precision frontier}'+'\n'+information+r'\subsection{Compact implementability and contextual comparators}'+'\n'+compact_core+r'''
The contextual-comparator result is a limitation of rule information, not an
LP-versus-heuristic theorem. In the constructed family, a mixture over all
context-insensitive priority rules has an unbounded capacity-related gap against
context-conditioned allocation. A fixed mixture of only $B+1$ context-aware
rules closes that gap exactly. Appendix~\ref{app:library} gives the construction,
proof and exact witnesses. Both comparators must be retained when interpreting
the finite oracle.

'''
decomp=body('A nondegenerate mechanism decomposition').replace('$h^*$','$s^*$').replace('$q_0$','$q^H$').replace('q_h-q_0','q_h-q^H')
cap=body('Verification-history cap')
cap=cap.replace(r'q_{\rm cap}(h,a)',r'q_{\rm cap}(s,a)').replace(r'q(h,a)',r'q(s,a)').replace('legal $h$','legal $s$').replace('=q_0','=q^H')
table_start=cap.index(r'\begin{table}')
table_end=cap.index(r'\end{table}',table_start)+len(r'\end{table}')
cap_table=cap[table_start:table_end].replace(r'\caption{',r'\label{tab:fixed_cap}'+ '\n'+r'\caption{',1)
cap_core=(cap[:table_start]+cap[table_end:]).replace(r'\begin{equation}',r'\begin{equation*}').replace(r'\end{equation}',r'\end{equation*}')
cap_core=cap_core.replace('the\nprimary table','the\nprimary fixed-profile table in Appendix~\\ref{app:fixed_cap}')
decomp=decomp.replace(r'\begin{align}',r'\begin{align*}').replace(r'\end{align}',r'\end{align*}')
decomp=decomp.replace('Positive $R$ can occur:',r'In the illustrative 10/12/14 example, $E=2$ and $R=2$. If the item receives its partial query with probability $p$, then $C=-2(1-p)$ and $G=2+2p$. The cap leaves the reported quote at 12 on both branches, reducing this gain to 2 rather than making honesty optimal. Positive $R$ can occur:')
recovery=r'\section{Recovery paths and a conditional history cap}\label{sec:recovery}'+'\n'+r'\subsection{Signed mechanism decomposition}'+'\n'+decomp+r'\subsection{History cap and fixed-peer guarantee}'+'\n'+cap_core
protocol=body('Matched factorial protocol and completed audits')
protocol=protocol.replace('The subsequent robust update combines', r"""Writing $L_H$ for truthful squared error, $L_V$ for mean squared error over
valid report states and $L_A$ for the squared anchor to the backbone's honest
quote, the mask objective is $L_H+0.25L_V+0.25L_A$. The robust objective adds
$0.5L_{\rm attack}+0.5L_{\rm gain}$, where
$L_{\rm gain}=\mathbb{E}[(\mu-q^H-0.02)_+]$ and $L_{\rm attack}$ averages the
endpoint squared errors before expectation. The honest anchor in the gain
penalty is detached. AdamW uses weight decay $10^{-4}$ and gradient clipping
at norm 5. The residual has two width-64 ReLU hidden layers and a scalar output.
The subsequent robust update combines""")
setup=r'\section{Experimental design and independent audits}\label{sec:experiment_setup}'+'\n'+r'\subsection{Cohorts and source boundaries}'+'\n'+data+r'\subsection{Matched training and evaluation}'+'\n'+protocol
setup=setup.replace('CatBoost', 'CatBoost')
params=r'''
\begin{table}[htbp]\centering\small
\begin{tabular}{lr}\toprule
Setting & Value\\\midrule
CatBoost backbone boosting rounds \cite{catboost} & 250\\
Residual hidden width / learning rate & 64 / 0.001\\
Initial epochs / robust-update epochs & 6 / 6\\
Outer folds / guidance fraction & 3 / 0.3\\
Acquisition-head trees / maximum depth / minimum leaf & 160 / 12 / 12\\
Training budget / response starts / response sweeps & 10\% / 1 / 2\\
Evaluation response starts / maximum sweeps & 4 / 20\\
Batch size / maximum concealed available fields & 100 / 2\\
Gain-penalty tolerance / main concealment cost & 0.02 / 0\\
Fitting seeds / crossed bootstrap repetitions & 10 / 1,000\\\bottomrule
\end{tabular}
\caption{Declared matched-experiment settings. Fitting seeds are
13, 42, 2026, 101, 211, 307, 401, 503, 601 and 701. The backbone and
ExtraTrees implementations follow established methods; they are not new
algorithmic contributions. All capacities share the fixed training budget.}
\label{tab:settings}\end{table}

'''
setup+=r'Table~\ref{tab:settings} records the declared settings.'+'\n'+params
factorial=body('Matched factorial results: feedback harm and source dependence')
factorial=factorial.replace('Yet feedback increased inflation','Feedback increased inflation')
# Inline vector paths preserve the original statistical geometry.
def figure(name,label,caption):
 vector=(ROOT/f'notes/manuscript-integration/{name}.inline.tex').read_text()
 return '\n'+r'\begin{figure}[htbp]\centering'+'\n'+r'\resizebox{\textwidth}{!}{%'+'\n'+vector+'}\n'+r'\caption{'+caption+'}\n'+r'\label{'+label+'}\n'+r'\end{figure}'+'\n\n'
fig1=figure('feedback-suppression','fig:feedback',r'Policy feedback increases mean inflation in all twelve suppression-acquisition cells at the primary 10\% capacity. Points are no-feedback minus policy-feedback paired differences; bars are 95\% unadjusted intervals from 1,000 crossed resamples of ten fitting seeds and ten shared batches. Positive differences would favor feedback. All models use the same fixed training records; 1,000 evaluation listings are reused across seeds. The two MUCars mask-objective intervals cross zero. Other scores are retained in the full contrast data.')
fig2=figure('initial-objective','fig:initial_objective',r'Initial-objective effects depend on the source. With suppression acquisition and no policy feedback, points are mask-objective minus robust-objective inflation differences at 10\% capacity. Positive values favor robust initialization. Intervals and repeated-unit definitions match Fig.~\ref{fig:feedback}. The source labels and row positions encode cohort identity independently of color. These newly trained objectives are not aliases for the original SAV/static-robust candidates.')
factorial=factorial.replace(r'\paragraph{Initial-objective effects depend on the source.}',r'Figure~\ref{fig:feedback} displays the suppression-acquisition comparisons.'+'\n'+fig1+r'\paragraph{Initial-objective effects depend on the source.}')
factorial=factorial.replace(r'\paragraph{A positive interaction can mean less harm.}',r'Figure~\ref{fig:initial_objective} shows the no-feedback suppression comparisons.'+'\n'+fig2+r'\paragraph{A positive interaction can mean less harm.}')
factorial=factorial.replace(r'\begin{table}[ht]',r'Table~\ref{tab:factorial_counts} summarizes all primary directions.'+'\n'+r'\begin{table}[ht]',1).replace('Counts are descriptive across correlated contrasts, not independent trials.}', 'Counts are descriptive across correlated contrasts, not independent trials.}\n'+r'\label{tab:factorial_counts}')
results=r'\section{Results}\label{sec:results}'+'\n'+r'\subsection{Matched factorial effects}\label{sec:factorial_results}'+'\n'+factorial
original=r'''
\subsection{Original candidate comparison: a distinct experiment}
The original SAV study supplies a comparator check rather than a factorial
attribution. Its ten-seed extension covers 30 source--seed pairs, 1,860 cells
and 1.86 million repeated outcomes. At 10\% capacity, SAV inflation was
0.021175 on synthetic data, 0.014988 on JUCars and 0.007340 on MUCars; the
corresponding static-robust values were 0.012084, 0.012082 and 0.006511.
The static-robust-minus-SAV crossed intervals were
$[-0.012355,-0.006323]$, $[-0.007025,0.000777]$ and $[-0.001870,0.000210]$,
respectively. These comparisons do not support consistent SAV superiority;
intervals including zero also do not establish equivalence. Appendix~\ref{app:original}
retains all five original comparators for each source, including strong
benefit-head controls and weaker masking/no-gap variants. These original models
must not be substituted for the matched factorial objectives.

'''
original+=r'Appendix~\ref{app:comparators} retains ordinary-benefit, equal-tuning, categorical support-margin and acquisition-conditioned neighbor controls, with their distinct fitting and adaptation assumptions.'+'\n\n'
results+=original+r'\subsection{Allocation changes on frozen models}'+'\n'+body('Matched allocation intervention: conditional gains and reversals').replace('The factorial study tests whether training feedback changes these','The completed factorial study evaluates whether training feedback changes these')
responses=body('Recomputed common responses and multiobjective effects').replace(r'\begin{table}[ht]',r'Table~\ref{tab:cap_responses} reports the primary robust-estimator comparison.'+'\n'+r'\begin{table}[ht]',1).replace('rate.}', 'rate.}\n'+r'\label{tab:cap_responses}',1)
results+=r'\subsection{Recomputed cap responses and multiobjective trade-offs}'+'\n'+responses
# Discussion uses the evidence matrix once, without development-status language.
discussion=last[:last.index(r'\begin{thebibliography}')]
discussion=discussion.replace(r'\section{Claims and evidence}',r'\section{Discussion}\label{sec:discussion}')
a=discussion.index('The code and compact evidence package are maintained')
discussion=discussion[:a].replace(r'\small',r'Table~\ref{tab:claims} connects the principal claims to their evidence.'+'\n'+r'\small',1).replace('general superiority.}', 'general superiority.}'+r'\label{tab:claims}').replace(r'{p{0.23\textwidth}p{0.32\textwidth}p{0.35\textwidth}}',r'{>{\raggedright\arraybackslash}p{0.23\textwidth}>{\raggedright\arraybackslash}p{0.32\textwidth}>{\raggedright\arraybackslash}p{0.35\textwidth}}')
discussion+=r'''
The study does not infer actual seller behavior from the advertised-price
cohorts. Concealment sets, utility, query success and response search are
stipulated. Only two real cohorts, four query fields, unit costs and batches
of 100 are evaluated. New market conditions, noisy verification, multi-field
queries, nonunit costs and adaptive interrogation can change the frontier or
the observed ranking. These limits restrict deployment claims rather than
invalidate the explicitly audited finite comparisons.

\section{Conclusion}\label{sec:conclusion}
Budgeted verification has both an information limit and a quotation-path
consequence. Uniform honest precision restricts the concealment gain that can
be removed when natural and strategic absence generate the same report. A
history cap can suppress adverse recovery paths under fixed peers, while
recomputed responses expose attacked-error and failed-query costs. The matched
experiment further shows that a positive feedback--allocation interaction is
insufficient evidence of improvement: all 36 primary feedback comparisons
increase mean inflation, even though robust initialization helps consistently
on MUCars. The practical implication is to audit public information, recovery
semantics and every comparison component, retaining negative results and
multiobjective trade-offs. This conclusion is conditional on the implemented
learning and response procedures, not a universal prescription for valuation.

\section*{Data, code and use of AI tools}
The source datasets are publicly available under CC BY 4.0 through the
versioned Mendeley Data records \cite{jucarsdata,mucarsdata}. All reported
prices are advertisements. A private research repository contains the
implementation, full six-capacity analysis tables, resampling tensors, figure
source data and hash-indexed audit receipts. It is not yet a public archival
release. Model weights and large per-listing outputs remain on the research
machine; independent clean-machine reproduction has not been demonstrated.
The source access and reconstruction instructions are included in the evidence
package. External access and an archival release must be finalized before an
editorial submission requiring public availability.

AI assistance was used for implementation support, experiment orchestration,
analysis-code development, literature checking, figure preparation and manuscript
drafting. Quantitative claims are tied to saved experimental records and
independent programmatic reconstructions; AI-generated empirical values were
not substituted for them. Human scientific review, author attribution and
final responsibility remain to be supplied before submission. Author names
and affiliations are deliberately omitted from this version.

'''

# Primary monetary-error and failed-query values remain source-separated.
import pandas as pd
frame=pd.read_csv(ROOT/'notes/manuscript-integration/multiobjective-primary.source.csv')
rows=[]
for dataset in ['synthetic','jucars','mucars']:
 for feedback,allocation in [('none','top_b'),('none','minimax'),('policy','minimax')]:
  x=frame[(frame.dataset==dataset)&(frame.feedback==feedback)&(frame.allocation==allocation)].iloc[0]
  display={'synthetic':'Synthetic','jucars':'JUCars','mucars':'MUCars'}[dataset]
  case=('None/' if feedback=='none' else 'Policy/')+('top-$B$' if allocation=='top_b' else 'minimax')
  rows.append(f"{display} & {case} & {x.positive_expected_log_inflation:.6f} & {x.honest_absolute_error:.2f} & {x.expected_attacked_absolute_error:.2f} & {100*x.failed_query_probability:.3f} "+r'\\')
multi=r"""\paragraph{Absolute outcomes qualify an inflation-only ranking.}
Table~\ref{tab:multiobjective} holds the robust initial objective and suppression
acquisition fixed. Minimax feedback increased JUCars inflation from 0.010432
to 0.011855 while reducing attacked MAE from 6902.07 to 6899.03 and lowering
query failures. On MUCars, the same feedback contrast increased both inflation
and attacked error. Thus improving prediction error need not reduce the
seller's gain over the model's own honest quote. Of the 432 source/capacity/cell
settings after aggregating seeds, 37 contained a nonconverged batch; eight of
these were synthetic primary-capacity settings. The maximum recorded remaining
regret was 0.177513 log units. All were retained.

\begin{table}[htbp]\centering\small
\begin{tabular}{llrrrr}\toprule
Source & Feedback/allocation & Inflation & Honest MAE & Attack MAE & Failure (\%)\\\midrule
"""+'\n'.join(rows)+r"""
\bottomrule\end{tabular}
\caption{Absolute primary-capacity outcomes for the robust initial objective
and suppression acquisition, averaged over ten fitting seeds and the same
1,000 evaluation listings. Inflation is positive expected log-quote inflation;
MAEs use the source's own currency, without currency pooling. Failures are
per listing, rather than conditional on receiving a query. These are descriptive
means; the effect intervals are in the full paired-contrast data.}
\label{tab:multiobjective}\end{table}

"""
results=results.replace(r'\subsection{Original candidate comparison: a distinct experiment}',multi+r'\subsection{Original candidate comparison: a distinct experiment}')
# Appendices preserve complete prior comparisons and proof-level boundaries.
appendix=r'\appendix'+'\n'+r'\section{Contextual policy-library witnesses}\label{app:library}'+'\n'+r'\paragraph{A capacity-related global-mixture gap.}'+gap
appendix+=r'\section{Fixed-profile cap comparisons}\label{app:fixed_cap}'+'\n'+r'Table~\ref{tab:fixed_cap} retains all four rule comparisons for each source.'+'\n'+cap_table+'\n'
appendix+=r'\section{Complete original-protocol ten-seed comparisons}\label{app:original}'+'\n'
for name in ['Source-complete ten-seed extension: synthetic','Ten-seed extension: JUCars and sensitivity to seed variability','Ten-seed extension: MUCars completes the source comparison']:
 appendix+=r'\subsection{'+name.replace('Source-complete ten-seed extension: ','').replace('Ten-seed extension: ','')+'}\n'+body(name)
stability=body('Conditional stability of verification probabilities')
stability=stability.replace(r'\begin{center}',r'Table~\ref{tab:stability} records the sufficient-certificate counts.'+'\n'+r'\begin{table}[htbp]\centering',1)
stability=stability.replace(r'\end{center}',r'\caption{Post-hoc stability certificates at four hypothetical relative score radii. Each row covers the same 1,080 dependent fixed-profile batch executions. Counts certify sufficient conditions, rather than observed perturbation errors or a ranking of performance.}\label{tab:stability}\end{table}',1)
appendix+=r'\section{Conditional probability-stability diagnostics}\label{app:stability}'+'\n'+stability
appendix+=(ROOT/'notes/manuscript-integration/additional_comparators.tex').read_text()+'\n'
# References for the newly self-contained method and related-work passages.
new_refs=r'''\bibitem{activeoracle} M. Valancius, M. Lennon and J. Oliva.
Acquisition Conditioned Oracle for Nongreedy Active Feature Acquisition.
ICML, PMLR 235:48957--48975, 2024.
\url{https://proceedings.mlr.press/v235/valancius24a.html}.
\bibitem{catboost} L. Prokhorenkova, G. Gusev, A. Vorobev, A. V. Dorogush and A. Gulin.
CatBoost: Unbiased Boosting with Categorical Features.
Advances in Neural Information Processing Systems 31, 2018.
\url{https://proceedings.neurips.cc/paper_files/paper/2018/hash/14491b756b3a51daac41c24863285549-Abstract.html}.
\bibitem{extratrees} P. Geurts, D. Ernst and L. Wehenkel.
Extremely Randomized Trees. Machine Learning 63:3--42, 2006.
\url{https://doi.org/10.1007/s10994-006-6226-1}.
'''
bib=re.sub(r'\\bibitem\{randomized\}.*?(?=\\end\{thebibliography\})','',bib,flags=re.S)
bib=bib.replace(r'\end{thebibliography}',new_refs+r'\end{thebibliography}')
bib=bib.replace('Version examined: \\url{https://arxiv.org/abs/2104.05182v1}.',r'\url{https://doi.org/10.1609/aaai.v35i6.16725}.')
appendix=appendix.replace('The same ten-seed source-binding',r'Table~\ref{tab:original_jucars} retains the five primary comparisons. The same ten-seed source-binding').replace('The completed three-source union',r'Table~\ref{tab:original_mucars} retains the five primary comparisons. The completed three-source union')
appendix=appendix.replace('The limitations stated for the synthetic extension apply.}', 'The limitations stated for the synthetic extension apply.}'+r'\label{tab:original_jucars}')
appendix=appendix.replace('unadjusted interpretation of the other two source extensions.}', 'unadjusted interpretation of the other two source extensions.}'+r'\label{tab:original_mucars}')
# The long mathematical interval is line-broken rather than shrinking the prose.
appendix=appendix.replace('interval is\n$[-0.003783,-0.002103]$, whereas', 'interval is\n$[-0.003783,\\, -0.002103]$, whereas')
appendix=appendix.replace('the crossed seed/batch interval is\n$[-0.007025,0.000777]$.',r'the crossed seed/batch interval is $[-0.007025,\,0.000777]$.')
text=preamble+abstract+'\n'+r'\end{abstract}'+'\n'+r'\noindent\textbf{Keywords:} strategic missingness; secondhand valuation; budgeted verification; incentive auditing; factorial evaluation'+'\n\n'+intro+related+problem+info+recovery+setup+results+discussion+appendix+bib
# Consistent citation spacing, with no invented data or source modifications.
text=re.sub(r'(?<!~)\\cite\{',r'~\\cite{',text)
source.write_text(text)
record={'original_sha256':hashlib.sha256(old.encode()).hexdigest(),'integrated_sha256':hashlib.sha256(text.encode()).hexdigest(),'abstract_words':len(abstract.split()),'author_affiliation_omitted':True,'preserved_experiment_data':True,'preserved_frozen_scientific_code':True,'figures':'two original Matplotlib vector figures in self-contained picture export','new_experiments':False,'scope':'complete manuscript integration; pre-submission review pending'}
(ROOT/'notes/manuscript-integration/integration_receipt.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
