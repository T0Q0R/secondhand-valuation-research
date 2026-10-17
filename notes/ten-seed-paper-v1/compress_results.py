"""Relocate supporting results without excluding numerical evidence."""
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[2]
p=ROOT/'paper/innovation-addendum-v1.tex';s=p.read_text()
a=s.index(r'\section{Results}');b=s.index('\\clearpage\n\\section{Discussion}',a)
r=s[a:b];ms=list(re.finditer(r'\\subsection\{([^}]+)\}',r))
blocks={m.group(1):r[m.start():ms[i+1].start() if i+1<len(ms) else len(r)] for i,m in enumerate(ms)}
archive=[]
titles=['Matched factorial effects','Strong controls and the original candidate comparison',
    'Allocation changes on frozen models','Continuous effects and decision-threshold sensitivity',
    'Positive costs change the conditional feedback ranking','Full-validation evaluation coverage']
for title in titles:
    v=blocks[title].replace(r'\label{sec:factorial_results}',r'\label{app:factorial_details}')
    archive.append(v.replace(r'\label{sec:full_validation}',r'\label{app:fullvalidation_details}'))
oldcap=blocks['Recomputed cap responses and multiobjective trade-offs']
fm=re.search(r'\\begin\{figure\}.*?\\end\{figure\}',oldcap,re.S);assert fm
capfig=fm.group();archive.append(oldcap[:fm.start()]+oldcap[fm.end():])
history=r'''\subsection{Historical feedback and allocation controls}\label{sec:factorial_results}
The original factorial had adverse mean inflation directions in all 36
primary feedback contrasts. Under post-hoc exploratory simultaneous families,
31 adverse intervals remained for the inflation-only family, 27 for three
co-primary outcomes, and 20 for all 1,536 primary metric contrasts. No family
established that every feedback contrast was harmful. These results describe
the original weak-search implementation; the stronger-search intervention
above changes that interpretation. Appendix~\ref{app:additional_controls}
retains all original intervals, interactions and counts.

The strong-control comparisons also restrict claims for the original SAV
candidate. Ordinary-benefit and acquisition-conditioned controls had lower
inflation in synthetic and JUCars comparisons, and the original ten-seed SAV
comparison did not show a universal advantage over static robust valuation.
These original-protocol comparisons are distinct from the new same-gap RPL
contrasts. Likewise, score-minimax allocation passed the descriptive joint
gate in only two of eighteen primary contrasts, while ten worsened inflation.
An advantageous interaction or a more complex allocator therefore does not
replace a matched no-feedback or simple-acquisition control. Complete
three-source evidence is retained in Appendices~\ref{app:original} and
\ref{app:historical_displays}.

'''
cap=r'''\subsection{History-cap outcomes and deployment costs}
The history cap's fixed-peer theorem does not imply a better joint outcome
after sellers recompute their reports. The 432-cell recomputation kept the
original response-search budget, public scores and rule weights. Its
multiobjective result is consequential: attacked MAE increased in 94 cells
and failed-query rates in 145, despite unchanged honest MAE. Figure~\ref{fig:cap_tradeoffs}
shows those costs alongside inflation reductions. Complete per-rule counts
and conditional intervals are in Appendix~\ref{app:historical_displays}.

Thirty-three capped cells retained at least one nonconverged batch and maximum
remaining regret was 0.204423 log units. No capped result is therefore
described as a certified market equilibrium. The descriptive 10\% inflation /
5\% honest-error gate does not constrain attacked error or failed queries;
threshold sensitivity cannot turn a single-metric improvement into Pareto
dominance. These costs also motivate the final-record alternative and its
natural-missingness boundary in Section~\ref{sec:recovery}.

'''+capfig+'\n\n'
boundary=r'''\subsection{Applicability beyond the zero-cost capped design}\label{sec:full_validation}
Positive concealment costs changed some rankings through deterrence.
In the synthetic top-$B$ subset, stipulated costs near 0.02 sharply reduced
concealment and moved outcomes toward ordinary valuation; feedback no longer
worsened the mean inflation in the high-cost specifications. Yet over 94\%
of attempted queries failed in the uniform-cost subset, residual concealment
remained positive, and the real-source directions stayed adverse. This
supports a conditional regime change rather than a general feedback remedy.
The full 108-cell cost design and net-deviation bounds remain in
Appendices~\ref{app:additional_controls} and~\ref{app:mechanism_diagnostics}.

A separate frozen-original-model check removed the real-source evaluation
caps, covering all 1,374 JUCars and 10,672 MUCars validation records. All 24
feedback point directions remained adverse. The two MUCars masking/suppression
intervals still crossed zero, with fitting-seed variability dominating the
uncapped conditional variance. The cohort and record-count weighting both
changed, so this is not a pure sample-size experiment or evidence of zero
effect. It does not extend the RPL evaluation population: the RPL ten-seed
study retains its fixed 1,000 listings per source. Complete uncapped counts,
weighting and variance decompositions are in
Appendices~\ref{app:additional_controls} and~\ref{app:mechanism_diagnostics}.

'''
keep=['Recovery failures in the learned four-field class',
      'Recovery-path regularization: improvement and costs',
      'Five task-adapted recent acquisition families on fixed price models',
      'Controlled components and a search-strength intervention']
new=r'\section{Results}\label{sec:results}'+'\n'+''.join(blocks[t] for t in keep)+history+cap+boundary
s=s[:a]+new+s[b:]
pos=s.index(r'\begin{thebibliography}')
extra=r'\section{Additional historical control analyses}\label{app:additional_controls}'+'\n'
extra+='The following analyses retain the full original protocols and numerical evidence summarized in the main text. Their original fitting-seed and uncertainty scopes are unchanged.\n\n'+'\n\n'.join(archive)
s=s[:pos]+extra+'\n'+s[pos:]
labels=re.findall(r'\\label\{([^}]+)\}',s);assert len(labels)==len(set(labels))
refs=re.findall(r'\\(?:ref|eqref)\{([^}]+)\}',s);assert set(refs)<=set(labels),set(refs)-set(labels)
assert s.split(r'\appendix')[0].count(r'\begin{figure}')==8
p.write_text(s)
j=ROOT/'notes/ten-seed-paper-v1/revision.json';d=json.loads(j.read_text())
d['historical_results_relocated_with_no_numeric_exclusion']=titles+['Full cap-response detail']
def prose_words(v):return len(re.findall(r'\b\w+\b',re.sub(r'\\begin\{figure\}.*?\\end\{figure\}','',v,flags=re.S)))
d['main_results_words_before_compression']=prose_words(r)
d['main_results_words_after_compression']=prose_words(new)
j.write_text(json.dumps(d,indent=2)+'\n')
print('Results prose words',prose_words(r),'->',prose_words(new))
