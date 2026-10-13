"""Apply evidence-backed A/B/D/E/F/G/H revisions to the reviewed baseline."""
from pathlib import Path
import difflib, hashlib, json, re
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
baseline = (HERE / 'baseline-reviewed-source.tex').read_text()
s = baseline
statistics = json.loads((HERE / 'statistics/completion.json').read_text())
assert statistics['resamples'] == 20000
assert [statistics['results'][key]['core_feedback_upper_below_zero'] for key in ['core36', 'co_primary108', 'all1536']] == [31, 27, 20]

def replace(old, new, count=1):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, count)

replace(r'\title{Budgeted Verification for Secondhand Valuation:\\Information Limits, Recovery-Path Effects and Audited Evidence}',
        r'\title{When Does Verification Help?\\A Controlled Audit of Strategy-Aware Valuation}')
abstract = r'''Verification can recover withheld information without reducing a seller's
valuation gain. We examine this distinction in secondhand-price prediction
with naturally missing fields, charged failed queries and batch capacity.
A restricted information frontier bounds what verification can remove under
uniform honest precision; it defines scope rather than predicting the effects
of our four-field learned models. Recovery-path analysis supplies a directly
checkable diagnostic. Exhaustive saved prediction tables contain gain-increasing
partial recoveries on all three cohorts, including real-source examples.
We separate initial objective, acquisition, feedback and allocation in a
ten-seed factorial study with 4,320 cells and 4.32 million repeated records.
At the declared 10\% capacity, all 36 feedback contrasts worsen inflation.
A post-hoc simultaneous analysis retains 31 adverse intervals for that family,
27 when attacked error and failed queries are included, and 20 across all
1,536 primary contrasts and metrics. These approximate intervals condition
on fixed training records and do not make retrospective data confirmatory.
Strong ordinary-benefit and acquisition-conditioned controls also have lower
inflation than the original SAV candidate on synthetic and JUCars; MUCars gains
remain conditional. A verification-history cap reduces fixed-peer gain but
can worsen attacked error or query failures after responses are recomputed.
A positive-cost sensitivity reverses the synthetic top-$B$ feedback ranking.
We expose shared audit primitives and add a separate exhaustive state-transition
oracle. The contribution is a reusable controlled audit, an empirical recovery
failure diagnostic and explicit information and deployment boundaries. No
universal method advantage or equilibrium guarantee is asserted.'''
assert len(abstract.split()) <= 250
s = re.sub(r'\\begin\{abstract\}.*?\\end\{abstract\}', lambda _: '\\begin{abstract}\n' + abstract + '\n\\end{abstract}', s, count=1, flags=re.S)

replace('The contribution is a set of bounded analytical and empirical findings.',
        'The main contribution is a controlled audit of when verification changes valuation incentives and predictive costs.')
replace('Section~\\ref{sec:information} characterizes a tight precision--incentive frontier\nin a single-recoverable-field family and supplies an implementable marginal\nreference.',
        'Section~\\ref{sec:information} uses a restricted precision--incentive frontier to define the information boundary. It does not supply a performance prediction for the learned four-field models.')
replace('Section~\\ref{sec:recovery} identifies a recovery-path failure and\nstates the cap\'s fixed-peer guarantee.',
        'Section~\\ref{sec:recovery} identifies a recovery-path failure and states the cap\'s fixed-peer guarantee. Section~\\ref{sec:empirical_recovery} checks that failure in the actual saved model class.')
replace('on MUCars. Positive interaction effects can represent less harm rather than\nimprovement.',
        'on MUCars. Competitive ordinary-benefit and acquisition-conditioned controls have lower inflation than the original SAV candidate on synthetic and JUCars comparisons. Post-hoc simultaneous sensitivity and multiobjective outcomes bound the negative finding. Positive interactions can represent less harm rather than improvement.')

replace('The principal inflation quantity is $[\\mu-q^H]_+$;', 'The incentive coordinate is $[\\mu-q^H]_+$;')
replace('errors before aggregation.\n\nFor the unilateral audit,', r'''errors before aggregation.

\paragraph{Inflation alone admits a degenerate solution.}
A constant-quote model has zero inflation for every report, irrespective of
its honest or attacked price error. Thus zero inflation is not evidence of
useful valuation. We treat inflation, attacked MAE and failed-query probability
as co-primary descriptive outcomes, with honest MAE as the precision coordinate.
The joint outcome vector, continuous paired effects and Pareto trade-offs take
priority over any single ranking. This reporting choice is retrospective;
it is not a preregistered change in the original experiment.

For the unilateral audit,''')

replace(r'\subsection{Compact implementability and contextual comparators}', r'''\paragraph{What is tested in the learned-model experiment.}
Equation~\eqref{eq:frontier} applies to the single-recoverable alias family,
verification-neutral quotes and a uniform error constraint. The empirical
model has four fields, can hide two and is evaluated by average MAE, so these
assumptions do not establish its empirical optimum or predict a feedback sign.
We use the frontier as a scope boundary. The recovery analysis instead gives
a finite diagnostic on the actual model class: enumerate legal partial
recoveries and test whether a query raises the quote above both its pre-query
and honest anchors. Section~\ref{sec:empirical_recovery} performs that check.

\subsection{Compact implementability and contextual comparators}''')

governance = r'''\subsection{History dependence and a final-record alternative}
The cap can assign different quotes to identical final records because it
retains the pre-query quote. Consequently, final-record consistency cannot
be claimed. A platform would need to explain the history rule, allow correction
and review, and evaluate whether verification selection creates systematic
disparities. We have not measured protected-group effects or established a
deployment fairness guarantee.

A final-record rule can instead be defined on a declared completion domain
$\mathcal Z$. Let $\mathcal C(r)$ contain its records extending the observed
values of $r$, and define
\[
 q_{\downarrow}(r)=\min_{z\in\mathcal C(r)}q(z).
\]
If a truthful record belongs to the domain, every concealed or partially
recovered report extends to that record, and the completion sets are nested.
Hence $\mathcal C(r^H)\subseteq\mathcal C(r)$ and
$q_{\downarrow}(r)\le q_{\downarrow}(r^H)$. Nonnegative concealment costs
therefore prevent a gain over this rule's own truthful quote, regardless of
which admissible partial query is allocated. The rule uses only the final
record and its fixed domain. This is an order-preserving envelope, not a new
general imputation technique; truthful withholding predictors are established
prior work~\cite{withheld,smi}.

The alternative can lower honest quotes and worsen honest MAE, unlike the
history cap's truthful-quote preservation. Its guarantee needs completion-domain
coverage and nonempty nested sets; unsupported records require abstention or
an explicitly uncertified fallback. It is an analytical alternative, not an
empirically evaluated replacement in the present comparisons.

'''
replace(r'\section{Experimental design and independent audits}', governance + r'\section{Experimental design and corroborating checks}')

replace('Fitting seeds vary training random-\nness, not the source cohorts or generator.',
        'Fitting seeds vary training randomness, not the source cohorts or generator.') if 'Fitting seeds vary training random-\nness, not the source cohorts or generator.' in s else None
replace('Fitting seeds vary training random-\nness', 'Fitting seeds vary training randomness') if 'Fitting seeds vary training random-\nness' in s else None
replace('These validation sources were inspected during earlier development and are\nretrospective, rather than fresh confirmatory tests.',
        'The hash cap is deterministic and label-independent; all ten fitting seeds share exactly the same evaluation records and batch membership. Seed variation reflects fitting randomness only. The validation sources were inspected during development and are retrospective, rather than fresh confirmatory tests. The capped cohorts contain ten batches of 100; these small cluster counts restrict uncertainty claims.')

dependency = r'''\paragraph{Audit dependency and independent state coverage.}
The historical outcome audit is a corroborating re-derivation with shared
primitives. It imports the separate replay checker and shares the production
state representation, data loader, prediction and head-scoring APIs. It does
not independently reimplement those APIs or every training-library operation.
Its rejection of changed outputs therefore does not certify absence of a
shared state-transition bug.

A separate bit-mask oracle now checks state membership, validity,
materialized values, public missingness and query success/failure without
using production state or query logic in the oracle. Production StateSpace is
only the system under test. All 16 natural masks and maximum-hidden values
0 through 4 cover 1,188 fixture field transitions. Direct CSV checks on all
1,374 JUCars and 10,672 MUCars validation records cover another 521,164 legal
field transitions. Four injected enumeration/transition/materialization
faults are rejected. Model prediction, scoring, dataset construction and
optimizer libraries remain outside this independent oracle's scope.

'''
replace('Table~\\ref{tab:settings} records the declared settings.', dependency + 'Table~\\ref{tab:settings} records the declared settings.')

stats = r'''\paragraph{Post-hoc simultaneous sensitivity.}
We supplement the original unadjusted intervals with 20,000 centered crossed
bootstrap draws~\cite{pigeonhole}. The family maximum of absolute standardized
errors supplies one common critical value; scales are the conditional standard
deviations of the crossed bootstrap, not re-estimated inside each draw.
Pairing across methods and metrics is retained. We report the 36 inflation
feedback contrasts, the same contrasts on three co-primary outcomes (108),
and all 1,536 primary contrast/metric combinations. A source-wise Bonferroni
sensitivity avoids requiring cross-source independence. Resampling maxima
are established multiple-testing tools~\cite{romanowolf}; this is a single-step
sensitivity analysis, not a transfer of their finite-sample guarantee.

The adverse feedback count falls from 34 unadjusted intervals to 31, 27 and
20 under these three families (Table~\ref{tab:simultaneous}). Source-wise bands
retain 31, 27 and 19. The original 36 adverse point estimates remain unchanged.
No family certifies that every contrast is harmful. With only ten seeds and
ten batches, approximate simultaneous bands do not establish finite-sample
coverage, fresh-cohort confirmation or training-population uncertainty.

\begin{table}[htbp]\centering\small
\begin{tabular}{lrrr}\toprule
Family & Comparisons & Critical value & Adverse feedback bands\\\midrule
Feedback inflation & 36 & 3.126 & 31/36\\
Feedback, three outcomes & 108 & 3.803 & 27/36\\
All primary contrasts/metrics & 1,536 & 4.882 & 20/36\\\bottomrule
\end{tabular}
\caption{Post-hoc 95\% approximate simultaneous sensitivity on the original
capped cohorts. The last column counts only the 36 inflation feedback contrasts
with an upper endpoint below zero. It is not a confirmatory family-wise
guarantee. All point effects and all three family definitions are retained.}
\label{tab:simultaneous}\end{table}

'''
replace(r'\paragraph{Feedback does not explain a beneficial effect in this design.}', stats + r'\paragraph{Feedback does not explain a beneficial effect in this design.}')

recovery = json.loads((HERE / 'evaluation/recovery_completion.json').read_text())
edge = recovery['source_edge_totals']
profiles = pd.read_csv(HERE / 'evaluation/recovery_path_cells.csv').groupby('dataset').sum(numeric_only=True)
table_rows = []
for source, label in [('synthetic', 'Synthetic'), ('jucars', 'JUCars'), ('mucars', 'MUCars')]:
    table_rows.append(f"{label} & {edge[source]['eligible_success_edges']:,} & {edge[source]['two_hidden_gain_increasing_edges']:,} & {int(profiles.loc[source,'allocated_gain_increasing_recovery_rows']):,} " + r'\\')
bridge = r'''\subsection{Recovery failures in the learned four-field class}\label{sec:empirical_recovery}
The recovery-path prediction is observable in the saved models, rather than
only in the illustrative 10/12/14 fixture. We enumerate all legal successful
recovery edges in the 14 unique fits per source/seed and the original 1,000
evaluation records. An adverse partial recovery requires two hidden fields,
a post-query quote above the pre-query quote and both at or above the model's
honest anchor, using tolerance $10^{-10}$. Table~\ref{tab:recovery_diagnostic}
reports these finite table properties separately from returned response rows.
\begin{table}[htbp]\centering\small
\begin{tabular}{lrrr}\toprule
Source & Successful edges & Adverse partial edges & Adverse queried rows\\\midrule
''' + '\n'.join(table_rows) + r'''
\bottomrule\end{tabular}
\caption{Recovery-path diagnostic on saved primary-capacity models. Edges use
14 unique fits per source/seed; the last column counts returned reports from
all 24 cells with positive query probability and gain-increasing partial recovery.
For randomized allocation these are eligible rows, not realized query counts.
Each source reuses the same 1,000 records over ten fitting seeds. Counts are
dependent finite diagnostics, not independent samples or deployment prevalence.}
\label{tab:recovery_diagnostic}\end{table}

A MUCars witness has honest, two-hidden and partially recovered log quotes
11.484823, 11.517865 and 11.546430, respectively. It hides transmission and
fuel type, then recovers transmission. Thus its report component is about
0.033042 and recovery adds about 0.028564. The query raises the gain-producing
quote in an actual fitted model. This witness is not a measurement of human
seller behavior. Across 720 primary cells and 720,000 returned-profile rows,
the saved $E+R+C=G$ identity is also reconstructed. These checks connect the
recovery argument to the empirical model class, but do not identify why
feedback training is harmful or estimate the restricted frontier's real-data
optimum.

'''
replace(r'\subsection{Original candidate comparison: a distinct experiment}', bridge + r'\subsection{Strong controls and the original candidate comparison}')
replace(r'Appendix~\ref{app:comparators} retains ordinary-benefit, equal-tuning, categorical support-margin and acquisition-conditioned neighbor controls, with their distinct fitting and adaptation assumptions.', r'''Competitive controls materially change the original-method story. In the
audited three-seed ordinary-benefit extension, reference-minus-SAV inflation
differences are $-0.00998$ on synthetic and $-0.00432$ on JUCars; their conditional
intervals are $[-0.01260,-0.00791]$ and $[-0.00598,-0.00285]$. The ACO-1 control
also beats SAV on these sources, with SAV-minus-ACO differences 0.00995 and
0.00431 and intervals $[0.00725,0.01345]$ and $[0.00291,0.00588]$.
These are separate original-protocol three-seed comparisons, not new
ten-seed matched-factorial effects. A universal SAV advantage is not reproduced
against these strong controls. MUCars remains conditional: ordinary benefit
favors SAV by 0.00089, while the ACO comparison spans zero; the largest-cap
equal-tuning experiment favors SAV on MUCars but reverses on the other sources.
Appendix~\ref{app:comparators} preserves all fitting, tuning and adaptation
boundaries. The main implication is to compare strategy-aware valuation with
competitive predictive acquisition before attributing a gain to strategic
feedback.''')

replace('Across all 432 paired cells, inflation decreases in 279 and is unchanged in 153\nwithin numerical tolerance. Attacked MAE decreases in 185 cells, is unchanged\nin 153, and increases in 94. Failed-query probability increases in 145 cells,\ndecreases in 4, and is unchanged in 283. Honest MAE is unchanged throughout.\nThese cell counts are descriptive; cells share records and fitted models.', r'''The consequential finding is the joint cost: attacked MAE increases in 94
of 432 recomputed-response cells and failed-query probability increases in
145, while honest MAE stays unchanged. Inflation falls in 279 cells and ties
in 153; attacked MAE falls in 185 and ties in 153, and query failures fall
in 4 and tie in 283. All counts remain descriptive. The fixed-peer theorem
already establishes pointwise cap monotonicity and is not an empirical
effectiveness test. Here peers' responses are recomputed, so cross-profile
monotonicity is not supplied by that theorem either. The useful question is
whether any inflation reduction survives the attacked-error and query-failure
trade-offs, not how many cells exhibit the cap's intended quote reduction.''')

threshold = r'''\subsection{Continuous effects and decision-threshold sensitivity}
The inherited 10\% inflation-reduction/5\% honest-MAE gate is a heuristic,
not an externally validated minimum important difference or a preregistration
claim. We retain it to avoid retrospective threshold selection, report the
continuous effects, and vary inflation cutoffs over 0, 5, 10, 15 and 20\%
and honest-error allowances over 0, 1, 5 and 10\%.

At a 5\% honest-error allowance, the frozen allocation study has 8, 4, 2, 0
and 0 passing points across the respective inflation cutoffs. Its JUCars
robust-benefit reduction is approximately 9.985\%, so classifying it below a
10\% gate is not a substantive discontinuity in usefulness. In the matched
joint-policy family, the zero-cutoff gate retains three small MUCars gains;
no joint point passes any inflation cutoff of 5\% or more. Full grids and
unrounded effects are supplied. A deployment threshold requires a platform's
error/query-cost preferences, which this retrospective study has not elicited.

'''
replace(r'\section{Discussion}\label{sec:discussion}', threshold + r'\section{Discussion}\label{sec:discussion}')

cost_done = ROOT / 'outputs/review-cost-sensitivity-v2-analysis/completion.json'
assert cost_done.exists()
cost_receipt = json.loads(cost_done.read_text())
assert cost_receipt['status'] == 'completed' and cost_receipt['new_positive_cost_cells'] == 108
cost_frame = pd.read_csv(cost_done.parent / 'feedback_point_contrasts.csv')
cost_rows = []
for scenario, label in [('zero','0'),('uniform005','0.005'),('uniform020','0.02'),('heterogeneous020','Heterogeneous 0.02')]:
    value = cost_frame[(cost_frame.dataset == 'synthetic') & (cost_frame.allocation == 'top_b') & (cost_frame.scenario == scenario)].iloc[0]
    cost_rows.append(f"{label} & {value.inflation:+.6f} & {value.attacked_mae:+.3f} & {100*value.failed_query:+.3f} " + r'\\')
cost_text = r'''\subsection{Positive costs change the conditional feedback ranking}
We recompute responses under per-hidden-field costs 0.005 and 0.02 in log-quote
utility units, and heterogeneous costs $0.02h_i$, where a fixed listing hash
gives $h_i\in[0.5,1.5)$. These are stipulated post-hoc sensitivities, not measured
human effort or monetary sanctions. All 108 positive-cost cells retain the
robust initial objective and suppression score, three original fitting seeds,
both feedback settings and both allocators. Four response starts and twenty
sweeps are unchanged. Costs enter report choice; they are not simply subtracted
from saved zero-cost outcomes. Independent algebraic replay and every legal
unilateral utility corroborate the returned profiles.

Table~\ref{tab:cost_sensitivity} shows a ranking reversal on synthetic top-$B$.
Uniform 0.02 and heterogeneous costs have lower mean inflation with feedback
than without it; the heterogeneous direction is positive for all three seeds,
while the uniform 0.02 direction is positive for only one. At heterogeneous
cost, feedback also lowers honest MAE by 4.293 synthetic price units, attacked
MAE by 12.198 units and failed queries by 0.100 percentage points. This is
descriptive mean Pareto improvement within that declared subset, not an
uncertainty-qualified or universal dominance result. Failure remains high
in absolute terms (9.4\% without and 9.3\% with feedback per listing).

\begin{table}[htbp]\centering\small
\begin{tabular}{lrrr}\toprule
Cost per hidden field & Inflation difference & Attack-MAE difference & Failure difference (pp)\\\midrule
''' + '\n'.join(cost_rows) + r'''
\bottomrule\end{tabular}
\caption{Synthetic robust/suppression/top-$B$ feedback sensitivity on the same
1,000 records and three fitting seeds. All differences are no-feedback minus
feedback, so positive values favor feedback. Costs are log-quote utility units;
MAE uses synthetic price units. All four cost regimes and all individual-seed
results are retained; the table is descriptive and post-hoc.}
\label{tab:cost_sensitivity}\end{table}

JUCars and MUCars retain adverse mean inflation directions for both allocators
under every declared cost regime in this subset. Twenty positive-cost
seed/cell batches remain nonconverged and are retained. Therefore the original
36/36 zero-cost direction describes its evaluated regime, not a cost-invariant
property of feedback training. The full three-source cost table is in the
evidence package; no winning cost distribution is substituted for the zero-cost
primary experiment.

'''
replace(r'\section{Discussion}\label{sec:discussion}', cost_text + r'\section{Discussion}\label{sec:discussion}')

full_done = ROOT / 'outputs/review-expanded-primary-v2-analysis/completion.json'
full_receipt = json.loads(full_done.read_text())
assert full_receipt['status'] == 'completed_and_corroborated' and full_receipt['cells'] == 480
full_feedback = pd.read_csv(full_done.parent / 'expanded_feedback_contrasts.csv')
for name, adverse_intervals in [('jucars', 12), ('mucars', 10)]:
    f = full_feedback[(full_feedback.dataset == name) & (full_feedback.metric == 'positive_expected_log_inflation')]
    assert len(f) == 12 and (f.difference < 0).all() and (f.upper < 0).sum() == adverse_intervals
extension_text = r'''\subsection{Full-validation evaluation coverage}
An additional frozen-model evaluation removes both real-source caps: all
1,374 JUCars and 10,672 MUCars validation records form fourteen and 107 batches,
respectively, using the same ten fitting seeds. Final batches contain 74 and
72 records, each with capacity seven. All 480 cells, 29,040 seed/cell batches
and 2,891,040 repeated outcomes pass algebraic allocation, bit-transition,
metric and complete unilateral-utility checks, covering 31,269,840 legal
deviations. All returned real-source batches meet the finite unilateral-regret
tolerance; this does not certify arbitrary actions or globally optimal joint
responses. The original 1,000-record prefixes are reproduced and reused;
no model is retrained.

All 24 real-source feedback inflation point estimates remain adverse.
Ten-thousand-draw exploratory intervals exclude zero adversely for all twelve
JUCars comparisons and ten MUCars comparisons; both MUCars masking-objective,
suppression-score comparisons span zero. These unadjusted intervals weight
batches by record counts, including the partial batches. They do not add
independent training records or make either retrospective source confirmatory.
The original capped factorial remains the declared primary comparison.

'''
replace(r'\section{Discussion}\label{sec:discussion}', extension_text + r'\section{Discussion}\label{sec:discussion}')

# The detailed audit matrix remains available without dominating the argument.
match = re.search(r'Table~\\ref\{tab:claims\}.*?\\begin\{longtable\}.*?\\end\{longtable\}\s*\\normalsize', s, re.S)
assert match
matrix = match.group(0)
s = s[:match.start()] + 'The detailed claim--evidence map is retained in Appendix~\\ref{app:audit_map}.\n\n' + s[match.end():]
insert = r'\section{Detailed claim--evidence map}\label{app:audit_map}' + '\n' + matrix + '\n'
replace(r'\begin{thebibliography}', insert + r'\begin{thebibliography}')

# Calibrate claimed independence without changing statistical independence or
# the context-independent policy-class terminology.
for old, new in [('Independent audits', 'Corroborating checks'), ('independent audits', 'corroborating checks'),
                 ('The independent evaluator', 'The separate evaluator'), ('independent full-sort auditor', 'separate full-sort auditor'),
                 ('independently audited', 'separately corroborated'), ('An independent statistical checker', 'A separate statistical checker'),
                 ('An independent raw-record checker', 'A separate raw-record checker'), ('An independent checker', 'A separate checker'),
                 ('It independently rebuilt all', 'It refitted all'), ('independently reconstructed by', 'reconstructed separately by')]:
    s = s.replace(old, new)
s = s.replace('pre-existing point criteria', 'inherited heuristic point criteria')
replace('all 36 feedback point estimates worsen inflation and 34 adverse intervals exclude zero.',
        'all 36 zero-cost feedback points worsen inflation; 31 adverse bands survive the post-hoc 36-contrast sensitivity.')
replace('This does not establish why feedback fails or rule out other feedback algorithms.',
        'Positive costs reverse one subset ranking. Neither a universal feedback failure nor confirmatory coverage is established.')

# Keep author accountability in the actual submission checklist, not an
# invented assertion that all authors have approved an AI-prepared manuscript.
replace('independent programmatic reconstructions; AI-generated empirical values were\nnot substituted for them. Human scientific review, author attribution and\nfinal responsibility remain to be supplied before submission. Author names\nand affiliations are deliberately omitted from this version.',
        'the programmatic checks described above; AI-generated empirical values were not substituted for saved records. AI tools are not authors. Author names and affiliations are deliberately omitted from this version.')

replace('increase mean inflation, even though robust initialization helps consistently\non MUCars. The practical implication is to audit public information, recovery',
        'increase mean inflation at zero concealment cost, even though robust initialization helps on MUCars. A three-seed positive-cost sensitivity reverses the synthetic top-$B$ feedback ranking, further limiting generalization. The practical implication is to audit public information, recovery')
replace('machine; independent clean-machine reproduction has not been demonstrated.',
        'machine. A fresh dependency environment on that same machine reproduced the 1,536 aggregate simultaneous-analysis rows within $10^{-12}$ tolerance and matched the threshold grids. This bounded replay does not establish external clean-machine reproduction or replicate model training.')

refs = r'''\bibitem{pigeonhole} A. B. Owen. The Pigeonhole Bootstrap.
The Annals of Applied Statistics 1(2):386--411, 2007.
\url{https://doi.org/10.1214/07-AOAS122}.
\bibitem{romanowolf} J. P. Romano and M. Wolf. Exact and Approximate Stepdown
Methods for Multiple Hypothesis Testing. Journal of the American Statistical
Association 100(469):94--108, 2005.
\url{https://doi.org/10.1198/016214504000000539}.
'''
replace(r'\end{thebibliography}', refs + r'\end{thebibliography}')
source = ROOT / 'paper/innovation-addendum-v1.tex'
source.write_text(s)
(HERE / 'manuscript-changes.patch').write_text(''.join(difflib.unified_diff(baseline.splitlines(True), s.splitlines(True), fromfile='reviewed-baseline.tex', tofile='innovation-addendum-v1.tex')))
record = {'status': 'draft_revised_pending_compile_and_review', 'baseline_sha256': hashlib.sha256(baseline.encode()).hexdigest(),
          'revised_sha256': hashlib.sha256(s.encode()).hexdigest(), 'abstract_words': len(abstract.split()),
          'supported_revisions': ['A scope + real recovery diagnostic', 'B post-hoc simultaneous sensitivity', 'D co-primary metrics and cap interpretation',
                                  'E threshold grid', 'F shared-primitives disclosure + independent state oracle', 'G competitive controls promoted',
                                  'H final-record alternative and governance'],
          'pending': ['author/public-release/independent-machine full reproduction'],
          'new_training': False}
(HERE / 'manuscript-revision-receipt.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record))
