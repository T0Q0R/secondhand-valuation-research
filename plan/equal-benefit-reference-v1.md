# Allowance-matched robust/ordinary-benefit reference extension

2026-10-06. Freeze this extension before inspecting any new benefit-output
candidate objectives or choosing weights. This is retrospective development,
separate from the live suppression-output size/tuning generation. Preserve
that generation and every completed case; do not edit its frozen sources.

## Matrix and controls

All three sources, seeds 13/42/2026, caps 1000/2500/5000 (actual JUCars full
count 4774), all six capacities. Fixed and tuned ordinary-benefit robust
references contribute 324 final cells. The existing fixed/tuned SAV and
suppression-output controls remain visible as different methods, with the
same evaluation IDs and settings. Partial receipts may identify ready cases
but cannot certify this full matrix.

## Candidate reuse and fair selection

For each outer/deployment stage, wait for the existing stage's complete,
hash-bound receipt. Verify its train, tuning-fit/validation, estimator/guidance
IDs and absent outer-held-out IDs. Reuse its three static robust candidate
price predictors and jointly fitted multi-output heads at weights .25/.5/1;
static fitting is independent of which head output is later selected.
Evaluate the benefit output for each candidate on the SAME training-internal
validation rows, using honest plus attacked squared log loss at .1 and the
same fixed response search. Select among exactly three trials; grid-order
ties. Do not copy the suppression-output winner or use source evaluation
labels. Store all objective components, score arrays, reports and selections.

The price predictor/refit at a selected weight may be reused only if that
stage has the exact same training IDs, seed, configuration and weight.
Otherwise refit the static robust model at that weight on the stage's full
70/30 estimator/guidance split. The fixed reference uses the exact .5 price
predictor. Record reused and newly fitted work separately; no zero training
cost claim. Reuse does not increase the three-trial allowance.

Generate each outer-held-out state bank from its own fold's selected/refitted
predictor. Collect these predictions before fitting the final multi-output
head; evaluate its benefit output. Deployment performs its separate internal
three-trial selection and refit. Held-out outcomes cannot enter their own
price/selection loop. Teacher/deployment choices and sample-size differences
remain limitations. Preserve the shared parent encoder/feature/state layout
and public query eligibility.

## Independent verification and completion

Save model/source/input bindings, candidate objectives/arrays, each reuse
provenance, selection/refit logs, OOF banks, final heads and per-listing
evaluation states/actions/metrics. Check that honest quotes match a reused
reference when the selected weight and training role match. Independently
recompute candidate losses, grid choices, role exclusions, final head targets,
public scores, allocations, transitions and exact first-batch deviations.
Pair against corresponding fixed/tuned SAV with common source/size/seed IDs;
average seed differences before shared-batch resampling. Retain all preset
capacities, negative findings and honest/attacked errors.

Do not modify the original success thresholds after seeing extension results.
Completion requires all 27 cases and independent audit of all 324 cells.
This saved plan alone is not implementation, experiment or result evidence.
