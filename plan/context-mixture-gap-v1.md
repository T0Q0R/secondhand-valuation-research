# Context-conditioned versus global-mixture separation checks

2026-10-08, before numerical checks. Use the construction and proof in
notes/design/紧凑OQBO与固定混合差距.md. Predetermined budgets1,2,3,4,6,8,10,16,20;
for each use distinct n in {B+1,2B+1,B²+B}. Check all26 cases with exact rational
primal and lower-bound witnesses across every declared context/item row.
For cases with context_count*choose(n,B)<=20,000, independently enumerate all
sizeB query subsets and solve both full allocation LPs. Adding queries weakly
reduces every gain here, so exactB suffices for the at-mostB optimum.

Global lottery: one probability vector shared by all contexts. Contextual
lottery: a separate vector per public context, both over the same legal
subsets. Risk is the fixed core subset and is already included. This is not
a real-source benchmark and does not establish performance or novelty in
general markets. Preserve all tested cases and full numerical certificates.
