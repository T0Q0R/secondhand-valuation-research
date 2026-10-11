# OQBO finite audit contract — 2026-10-07

This is a new theoretical/algorithmic investigation motivated by the complete
SAV/CDM negative results. The existing manuscripts, empirical outcomes and
frozen packages are not overwritten. No newly observed source result is
confirmatory. Novelty of the specific contribution remains under literature
review; LP, minimax, state-conditioned randomization and systematic sampling
are established tools.

## Research claim to test

An observable-report quotient oracle can distinguish a restricted policy
family's limitation from an unavoidable information/budget bottleneck. Unlike
one global mixture over a fixed rule library, its decision variables are
probabilities of complete feasible actions at each public report. Identical
public inputs share variables across every compatible latent source world.
It provides a finite-family optimal value and a dual witness, not an unseen
type guarantee or a new full-information deployment policy.

## Constructed analytical market

Three persistent public IDs; one optional field per item; non-adaptive query
budget B in {0,1,2,3}; continuous toy quote/utility units, not currency or
log-price outcomes from the vehicle datasets. Each item is either naturally
missing H (honest target100), or has one recorded low-value indicator L
(honest target100-g_i). At most one L exists per batch. L may disclose1 or
withhold; H can only reportmissing. Thus all-H and each hidden-L world have
exactly the same public report, including IDs and mode. A query of H fails
and consumes one unit; a query of hidden L restores1. Pricing is a fixed,
verification-neutral function of the final own public record. No penalties,
source-availability labels, hidden target or private world ID reach selection.

Two immutable, publicly observed modes have g=(9,8,1) and
g=(1,72/13,18). These are deliberately constructed theoretical witnesses,
not sampled market observations. The family is chosen before computation to
test whether public-state conditioning can strictly improve on a global
mixture of six static priorities, a risk ranking and no query.

Accuracy allowance eta in {0,1/4,1/2,1,2,3,4,6}. The theorem uses a uniform
per-report absolute-error bound, stronger than an average MAE constraint.
For item i set e_i=min(eta,g_i/2), q_missing=100-e_i,
q_observed=100-g_i+e_i. Effective leverage a_i=(g_i-2eta)_+.
This prices every honest world with maximum error <=eta. Do not claim that
the resulting exact frontier is also the optimum under an MAE-only condition.

## Analytic hypotheses

For each mode the observable minimax value is the minimum of
max_i a_i(1-p_i), subject to0<=p_i<=1, sum p_i<=B. When0<B<m positive
leverages, the unique positive water level t satisfies
sum_i(1-t/a_i)_+=B. All-mode optimum is max of the mode values. The
lower bound follows from aliases and actual hard capacity; a public
systematic subset lottery realizes the marginals with capacity on every draw.
For B=0 use max a_i; B>=m gives0. Deterministic optimum is the (B+1)-th
largest leverage, achieved by the simple risk rule in this stylized class.

At eta0/B1 the analytical target is72/17, and the restricted global mixture
is predicted to be strictly worse. A privileged recoverability oracle is
expected to achieve0 at B>=1, since there is at most one recoverable field.
That oracle is an explicitly nondeployable diagnostic. It is not a baseline
allowed the same information. A fixed-library LP is a baseline in the same
public-information class.

## Verification and denial cases

Run all32 allowance/capacity cases and retain every outcome. Enumerate all
latent worlds and legal reports, all complete feasible query subsets and
all unilateral deviations. Solve the quotient LP and global-library LP.
Preserve matrices, keys, solutions, solver duals and exact rational analytic
construction. No expectation may move outside a maximum or positive part.

An independent script reconstructs public keys/actions/payoffs without
importing the solver implementation, checks primal and dual feasibility,
all hard-budget draws, exact systematic marginals, all aliases, failed
queries, honest error and the rational optimum. It must reject a kernel
overusing capacity, a changed public key, and a changed payoff coefficient.
Numerical LP certificates use declared1e-8 tolerance; exact rational
construction checks do not use this tolerance. No toy result is merged into
the existing source empirical tables.

## Subsequent paper work

Preserve the audit/negative-results positioning. Separate factor effects
using identical estimator, head, feedback and allocation. The source study
will need10 training seeds, source/capacity interactions and training+batch
resampling; those are new work, not already satisfied by3-seed conditional
intervals. Use the oracle only on explicitly finite counterfactual families,
with a public fallback outside them; report coverage and oracle-runtime
limits. Full-field continuous-world guarantees are out of scope. Public
release packages can be prepared locally; author/license/release facts still
must be real before external publication.
