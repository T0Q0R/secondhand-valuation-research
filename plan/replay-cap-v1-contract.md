# Verification-history cap: developmental mechanism experiment

2026-10-07, before computing capped outcomes. Motivated by the completed
360,000-row decomposition: partial recovery can increase a seller's quote.
This is an exploratory follow-up using previously examined data, not a
preregistered confirmatory test and not yet a claim of literature novelty.

For a fixed estimator and fixed public query rule, define the final log quote
per realized allocation as min(unqueried reported quote, post-replay quote).
For mixtures, cap each realized rule's quote BEFORE taking expectations.
Use the exact saved policy weights and public score rules without refitting.

Theorem candidate: at every fixed peer profile, all legal reports weakly lose
quote under the cap; truthful quotes stay unchanged because queries on a
truthful record only attempt naturally missing fields and cannot change it.
Consequently the worst expected unilateral gain relative to truthful reporting
weakly decreases, for any fixed policy mixture. This proof does not imply
improved attacked MAE, unchanged response profiles, equilibrium dominance or
equal final-record treatment. The cap is verification-history-dependent.

Evaluate all original nine source/seed pairs, two fixed estimators, six
capacities, five peer profiles and four policies (suppression/benefit/risk/CDM).
At every entry enumerate all legal own reports again. Publish unmodified and
capped mean/max gain plus zero-change cells, independently reconstruct and
audit every gain row, and retain all cases. Honest quotes must match exactly
within numeric tolerance. Do not attribute any changed query/failure rates
to this fixed-profile comparison; the chosen report may change.

Use the existing independently audited signed gain matrices, whose entries
equal q_after(h,rule)-q_truthful and whose concealment cost is zero. For each
legal h, cap gain equals min(q_before(h)-q_truthful, signed_gain), per rule.
An independent check instead reconstructs absolute quotes, takes their
minimum and subtracts truthful quotes, then recomputes expectations and maxima.
Track ties with tolerance1e-10 and compare actual gain values, not fragile
argmax identity. Save all entry-level envelopes and new maximizing reports.

Primary descriptive comparison: capacity0.1, robust fixed estimator, all five
profiles with equal weight, source-level averaging of all three seeds. Also
publish all other estimator/capacity/profile cells. No promotion to a
deployable generally superior method without attacked-error/response analysis
and nearest-work review. Existing10% relative/5% honest-error practical
thresholds can describe point effects, but no training-population interval
or threshold pass is inferred from these three fixed seeds.
