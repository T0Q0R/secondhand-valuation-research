# Matched factorial attribution analysis

9 October 2026. Freeze before inspecting any formal factorial performance
summaries. The original-protocol and frozen-model allocation results have already
been inspected and inform the scientific question; this is an exploratory
developmental analysis, not a prospectively registered confirmatory trial.

## Question and claim boundary

Does policy feedback improve outcomes under a common training schedule, and is
its effect different for top-B and score-minimax allocation? The novelty candidate
is the coupled valuation/verification feedback mechanism under strategic
missingness. A water-filling allocator or a variance identity alone is established
mathematics, not sufficient evidence of methodological novelty.

The key diagnostic is a paired difference of differences, not the rank of the
best selected cell. For an outcome L where smaller is preferable, at fixed source,
initial objective, acquisition score and capacity, define

    D = [L(none, minimax) - L(policy, minimax)]
        - [L(none, top-B) - L(policy, top-B)].

Positive D means the incremental benefit of feedback is greater with minimax.
It does not imply that the resulting joint policy beats every baseline. Report
both constituent feedback effects alongside D; for example, two harmful feedback
effects can still produce a positive D. Do not interpret the sign as a structural
property of the marketplace outside the stipulated response model.

## Coverage and input gate

Require all 30 configured source/seed pairs, all six capacities and all 24 cells
(4320 method/capacity cells). Require completed independent fit and outcome
audits, including held-out prediction reconstruction and deployment-head refits.
Every paired difference must align the same source, seed, batch and listing IDs.
Retain nonconverged response batches and quantify final unilateral regret.
No partial source, selected seed, favorable capacity or individual score can
replace the declared full experiment. Interim execution/fit audits may proceed;
they provide no performance conclusion.

## Factor contrasts

At every source/capacity and for every recorded metric, compute the following
58 explicitly paired contrasts, retaining their conditioning factors:

1. Feedback: none minus policy, 2 initial objectives x 3 scores x 2 allocators = 12.
2. Allocation: top-B minus minimax, 2 initial objectives x 3 scores x 2 feedback
   settings = 12.
3. Initial objective: masking minus robust, 3 scores x 2 feedback settings x
   2 allocators = 12. This is the matched initial-objective intervention, not
   a comparison of the original SAV and static-robust checkpoints.
4. Acquisition: risk minus benefit and risk minus suppression, 2 initial
   objectives x 2 feedback settings x 2 allocators x 2 comparisons = 16.
5. Feedback-by-allocation difference of differences above, 2 initial objectives
   x 3 scores = 6.

This is 174 contrasts at the primary 10% capacity and 1044 across six capacities.
Write the four constituent cell means for every interaction, the two means for
every simple effect, and the exact coefficient vector. Check that each vector
sums to zero. Do not average away acquisition/initial-objective conditioning to
make a broad source-level feedback claim. A separate pooled model would need an
explicit weighting choice and can only supplement these direct contrasts.

## Outcomes and uncertainty

Primary: mean positive expected log-quote inflation. Report honest MAE,
expected attacked MAE, failed-query probability and unilateral deviation
envelope jointly. Also retain expected realized positive inflation, signed log
bias, maximum final regret and nonconverged batch counts. Never pool MAE across
sources with different price units.

For each source, preserve the ten fitting seeds crossed with the ten shared
evaluation batches. Reuse identical resampling indices for every cell, capacity,
metric and contrast within that source. Use 1000 independently drawn seed-index
and batch-index resamples to construct the paired grid. All reported intervals
condition on the existing training records. They are not a bootstrap over new
training populations, and nominal coverage with ten batch clusters is not
established. Do not label the 100 seed/batch combinations independent batches.

Provide unadjusted 95% percentile intervals as exploratory effect descriptions.
The 174 primary contrasts are not 174 independent chances to declare success.
Do not use isolated exclusion of zero as a confirmatory claim. Report the whole
contrast family, including negative interactions and zero-query effects.
If simultaneous intervals or mixed-effects modeling are added, freeze that
procedure separately before running it and report its assumptions; do not
silently switch interval definitions according to which one favors the method.

## Practical importance and joint-policy checks

For simple inflation comparisons retain the existing point criterion of at least
10% relative reduction with at most 5% honest-MAE increase, marking undefined
zero-baseline ratios. For the interaction, report its absolute log-unit magnitude
and the constituent relative effects; the simple-effect 10% gate has no automatic
difference-of-differences interpretation. Do not invent a favorable interaction
threshold after observing the results.

Explicitly compare the joint policy against the corresponding no-feedback top-B
cell and the matched risk rule. Show failed-query and attacked-error changes even
when the inflation/honest-error gate passes. Identify nondominated points within
each source/capacity over inflation, honest MAE and failed-query rate, with an
additional attacked-MAE version. A point Pareto frontier is descriptive and
does not establish statistically certain dominance.

## Independent statistics check and publication decision

An independent checker must reconstruct contrast arrays and all bootstrap
endpoints from raw records using count-weighted resampling rather than copying
the generator's indexed resampling implementation. Verify factor-cell coverage,
sign conventions and difference-of-differences arithmetic with corruption tests.

The manuscript may claim conditional joint-mechanism gains only if the relevant
comparisons and tradeoffs support them. Failure to find complementarity is a
substantive result and must change the contribution wording. Completing this
factorial experiment does not itself establish originality against related work
or journal acceptance.
