from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[2];p=ROOT/'paper/innovation-addendum-v1.tex';s=p.read_text()
# Keep empirical denominators; no new normalization is inferred during editing.
s=s.replace('Its masked-predictor/ranking/trajectory stages use\n250/200/16 epochs, two recoveries and a fixed history-free initial marker;', 'Its masked prediction, ranking and trajectory stages use 250, 200 and 16\nepochs, respectively, with two recoveries and a fixed initial marker;')
# The abstract and subsection opening already state these conclusions.
s=re.sub(r'\\noindent\\textbf\{Takeaway\.\}.*?\n\n','',s,flags=re.S)
# Main RPL scope: keep controls, seed counts and confidence limits once.
a=s.index('The ten-seed extension compared');b=s.index(r'\paragraph{Inflation improvement and uncertainty.}',a)
s=s[:a]+r'''RPL compares $\lambda=0,.1,.5,1$ at $\beta=.5$ and
$\lambda=0,.5$ at $\beta=0$, across capacities $0,.1,.3$ with the same
no-feedback reset schedule. Each branch uses its same-gap zero-path control.
The \href{https://github.com/T0Q0R/secondhand-valuation-research/commit/6643cbe3266f2c1548d987c2bb53e366e19ad3ef}{declared development grid}
predates formal evaluation; it is not independent preregistration or proof
that $\lambda=1$ was a prespecified headline. Weight .5 matches the existing
gap scale; neither .5 nor 1 is claimed optimal.

'''+s[b:]
a=s.index(r'\paragraph{Loss-component boundary.}');b=s.index(r'\paragraph{Predictive and verification costs.}',a)
s=s[:a]+r'''\paragraph{Loss-component boundary.}
The matched path/gap comparison (Figure~\ref{fig:rpl_gap}) distinguishes
path regularization from the existing gap term at the tested weights.
Appendix~\ref{app:extended} retains the original component ablation and
three-seed recovery-edge pilot; neither is relabeled as ten-seed evidence.

'''+s[b:]
# Tight contextual proof: all values, construction and stronger comparator survive.
a=s.index(r'\section{Contextual policy-library witnesses}');b=s.index(r'\section{Mechanism and uncertainty boundaries}',a)
s=s[:a]+r'''\section{Contextual policy-library witnesses}\label{app:library}
Take $n>B\ge1$, a core $C$ of size $B$, and public active contexts
$j\in\{B+1,\ldots,n\}$. Gaps in linear toy units are 2 for core items,
1 for $j$, and $\epsilon=1/(B+2)$ for other items, using honest-exact
missingness-alias worlds. The library includes every context-insensitive
priority order and exact-gap risk ordering, but shares one mixing vector.
Each priority chooses a fixed $B$-subset; risk always chooses the core.

\begin{proposition}[Global-mixture separation]
The optimal values are
\[
 T_{\rm global}=\frac{2(n-B)}{2n-B},\qquad
 T_{\rm context}=\frac{2}{B+2}.
\]
For $n=B^2+B$, their ratio $B(B+2)/(2B+1)$ is unbounded in $B$.
\end{proposition}
\begin{proof}
A global value $t$ requires $2(1-p_i)\le t$ on core items and
$1-p_i\le t$ on every potentially active item. Summing yields
$B\ge n-t(B/2+n-B)$. Core marginals $1-T_{\rm global}/2$ and other
marginals $1-T_{\rm global}$ attain equality through fixed-priority lotteries.
For one context, $B\ge B+1-t(B/2+1)$; core marginals $(B+1)/(B+2)$,
active marginal $B/(B+2)$ and others zero attain its bound, with
$\epsilon<T_{\rm context}$. Proposition~\ref{prop:compact} implements both.
\end{proof}
A stronger fixed library closes the gap: one rule queries the core and each
of $B$ others replaces one core item by the active item. Fixed weights
$2/(B+2)$ on the core rule and $1/(B+2)$ on each replacement yield exactly
these contextual marginals. Thus the separation concerns rule information,
not dynamic weights or the intrinsic necessity of an LP solver.

Exact witnesses cover 26 $(n,B)$ cases, 257,274 context--item losses and
15,922 context--rule allocations; sixteen small cases match independent
complete-subset LPs. At $B=20,n=420$, the ratio is $440/41$. Freezing the
active item or using uniform rule weights fails the optimum check. These
constructed results neither explain real-source CDM loss nor guarantee
unseen-context behavior.

'''+s[b:]
# The main protocol already enumerates stages and the table records their scope.
a=s.index('The latter count comprises');b=s.index('The checks reconstruct fitting roles',a)
s=s[:a]+'''Stage counts are 162 pilot RPL, 90 search, 432 SEFA/GDFS/DIME/explanation,
144 ACO and 378 additional RPL cells. The 540-cell RPL audit overlaps the
pilot; remaining support cells are not upgraded.

'''+s[b:]
# Readable compact repository paths, avoiding justified-table stretching.
s=s.replace(r'\begin{tabular}{p{.27\textwidth}p{.65\textwidth}}',r'\begin{tabular}{>{\raggedright\arraybackslash}p{.27\textwidth}>{\raggedright\arraybackslash}p{.65\textwidth}}')
p.write_text(s)
