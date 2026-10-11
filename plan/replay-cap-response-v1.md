# Replay-cap common-response experiment

2026-10-07. Freeze this contract before new response outcomes are computed.
Follow up the independently audited fixed-peer cap comparison. Full scope:
nine source/seed pairs, two fixed estimators, six capacities, suppression,
benefit, risk and the original calibrated CDM mixture: 432 capped method cells.
Use the original 1,000 listings, batch size100, four response starts and up to
20 sweeps. Refit neither scores nor mixture weights. Keep all failure/negative
results. This is exploratory development on previously examined data.

For each realized rule, final log quote is min(pre-query reported quote,
post-replay quote). Apply before expectation. Use the same private mixture
timing as the baseline: reports respond to expected utility, before the draw.
Zero-weight policies may be omitted computationally; preserve the exact
positive weights and policy order. Query ranking is unchanged conditional on
the reports, but sellers' response and consequently allocation can change.

Reuse the independently audited original response as the paired baseline.
Save new listing reports, all supported rule allocations/final states/quotes,
regrets, convergence/cycle flags and input hashes. Independently replay every
saved allocation using full stable sorting. Re-enumerate every legal own
deviation at every final batch profile to verify regret and unilateral gain.
Do not infer a certified equilibrium from the response heuristic or search
global optimality from small regret. Verify actual hard capacity for every
supported complete rule, including failed queries.

Primary descriptive comparison: robust estimator and10% capacity, each source
reported separately, three seed means. Also publish every other cell. Metrics:
mean positive expected log inflation, expected realized positive inflation,
honest MAE, expected attacked MAE (expect absolute error, not error of expected
price), signed log bias, query and failed-query probability, conditional
failure/query ratio, unilateral envelope and remaining regret. Honest quotes
must reproduce the original records. Compare failure/query denominators clearly.

Pointwise dominance at fixed peers does NOT imply improved common-response
inflation, error or failure rates. Measure rather than assume these. The cap
uses verification history and does not obey OQBO's verification-neutral class.
Three frozen training seeds provide no new training-population uncertainty.
Any conditional paired batch interval must explicitly keep models fixed.
