"""In-place evidence update. Exact original source guard; no scientific reruns."""
from pathlib import Path
import re, json, hashlib
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
FILE=ROOT/'paper/innovation-addendum-v1.tex'
NOTE=Path(__file__).parent
OLD=FILE.read_text()
assert hashlib.sha256(FILE.read_bytes()).hexdigest()=='e411705f97680aff89719e245e88abb9ca8e0e6318a949a429feef52c7474d38'
text=OLD
changes=[]


def between(start,end,new):
    global text
    left=text.index(start);right=text.index(end,left)
    changes.append(dict(anchor=start,old_words=len(re.findall(r'\b\w+\b',text[left:right])),new_words=len(re.findall(r'\b\w+\b',new))))
    text=text[:left]+new+'\n\n'+text[right:]


def swap(old,new):
    global text
    assert old in text,old[:120]
    text=text.replace(old,new,1)


def take_float(label,kind='figure'):
    global text
    pattern=r'\\begin\{'+kind+r'\}.*?\\end\{'+kind+r'\}'
    hits=[m for m in re.finditer(pattern,text,re.S) if '\\label{'+label+'}' in m.group()]
    assert len(hits)==1,(label,len(hits))
    m=hits[0];value=m.group();text=text[:m.start()]+text[m.end():]
    return value


def figure(name,label,caption):
    return '\\begin{figure}[p]\n\\centering\n\\includegraphics[width=\\textwidth]{figures/ten-seed-v1/'+name+'.pdf}\n\\caption{'+caption+'}\n\\label{'+label+'}\n\\end{figure}\n'


swap(r'\title{When Does Verification Help?\\A Controlled Audit of Strategy-Aware Valuation}',
     r'\title{When Does Verification Help?\\Recovery-Path Regularization for Strategy-Aware Valuation}')
swap(r'\author{}',r'''\author{Yuchen Tang \quad Fengqin You\thanks{Corresponding author: \href{mailto:irisyou@njust.edu.cn}{irisyou@njust.edu.cn}} \quad Xin Pang\\[.5em]
\small School of Computer and Artificial Intelligence\\
\small Nanjing University of Science and Technology Zijin College\\
\small Nanjing, China}''')
abstract=r'''\begin{abstract}
Recovering withheld information can increase a seller's predicted price when the valuation model is nonmonotone. We study this failure under natural missingness, charged failed queries and shared verification capacity. A recovery-path decomposition separates information recovery from its effect on concealment gains. We introduce recovery-path regularization, which penalizes increases in positive concealment gain along legal recovery edges while retaining public-record deployment inputs. A restricted information frontier states the limits of verification, rather than predicting learned-model performance. In a matched ten-seed study at 10\% query capacity, the declared unit-weight endpoint reduces mean inflation by 50.41\%, 26.58\% and 23.81\% on synthetic, JUCars and MUCars relative to same-gap zero-weight controls. All thirty source--seed comparisons have the same direction. Synthetic honest mean absolute error rises 0.82\% and failed queries rise 1.10 percentage points, so lower inflation does not imply multiobjective dominance. Stronger training-response search also removes some earlier feedback damage, showing that the negative feedback result depends on implementation. The claim-bearing extensions complete a four-stage computational audit covering 1,206 distinct cells, including the 540-cell ten-seed study. Remaining response regret, retrospective cohorts and cross-machine numerical differences bound the findings. The supported practice is to diagnose recovery paths and evaluate incentive gains jointly with prediction and verification costs before deploying feedback or regularization.
\end{abstract}'''
between(r'\begin{abstract}',r'\noindent\textbf{Keywords:}',abstract)
between('The main contribution is a controlled audit',r'\section{Related work}',r'''The central contribution is a recovery-path diagnosis linked to a targeted
training intervention. Section~\ref{sec:information} delimits guarantees under
observationally identical missing reports; its restricted theorem is not a
quantitative prediction for the learned four-field models. Section~\ref{sec:recovery}
decomposes the valuation effect of recovery, gives a conditional history-cap
guarantee, and defines recovery-path regularization (RPL).

The empirical evidence separates initial objective, acquisition score, policy
feedback and allocation. The original factorial identifies a weak-search
feedback failure. Matched stronger-search interventions qualify that finding,
while competitive ordinary-benefit and acquisition-conditioned controls
prevent a universal claim for the original SAV candidate. The ten-seed RPL
extension then tests the diagnosed recovery failure directly against same-gap
zero-weight controls, including zero-query outcomes and path/gap removals.
Its lower inflation coexists with predictive and verification costs. The
claim-bearing extensions have completed a four-stage computational audit,
with shared model primitives and conditional uncertainty explicitly disclosed.
The resulting contribution concerns recovery-aware learning and a reusable
comparison protocol, without establishing universal superiority or actual
seller behavior.''')
start=text.index(r'\paragraph{Controlled completion study.}')
end=text.index(r'\section{Results}',start)
text=text[:start]+r'''\paragraph{Completion study and ten-seed extension.}
The three-seed development study completed 1,719 cells, including reused
references, across component removals, parameter scans, acquisition adapters,
search interventions, availability stress and the original RPL pilot.
Appendix~\ref{app:completion_methods} retains the complete inventory.
The subsequent RPL extension kept the six configurations and three budgets
unchanged, reused the original 162 cells, and added seven fitting seeds per
source. Its 540 cells cover thirty source--seed pairs. This increases fitting
replication, not the number of independent training populations or evaluation
cohorts. Parameter and availability scans retain their original three seeds.

\paragraph{Completed computational audit and its limits.}\label{sec:audit_levels}
The original 4,320-cell chain remains unchanged. A new fit/outcome/analysis/
statistics-check chain covers the 828 claim-bearing original extension cells
and 378 additional RPL cells, hence 1,206 distinct cells. The audited stages
are the RPL pilot (162), search interventions (90), SEFA/GDFS/DIME/explanation
adapters (432), ACO including neighbor sensitivities (144), and the ten-seed
RPL extension (540, overlapping the pilot by 162). Each stage reconstructs
fitting roles and provenance, re-derives all recorded batch outcomes and legal
unilateral deviations, aggregates comparisons, and separately reconstructs
the saved statistics. Completion does not independently reimplement shared
prediction libraries or provide external scientific confirmation.

The new analyses retain 4,000 paired crossed seed--batch resamples. Marginal
percentile intervals and exploratory studentized maximum-deviation bands
condition on the same fixed populations; the RPL family contains 216
metric contrasts. Neither the ten-seed nor the three-seed families have a
finite-sample family-wise coverage certificate. The remaining parameter,
component and availability cells are not silently upgraded to the new chain.
All failed and nonconverged outcomes remain in their respective evidence sets.

\begin{table}[tbp]\centering\small
\caption{Computational audit scope. Counts overlap where explicitly stated;
human scientific approval and exact cross-machine reproduction are separate
from these checks. Historical failure receipts are preserved.}
\label{tab:audit_levels}
\begin{tabular}{>{\raggedright\arraybackslash}p{.23\textwidth}>{\raggedright\arraybackslash}p{.32\textwidth}>{\raggedright\arraybackslash}p{.35\textwidth}}\toprule
Evidence & Completed chain & Boundary\\\midrule
Original 4,320 cells & Fit, outcome, analysis, statistics check & Original implementation; shared primitives disclosed\\
Claim-bearing extensions: 1,206 distinct cells & Same four computational phases; includes all 540 ten-seed RPL cells & Conditional exploratory inference; not an independent full-stack implementation\\
Remaining completion-study support & Hash bindings, utility checks and recorded summaries & No whole-study four-stage upgrade of all 1,719 cells\\\bottomrule
\end{tabular}\end{table}

'''+text[end:]
swap('The later, less-audited\nsearch intervention','The later, four-stage-checked\nsearch intervention')
swap('The asymmetry in audit depth is stated in Table~\\ref{tab:audit_levels}.',
     'Table~\\ref{tab:audit_levels} separates completed computational checks from independent scientific confirmation.')
swap('Figure~\\ref{fig:completion_mechanism} shows the three individual seeds and their\nmeans at 10\\% capacity.',
     'Figure~\\ref{fig:completion_mechanism} shows the audited paired improvements and conditional intervals at 10\\% capacity, retaining three fitting seeds.')
swap('unchanged reproductions of five original methods; they are not audited to the\nsame level as the original factorial study. Estimator choice and simple strong',
     'unchanged reproductions of five original methods. Their four-stage computational checks are complete; estimator choice and simple strong')

# Replace old embedded figures by checked local project assets.
take_float('fig:completion_mechanism')
anchor=r'\subsection{Recovery-path regularization: improvement and costs}'
at=text.index(anchor)
text=text[:at]+figure('mechanism_search_audited','fig:completion_mechanism',r'''Search-strength and score-refresh interventions relative to matched no-feedback controls, at 10\% capacity. Points are mean reference-minus-candidate inflation differences; positive values favor feedback. Thin segments are marginal 95\% crossed-bootstrap intervals and pale segments are exploratory simultaneous bands. This intervention retains three fitting seeds and ten shared batches; it is separate from the ten-seed RPL extension.''')+'\n'+text[at:]

data=pd.read_csv(ROOT/'outputs/core-evidence-audit-v2/analysis/rpl10/audited_cell_summaries.csv')
means=data[data.budget==.1].groupby(['dataset','method'])[['mean_positive_log_inflation','clean_mae','attack_mae','failed_query_fraction']].mean()
table=[]
for source in ['synthetic','jucars','mucars']:
    for weight in [0,.5,1]:
        row=means.loc[(source,f'path-{weight:g}-gap-0.5')]
        table.append(f'{source} / {weight:g} & {row.iloc[0]:.5f} & {row.iloc[1]:.2f} & {row.iloc[2]:.2f} & {100*row.iloc[3]:.2f} '+r'\\')
rpl=r'''\subsection{Recovery-path regularization: improvement and costs}\label{sec:rpl_results}
\noindent\textbf{Takeaway.} RPL lowers primary mean inflation across all thirty
source--seed comparisons at the declared unit-weight endpoint. Predictive,
query-failure and convergence costs keep this from being a dominance claim.

The ten-seed extension compared path weights $0,0.1,0.5,1$ at gap weight
$\beta=0.5$, plus path weights $0,0.5$ at $\beta=0$, over query capacities
$0,0.1,0.3$. All branches used no policy feedback and the same two-round reset
schedule. The original 162 cells were reused and 378 added, for 540 cells.
Each positive path-weight branch is compared with its own same-gap zero-path
control. RPL changes the predictor; it is not a fixed-predictor acquisition
comparison.

The original grid, including $\lambda=1$, was committed before formal
evaluation in \href{https://github.com/T0Q0R/secondhand-valuation-research/commit/6643cbe3266f2c1548d987c2bb53e366e19ad3ef}{\texttt{6643cbe}}.
This is a timestamped development grid, not independent preregistration or
proof that the endpoint was prespecified as the headline. Weight 0.5 retained
the existing gap term's numerical scale; neither 0.5 nor 1 is claimed optimal.

\paragraph{Inflation improvement and uncertainty.}
At 10\% capacity and $\lambda=1,\beta=0.5$, ratios of mean inflation to the
matched $\lambda=0$ control fell by 50.41\%, 26.58\% and 23.81\% on synthetic,
JUCars and MUCars. All ten fitting seeds in each source had lower inflation.
The absolute paired reductions were 0.006268, 0.003306 and 0.001573 log units.
The exploratory simultaneous bands over 216 metric contrasts were
$[0.004644,0.007891]$, $[0.001209,0.005403]$ and
$[0.000624,0.002522]$, respectively (Figure~\ref{fig:rpl_primary}). These
conditional bands support the within-design direction without certifying
finite-sample coverage or new-population generalization. Smaller weights were
less uniform: at $\lambda=0.1$, only six of ten seeds improved on each real
source; at $\lambda=0.5$, nine of ten did so. Appendix~\ref{app:rpl_extended}
retains every seed.

\paragraph{Predictive and verification costs.}
Table~\ref{tab:rpl_primary} reports absolute outcomes. At the unit endpoint,
honest MAE changed by $+0.82\%$, $-0.10\%$ and $-0.80\%$, while attacked MAE
changed by $-0.91\%$, $-0.02\%$ and $-0.87\%$. Failed attempts per all listings
changed by $+1.10$, $+0.44$ and $-0.12$ percentage points. The synthetic honest
error and failed-query increases also excluded zero in the exploratory
simultaneous bands; real-source MAE changes did not. Figure~\ref{fig:rpl_tradeoffs}
shows all paired seed changes, including unfavorable cases. Its means of seed
ratios are distinct from the ratios of means reported above. Inflation
improvement alone therefore does not determine a deployment choice.

\paragraph{Budget and loss-component boundaries.}
Figure~\ref{fig:rpl_budget} includes zero queries, so estimator changes remain
separate from gains due to verification. Greater capacity can lower inflation
while increasing charged failed queries. The matched path/gap comparison
(Figure~\ref{fig:rpl_gap}) shows that the path intervention is not an alias
for the existing gap term at the tested weights. It complements the original
eight-switch component ablation rather than turning its switches into three
independent innovations. The original three-seed recovery-edge diagnostic
also showed lower positive gain increments, which remained strictly positive;
those measurements are retained as a pilot in Appendix~\ref{app:rpl_extended}
and are not relabeled as ten-seed evidence.

\paragraph{Finite-response boundary.}
All 540 cells remain in Figure~\ref{fig:rpl_convergence}. Fifty-one cells
contained nonconverged batches, covering 89 of 5,400 batch replays, with a
maximum remaining unilateral regret of 0.143721 log units. At the primary
unit-weight endpoint, two synthetic seeds each retained one nonconverged batch;
the maximum regret there was 0.011042. Both real-source endpoint responses
met the stated finite unilateral tolerance. These are outcomes of the declared
finite response search, not evidence of improvement at an exact market
equilibrium.

\begin{table}[tbp]\centering\small
\caption{Ten-seed RPL means at 10\% capacity, $\beta=0.5$. MAE is in source
currency; failed queries are a percentage of all listings. All seeds and
nonconverged responses are retained.}\label{tab:rpl_primary}
\begin{tabular}{lrrrr}\toprule
Source / $\lambda$ & Inflation & Honest MAE & Attacked MAE & Failed (\%)\\\midrule
'''+ '\n'.join(table)+r'''
\bottomrule\end{tabular}\end{table}

'''
rpl+=figure('ten_seed_primary','fig:rpl_primary',r'''Ten-seed paired inflation improvement at 10\% capacity. Positive values favor RPL. Each branch uses its same-gap zero-path control. Thin segments are marginal 95\% intervals; pale segments are exploratory simultaneous bands over 216 metric contrasts. Ten fitting seeds share fixed training/evaluation populations and ten batches. Bands do not establish finite-sample family-wise coverage.''')
rpl+=figure('ten_seed_tradeoffs','fig:rpl_tradeoffs',r'''Paired seed trade-offs at 10\% capacity and $\beta=0.5$. Small markers retain all ten fitting seeds per source and positive path weight; outlined markers are their means. Horizontal axes show honest or attacked MAE changes, while vertical axes show inflation reductions. Upper-left is favorable. Each point uses its same-seed control, so these mean seed ratios differ from the headline ratios of means. No confidence region is claimed.''')
rpl+=figure('budget_response','fig:rpl_budget',r'''Budget transfer and verification costs at $\beta=0.5$. The measured capacities are 0, 10 and 30\%; straight segments connect evaluated settings only. Lines show ten-seed means and shading the full seed range, not a confidence interval. Failed queries use all listings as the denominator. Zero-query differences are estimator effects.''')
rpl+=figure('gap_ablation','fig:rpl_gap',r'''Matched path/gap loss-component comparison at 10\% capacity. Each line connects one fitting seed across four configurations; dots retain all observations and black diamonds show means. The axis lists path weight/gap weight. This tests the path term against matched zero-path controls with and without the gap term.''')
rpl+=figure('response_convergence','fig:rpl_convergence',r'''Convergence boundary across all 540 RPL cells and six configurations. Top panels show batch nonconvergence rates; bottom panels show the maximum unilateral regret within each cell on a symmetric-log axis. Curves are ten-seed means, bands the full seed range. The mean of cell maxima is not the worst observed regret. All 51 cells containing nonconverged batches are retained.''')
between(anchor,r'\subsection{Five task-adapted recent acquisition families',rpl)

# Replace the two old parameter figures, retaining their labels and n=3 scope.
for label,name,caption in [
 ('fig:completion_parameters','parameter_defaults',r'''Core-parameter scans in the original feedback implementation, with three fitting seeds. Dotted lines mark design defaults and all evaluated settings are ticked. Gap weight and tolerance use symmetric-log coordinates. Means and full ranges are descriptive, not confidence intervals. The defaults are engineering choices, not evaluation-selected optima.'''),
 ('fig:completion_stability','implementation_defaults',r'''Six implementation-parameter scans at 10\% capacity, retaining three fitting seeds. Every ratio uses the same-seed matched default. Dotted lines mark defaults; ticks show all evaluated values, and learning rate uses a logarithmic axis. Curves show means and full seed ranges, not confidence intervals.''')]:
    old=take_float(label)
    # Preserve the original location using the old caption label as a unique anchor.
    pos=OLD.index(old)
    if label=='fig:completion_parameters':
        location=text.index('A further 144 cells vary')
        paragraph_end=text.index('\n\n',location)
    else:
        paragraph_end=text.index(r'\subsection{Availability-shift stress')
    text=text[:paragraph_end]+'\n\n'+figure(name,label,caption)+'\n'+text[paragraph_end:]

between(r'\section{Discussion}',r'\section{Conclusion}',r'''\section{Discussion}\label{sec:discussion}
\noindent\textbf{Takeaway.} The contribution is a recovery-aware intervention
supported by matched ten-seed effects and explicit deployment costs. Verification
quality depends on how recovered records enter the predictor and response
procedure, as well as which information is acquired.

The information frontier and learned recovery graph address complementary
questions. Observationally identical missing reports restrict what a budgeted
verifier can guarantee, while recovery paths reveal how a valid query can
increase a learned quotation. RPL translates the latter diagnosis into a loss
term and reduces inflation in the tested finite-response design. The effect
does not require new private deployment inputs, but its zero-query component
shows that part of the benefit comes from changing the estimator. Existing
predictive acquisition objectives~\cite{activeoracle} and strategic withholding
models~\cite{smi,withheld} therefore remain relevant comparators, rather than
being displaced by the recovery-path objective.

Search-strength interventions qualify the earlier negative feedback finding.
They show that an adverse weak-search implementation need not characterize
all feedback procedures; they do not isolate one unique causal defect or
establish feedback benefit across sources. RPL likewise does not dominate all
objectives: the synthetic predictor pays higher honest error and failed-query
costs. The history cap supplies a restricted fixed-peer guarantee, but its
history dependence raises consistency and appeal issues for equal final
records. Deployments should choose among these interventions using the joint
error, failure and incentive outcomes, not inflation alone.

The scientific scope remains finite and retrospective. Seller concealment,
costs, query success and response search are modeled, not observed behavior.
The real data are advertised prices from two cohorts, not verified transactions.
Fitting seeds quantify algorithmic variability on fixed populations and cannot
establish uncertainty over new training populations. Nonconverged response
batches bound equilibrium interpretations. Four-stage computational checks
improve traceability but share loading and prediction primitives. A separate
external run completed, yet failed the original numerical tolerances; this
limits cross-machine reproducibility rather than being silently absorbed into
the uncertainty bands. Testing learned recovery effects with actual seller
decisions and independently controlled numerical environments would address
these two remaining transportability questions.
''')
between(r'\section{Conclusion}',r'\section*{Data, code and use of AI tools}',r'''\section{Conclusion}\label{sec:conclusion}
Information recovery does not by itself ensure better valuation incentives.
A bounded information frontier and observed gain-increasing recovery paths
motivate RPL, which lowers primary mean inflation across all thirty tested
source--seed comparisons at the declared unit-weight endpoint. Honest-error,
query-failure and response-convergence costs prevent a universal dominance
claim. Stronger response search also narrows the original negative feedback
finding to its implementation. Together, these results support diagnosing
recovery paths before choosing feedback or regularization and retaining
prediction and verification costs in the deployment decision. The findings
remain conditional on the fixed cohorts and modeled finite unilateral
responses.
''')
between(r'\section*{Data, code and use of AI tools}',r'\appendix',r'''\section*{Statements and declarations}
\paragraph{Data and code availability.}
The source datasets are available under CC BY 4.0 through the versioned
Mendeley Data records~\cite{jucarsdata,mucarsdata}. Prices are advertisements.
The public repository,
\href{https://github.com/T0Q0R/secondhand-valuation-research}{\nolinkurl{github.com/T0Q0R/secondhand-valuation-research}},
contains project-authored code under MIT, source reconstruction instructions,
aggregate results, figure source data, resampling tensors and audit receipts.
Third-party software and data retain their own licenses. Large model weights
and per-listing artifacts remain on the research machine; a DOI-backed
archival release has not yet been issued.

\paragraph{External execution and numerical reproducibility.}
An independently operated Mac completed the six-cell synthetic/seed-13
training-and-evaluation package. Training/evaluation populations and tree
backbones matched, but residual-network parameters and aggregate outcomes did
not meet the original numerical tolerances. Those failures are retained.
Subsequent saved-model diagnostics reproduced each machine's own parameters
and found the first recorded cross-machine difference in first-batch output
weight gradients. Hidden intermediate activations were not captured, so a
specific arithmetic primitive or environment was not causally identified.
Effect directions at the three tested budgets agreed in this one seed, but
that is not numerical equivalence or a multi-seed external confirmation.
An isolated float64 engineering candidate has not replaced the reported
float32 experiments and has not established cross-machine performance.

\paragraph{Use of AI tools.}
OpenAI Codex assisted implementation, experiment orchestration, analysis code,
literature checks, data-derived figure preparation and manuscript drafting.
Figures were plotted from inspectable saved results, not generated as
invented empirical images. Quantitative statements are bound to experiment
records and the computational checks above. AI tools are not authors;
the named authors remain responsible for scientific interpretation and final
approval. Author contributions, funding and competing-interest declarations
require author confirmation before submission and are not inferred here.
''')

# Preserve earlier visual evidence in appendices rather than repeat main claims.
moved=[]
for label in ['fig:feedback','fig:initial_objective','fig:cost_mechanism','fig:uncertainty_components']:
    moved.append(take_float(label))
tables=[]
for label in ['tab:simultaneous','tab:multiobjective','tab:cap_responses','tab:cost_sensitivity']:
    tables.append(take_float(label,'table'))
tables.append(take_float('tab:allocation','longtable'))
main,append=text.split(r'\appendix',1)
for label in ['fig:feedback','fig:initial_objective','fig:cost_mechanism','fig:uncertainty_components',
              'tab:simultaneous','tab:multiobjective','tab:allocation','tab:cap_responses','tab:cost_sensitivity']:
    main=re.sub(r'(?:Figures?|Figs?\.|Tables?)~\\ref\{'+re.escape(label)+r'\}',
                lambda _:r'Appendix~\ref{app:historical_displays}',main)
text=main+r'\appendix'+append

extra=r'''\section{Ten-seed recovery-path diagnostics}\label{app:rpl_extended}
Figure~\ref{fig:rpl_seeds} retains every fitting seed and all four nonzero
path/gap comparisons at primary capacity. Small weights can reverse individual
seed effects; their means do not imply per-seed monotonic improvement. All
zero-weight controls remain in the public source tables, although their
self-difference is identically zero and is not colored as new evidence.

The original three-seed recovery-edge measurement, separate from the ten-seed
performance expansion, gave mean positive gain increments of
0.001790 to 0.000693 (synthetic), 0.001648 to 0.001048 (JUCars), and
0.000788 to 0.000450 (MUCars) at $\lambda=1,\beta=0.5$.
They remained positive, so the zero-edge-penalty premise of
Proposition~\ref{prop:rpl} was not achieved. The pilot is not a ten-seed
mechanism remeasurement or proof of a unique causal explanation.

The new four-stage ACO audit initially stopped because its independent
distance reconstruction subtracted archived float32 bank/query arrays,
whereas production promoted both to float64 before distance calculations.
The corrected, separately versioned auditor matches that arithmetic contract
and passed the full 144-cell chain. The failed receipt, original checker and
new source closure remain public; no tolerance, production model or saved
result was changed to obtain a pass.

'''+figure('seed_consistency','fig:rpl_seeds',r'''All ten fitting seeds at 10\% capacity. Cell values are inflation reductions against each configuration's same-gap zero-path control. Positive values favor RPL; negative values retain adverse seeds. Display values are rounded, retaining one decimal below 1\% magnitude; unrounded data are public. No nonconverged outcome is excluded.''')
extra+=r'''\section{Detailed historical controls and visual diagnostics}\label{app:historical_displays}
The following displays retain the original feedback and initial-objective
comparisons, positive-cost mechanism and capped/uncapped variance diagnostics.
They support the corresponding main-text qualifications and are not additional
independent replications. Parameter, cost and historical-control results keep
their original sample sizes and uncertainty conventions.

'''+ '\n\n'.join(moved)+ '\n\n'+r'\small'+'\n\n'+'\n\n'.join(tables)+ '\n'+r'\normalsize'+'\n'
index=text.index(r'\begin{thebibliography}')
text=text[:index]+extra+'\n'+text[index:]

# Keep the claim/evidence map aligned with the now-complete core extensions.
swap('the separate factorial study does not show beneficial feedback.',
     'the original factorial does not show beneficial weak-search feedback; stronger-search means qualify that result.')
claim=r'''\addlinespace
C9. RPL lowers primary inflation at the unit endpoint. & Ten fitting seeds per source; all 30 matched directions favorable, with positive exploratory simultaneous lower bounds. & Supported within the fixed finite-response design; synthetic honest error and failed queries increase, and nonconverged responses remain.\\
\addlinespace
C10. Core extensions have completed computational checks. & Four-stage chain for 1,206 distinct cells, including all 540 RPL extension cells. & Shared primitives and retrospective cohorts remain; external exact numerical reproduction failed.\\
'''
map_start=text.index(r'\section{Detailed claim--evidence map}')
map_end=text.index(r'\end{longtable}',map_start)
last=text.rfind(r'\bottomrule',map_start,map_end)
text=text[:last]+claim+text[last:]

# No undefined reference, duplicate label, or unintended main/SI display count.
labels=re.findall(r'\\label\{([^}]+)\}',text)
assert len(labels)==len(set(labels))
refs=re.findall(r'\\(?:ref|eqref)\{([^}]+)\}',text)
assert set(refs)<=set(labels),set(refs)-set(labels)
main,append=text.split(r'\appendix',1)
counts=dict(main_figures=main.count(r'\begin{figure}'),appendix_figures=append.count(r'\begin{figure}'))
assert counts==dict(main_figures=8,appendix_figures=9),counts
abstract_words=len(re.findall(r'\b[\w]+\b',abstract))
assert 150<=abstract_words<=250,abstract_words
FILE.write_text(text)
(NOTE/'revision.json').write_text(json.dumps(dict(status='edited_compile_and_layout_pending',
    source_before=hashlib.sha256(OLD.encode()).hexdigest(),source_after=hashlib.sha256(text.encode()).hexdigest(),
    abstract_word_count=abstract_words,display_counts=counts,changed_sections=changes,
    retained_old_theory_and_experiments=True,external_failure_disclosed=True,
    external_figure_includes=True,manuscript_is_same_file=True,new_training=False),indent=2)+'\n')
print(counts,'abstract words',abstract_words)
