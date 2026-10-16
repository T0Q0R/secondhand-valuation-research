from pathlib import Path
import re,json,hashlib,difflib
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent;target=ROOT/'paper/innovation-addendum-v1.tex'
before=target.read_text();assert hashlib.sha256(target.read_bytes()).hexdigest()=='bf799e53b6ba4cbebf84ec78d6c2c3ffe581e6a9a21a8f4e312dd2646f656a24'
(HERE/'before-source.tex').write_text(before)
s=before

def figure(name,caption,label):
 return '\n\\begin{figure}[tbp]\\centering\n\\resizebox{\\textwidth}{!}{%\n'+(HERE/(name+'.inline.tex')).read_text()+'%\n}\n\\caption{'+caption+'}\n\\label{'+label+'}\n\\end{figure}\n'
method=r'''
\subsection{Recovery-path regularization of the public predictor}\label{sec:rpl_method}
\noindent\textbf{Takeaway.} A training penalty can target the diagnosed recovery
failure directly, but a finite penalty is not an incentive guarantee.

Let $q_\theta(s)$ denote a log quotation and $q_\theta(H_i)$ its honest-report
anchor for training record $i$. For each legal hidden-field recovery edge
$(s,a)\in\mathcal E_i$, define
\begin{align}
 g_{i,\theta}(s)&=[q_\theta(s)-\operatorname{sg}(q_\theta(H_i))]_+,\\
 L_{\rm path}(\theta)&=\frac{1}{\sum_i|\mathcal E_i|}
 \sum_i\sum_{(s,a)\in\mathcal E_i}
 [g_{i,\theta}(T(s,a))-g_{i,\theta}(s)]_+ .\label{eq:rpl}
\end{align}
Here $\operatorname{sg}$ stops the anchor gradient within an optimizer step.
The objective adds $\lambda L_{\rm path}$ to the matched no-feedback loss;
$\mathcal E_i$ contains recoveries of actually concealed fields, excluding
naturally unavailable values. The ordinary gap term penalizes a quotation
relative to honesty; this term additionally penalizes increases in positive
gain along intermediate recoveries. Honest values and the anchor are training
supervision, not deployment inputs. Deployment uses the same public-record
predictor, without a quotation-history input.

\begin{proposition}[Finite recovery-graph implication]\label{prop:rpl}
On a fixed finite collection of record graphs, if $L_{\rm path}=0$, positive
gain cannot increase along any path composed of their legal recovery edges.
\end{proposition}
\begin{proof}
Every summand in \eqref{eq:rpl} is nonnegative. A zero finite sum makes each
edge increment nonpositive; chaining these inequalities proves the claim.
\end{proof}

This implication allows positive initial concealment gain. It provides no
guarantee on unseen records, finite-penalty fits, allocation optimality or
honest error. Shared parameters can move the anchor between steps despite
its stopped gradient. Recovery-path regularization (RPL) is therefore a
mechanism-targeted candidate, not a new general monotonicity principle or an
established replacement for existing strategic-missingness methods.

'''
s=s.replace(r'\section{Experimental design and corroborating checks}',method+r'\section{Experimental design and corroborating checks}',1)
intro=r'''
The recovery diagnosis also motivates a training intervention:
RPL penalizes increases in positive concealment gain along legal recovery
edges (Section~\ref{sec:rpl_method}). Its three-seed pilot separates path
weight from the existing gap term, retains zero-query evaluations, and exposes
honest-error and failed-query costs. A stronger training-response intervention
also qualifies the original feedback finding: some observed damage disappears
when the response search is strengthened. These results link the diagnosed
failure to a testable algorithmic intervention, without treating the restricted
information theorem as a quantitative prediction for the learned model.
'''
s=s.replace(r'\section{Related work}',intro+'\n'+r'\section{Related work}',1)
s=s.replace('Instead, we test a frozen-policy implementation\nunder matched fitting budgets.', 'Instead, we test an epoch-refreshed implementation under matched fitting\nbudgets and separately intervene on within-epoch score refresh and training\nresponse-search strength.')
related=r'''
Recent acquisition methods include amortized greedy selection (GDFS)~\cite{gdfs},
discriminative information estimation (DIME)~\cite{dime}, stochastic latent
encodings (SEFA)~\cite{sefa}, and explanation-ranked transformer
policies~\cite{explainafa}. Alongside ACO~\cite{activeoracle}, they broaden
acquisition coverage beyond simple risk and predictive benefit. Their predictive
objectives, sequential budgets and input assumptions do not imply control of
strategic quotation gain. Our executed adapters and their limitations are
specified in Appendix~\ref{app:completion_methods}.
'''
s=s.replace(r'\subsection{Strategic feedback and contextual policy classes}',related+'\n'+r'\subsection{Strategic feedback and contextual policy classes}',1)
# Add design at end of setup, before Results.
design=r'''
\paragraph{Controlled completion study.}
A subsequent development study used the same three sources, fixed populations,
1,000 evaluation records per source, and fitting seeds 13, 42 and 2026.
It completed 1,719 cells including exact reused references: 432 complete
$2^3$ component combinations, 270 core-parameter cells, 144 implementation
sensitivities, 108 SEFA cells, 90 search/refresh interventions, 189 availability
stress cells, 162 RPL cells and 324 additional recent-baseline cells. These
counts overlap earlier references and are not independent replications or
1,719 new training runs. Role-separated cross-fitting and frozen-price-model
comparisons were preserved where specified. Source and adaptation details are
in Appendix~\ref{app:completion_methods}.

The three-seed additions are retrospective development evidence. Figures show
seed points or means and full seed ranges, not confidence intervals. Existing
4,000-draw paired crossed-bootstrap summaries for the component, parameter,
SEFA and search stages remain conditional sensitivity analyses, without a
finite-sample coverage or family-wise guarantee. They are not transferred to
RPL or the additional baseline stages. Across the 1,719 cells, 137 contained
at least one nonconverged batch; the maximum remaining unilateral regret was
0.2670021 log units. All were retained. Integer-state/utility re-derivations
share predictor and score primitives; hash checks do not establish an
independent implementation of these shared primitives.

'''
s=s.replace(r'\section{Results}',design+r'\section{Results}',1)
results=r'''
\subsection{Controlled components and a search-strength intervention}\label{sec:completion_mechanisms}
\noindent\textbf{Takeaway.} Stronger training-response search removed some
feedback damage; the original negative result does not describe every feedback
implementation.

The complete suppression-score/feedback/gap factorial retained all eight
combinations, including removal of two or all three switched components
(Figure~\ref{fig:completion_ablation}). These switches are experimental
components, not three independently established innovations. Gap removal
substantially increased mean primary inflation on the real sources, whereas
the full three-component configuration was not uniformly best.

The original scoring network was refreshed each epoch, rather than frozen
throughout training. We crossed epoch versus minibatch score refresh with weak
(two sweeps, one start) versus strong (20 sweeps, four starts) training-response
search. Both retained two six-epoch rounds and matched no-feedback references.
Figure~\ref{fig:completion_mechanism} shows the three individual seeds and their
means at 10\% capacity. On synthetic, epoch-weak inflation was 0.02075,
epoch-strong 0.01279, batch-strong 0.01269, and no-feedback 0.01303. Thus
strengthening search substantially reduced the weak implementation's damage,
and the strong means were slightly below the no-feedback reference. Strong
JUCars means were also slightly lower than no-feedback, whereas all four
MUCars feedback means remained higher. Changing score-refresh frequency alone
was not a consistent remedy. These are conditional mean comparisons, not
proof of a uniquely identified cause or population-wide feedback benefit.
'''
results+=figure('mechanism_search',r'''Training-response strength changes the feedback comparison. Primary 10\% capacity, three fitting seeds on fixed records. Faint lines and circle/square/triangle markers retain paired seeds; bold diamonds are arithmetic means. Off is the matched no-feedback reference; epoch/batch denotes score-refresh frequency and weak/strong denotes response search. Different source scales are intentional. All outcomes, including nonconverged ones, are retained. No confidence intervals or significance tests are encoded.''','fig:completion_mechanism')
results+=r'''
\subsection{Recovery-path regularization: improvement and costs}\label{sec:rpl_results}
\noindent\textbf{Takeaway.} Penalizing recovery-path amplification reduced
primary mean inflation on all three sources, with honest-error, failed-query
and convergence costs that prevent a universal dominance claim.

The RPL pilot compared path weights $0,0.1,0.5,1$ with gap weight 0.5, plus
path weights $0,0.5$ with the gap removed, at capacities $0,0.1,0.3$.
Matched zero-weight branches were reused exactly. The 162 cells comprised
54 reused and 108 new evaluations, with 144 new role-separated price fits.
The design value 0.5 used the existing gap coefficient's scale; the full grid
was fixed before evaluation. It is an engineering choice, not an estimated
optimum. Table~\ref{tab:rpl_primary} retains the design value and endpoint;
Figure~\ref{fig:rpl_tradeoffs} also includes weight 0.1.

At the prespecified $\lambda=1$ sensitivity endpoint, the ratio-of-means
inflation reductions from the matched $\lambda=0$, gap-0.5 reference were
50.93\%, 33.22\% and 18.72\% on synthetic, JUCars and MUCars. Inflation fell
in all nine source/seed comparisons. Mean honest MAE changed by $+0.99\%$,
$-0.19\%$ and $-0.91\%$, and attacked MAE by $-0.91\%$, $-0.17\%$ and
$-1.07\%$. Failed queries increased by 0.63 and 1.47 percentage points per
listing on synthetic and JUCars and were unchanged in the MUCars mean.
Two synthetic seeds each retained one nonconverged batch out of ten at this
endpoint. These results do not establish improvement under an exact response
equilibrium or justify selecting the endpoint as a new default.

The mean positive gain increment per legal recovery edge decreased from
0.001790 to 0.000693 on synthetic, 0.001648 to 0.001048 on JUCars, and
0.000788 to 0.000450 on MUCars. The increments remained positive, so the
zero-penalty premise of Proposition~\ref{prop:rpl} was not achieved. Paired
zero-query results and training-quantile price-tail/natural-missingness
subgroups remain in the source data. Zero-query changes are estimator effects;
they cannot be credited to acquisition. RPL modifies the predictor, whereas
the next comparison fixes it, so the two experiments answer different questions.
'''
r=pd.read_csv(HERE/'rpl_primary_table.csv');table=r'''\begin{table}[tbp]\centering\small
\caption{RPL at 10\% capacity and gap weight 0.5. Means of three fitting seeds;
MAE is in source currency and failure is the percentage of all listings.
All branches use no feedback and the matched two-round reset schedule.}
\label{tab:rpl_primary}
\begin{tabular}{lrrrrr}\toprule
Source / $\lambda$ & Inflation & Honest MAE & Attacked MAE & Failed (\%)\\\midrule
'''
for source in ['synthetic','jucars','mucars']:
 for _,v in r[r.dataset==source].sort_values('path_weight').iterrows():table+=f"{source} / {v.path_weight:g} & {v.mean_positive_log_inflation:.5f} & {v.clean_mae:.2f} & {v.attack_mae:.2f} & {100*v.failed_query_fraction:.2f} \\\\\n"
table+=r'\bottomrule\end{tabular}\end{table}'+'\n';results+=table
results+=figure('rpl_tradeoffs',r'''Paired RPL sensitivity exposes benefits and costs. Gap weight 0.5, 10\% capacity, all three fitting seeds. Lines show means of seed-relative inflation reductions and honest-error changes; failure changes are percentage points per listing. Bands are full seed ranges, not confidence intervals. Positive values are favorable only in panel (a). The table instead reports absolute means; its ratio-of-means percentages need not equal panel (a)'s mean of seed-relative percentages. No outcomes or weights are discarded.''','fig:rpl_tradeoffs')
results+=r'''
\subsection{Five recent acquisition families on fixed price models}\label{sec:recent_results}
\noindent\textbf{Takeaway.} Estimator choice and simple strong controls remain
material after expanding recent-method coverage.

ACO, SEFA, GDFS, DIME and explanation-ranked AFA each covered three sources,
three fitting seeds, two frozen price backends and six capacities, totaling
540 common-grid cells; ACO additionally retained 36 fixed-neighbor sensitivities.
Within source/seed/backend/capacity, honest MAE agreed across these methods to
less than $10^{-6}$, as required when only acquisition changes. ACO's declared
$k=25$ was used throughout; no evaluation-best neighbor count replaced it.
Figure~\ref{fig:recent_curves} shows every family's budget curve alongside
available matched risk/benefit controls. At 10\% capacity with the robust
backend, GDFS had the lowest family-mean inflation on JUCars (0.01013),
whereas SEFA was lowest on MUCars (0.00660); ACO was lowest on synthetic
(0.01081). No recent family minimized inflation on all three sources.
Simple risk or benefit remained competitive or better in several mask-aware
comparisons. Full four-metric primary means are in
Appendix~\ref{app:completion_methods}; an inflation ranking is not a
multiobjective dominance result.
'''
results+=figure('recent_budget_curves',r'''Five recent acquisition families under shared one-query batch capacity. Lines are means over three fitting seeds; shading is the full seed range, not a confidence interval. Rows fix the mask-aware or robust price predictor and columns denote sources. ACO uses fixed $k=25$. Risk and benefit use their available matching mask-aware backend; no matching robust-backend version is invented. All nonconverged outcomes remain included. The four classification-based adapters use training-only price bins, and every method has explicit task-specific adaptation boundaries.''','fig:recent_curves')
s=s.replace(r'\section{Discussion}',results+'\n'+r'\section{Discussion}',1)
# Qualify old broad interpretation with the new intervention evidence.
s=s.replace('frontier and an audited verification-path mechanism. General superiority is unsupported; the completed factorial experiment\nseparates source-dependent initial-objective effects from adverse feedback effects.', 'frontier, an audited recovery-path diagnosis and a targeted regularization\npilot. The original factorial identifies adverse effects of its implemented\nfeedback procedure; stronger-search interventions narrow that interpretation.')
s=s.replace('These controlled effects do not establish the cause of the original unmatched\nSAV comparison, and response-search behavior remains a possible contributor.', 'These controlled effects do not establish the cause of the original unmatched\nSAV comparison. Section~\\ref{sec:completion_mechanisms} directly varies response\nsearch and shows that strengthening it removes part of the observed damage.\nThe RPL intervention further links a measured failure path to lower gain, while\nits failed-query and honest-error costs keep the deployment claim conditional.')
s=s.replace('implementation; they do not claim a new general linear-programming method,', 'implementation and the bounded recovery-path pilot; they do not claim a new general linear-programming method,')
s=s.replace('increase mean inflation at zero concealment cost, even though robust initialization helps on MUCars.', 'increase mean inflation at zero concealment cost in the original implementation,\neven though robust initialization helps on MUCars. Stronger training-response\nsearch removes some of that harm in matched development controls. RPL directly\npenalizes gain-increasing recovery edges and reduces primary inflation in a\nthree-seed pilot, while predictive error, failed queries and nonconvergence\npreclude a universal superiority claim.')
# Appendix for full implementation/parameter evidence; main remains claim-focused.
appendix=r'''
\clearpage
\section{Controlled completion protocols and full comparison evidence}\label{app:completion_methods}
\subsection{Recent-method identity and training boundaries}
The adapters use the same fixed price backends as ACO-1, not each paper's
original predictive task. SEFA, GDFS, DIME and explanation-ranked AFA learn
acquisition using four training-quantile price classes; their scores feed a
shared hard-capacity, one-query allocator. This does not make them native
strategic regressors. Nonquery context is available, natural absence is
unrecoverable, and deployment scores do not observe a hidden value or its
missingness cause. Hidden-mileage perturbation checks left the corresponding
public-state scores unchanged. Predictive information scores and policy
probabilities are used as cross-listing priority proxies without a theorem of
cross-listing cardinal comparability.

SEFA used its official MIT implementation, commit
\texttt{3af8da2c9212c294fc7fedad27bc31045db7607a}, configurations 1/5/9,
120 epochs per trial and their original latent-sampling settings. GDFS and DIME
used the comparison implementations in that repository, retaining their
relaxed-one-hot/temperature and entropy-scaled value/epsilon-greedy cores.
Their configurations 1/5/9 use 80 predictor-pretraining epochs and 15 epochs
per annealing stage. The task adapter starts from legal public reports and
trains at most two recoveries, uses Adam and stagewise best validation states,
and does not reproduce the original learning-rate scheduler. This is a sourced
task adaptation, not an unchanged original-author reproduction.

Explanation-ranked AFA used the official repository commit
\texttt{d08f39ae7a50c0dd2bc6d9113d9a124b1cec085e}, its tabular MLP and
three-layer, four-head GPT, hidden width 128 and embedding width 64.
A fitting-partition 250-tree CatBoost classifier supplies TreeSHAP rankings;
field-value and missing-indicator absolute contributions for the training label
are summed. Natural missingness and numeric category coding are task
adaptations. The stages comprise 250 masked-predictor, 200 ranking-supervised
and 16 policy-trajectory epochs, with at most two recoveries per training
trajectory and a fixed initial action marker at history-free deployment.
Learning rates $0.001,0.0005,0.0003$ form a fixed local grid; the last is an
additional sensitivity value rather than an original default.

All four classification adapters select among three configurations using the
same training-only 80:20 split and then refit on all training records. SEFA
uses its masked validation NLL and selected epoch, while the other three use
mean pre/post-query NLL and their full fixed schedule. Thus selection effort
is documented but their validation objectives are not identical. No evaluation
outcome is used to select a configuration. ACO-1 instead retains the declared
training-bank rule and fixed neighbor sensitivities described in
Appendix~\ref{app:comparators}. These differences, the fixed 1,000-record
completion cohort, and three fitting seeds bound cross-family conclusions.

\subsection{Full component removals and parameter choice}
$S$ switches suppression rather than ordinary-benefit score training, $F$
switches feedback, and $G$ switches the gap penalty. All $2^3$ combinations
share the role separation, epoch budget and reset schedule. The conventional
backbone, mask augmentation, prediction/attack-error and anchor terms remain
when all three switches are removed. Figure~\ref{fig:completion_ablation}
therefore is a complete component ablation, not a comparison with an untrained
or native predictor.
'''
appendix+=figure('factorial_ablations',r'''Complete three-component ablation at 10\% capacity. Circles retain three paired seed differences from S1F1G1 and diamonds show their means. Negative differences indicate lower inflation than the full switched configuration. S/F/G denote suppression-score, feedback and gap switches. Neither number of cells nor number of components is an independent sample size or an innovation count. All nonconverged responses remain in the plot.''','fig:completion_ablation')
appendix+=r'''
Core sensitivity varied gap weight over $0,0.1,0.25,0.5,1,2$, tolerance over
$0,0.01,0.02,0.05,0.1$, and one/two/four reset-feedback rounds at fixed total
12 residual epochs. The design values 0.5 and 0.02 are fixed engineering
choices on the log-quotation scale, not optimal values estimated from these
curves. Increases in gap weight reduce inflation means in this grid, but
inflation alone cannot select a default. Figure~\ref{fig:completion_parameters}
retains both evaluated capacities. A further 144 cells vary anchor weight,
attack-loss weight, learning rate, epochs, action-head tree count and hidden
width one at a time (Figure~\ref{fig:completion_stability}). The defaults are
inserted from the exactly matched S1F1G1 branch, not retrained or interpolated.
All error, failure and convergence metrics remain in the source tables.
'''
appendix+=figure('parameter_sensitivity',r'''Core parameter sensitivity under the original weak-feedback training, at 10\% (top) and 30\% (bottom) capacity. Means and full ranges over three fixed fitting seeds. The horizontal axis shows actual evaluated settings, joined by straight lines. Changing round count preserves 12 total residual epochs but changes the optimizer/reset schedule. The plots describe sensitivity and do not select an evaluation-best default.''','fig:completion_parameters')
appendix+=figure('implementation_stability',r'''Additional implementation sensitivity at 10\% capacity. Each point is normalized within source/seed to the unchanged matched default, then averaged; shading is the full seed range. All six parameter axes show actual settings, including the exact default. The learning-rate axis is logarithmic and strictly positive. These inflation curves are accompanied by error/failure metrics in source data; a low ratio alone does not establish a better model.''','fig:completion_stability')
appendix+=r'''
\subsection{Availability-shift stress and source-data coverage}
The availability stress study held fitted models fixed and additionally removed
0, 10\% or 30\% of originally observed query fields using nested stable hashes
of listing and field. Targets were unchanged; newly missing values could not
be recovered. Seven mechanisms (four search/refresh variants, matched
no-feedback, risk and benefit) yielded 189 cells: 63 reused and 126 new
evaluations, with no refitting. Reports were reoptimized after the shift.
This is a controlled availability perturbation, not a new market, MNAR model
or actual-seller validation. Paired metrics, recovery paths and all three
seed values remain in the evidence files. RPL additionally retained low/middle/high
price groups using training-only 10th/90th quantiles and naturally
complete/missing groups; these shared-population subgroups are descriptive.

\subsection{Primary recent-family numerical comparison}
Table~\ref{tab:recent_primary} reports all five family means rather than only
winners. Currency MAE is not pooled across sources. Identical honest MAE within
a frozen backend is expected and does not demonstrate equal attacked error.
'''
appendix+=r'''\begin{longtable}{lllrrrr}
\caption{Five recent families at 10\% capacity. Means of three fitting seeds;
M/R denote fixed mask-aware/robust price backends. Failed queries are percent
of all listings. ACO uses $k=25$. Adapter boundaries are given above.}\label{tab:recent_primary}\\
\toprule Source & Backend & Family & Inflation & Honest MAE & Attacked MAE & Failed (\%)\\\midrule\endfirsthead
\toprule Source & Backend & Family & Inflation & Honest MAE & Attacked MAE & Failed (\%)\\\midrule\endhead
'''
t=pd.read_csv(HERE/'recent_primary_table.csv')
for source in ['synthetic','jucars','mucars']:
 for backend in ['masking_suppression','robust_no_feedback']:
  for _,v in t[(t.dataset==source)&(t.price_backend==backend)].sort_values('recent_family').iterrows():
   appendix+=f"{source} & {'M' if backend=='masking_suppression' else 'R'} & {dict(aco='ACO',sefa='SEFA',gdfs='GDFS',dime='DIME',efa='Expl.-AFA')[v.recent_family]} & {v.mean_positive_log_inflation:.5f} & {v.clean_mae:.0f} & {v.attack_mae:.0f} & {100*v.failed_query_fraction:.2f} \\\\\n"
appendix+=r'\bottomrule\end{longtable}'+'\n'
s=s.replace(r'\begin{thebibliography}{99}',appendix+'\n'+r'\begin{thebibliography}{99}',1)
refs=r'''
\bibitem{gdfs} I. C. Covert, W. Qiu, M. Lu, N. Y. Kim, N. J. White and S.-I. Lee.
Learning to Maximize Mutual Information for Dynamic Feature Selection.
ICML, PMLR 202:6424--6447, 2023.
\url{https://proceedings.mlr.press/v202/covert23a.html}.
\bibitem{dime} S. Gadgil, I. Covert and S.-I. Lee.
Estimating Conditional Mutual Information for Dynamic Feature Selection.
ICLR, 2024. \url{https://arxiv.org/abs/2306.03301}.
\bibitem{sefa} A. L. I. Norcliffe, C. Lee, F. Imrie, M. van der Schaar and P. Lio.
Stochastic Encodings for Active Feature Acquisition.
ICML, PMLR 267:46784--46814, 2025.
\url{https://proceedings.mlr.press/v267/norcliffe25a.html}.
\bibitem{explainafa} O. B. Guney, K. S. Saichandran, K. Elzokm, Z. Zhang and V. B. Kolachalama.
Active Feature Acquisition via Explainability-driven Ranking.
ICML, PMLR 267:20748--20765, 2025.
\url{https://proceedings.mlr.press/v267/guney25a.html}.
'''
s=s.replace(r'\end{thebibliography}',refs+r'\end{thebibliography}',1)
abstract='''Verification can recover withheld information while increasing a seller's valuation gain. We study secondhand-price prediction with natural missingness, charged failed queries and shared batch capacity. A restricted precision--incentive frontier delimits possible guarantees, while exhaustive recovery graphs expose gain-increasing partial recoveries in learned models. This diagnosis motivates recovery-path regularization, which penalizes increases in positive concealment gain along legal recovery edges without adding hidden information to deployment inputs. A ten-seed factorial audit covers 4,320 cells; its 36 primary zero-cost feedback contrasts all worsen inflation under the original training implementation. A subsequent controlled completion study covers 1,719 cells including reused references, full component ablations, parameter sensitivities, search-strength interventions and five recent acquisition families. Stronger training-response search removes some original feedback damage, restricting the negative conclusion to its implementation. In a three-seed regularization pilot at 10\\% capacity, the prespecified unit-weight sensitivity endpoint reduces mean inflation by 50.93\\%, 33.22\\% and 18.72\\% on synthetic, JUCars and MUCars relative to its matched zero-weight control. Synthetic honest MAE rises 0.99\\%, and failed-query fractions rise on two sources; some responses remain nonconverged. Recent-family rankings also change across sources and fixed price backends. The resulting contribution links an auditable recovery failure to a targeted algorithmic intervention and multiobjective evidence, without claiming universal superiority, incentive compatibility or actual-seller validation.'''
s=re.sub(r'\\begin\{abstract\}.*?\\end\{abstract\}',lambda m:'\\begin{abstract}\n'+abstract+'\n\\end{abstract}',s,count=1,flags=re.S)
target.write_text(s)
(HERE/'changes.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),s.splitlines(True),fromfile='pre-completion',tofile='post-completion')))
r=dict(status='source_integrated_pending_builtin_compile',source_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),previous_sha256=hashlib.sha256(before.encode()).hexdigest(),abstract_words=len(abstract.split()),figures=s.count('\\begin{figure}'),references=s.count('\\bibitem'),new_figure_count=6,new_training_runs=0)
(HERE/'revision.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
