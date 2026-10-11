# EMC public-state scale refinement: frozen development comparison

Date:2026-10-07. This protocol is fixed after inspecting EMC-v1 outcomes and
before opening new scale-refinement outcomes. It is a retrospective refinement,
not a new confirmatory experiment or a new strategic-conformal theorem. The
full paper goal and unfinished original SAV/CDM studies remain unchanged.

## Motivation and hypotheses

The completed EMC-v1 prototype has weak interval reductions on JUCars and an
average-model median lower-quote/asking-price ratio of0.24036 under honest
reports. A global additive conformal adjustment may spend too much uncertainty
on predictable records. The testable proposal is to learn a positive public
state scale and use it in the existing strategic nonconformity score.

Locally adaptive conformal intervals are established; see [Conformalized
Quantile Regression, NeurIPS2019](https://papers.neurips.cc/paper_files/paper/2019/hash/5103c3584b063c431bd1268e9b5e76fb-Abstract.html)
and [Strategic Conformal Prediction, AISTATS2025](https://proceedings.mlr.press/v258/csillag25a.html).
This is a mechanism-feasibility refinement, not a claim that normalization or
heteroscedastic calibration is novel. A publication requires a defensible
contribution beyond this composition.

## Fixed data and fitting scope

Reuse all9 completed EMC-v1 quantile-estimator pairs, their selected records,
calibration/evaluation membership, public masks, and verified base interval
arrays. Keep SYN/JUCars/MUCars and fitting seeds13/42/2026, all original16
deletion states, primaryalpha0.05 and secondary0.10. No original validation or
test CSV is read. Current evaluation and calibration data have already been
seen; theoretical coverage describes an independently trained fixed family
under exchangeability, not a certified guarantee for this adaptive research
history.

Split the existing20% head cohort by ID hash namespace emc-scale-split-v1:
first floor(n_head/2) rows for the scale learner, remainder for the acquisition
head. This adds a fifth disjoint role without changing the estimator,
calibration or evaluation cohorts. The matched unit-scale controls also refit
their acquisition outputs on exactly the same reduced head cohort; compare
within this new study to isolate scale adjustment, not against the larger
EMC-v1 head as if its fitting allowance were identical.

Scale target: log(max(0.05, abs(y-(l+u)/2))) on every feasible state. Fit a
CatBoost RMSE regressor160iterations/depth6/learning_rate0.05/thread_count1,
with each source record's feasible states weighted to sum to1. Inputs are only
the whitelisted public state features and its raw lower/upper quantiles.
Deployment sigma=max(0.05,exp(clip(scale_prediction,log(0.05),log(4)))) in log
price units. The upper bound4 is a preset numeric stabilization, not tuned on
new outcomes. It is applied identically in calibration and deployment.

## Calibration and four retained families

Scaled score S_i=max_{s feasible} max(0,l(s)-y_i,y_i-u(s))/sigma(s).
q uses the exact ceil((n+1)(1-alpha)) order statistic with an infinite sentinel.
Two raw families are unit-scale strategicCP and scaled strategicCP; two
inherited families intersect each raw family's intervals over all weaker
public reports. Positive sigma need not be disclosure-monotone: applying the
intersection after the state-dependent adjustment ensures nested endpoints.
Never inherit the base endpoints first and then subtract q*sigma(E); that
shortcut may break nesting.

All four families appear in every experiment. Fit one shared4-output query
head per alpha on the new disjoint head rows, predicting signed-span shrink
after replay for each family. Inputs include public state features, its scale,
all four before-query endpoint pairs, and query-field identity. q has been
calibrated but changes neither the base/scale model nor the family. A policy
chosen using q remains a choice within the already calibrated state family;
this is not calibration-label training of the base interval score.

Query head160iterations/depth6/MultiRMSE/learning_rate0.05/thread_count1; same
rows, targets and allowance for all output families. Realized query selection
uses only public scores/missingness. Nonpositive predicted shrink is skipped;
an invalid before-query certificate has zero score. Each listing receives at
most one queried field; failed replay spends a slot and preserves the report.

## Evaluation matrix and evidence

Three unchanged common profiles: honest, EMC-v1 raw-lower maximizer with at
most two deliberately hidden fields, and ID-hashed feasible hiding. Same
profiles across all four methods. Keep capacities0/10/30%, batch100, none at0,
hash random and learned shrink otherwise. Total9cases x2levels x4families
x3profiles x5capacity-policycombinations = **1080cells**. Calibration and
certificate inheritance still cover up to four-field deletion; do not quietly
truncate their closure to the two-hidden reporting profiles.

Save head split memberships/hashes, sigma model and every pre-query sigma,
calibration scores/ranks, all adjusted/inherited endpoints, both acquisition
heads, public scores, reports/replay outcomes, summaries and receipts.
Independent audit must load saved models, reconstruct splits/targets and
order statistics, check family endpoints by brute-force weaker reports,
force public-equivalence cases with different private hidden values, replay
hard-cap allocation, and recompute all arithmetic. Archive/copy proof must
remain separate from original-run test success.

As a preservation check, unit-scale/no-query and unit-scale/hash-query cells
must reproduce EMC-v1 strategicCP/EMC endpoints and execution exactly; learned
query cells may change because matched heads are now refit on fewer records.

## Decision rules, fixed before new outcome inspection

Primary feasibility target: JUCars honest/no-query EMC-scaled median lower
quote/asking-price ratio improves by at least0.10 absolute versus matched
EMC-unit, with a positive paired common-batch median-difference interval.
All3 sources/seeds must retain 95% in their per-model joint-state Wilson
intervals and zero observed disclosure-monotonicity/positive lower-quote
deviation violations. Report coverage shortfalls and extra conservative
coverage, not just interval consistency. Empty certificates and quote reset
are never hidden; reset-on-empty is prohibited because it breaks incentives.

Also report honest bias/MAE, mean widths, invalid rates, lower-bound
overpricing, actual query fractions/failures, shared-profile effects and all
negative outcomes. Paired intervals average fitting-seed effects first and
resample common batches1000times; median effects resample the same batch
records for each seed then average paired median differences. They condition
on fixed fitted models and are unadjusted; no training-population uncertainty
or real-market welfare claim.

If the practical target fails, do not redefine the original810-cell results
or claim the full method is ready for a Q3 paper. Record the failure and decide
whether the direction merits further work; no unbounded hyperparameter search
on the same seen evaluation labels.
