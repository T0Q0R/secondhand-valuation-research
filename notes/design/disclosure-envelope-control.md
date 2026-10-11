# Generic disclosure-monotone diagnostic control

For a reported optional-field withholding pattern H, compute the maximum
backbone quote over all reports formed by withholding additional visible
optional fields: g(z_H) = max over J containing H of f(z_J). Evaluate all 16
patterns for four optional fields. The maximization set shrinks when more
information is withheld, hence g cannot increase through withholding.
Every maximized input hides all entries hidden in H; runtime never uses their
values. Originally missing entries remain missing throughout.

This is a generic order-closure control, not claimed to be novel, not the
published AAAI classification implementation and not an SMI reproduction.
For the present upward-quote payoff and nonnegative concealment cost, honest
reporting is a weak best response. This statement concerns the stipulated
withholding model, not fabrication, market incentives or natural-data error.

It can achieve zero positive quote uplift while making honest prices too
large. The meaningful comparison is therefore both source-price error and
inflation, with signed bias retained. A toy behavior test explicitly verifies
this failure case.

Plan: evaluate the saved common masking backbones without refitting or
queries. Taking fewer than the available queries is feasible under the hard
budget. The closure evaluates three/four-hidden-field patterns not included
in the backbone's primary two-hidden-field training augmentation; disclose
this as its estimator generalization limitation. This diagnostic must not
be substituted for the missing exact strategic-regression comparator.
