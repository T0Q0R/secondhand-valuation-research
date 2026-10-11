# CDM-Val full-field source-development contract v1

Frozen before opening any CDM source performance outcomes. Created 2026-10-05.
This is retrospective algorithm development, not confirmation or a completed
Q3 paper. The earlier three-item finite demonstration is separate evidence.

## Inputs and independence

Reuse the immutable nested-v2 data loader, source caps, four optional fields,
maximum two hidden fields, complete original covariates, three training seeds,
100-record shared batches and six capacity fractions 0/.01/.05/.1/.2/.3.
The primary capacity remains .1. Use both fixed masking and robust-no-feedback
price estimators from each parent deployment fit. These price estimators used
only the estimator 70% for supervised fitting; no feedback variants are used.
Parent saved action heads are discarded for this experiment.

Recover the exact parent estimator/guidance ID split. Split the unused 30%
guidance records into equal action-head and probability-calibration portions
using a fixed ID hash namespace `cdm-head-calibration-v1`. Fit a fresh joint
action head (parent 160-tree parameters) on the first half, using only the fixed
price model and that half's labels. Fit mixture weights on the second half.
No evaluation ID or label enters either fit. Encoder/model covariates and
parameters remain those of the parent's estimator split. This first experiment
has disjoint estimator/head/probability rows, not a complete outer cross-fit CDM
pipeline. An outer replication is required before stronger final-paper claims.

## Fixed policy bank and public inputs

12 complete deterministic functions: no query; suppression, ordinary benefit,
fixed-field risk head; each of the four constant field-only rules; four fixed
hash-priority rules. Hash scores use public immutable listing keys, namespace
`cdm-public-hash-{k}-field-{a}`. A hidden/naturally absent field with identical
public values must receive the same score. Public absence alone determines
eligibility. All rules use the parent positive-merit, single-query top-B
allocator and fixed row-order tie convention. Each execution, including each
counterfactual, obeys floor(budget*batch_n). Failed reveals consume capacity.
Original values/availability are environment replay information only.

## Payoffs and probability fit

Risk model: seller maximizes expected log quotation minus κ*newly-hidden count,
κ=0 in this primary development. Seller knows functions and probabilities but
cannot observe or change reports after the private batch draw. This is not
maximization of expected currency quotation.

For every probability-calibration batch use five fixed peer profiles: all
honest; no-query maximal quote; a fixed random valid profile (seed 603);
suppression-rule response and benefit-rule response. The latter use four starts
and twenty sweeps, same search as evaluation. For every profile, listing and
legal report, recalculate that listing's final quote under each rule, and its
counterfactual truthful quote against the same peer reports. Include signed
differences; apply positive truncation only after mixing through t>=0. Preserve
full payoff matrices, row locators and generated profiles. These five sampled
profiles are not all possible combinations of peer reports.

Minimize t subject to D alpha<=t, alpha>=0, sum alpha=1, t>=0, and an honest
currency-MAE cap of 1.01 times the no-query reference. Exact violated-row
separation over the stored finite matrix uses tolerance 1e-9. Preserve full
history and strongest rows. No strategy-column learning in this version.

**Honest-error constraint is inactive as a discriminator here:** all policy
columns use the same estimator, and an honestly reported record has no withheld
recorded value to recover. Originally absent values remain absent. Therefore
all columns have identical honest MAE; write the observed variation flag and
do not credit the error cap as an empirical algorithm improvement. A future
multi-estimator/physical-reveal extension needs its own contract and evidence.

## Evaluation and fair controls

Retain all 12 deterministic rules, uniform mixture and optimized CDM mixture.
Record the best finite-calibration deterministic rule in fit metadata, but do
not select a rule from evaluation performance. Seller response uses mixture
expectation over all rules, four starts/twenty sweeps, fixed peers, and explicit
remaining exact unilateral regret. Keep ties, detect cycles; no global or
unique-equilibrium claim. At each returned profile, independently reallocate
all rules for every unilateral candidate in the first evaluation batch.

Report both max(E[log quote]-honest,0) and E[max(log quote-honest,0)]. They are
different. Attack MAE is E[|currency quote-target|], not MAE of exponentiated
expected log quote. Include normal/attack bias, expected and realized query
failure, concealment, regret, unilateral envelope, convergence and draw variance.
Twenty private draws per batch use predetermined common uniforms, independently
of seller states. Each draw selects one complete rule for the batch; reports
stay fixed between draws. Preserve every rule's final states/actions/quotes
and each draw's index. No fieldwise independent Bernoulli sampling.

## Generation and scope

Outputs must be fresh, source/config/model/head/cohort hashes are saved. Require
completed parent pairs at startup; `--partial` freezes those pairs explicitly
and does not acquire more as the parent finishes. A partial run cannot be called
the full nine-pair study. Software smoke uses synthetic seed 13 only, 64 head
and 64 probability rows, 64 evaluation rows, batch 32, budgets 0/.1; its outcomes
are excluded from source-performance claims. The normal full cap remains 5000
training and 1000 evaluation where sources permit. All source/seed/budget
results remain visible, including failure or collapse to one rule/no audit.

Required after execution: independent source/cohort/score/matrix/LP/allocator/
expectation/draw audits; paired seed-averaged batch intervals; whole-study outer
cross-fit and sensitivity/efficiency evidence; verified novelty comparison;
complete paper and rendered QA. A finite LP certificate never proves unseen
market incentives, strategic ID changes, coalitions or real inspection accuracy.
