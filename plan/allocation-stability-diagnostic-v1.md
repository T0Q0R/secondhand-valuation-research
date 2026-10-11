# Fixed-profile score stability diagnostic

9 October 2026. This is a post-hoc diagnostic of the completed, independently
audited 108-cell frozen-model allocation experiment. Its effects are already
known. Do not modify any live training or allocation source and do not call
this a causal explanation or another performance experiment.

Use all 1080 saved response batches from both top-B and minimax. At each saved
joint report, inspect the public score of every eligible item/field. Set the
absolute score perturbation radius to alpha times the median positive item-best
score, for alpha in {0.001, 0.01, 0.05, 0.1}. These relative radii are diagnostic
choices, not learned bounds on the real head error. Keep sources, price models,
score types and generating allocators separate; their raw score units differ.

Certify unchanged positive support only if every positive item-best score is
strictly above delta and each finite nonpositive item-best score is strictly
below -delta; items with no finite public field remain ineligible. Certify the
chosen fields only if each positive item's top-two finite score gap exceeds
2 delta, or only one public field exists. Field and support tests apply to the
whole batch. With these conditions, m is the minimum positive score minus delta
and the conditional probability change bound is min(1,2 delta/m).

Compute each item's queried quote from the saved prediction table and the
chosen-field replay transition, even when it was not queried by top-B. A saved
realized after-quote is not a substitute for that counterfactual. With frozen
price endpoints, the batch maximum expected-quote change is bounded by
R min(1,2 delta/m), where R is the largest absolute counterfactual recovery
span. This applies to the minimax mapping at that fixed report, regardless of
which allocator generated the saved report. It is not a bound after agents
adapt again. Exclude no batches; mark no-positive-score radii undefined.

For comparison, top-B is locally constant if the same support/field conditions
hold and the gap between its Bth and (B+1)th positive item scores exceeds
2 delta (or all positive items fit). Report this sufficient condition too.
Do not claim randomized allocation is always more stable: top-B can be exactly
constant away from its ranking boundary, while minimax probabilities vary.

Export every batch/radius and aggregate only counts and certificate coverage.
Count separately: support condition, field condition, combined minimax
certificate, nontrivial probability bound (<1), top-B local-constancy certificate,
and zero recovery spans. Preserve all input hashes. These are sufficient
conditions; an uncertified case is not evidence of actual instability.
