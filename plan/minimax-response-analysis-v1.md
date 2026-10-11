# Matched allocation analysis, frozen before full outcomes

2026-10-08. Analyse only a completed run with independently verified source,
model, outcome and summary bindings. Full coverage: 3 sources x 3 seeds x
2 prices x 3 score kinds x 2 allocation methods, at capacity0.1. Do not mix
these results with ten-seed fitting extensions, tuned ordinary-benefit studies,
or the verification-history cap.

For each of18 source/price/score contrasts, pair methods on listing ID, seed
and shared batch. Report top-B minus minimax for inflation, honest MAE,
expected attacked MAE, failed-query probability and deviation envelope;
positive differences mean a reduction under minimax. Also report signed bias,
maximum response regret and nonconverged batches, without filtering them out.
Use1000 crossed resamples of3 fitting seeds and10 shared batches, nominal95%
percentile intervals, exploratory and unadjusted. These are conditional on
fixed training records and the searched response protocol. Three seeds are
still weak procedural replication; no population-training or equilibrium claim.

Retain the pre-existing point thresholds: at least10% inflation reduction,
at most5% honest MAE increase. Report the positive interval requirement
separately; neither is a failed-query or attacked-error guarantee. On each
source/price/score pair, give separate dominance indicators for
(inflation,honest error,failed queries) and for that triple plus attacked MAE.
Use1e-10 absolute numerical tolerance solely for ties, not for practical
importance. Preserve every comparator, zero denominator and negative result.
