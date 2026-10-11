# Compact marginal OQBO: pre-computation contract

2026-10-07. Candidate structural improvement to the finite oracle. No claim
that marginal polytopes, LP or systematic sampling are new.

Assumptions: fixed finite observable report classes; complete declared
counterfactual rows; nonadaptive allocation; itemwise utility after replay;
at most one field queried per item; each query costs one unit, including
failure. A realized seller quote depends only on its own chosen field or no
query. The history cap also satisfies this locality. Correlated quotes,
adaptive trees, nonuniform costs and joint chance constraints are excluded.

For each public class o, use field marginals y[o,i,f]>=0, summing to at most1
per item and at most integerB per batch; ineligible fields have zero marginal.
Every deviation is an affine function of these marginals. Any full allocation
lottery induces feasible marginals. Conversely let p_i=sum_f y_if. Systematic
sampling with a private U selects at mostB items with inclusion marginalp_i;
conditional on selection draw fieldf with probability y_if/p_i. This realizes
all field marginals under hard capacity on every draw. Therefore the compact
LP has the SAME finite-universe optimal value as complete-allocation OQBO.

The bound concerns expected per-seller utility and linear aggregate criteria.
It does not preserve arbitrary joint-event probabilities or certify unseen
types. It removes allocation enumeration, not report/world enumeration.
Variables scale as O(number of public classes * items * fields), rather than
the number of complete query allocations. Public equivalence constraints are
retained, and source labels are never added to deployment keys.

Execute: (1) all32 original OQBO cases; (2)24 predetermined affine algebraic
fixtures with2--6 items,1--3 fields,1--3 public classes, variable budgets and
signed row coefficients; independently compare full enumeration and compact
LP; (3) one larger100-item/4-field/8-class/96-row/B10 fixture, with compact
primal/dual certificate and2,000 draws per class. Algebraic fixtures are not
vehicle market results. Count the infeasible-to-enumerate full action space
combinatorially; do not claim a measured speedup over a solver never run.

Represent sampler probabilities as rational numbers converted from saved LP
floats, removing tiny negative mass and scaling down any item/budget numerical
excess. Record total repair and recheck the repaired bound. Reject substantive
violations. Independently verify the continuous-U interval lottery exactly,
including marginal identities and hard capacity, without enumerating field
combination products. Numerical private draws stress the implementation.
Save all matrices, input/output hashes, both small LP results and certificates.
