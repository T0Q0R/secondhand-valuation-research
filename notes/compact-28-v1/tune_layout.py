from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[2]
p=ROOT/'paper/innovation-addendum-v1.tex';s=p.read_text()
def getfig(label):
 for m in re.finditer(r'\\begin\{figure\}.*?\\end\{figure\}',s,re.S):
  if r'\label{'+label+'}' in m.group():return m.group()
 raise KeyError(label)
def interior(v):return re.sub(r'^\\begin\{figure\}(?:\[[^\]]+\])?','',v).removesuffix(r'\end{figure}')
f1=getfig('fig:rpl_primary');fg=getfig('fig:rpl_gap');s=s.replace(fg,'');s=s.replace(f1,r'\begin{figure}[p]'+interior(f1)+'\n'+r'\vspace{.5em}'+'\n'+interior(fg)+r'\end{figure}')
# First mention of matched component figure precedes the trade-off and budget figures.
a=s.index(r'\paragraph{Predictive and verification costs.}');b=s.index(r'\paragraph{Budget and loss-component boundaries.}');c=s.index(r'\paragraph{Finite-response boundary.}')
cost=s[a:b];gap=s[b:c]
gap=gap.replace('Figure~\\ref{fig:rpl_budget} includes zero queries, so estimator changes remain\nseparate from gains due to verification. Greater capacity can lower inflation\nwhile increasing charged failed queries. ','')
gap=gap.replace('\\paragraph{Budget and loss-component boundaries.}','\\paragraph{Loss-component boundary.}')
cost += r'''\paragraph{Budget boundary.}
Figure~\ref{fig:rpl_budget} includes zero queries, separating estimator changes
from verification gains. Greater capacity can lower inflation while increasing
charged failed queries.

'''
s=s[:a]+gap+cost+s[c:]
# Pair the two compact three-panel appendix figures at full text width.
fa=getfig('fig:completion_ablation');fs=getfig('fig:rpl_seeds');s=s.replace(fs,'');s=s.replace(fa,r'\begin{figure}[p]'+interior(fa)+'\n'+r'\vspace{.5em}'+'\n'+interior(fs)+r'\end{figure}')
# Citation order matches display order: switches, seed heterogeneity, parameter scans.
a=s.index('Core scans vary gap weight');b=s.index(r'\begin{figure}',a)
old=s[a:b];u=old.index('Figure~\\ref{fig:rpl_seeds}');s=s[:a]+old[u:]+old[:u]+s[b:]
s=s.replace('using observed query\ncoordinates and at least $k=25$ neighbors','using observed query\ncoordinates and fixed $k=25$ neighbors')
s=s.replace(r'\texttt{notes/review-mechanism-v1/}',r'\path{notes/revision-mechanisms-v3/}')
s=re.sub(r'\\texttt\{((?:notes|paper)/[^}]+)\}',r'\\path{\1}',s)
s=s.replace(r'\begin{thebibliography}{99}',r'\begingroup\small'+'\n'+r'\begin{thebibliography}{99}').replace(r'\end{thebibliography}',r'\end{thebibliography}'+'\n'+r'\endgroup')
p.write_text(s)
