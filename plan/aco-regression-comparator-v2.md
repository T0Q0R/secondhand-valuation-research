# ACO-1 regression/group/hard-cap adaptation

Frozen before execution, 2026-10-05. This is a clean-room adaptation of
Valancius, Lennon and Oliva's acquisition-conditioned expected-loss idea
(ICML 2024, https://proceedings.mlr.press/v235/valancius24a.html).
It is not an unchanged execution of the author's classification rollout and
does not import or redistribute that code.

## Fixed construction

Use the parent's capped training/evaluation memberships, saved masked
CatBoost predictor and saved robust/no-feedback predictor. Their estimator
fits do not use guidance outcomes. Use the exact parent inner-guidance 30%
of allowed training records as the conditional neighbor bank; never use
validation records/outcomes as neighbors. Retain every price input and all
four optional original-field groups. Price encoders/models remain frozen.

Precompute each bank record's squared log-price error for all sixteen public
optional-field missingness patterns. Masked bank inputs preserve original
natural missingness. Revealing an unavailable bank field leaves its input
and loss unchanged, thereby contributing zero estimated acquisition benefit.
The neighbor's whole record is used under each observation pattern, as in
the inspected neighbor-mask rollout; do not pretend these are exact
conditional expectations at the query's fixed known values.

For a public query report, find nearest training-bank records using only
encoded observed optional groups and all encoded nonoptional groups.
Exclude bank records missing any optional field that the query reports as
observed. Categorical one-hot squared distances receive weight 1/2 per
coordinate (different categories contribute one unit); standardized numeric
coordinates receive weight 1, and their encoded missing indicators 1/2.
Account for infrequent-category grouping in encoder output widths. This
heterogeneous distance is an explicit adaptation, not a tuned author setting.
Neighbor ties use fixed bank order. If no eligible neighbors remain, assign
no positive query scores and record that coverage failure.

Numeric distance arithmetic uses float64 coordinate differences; categorical
blocks use exact 0/1 match counts. Original-field blocks are processed in
canonical encoded-coordinate order, independent of serialized dictionary
order. The first smoke's independent score audit exposed a float32 checker
calculation and Gram-cancellation/tie sensitivity. Both are corrected before
source-market execution; the original smoke outputs remain archived and are
not empirical performance evidence.

Let R be the publicly missing original-field set. The score of missing field
a is the neighbor mean of loss(R)-loss(R minus a). Scores use no validation
target, hidden validation value, honest validation quote, or simulator
concealment flag. Choose the best positive field per listing, then the
highest positive scores under the parent's hard shared capacity. A query
that cannot replay a recorded value still consumes one slot.

Only empty/single-field acquisitions are feasible because this task allows
at most one query per listing. The non-greedy multi-step component of general
ACO is consequently absent in this task-specific ACO-1 adaptation. A hard
capacity replaces the original acquisition-cost trade-off; no extra price
cost penalty is introduced. Outcomes must report actual capacity usage.

## Prespecified comparisons and interpretation

Main k=25: both saved price predictors at every preset capacity 0,1,5,10,20,30%.
Neighbor sensitivities k=10 and k=50: both predictors at the primary 10%
capacity. Use all three sources and seeds, the same returned-report attack
search, concealment cost and exact unilateral audit as the parent. Thus
16 cells/source/seed and 144 cells for nine completed pairs. Smaller smoke
parents inherit their cohorts; software execution is not method evidence.

Bank masks with more than two newly hidden recorded fields may exceed the
parent's fitting augmentation. Retain and report this approximation/domain
limitation. Do not claim a general conditional-density estimator, physical
inspection model, or exact equilibrium. Ordinary benefit heads are still
separate comparators; adding this adaptation does not retrospectively make
them ACO reproductions.

An explicit partial run may read only completed, hash-bound parent source/seed
checkpoints. It freezes that pair list before evaluation and is labeled partial.
Incomplete pairs are never used. Full evidence requires all nine pairs and
independent metric/capacity/receipt checks. Sources/config/results are immutable;
no winning k, seed, market or budget is chosen after examining outcomes.
