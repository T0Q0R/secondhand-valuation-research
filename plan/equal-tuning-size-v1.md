# Equal-budget nested tuning and source-size sensitivity v1

Created 2026-10-06 before any outcomes from this new study. This supplements,
and does not replace, the fixed-parameter nested-v2 main matrix, its full
ablations/six capacities, the CDM study or direct-comparator obligations.

## Matrix and allocation

All three original sources and seeds 13/42/2026. Training caps 1000, 2500 and
the parent full cap (5000, or all 4774 available JUCars rows). Keep the same
1000 evaluation IDs/order at each size. Hash-ranked training subsets are nested
and label-independent. Same four action groups, maximum two newly hidden
fields, recorded-value replay, failed-query charging, batch 100, primary
capacity .1 and all six declared parent capacities for final comparisons.

For each size compare robust/no-feedback, full SAV suppression and SAV ordinary
benefit. Each receives exactly three gap-weight trials [.25,.5,1.0]. All other
parameters match parent v2, including 12 total residual epochs and two six-epoch
feedback rounds. Record a fixed-.5 version of each as the size sensitivity and
a selected-weight version as equal tuning. Do not use the evaluated source to
choose a winning weight, source or size.

## Selection inside each outer fold

For each outer training fold, split 80% tuning-fit / 20% tuning-validation by
fixed ID namespace `sav-equal-tune-validation-v1`. Outer-held-out IDs must be
absent from both portions. Inside tuning-fit recover the parent 70/30
estimator/guidance split. All three trial weights use identical IDs, backbone
and encoder, and equal training iterations. Fit three models per weight:
robust/no-feedback, suppression-feedback and benefit-feedback. Guidance labels
may guide the fitting loop, but tuning-validation labels cannot.

Score each trial on its tuning-validation reports using honest squared log
loss plus attacked squared log loss at .1. The attack uses public rules and the
fixed parent four-start/twenty-sweep response; no global equilibrium claim.
The lowest training-internal validation score wins per method; ties use the
declared grid order. Save all trials, records, scores and chosen parameters.

Refit each chosen model on the complete outer training fold, with its 70/30
estimator/guidance split, then produce outer-held-out state predictions. Fit
the fixed-.5 methods on exactly that same outer training fold. If a chosen
weight is .5, reuse that exact fit rather than relabel/retrain a duplicate.
No outer-held-out label can influence its own hyperparameter selection or
price/feedback loop. Only after all outer predictions are collected may those
labels enter final action-head targets, as in the parent protocol.

Final deployment performs its own equal-budget 80/20 selection on the allowed
training rows, followed by a complete 70/30 refit. Each fixed/tuned deployable
head uses its corresponding out-of-loop predictions. Teacher/deployment size
and selected-parameter differences are disclosed; no distribution-equivalence
guarantee is claimed. Do not choose one globally tuned parameter from all
training labels and then call predictions on those rows out-of-loop.

## Evidence, cost and scope

Save hashes, stage/cohort IDs, per-candidate fitting/head scores and time,
chosen values, refit logs, outer predictions, models and actual evaluation
rows. Shared-backbone time and per-residual-method time are separate; do not
attribute shared fitting time to individual methods. Use an OS lock and
hash-bound stage checkpoints. Archive terminal incomplete stages instead of
overwriting them; never restart a live handle merely because its log is quiet.

Software smoke: synthetic seed 13, 240 train / 64 evaluation rows, three folds,
20 backbone iterations, 24 head trees, 2 total residual epochs with 2 rounds,
one capacity .1. Preserve the three-weight grid and all six fixed/tuned models
to test the selection/refit/OOS path. Its performance is excluded from claims.

Final conclusions must retain all sizes, seeds, capacities and stronger simple
controls, including failures. This is retrospective follow-up because earlier
source validation labels were already observed. Independent arithmetic/cohort/
selection/outer-target audits and source-size paired batch intervals are
required before manuscript backfill. A completed smoke or a selected parameter
does not fulfill the complete tuning/size study.
