"""Apply evidence-bounded review revisions to the current manuscript once."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent
P=ROOT/'paper/innovation-addendum-v1.tex'

def main():
    source=P.read_text()
    if 'tab:ten_seed_mechanism' in source:return
    shutil.copy2(P,OUT/'before-prose-revision.tex')
    def replace(old,new):
        nonlocal source
        assert source.count(old)==1,old[:80]
        source=source.replace(old,new)
    replace('A separate three-seed, 90-cell crossing',
      'On the real sources, most improvement is already present without queries, limiting a recovery-mechanism interpretation. A separate three-seed, 90-cell crossing')
    replace('The supported practice is to diagnose recovery paths and evaluate incentive gains jointly with prediction and verification costs before deploying feedback or regularization.',
      'These retrospective fixed-cohort results support a proof of concept for evaluating concealment gains jointly with prediction and verification costs.')
    replace('Naturally missing fields cannot be concealed or recovered.',
      'Fields unavailable in the source record are stipulated to be unrecoverable in the simulation; their real missingness causes are not identified. They cannot be additionally concealed. Supplement S1 reports the complete sample flow, field mappings, missingness and synthetic generator.')
    replace('It motivates a testable training intervention, not a general incentive guarantee.',
      'Because $g_{i,\\theta}(H_i)=0$, an edge ending at honesty has zero penalty regardless of its starting gain. The constraint acts on intermediate partial-recovery states. It motivates a recovery-graph-inspired regularizer, not a general incentive guarantee.')
    replace('Figure~\\ref{fig:rpl_budget} includes zero queries, separating estimator changes\nfrom verification gains. Greater capacity can lower inflation while increasing\ncharged failed queries.',
      r'''Figure~\ref{fig:rpl_budget} includes zero queries. The paired improvement
at zero versus 10\% capacity is .004276/.006268 on synthetic,
.003249/.003306 on JUCars and .001527/.001573 on MUCars. Thus zero-query
improvements are 98.3\% and 97.1\% of the real-source 10\% improvements;
these ratios are descriptive, not causal shares. The paired budget
interactions are .001992, .000057 and .000046. Post-hoc marginal crossed
bootstrap intervals include zero for both real sources (Supplement S2).
The real-source results establish an estimator improvement at the tested
gap weight, without identifying an additional verification mechanism.

\paragraph{Recovery geometry and quote shifts.}
Table~\ref{tab:ten_seed_mechanism} extends the recovery-edge diagnostic to
all ten fitting seeds. Positive-gain violations decrease on average, while
raw quote-raising edge rates rise slightly on synthetic and JUCars. These
are different targets. On MUCars, honest signed log bias rises from .029095
to .034913 and attacked bias from .035701 to .039946, despite lower MAE;
their paired bias-change intervals include zero. A moving honest quote can
change relative inflation. Fixed-report $E/R/C$ decompositions and
endogenously reselected reports are separately reported in Supplement S3;
they do not uniquely identify a causal mediator.

\begin{table}[htbp]\centering\small
\caption{Ten-seed recovery geometry at $\beta=.5$, before/after $\lambda=1$.
Rates and positive increment means use all legal concealed-field recovery
edges, including zero increments; units are log price.}
\label{tab:ten_seed_mechanism}
\begin{tabular}{lrr}\toprule
Source & Positive-gain violation (\%) & Mean positive increment\\\midrule
Synthetic & 15.79/5.03 & .001648/.000663\\
JUCars & 7.08/4.76 & .001498/.001032\\
MUCars & 5.27/2.60 & .000743/.000393\\
\bottomrule\end{tabular}
\end{table}''')
    replace('inflation alone therefore does not determine a deployment choice.',
      'inflation alone therefore does not determine a deployment choice.') if 'inflation alone therefore does not determine a deployment choice.' in source else None
    replace('improvement alone therefore does not determine a deployment choice.',
      'improvement alone therefore does not determine a deployment choice. For JUCars at $\\lambda=1$, actual queries cover 10\\% of listings: 6.17\\% of all listings have failed attempts, or 61.7\\% of attempted queries; successful queries cover 3.83\\%.')
    replace('equilibrium.\n\n\\begin{table}',
      'equilibrium. Replacing primary synthetic inflation by the fixed-peer unilateral envelope changes its paired reduction from .006267693 to .006266569, a difference of $1.125\\times10^{-6}$; this cannot explain the mean effect.\n\n\\begin{table}')
    replace('Its zero-query\ncomponent shows that part of the gain comes from changing the estimator.',
      'Its zero-query\ncomponent accounts descriptively for nearly all real-source improvement.\nThe evidence supports recovery-graph-inspired regularization; it does not\nidentify recovery as the main causal source of that improvement.')
    replace('which is not numerical equivalence.',
      'which is not numerical equivalence. At 10\\% capacity, the local/external paired inflation reductions are 53.97/57.54\\%, but maximum residual regret for $\\lambda=1$ changes from .000204 to .021973. Supplement S5 reports all six cells under the original failed tolerance verdict.')
    replace('Software and aggregate evidence are archived at\n\\href{https://doi.org/10.5281/zenodo.23447567}{DOI 10.5281/zenodo.23447567}.',
      'Software and aggregate evidence through source commit \\texttt{89ad56e} are archived at\n\\href{https://doi.org/10.5281/zenodo.23447567}{DOI 10.5281/zenodo.23447567}.\nThe later review diagnostics and stronger-gap comparison are subsequent repository evidence, not additions to that immutable ZIP. Supplement S6 maps versions and artifacts.')
    replace('Contributions, funding and competing-interest facts require\nauthor confirmation before submission and are not inferred.',
      'Yuchen Tang drafted the manuscript. Fengqin You provided supervision as advisor, and Junxiang Gu provided guidance on manuscript writing.')
    # Clarify metric interpretation without implying transaction-price effects.
    replace('It differs from the realized-positive quantity',
      'A relative reduction of this metric is neither the same percentage price reduction nor observed overpayment avoided. It differs from the realized-positive quantity')
    P.write_text(source)

if __name__=='__main__':main()
