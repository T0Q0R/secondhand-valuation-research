# Public-score minimax allocation baseline

2026-10-08. Required strong allocation comparator for the matched factorial
study, not a claim of a novel general optimizer. The public input is a finite
nonnegative vulnerability score for each currently missing field, with
ineligible entries explicitly excluded. No original reports, hidden values,
source-availability labels, targets or replay transitions enter allocation.

Choose each item's highest positive eligible score g_i and its field. Solve
min_{0<=p<=1,sum p<=B} max_i g_i(1-p_i), where B is the integer hard capacity.
Use scalar threshold water filling and realize marginals by systematic private
sampling. This optimizes a declared score surrogate, not actual unilateral
incentives: sellers can change both scores and their competitors' allocation.
Failed queries still spend budget. Zero scores are left unqueried. An unseen
report is scored by the frozen public head, without a hidden-state fallback.

Compare against top-B using exactly the same estimator/head/score tensor.
Audit against independent LP solutions, direct integration over all draw
intervals, capacity checks and boundary cases. Before any market-performance
claim, integrate expected marginals into complete unilateral response search,
recompute allocations for every candidate, retain query failures and regret,
and run the full matched design. Existing source results cannot be attributed
to this new allocator.
