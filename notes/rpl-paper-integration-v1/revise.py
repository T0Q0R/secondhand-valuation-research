"""Integrate the verified crossing into the same manuscript; no computation."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
target=ROOT/'paper/innovation-addendum-v1.tex'
s=(OUT/'before.tex').read_text()
oldfig=None
for m in re.finditer(r'\\begin\{figure\}.*?\\end\{figure\}',s,re.S):
    if r'\label{fig:recent_curves}' in m.group():oldfig=m.group();break
assert oldfig
(OUT/'legacy-recent-budget-figure.tex').write_text(oldfig+'\n')
start=s.index(r'\subsection{Five task-adapted recent acquisition families on fixed price models}')
end=s.index(r'\subsection{Controlled components and a search-strength intervention}',start)
section=r'''\subsection{Matched RPL and five recent acquisition families}\label{sec:recent_results}
The direct comparison crosses $\lambda=0,1$ with ACO, SEFA, GDFS, DIME
and explanation-ranked AFA at $\beta=.5$ and 10\% capacity: three sources
and the same three fitting seeds give 90 cells. Both predictors use the
same no-feedback training schedule and cohorts. The four neural acquisition
tables remain frozen; ACO's training-bank losses are recomputed under each
predictor, with $k=25$ fixed. No policy is selected or refitted on evaluation
outcomes. These are task adaptations, with code/observation/selection
boundaries in Appendix~\ref{app:completion_methods}, not official end-to-end
reproductions of the original papers.

\paragraph{Does RPL help each acquisition family?}
Table~\ref{tab:rpl_crossing} shows both predictor settings and matched costs.
Adding RPL lowers inflation in all 45 source--family--seed pairs. Ratios of
family means fall by 32.97--48.00\% on synthetic, 30.56--32.70\% on JUCars
and 18.97--25.55\% on MUCars. Within each source, even the largest
RPL-on family mean is below the smallest RPL-off family mean. Thus the
inflation gain persists across these acquisition choices in the fixed design.

\paragraph{Does stacking improve on the native RPL pipeline?}
Eighteen existing matched cells retain the original suppression head
(\emph{native head}); it still performs acquisition. At $\lambda=1$,
SEFA has the lowest observed inflation mean on synthetic and GDFS on both
real sources, respectively 17.07\%, 4.76\% and 22.47\% below native-head
RPL. These retrospective minima are not selected deployment defaults.
Stacking is not uniformly better than native-head RPL: synthetic GDFS
gives 0.00907 versus the native head's 0.00639. The best complete pipeline
therefore depends on the acquisition family and objective.

\paragraph{Costs and evidence boundary.}
Across the matched three-seed predictors, honest MAE changes by
$+0.99\%,-0.19\%,-0.91\%$ on synthetic/JUCars/MUCars, independently of
acquisition. All five-family attacked-MAE means decrease, while failed-query
changes range from $-0.07$ to $+1.23$ percentage points per listing.
All 18 nonconverged batches among the 900 crossing batches remain included;
maximum remaining regret is 0.14916 log units. This is three-seed development
evidence on shared cohorts; seed ranges are not confidence intervals or the
ten-seed study. Appendix~\ref{app:completion_methods} gives absolute error
and failure means; source CSVs retain every seed and convergence value.

'''
s=s[:start]+section+(OUT/'main-table.tex').read_text()+'\n\n'+s[end:]
oldtable=None
for m in re.finditer(r'\\begin\{longtable\}.*?\\end\{longtable\}',s,re.S):
    if r'\label{tab:recent_primary}' in m.group():oldtable=m.group();break
assert oldtable
(OUT/'legacy-recent-primary-table.tex').write_text(oldtable+'\n')
s=s.replace(oldtable,(OUT/'appendix-table.tex').read_text().rstrip())
old=r'''All five acquisition families use the same frozen price backends, one-query
hard-capacity interface, public nonquery context and unrecoverable natural
absence. The four classification adapters train on four price-quantile
classes and use acquisition scores as cross-listing priorities; no cardinal
comparability theorem is asserted. Hidden-mileage perturbations leave their
public-state scores unchanged. The shared design has three sources, three
seeds, two backends and six budgets (540 cells), plus 36 ACO sensitivities.
Table~\ref{tab:recent_primary} gives every primary family mean.'''
new=r'''The matched comparison in Table~\ref{tab:recent_primary} uses the same
three sources, fitting seeds 13/42/2026, evaluation records, batch ordering,
gap weight .5, no-feedback schedule and 10\% capacity for both RPL settings.
Its 90 cells add no fits: four neural acquisition tables reuse their frozen
training-only choices, while ACO reconstructs all sixteen guidance-bank
observation losses under each predictor. The native suppression heads reuse
18 previously audited cells with identical predictor/evaluation hashes and
listing order. Their three-seed means are distinct from the ten-seed means
in Table~\ref{tab:rpl_primary}. Per-seed outcomes, full ranges and
convergence values are at \path{notes/rpl-paper-integration-v1/}.

All adapters share a one-query hard cap, public nonquery context and
unrecoverable natural absence. The four classification adapters train on
four price-quantile classes; using their scores as cross-listing priorities
has no cardinal-comparability theorem. Concealed-mileage perturbations leave
the relevant public-state scores unchanged. The earlier two fixed-backend,
six-budget study (540 cells plus 36 ACO sensitivities) remains in
\path{outputs/recent-five-analysis-v1/}; its budget curves are preserved at
\path{paper/figures/postcompute-v1/recent_budget_curves.pdf}. The present
table answers the matched RPL/stacking question instead.'''
assert old in s;s=s.replace(old,new)
old='pilot; remaining support cells are not upgraded.'
new='''pilot; remaining support cells are not upgraded. A separate matched
RPL--acquisition crossing adds 90 cells with independent integer-allocation,
all-legal-deviation and outcome-summary checks. Its 18 native-head reference
cells are reused from the core; the new crossing has no four-stage
fit/statistics-audit upgrade.'''
assert old in s;s=s.replace(old,new)
old=r'Remaining completion-study support & Hash bindings, utility checks and recorded summaries & No whole-study four-stage upgrade of all 1,719 cells\\\bottomrule'
new=r'''Matched RPL--acquisition crossing: 90 cells & Independent allocation/deviation/outcome checks; 18 native references reused & Three-seed descriptive effects; no new four-stage fit/statistics chain\\
Remaining completion-study support & Hash bindings, utility checks and recorded summaries & No whole-study four-stage upgrade of all 1,719 cells\\\bottomrule'''
assert old in s;s=s.replace(old,new)
old='''initial objective, acquisition, feedback and allocation, then assess RPL with
ten fitting seeds, component removals, budget variation and four-stage
computational checks.'''
new='''initial objective, acquisition, feedback and allocation. We assess RPL with
ten fitting seeds and a separate 90-cell crossing with five recent acquisition
families, including native-head references and prediction/query costs.
Component removals, budget variation and computational checks bound both studies.'''
assert old in s;s=s.replace(old,new)
old='The claim-bearing extensions complete a four-stage computational audit covering 1,206 distinct cells, including the 540-cell ten-seed study.'
new='A separate three-seed, 90-cell crossing lowers inflation in all 45 paired comparisons when RPL is combined with five task-adapted acquisition families. Four-stage checks cover 1,206 earlier extension cells; the crossing has independent outcome checks.'
assert old in s;s=s.replace(old,new)
old='''response regret, preclude a universal dominance claim.

Stronger-search interventions'''
new='''response regret, preclude a universal dominance claim. The matched crossing
supports RPL as a complement to acquisition at the tested weights and cohorts.
Native-head counterexamples and error/failure costs keep the deployment
decision specific to the complete predictor--policy pair.

Stronger-search interventions'''
assert old in s;s=s.replace(old,new)
old='machine. A DOI-backed archive has not yet been issued.'
new=r'''machine. Software and aggregate evidence are archived at
\href{https://doi.org/10.5281/zenodo.23447567}{DOI 10.5281/zenodo.23447567}.'''
assert old in s;s=s.replace(old,new)
old=r'RPL ten-seed effects & \path{notes/ten-seed-visual-review-v1/}; all seeds and figure CSVs\\'
new=old+'\n'+r'RPL--acquisition comparison & \path{notes/rpl-paper-integration-v1/}; 90 crossed + 18 reused cells\\'
assert old in s;s=s.replace(old,new)
s=s.replace('Different cohorts/models prevent\nan isolated acquisition-effect interpretation.',
            'These support-margin comparisons do not isolate acquisition effects.')
target.write_text(s)
abstract=s.split(r'\begin{abstract}')[1].split(r'\end{abstract}')[0]
report=dict(status='draft_written_compilation_pending',source_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
            abstract_space_tokens=len(abstract.split()),main_table='tab:rpl_crossing',
            original_table_preserved='legacy-recent-primary-table.tex',original_figure_preserved='legacy-recent-budget-figure.tex')
(OUT/'revision.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

