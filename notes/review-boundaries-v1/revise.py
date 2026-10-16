from pathlib import Path
import re,hashlib,json,difflib
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent;p=ROOT/'paper/innovation-addendum-v1.tex';s=p.read_text();before=s;assert hashlib.sha256(p.read_bytes()).hexdigest()=='c6b0e07900e150ce1995d04537979504f7d6e1ab4e3b4360d86839c89b99482e'
abstract=r'''Verification can recover withheld information while increasing a seller's valuation gain. We study secondhand-price prediction with natural missingness, charged failed queries and shared batch capacity. A restricted precision--incentive frontier delimits guarantees, while recovery graphs expose gain-increasing partial recoveries in learned models. This diagnosis motivates recovery-path regularization, penalizing increases in positive concealment gain along legal recovery edges without adding hidden information to deployment inputs. A ten-seed, 4,320-cell factorial audit finds adverse inflation directions in all 36 primary feedback contrasts under its original weak-response-search implementation. Subsequent interventions largely remove the mean damage on synthetic and JUCars when training-response search is strengthened. The empirical conclusion is implementation dependence, not inherent harm from feedback. A 1,719-cell completion study adds ablations, parameter sensitivities and five task-adapted recent acquisition families; its verification is below the original four-stage audit standard. In a three-seed exploratory pilot at 10\% capacity, the unit-weight endpoint in a timestamped development grid reduces mean inflation by 50.93\%, 33.22\% and 18.72\% on synthetic, JUCars and MUCars relative to matched zero-weight controls. Synthetic honest MAE rises 0.99\%, failed-query fractions rise on two sources, and some responses remain nonconverged. The contribution links a recovery failure to a targeted intervention with explicit audit and multiobjective boundaries, without establishing universal superiority, incentive compatibility or actual-seller validity.'''
s=re.sub(r'\\begin\{abstract\}.*?\\end\{abstract\}',lambda m:'\\begin{abstract}\n'+abstract+'\n\\end{abstract}',s,count=1,flags=re.S)
s=s.replace('factorial study. At its prespecified 10\\% capacity, all 36 feedback comparisons\nincrease mean inflation;', 'factorial study. Under its original weak training-response search, all 36\nfeedback comparisons at the declared primary 10\\% capacity increase mean inflation;')
anchor='\n\\section{Results}\\label{sec:results}'
audit=r'''
\paragraph{Audit levels are not interchangeable.}\label{sec:audit_levels}
The original 4,320-cell study completed the recorded fit-audit,
outcome-audit, analysis and statistics-check chain. The 1,719-cell completion
study has hash-bound outputs, recorded integer-state/utility re-derivations,
and subsequent descriptive, table and figure review, but has \emph{not}
completed an equivalent whole-study fit/analysis/statistical audit chain.
In particular, the RPL and newer acquisition-adapter conclusions in
Sections~\ref{sec:rpl_results}--\ref{sec:recent_results} are exploratory and
not audited to that same level. Search-strength interventions in
Section~\ref{sec:completion_mechanisms} have the same completion-study
limitation. Selected stages have conditional resampling summaries; that does
not substitute for the missing chain. Neither level constitutes a fully
independent reimplementation of all shared prediction primitives.

\begin{table}[tbp]\centering\small
\caption{Audit scope by experimental generation. A completed computation or
visual review does not imply an equivalent scientific audit. Historical
producer receipts are preserved rather than relabeled after manuscript review.}
\label{tab:audit_levels}
\begin{tabular}{p{.20\textwidth}p{.35\textwidth}p{.35\textwidth}}\toprule
Evidence & Completed scope & Claim boundary\\\midrule
Original 4,320 cells & Fit, outcome, analysis and statistics-check chain & Original implementation; disclosed shared primitives remain\\
Completion 1,719 cells, including reuse & Hash bindings, recorded utility re-derivations and descriptive/visual review; selected resampling summaries & No equivalent whole-study chain; search interventions, RPL and adapter comparisons remain exploratory\\\bottomrule
\end{tabular}\end{table}
'''
assert anchor in s;s=s.replace(anchor,'\n'+audit+anchor,1)
old=r'''\noindent\textbf{Takeaway.} At the prespecified 10\% capacity, none of the
36 feedback comparisons reduces mean inflation. A robust initial objective
helps consistently on MUCars, but positive interactions do not imply beneficial
feedback or a successful combined policy.'''
new=r'''\noindent\textbf{Takeaway.} Under the original weak training-response search,
all 36 primary feedback contrasts increase mean inflation. This documents a
failure of that implementation, not a general negative effect of feedback.

\paragraph{Which conclusion is primary?}
The paper's empirical conclusion is that verification and feedback outcomes
depend on the learning and response procedures. The 36/36 count and
Tables~\ref{tab:simultaneous}--\ref{tab:factorial_counts} establish the
well-audited original implementation's failure pattern. They are not the
headline claim that feedback is intrinsically harmful. The later, less-audited
search intervention (Section~\ref{sec:completion_mechanisms}) largely removes
the synthetic/JUCars mean damage with stronger training search, while MUCars
remains adverse in those means. Both findings must be read together; neither
identifies weak search as the sole cause nor proves exact-equilibrium benefit.
The asymmetry in audit depth is stated in Table~\ref{tab:audit_levels}.'''
assert old in s;s=s.replace(old,new,1)
s=s.replace('capped cohorts. The last column counts only the 36 inflation feedback contrasts', 'capped cohorts under the original weak training-response search. These bands\ndo not cover the strengthened-search interventions. The last column counts only the 36 inflation feedback contrasts',1)
s=s.replace('This is a negative result for the implemented two-round frozen-policy training\nprocedure, not an impossibility result for feedback learning.', 'This is a negative result for the implemented two-round, epoch-refreshed,\nweak-response-search training procedure. The strong-search means in\nSection~\\ref{sec:completion_mechanisms} narrow its interpretation; they do not\nalter the original counts.')
s=s.replace(r'\caption{Primary-capacity factorial diagnostics. Counts refer to positive',r'\caption{Original weak-search implementation: primary-capacity factorial diagnostics. These counts do not apply to strong-search retraining (Section~\ref{sec:completion_mechanisms}). Counts refer to positive',1)
s=s.replace(r'\caption{Policy feedback increases mean inflation in all twelve suppression-acquisition cells at the primary 10\% capacity.',r'\caption{Under the original weak training-response search, policy feedback increases mean inflation in all twelve suppression-acquisition cells at the primary 10\% capacity.',1)
s=s.replace(r'\caption{Absolute primary-capacity outcomes for the robust initial objective',r'\caption{Original weak-search implementation: absolute primary-capacity outcomes for the robust initial objective',1)
s=s.replace('but does not identify why feedback increased inflation. Frozen acquisition\nscores, the weaker training response search and capacity transfer are possible\nexplanations requiring separate interventions. They are not established causes\nin this paper.', 'but does not identify a unique cause of the original feedback damage.\nSection~\\ref{sec:completion_mechanisms} supplies development interventions on\ntraining-response strength and score-refresh frequency; stronger search\nremoves some damage, whereas capacity transfer is not separately identified.\nThese less-audited interventions qualify the negative result rather than\nestablishing a single causal explanation.')
s=s.replace('At the prespecified $\\lambda=1$ sensitivity endpoint, the ratio-of-means', 'At the declared $\\lambda=1$ development-grid endpoint, the ratio-of-means',1)
marker='\nAt the declared $\\lambda=1$ development-grid endpoint,'
timeline=r'''
\paragraph{Timestamped grid, not preregistration.}
The complete path-weight grid, including $\lambda=1$, is present in repository
commit \href{https://github.com/T0Q0R/secondhand-valuation-research/commit/6643cbe3266f2c1548d987c2bb53e366e19ad3ef}{\texttt{6643cbe}}, created on 14 October 2026 at 21:10:17 (UTC+08).
Its committed runner exactly matches the source hash in the executed manifest.
The formal RPL stage required its predecessor to finish, which occurred on
15 October 2026 at 22:57:51 (UTC+08). Thus the grid was timestamped before
formal evaluation. This is not an independent preregistration and does not
show that $\lambda=1$ was selected in advance as a headline endpoint.
We therefore call it a declared development-grid endpoint and retain all
weights and their costs, rather than claiming confirmatory selection.
'''
assert marker in s;s=s.replace(marker,'\n'+timeline+marker,1)
s=s.replace(r'\subsection{Five recent acquisition families on fixed price models}',r'\subsection{Five task-adapted recent acquisition families on fixed price models}',1)
s=s.replace(r'''\noindent\textbf{Takeaway.} Estimator choice and simple strong controls remain
material after expanding recent-method coverage.

ACO, SEFA, GDFS, DIME and explanation-ranked AFA each covered three sources,''',r'''\noindent\textbf{Takeaway.} These are five task-adapted comparisons, not
unchanged reproductions of five original methods; they are not audited to the
same level as the original factorial study. Estimator choice and simple strong
controls remain material.

ACO is a clean-room one-query adaptation. SEFA uses official model code inside
a changed task interface; GDFS and DIME use the SEFA repository's comparison
implementations; explanation-ranked AFA uses official network classes with
adapted ranking generation and training. Original code provenance therefore
does not make the complete experiment an official reproduction. The
classification/regression, observation, selection and budget differences are
specified in Appendix~\ref{app:completion_methods}. No claim of reproducing
or defeating the original papers follows from this comparison.

The ACO, SEFA, GDFS, DIME and explanation-ranked AFA adapters each covered three sources,''',1)
s=s.replace('The original factorial identifies adverse effects of its implemented\nfeedback procedure; stronger-search interventions narrow that interpretation.', 'The original factorial identifies adverse effects of its implemented\nweak-search feedback procedure; less-audited stronger-search interventions\nnarrow that interpretation. RPL and recent-family findings remain exploratory\nand have not completed the original four-stage audit chain.',1)
s=s.replace('Strong scorer', 'Strong scorer')
# Ensure final conclusion does not silently elevate the pilot to original audit level.
s=s.replace('The practical implication is to audit public information, recovery', 'The completion-stage interventions and RPL pilot remain below the original\nfour-stage audit level. The practical implication is to audit public information, recovery',1)
p.write_text(s)
(HERE/'changes.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),s.splitlines(True),fromfile='postcompute-v1',tofile='review-boundaries-v1')))
a=re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}',s,re.S).group(1);assert 150<=len(a.split())<=250
(HERE/'revision.json').write_text(json.dumps(dict(status='revised_pending_compile',abstract_words=len(a.split()),source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),old_sha256=hashlib.sha256(before.encode()).hexdigest(),raw_receipts_changed=False,new_training=False),indent=2)+'\n');print('abstract',len(a.split()))
