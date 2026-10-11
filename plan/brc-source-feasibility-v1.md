# BRC real-source feasibility screen v1

2026-10-07. Freeze before running this new source screen. Earlier SAV/CDM/EMC
validation results have already been observed: this is exploratory development,
not a new confirmatory holdout study and not an extension of the SAV endpoints.

Use the original three sources, full training caps5000/4774/5000 and the same
1000 ordered validation records. Inherit checksum-bound input configuration
from the completed nested-development-v2 parent. Do not read original test
labels or use validation outcomes to select an encoder, cap or hyperparameter.

This first screen fits one deterministic, currency-scale ridge price model per
source, alpha10 and LSQR solver, on all allowed training records. It is a
separate certifiable additive estimator, not the SAV neural/CatBoost model and
not a performance-matched comparison. No three-seed robustness claim is made.
Freeze M as the largest allowed training asking price. Clip model outputs to
[0,M] before defining the target g(x); unbiasedness concerns g, not true value.

Numeric features are mapped into[0,1] using training extrema, clipped at the
same boundaries for all inputs, with training-median missing imputation and
a separate missing indicator. Constant observed numeric fields map to0.
Categorical features use training-only one-hot categories plus an explicit
missing category; unseen categories have the all-zero encoding. Identifiers,
targets, source-row indices, price columns and direct-reveal aliases remain
excluded by the existing price_features guard.

The four optional fields retain their original roles. A publicly absent
optional field permits every allowed observed numeric/category encoding and
the natural-missing encoding. Visible values fix their contributions. For an
additive model, obtain lower/upper raw model bounds by independently minimizing
or maximizing each missing field's contribution, then apply the monotone[0,M]
clip. The independent completion domain is a conservative superset of physical
combinations; labels and actual hidden values are not used to narrow it.
Save extrema and witnesses, training schema, model and exact source bindings.
Floating arithmetic checks use a declared1e-7*M tolerance, not a formal machine
rounding proof. Separate finite mechanism02 has exact rational sampling checks.

For each immutable public batch of100 records, calculate the all-optional-
missing report's midpoint-anchor reserve floor, a sufficient condition for
every allowed report profile. Also report the sum of(U-L)/M, the necessary
floor for the bounded two-branch unbiased class; failing the midpoint floor
alone does not prove every other anchor choice impossible.

Retain all six original field-query allowances0,.01,.05,.1,.2,.3. Charge one
complete verification bundle as four field-query units, including no-result
fields; budget is floor(floor(rho*n)/4) bundles. Primary allowance isrho=.1.
Assume successful restoration/absence certification only for the feasibility
model; real failure remains an explicit unresolved limitation. Report natural
missingness and all infeasible batches, without excluding difficult records.

Gate: the current mechanism is source-feasible at the primary allowance only
if all ten batches satisfy the report-independent midpoint reserve condition.
If any source fails, report that failure and do not claim practical validated
truthfulness for that source. Do not increase M, reduce audit cost, suppress
records, reinterpret failed audits or change the gate after results are visible.
No performance/marketplace-success claim follows from passing this screen.

An independent saved-model audit must reconstruct the envelope extrema and
their endpoint witnesses, every batch budget/floor, gate and input/model hashes.
All three sources and all capacities remain in the report. This screen is not
the full variance/performance/seller-cost study and cannot complete the paper.
