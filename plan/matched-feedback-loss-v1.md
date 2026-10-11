# Exact expected replay loss for the matched factorial trainer

2026-10-08. This is a training primitive and design clarification, not a
completed factorial study or new general stochastic-optimization theorem.
Do not alter immutable original training cores or live experiment scripts.

The24-cell factor labels require an explicit operational definition. Proposed
implementation: estimator factor specifies matched-budget mask-augmented versus
adversarial initial fitting with the same residual architecture. Feedback factor
controls whether subsequent adversarial training states respond to the public
query policy or to no-query valuation. Both receive the same number of updates,
round boundaries, batches and head-refresh opportunities. All score/allocation
cells reuse the same guidance records and head target family. In the no-policy-
feedback cells, score/allocation need not change fitted weights; shared identical
fits may be cached with explicit receipts. This proposed training intervention
requires a separate full-loop nested split implementation before execution and
must not relabel saved original SAV fits as factorial cells.

For policy feedback, keep the selected report state, field and probability
frozen within each gradient step, as in the existing discrete top-B surrogate.
Let q0 be the before-query quote, q1 the queried quote, p the public query
marginal, a the detached honest quote and y the target. Use

L_attack=(1-p)(q0-y)^2+p(q1-y)^2.
L_gap=relu((1-p)q0+p*q1-a-tolerance).

The first equals squared error of the expected quote plus
p(1-p)(q1-q0)^2. The second penalizes expected seller gain and does not equal
expected realized positive gain. Report that latter quantity separately in
evaluation. Failed query q1=q0 is allowed and still consumes capacity.

Combine with the same honest, valid-mask augmentation and fixed-backbone
anchor losses and coefficients for all matched feedback cells. This gradient
ignores derivatives through report search, field selection and probabilities;
it is a frozen-policy surrogate, not exact differentiation of equilibrium or
proof of improved incentives. Deterministic p in{0,1} must reduce to the
corresponding selected-state loss. Verify values and gradients against an
independent explicit two-outcome enumeration before training integration.
