## ten_seed_primary

Matched inflation improvement at10% query capacity, reference minus candidate. Each β=0.5 branch uses λ=0,β=0.5; the β=0 branch uses its own zero-weight control. Points are paired means. Thin segments are saved marginal percentile intervals; pale segments are saved exploratory max-deviation bands over216 metric contrasts. Ten fitting seeds share fixed populations and ten evaluation batches. Bands do not certify finite-sample FWER or new-population coverage.

## ten_seed_tradeoffs

Inflation reduction against honest and attacked MAE changes at10% capacity, all paired fitting seeds for λ0.1/0.5/1 and β0.5. Each point uses its own zero-weight seed control. Larger outlined markers are means of seed ratios, not ratios of cohort means. All30 source-seed pairs are retained at each weight. Raw points supply the variability display; no confidence region or independent replications beyond fitting seeds is claimed.

## budget_response

Actual budget grid0/10/30%, four path weights at β0.5. Lines show seed means and shading the full ten-seed range, which is not a CI. Top panels measure strategic gain, bottom panels failed attempts per all listings, not per query. Zero-query changes must be attributed to the estimator. Straight segments connect evaluated settings only.

## gap_ablation

Matched path-by-gap2×2 intervention at10% capacity, ten seeds in each source. Each line connects one seed across four configurations. Dots retain all seed observations and black diamonds are means. This isolates the path term from the existing gap term at the tested weights; it does not assign three separate innovation claims to the earlier switch ablations.

## seed_consistency

Complete seed heterogeneity at10% capacity. Four nonzero path/gap configurations each use the same-gap λ0 control. All ten fitting seeds are shown per source, and positive percentages mean lower inflation. Zero-weight controls are omitted from the heatmap because their paired self-change is identically zero; the full paired source table includes them. Display labels are rounded, retaining one decimal for magnitudes below1%, with unrounded data in CSV.

## response_convergence

Convergence boundary for all540 RPL cells and six configurations. Top panels show nonconverged batch percentages within each cell; bottom panels the maximum unilateral regret within that cell on a symmetric-log axis with linear threshold0.0001. Curves average ten cell-level values and bands span their full range; they are not CIs. All51 cells containing nonconverged batches remain, including89 such batch replays out of5400. Worst observed regret0.143721log is not hidden by the mean-of-maxima curves.

## mechanism_search_audited

Training-response search and score refresh relative to the matched feedback-off control at10% capacity. Points are paired mean reference-minus-candidate differences; saved marginal and exploratory simultaneous intervals are shown as in the RPL primary figure. This separate intervention retains three fitting seeds and fixed populations. Stronger search can remove mean damage in some sources, but intervals and multiobjective costs prevent a universal benefit claim.

## parameter_defaults

Existing original-feedback scans of gap weight, tolerance and feedback rounds at10/30% capacity. Vertical dotted lines explicitly mark the declared design values0.5,0.02 and2. Gap-weight and tolerance axes use symmetric-log coordinates with a linear threshold equal to half the smallest positive setting; all actual scan values are ticked. Matching default rows are included from the existing baseline. Means and full ranges use three fitting seeds. These scans do not retune RPL or prove the design values optimal.

## implementation_defaults

Existing sensitivity to six implementation settings,10% capacity. Dotted vertical lines mark declared defaults; all evaluated settings are ticked, with learning rate on a logarithmic axis after a strict positivity check. Each seed ratio uses its unchanged matched default, which is included exactly at ratio1. Curves and ranges describe three fitting seeds, not the ten-seed RPL expansion. No default is selected by validation ranking.
