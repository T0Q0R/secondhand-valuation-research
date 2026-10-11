# Stronger comparator for the constructed context gap

2026-10-08. Before executing this extension, fix the same 26 artificial cases
in context-mixture-gap-v1. No fitting, real-data experiment or new seed study.

The previous separation restricts rules to fixed item orders plus risk. Add a
fixed mixture over context-aware deterministic rules: one rule queries all B
core items; each of B further rules omits its indexed core item and queries the
publicly active non-core item instead. Assign weight 2/(B+2) to the first and
1/(B+2) to each other. Thus B+1 unique rules suffice, with context-independent
weights. Every realized rule spends exactly B queries.

Enumerate every context/rule allocation, reconstruct integer marginal counts,
and evaluate every item loss with exact rational arithmetic. Compare the
attained worst loss with the saved full-context optimum and independently
rederive the budget lower bound. Reject mutations that freeze the active item
or assign uniform weights. This comparator tests whether conditioning rules,
rather than dynamically changing mixture weights, is the essential resource.
Do not label the closed-form rule library a broadly novel algorithm.
