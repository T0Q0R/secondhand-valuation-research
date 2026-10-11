# Revised paper positioning — working prose,2026-10-07

The frozen generation36 PDFs are retained. The text below is a new candidate
rewrite; it has not yet been promoted through the existing source/PDF receipt
pipeline. The four paragraphs follow the user's requested rhetorical order.

## Title

**Budgeted Verification under Strategic Missingness: Audited Effects and Information Limits**

Alternative: **When Does Suppression-Aware Valuation Help? An Audited Study of Budgeted Verification**

## Abstract

Predictive valuation can reward sellers who withhold unfavorable attributes.
Natural source missingness can produce the same public report, while failed
verification still consumes a shared batch budget.

We audit suppression-aware valuation and finite mixtures of verification
rules using nested fitting, paired counterfactual allocation and independent
replay. We introduce an observable-report budget oracle to separate
candidate-family restrictions from information constraints in an explicitly
finite constructed market.

Results are heterogeneous. At the largest training cap, tuned SAV-Val reduces
positive log-quote inflation by20.41% on MUCars relative to ordinary-benefit
robust pricing, but increases it by30.09% and27.09% on synthetic and JUCars
cohorts. CDM-Val does not consistently improve on a simple risk rule. A
constructed missingness-alias family yields a tight precision–incentive
frontier and a strict gap between a global rule mixture and a realizable
public-report-conditioned oracle.

The contributions are audited evidence, negative results and bounded
diagnostic certificates. The source study uses historical asking prices,
stipulated responses and three training seeds; its intervals are conditional
on fitted models. The oracle is not a market-performance or unseen-type
guarantee, and no universal method advantage is established.

## Contribution paragraph

Our first contribution is an auditable protocol that keeps natural absence
and withholding observationally indistinguishable to deployed rules, charges
failed replay, and reallocates the whole batch on both sides of each
counterfactual deviation. Our second contribution is complete source-specific
evidence showing when suppression-aware valuation helps and when strong
references remain preferable. Our candidate theoretical contribution is a
finite observable-report oracle with realizable hard-budget actions and
lower-bound witnesses, together with a tight precision–incentive frontier
for a stated missingness-alias family. This last contribution must be
positioned against existing automated mechanism design and auditing theory;
LP, randomization and minimax coverage themselves are established methods.

## Claim–evidence layout for the rewritten main results

|Claim|Current evidence|Status and limitation|
|---|---|---|
|Suppression-aware valuation is not uniformly stronger|Full972/324 extensions; tuned largest-cap effects: MUCars−20.41% inflation, synthetic+30.09%, JUCars+27.09% vs ordinary-BEN|Supported retrospective heterogeneity; do not infer market causes from source identity|
|CDM's finite calibration optimum does not imply a strong unseen-policy advantage|Full fixed-estimator1512-cell study and common-profile diagnostics; no consistent risk-rule advantage|Supported negative finding; stored rows/types/peer profiles delimit guarantees|
|A method gap can be caused by its policy family|OQBO32 cases; constructed primary72/17 vs global-library72/13, independently audited|Supported constructed counterexample, not source empirical attribution|
|Accurate natural-missing quotes can force residual concealment gain|Conditional tight bound and rational attainable construction;448 finite world/report checks|Theoretical within uniform-error, verification-neutral, alias-world assumptions; theorem novelty review remains|
|MUCars gain is due to a particular factor or mechanism|Existing zero-query and missingness diagnostics only|Not established; matched factorial and training-uncertainty extension are required|

Retain the complete numerical tables in supplementary material. Main tables
should use signed effects, intervals, practical thresholds and support status;
do not discard adverse rows to simplify presentation.

## Practical guidance — bounded draft

Takeaway: choose a valuation/acquisition combination using matched local
evidence, an honest-error limit and a clearly defined verification process.
The present results justify testing suppression-aware valuation under
MUCars-like recorded-data conditions; they do not identify a deployable
criterion that certifies a new market as Mucars-like. Risk ordering remains
a required strong reference. CDM can be evaluated as finite heuristic
calibration and a tail-risk diagnostic, with its calibration coverage shown.
Where verified honest precision and available query capacity imply a large
residual incentive floor, increasing model complexity alone is not a remedy.
The oracle's observation-consistent floor applies only to its stated
counterfactual universe; avoid deploying its privileged diagnostic version.
