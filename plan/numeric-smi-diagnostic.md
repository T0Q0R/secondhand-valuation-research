# Numerical SMI domain diagnostic

Frozen before execution, 2026-10-05. This is a retrospective, restricted
source-market diagnostic of the inspected SMI equations. It does **not**
replace a full categorical-field, shared-budget comparison or claim an
official Weka reproduction.

Use the same capped training/evaluation membership as nested protocol v2.
Use its outcome-independent inner estimator split only for fitting.
Predict log advertised price from year, mileage and fiscal power
(synthetic/MUCars), or year, mileage and seats (JUCars). Only mileage is
withholdable, and there are no queries. Nonoptional missing numeric values
use estimator-training medians. Full/reduced SVRs use the same
mileage-observed estimator records. Training-only min/max normalization
applies to log1p mileage, other inputs and log price. Epsilon is 0.15 in
normalized target units, following the inspected source's sensitivity
setting, without source-outcome tuning; C=1, linear kernel and an
unregularized intercept follow the standard epsilon-SVR formulation.

One deterministic fit per source: repeating a deterministic fit under
three nominal seeds would not create training-seed evidence. Report full
and reduced coefficients, fit convergence and row counts. Compare ordinary
median imputation with SMI equations (7)/(8) using free, normalized
nonnegative, and normalized [0,1] missing-coordinate domains. These
domains are distinct; the nonnegative domain does not assert that the
training minimum equals physical zero. Known held-out values are not
clipped to the training range.

The solver's strict sign check applies to retained coefficients. Inconsistent
models or infeasible/unbounded programs are reported explicitly. To retain
the complete cohort, those reports receive the same declared full-SVR
median fallback as the ordinary baseline. Thus rows using a fallback
cannot support an SMI incentive guarantee. Report fallback fraction and
reason, imputation outside the training range, honest and attacked native
price error, signed bias, and positive quote inflation. These diagnostic
metrics are not pooled with the main high-dimensional methods.

Each seller has exactly two reports when mileage is recorded, or one if
it is naturally absent. With no shared query allocation, enumerate these
reports exactly and retain the honest report on ties. There is no approximate
response search. Save per-listing quotes and training/source/code hashes;
an independent arithmetic audit must precede manuscript use.
