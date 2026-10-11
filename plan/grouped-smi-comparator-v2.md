# Full-field grouped SMI adaptation: convergence-limit revision

Frozen before source generation v2, 2026-10-06. Generation v1 completed the
synthetic source and then reached its 200,000-iteration solver cap while
fitting JUCars; its partial outputs are preserved. No evaluation effects were
used to select this revision. It removes that numerical cap; the statistical
objective, preprocessing, C, epsilon, domains and comparison matrix remain
fixed. This is a clean-room adaptation
of the inspected equations (7)/(8) in Zhang, Liu and Li (2020), DOI
10.1287/ijoc.2019.0947. The inspected prose explicitly converts categories
to binary attributes. Keeping whole categorical fields consistent requires
an additional one-hot constraint; this adaptation is not an unchanged Weka
reproduction or an extension of the source's incentive theorem.

Use every allowed predictor in parent FEATURES and the same capped source
training/evaluation membership. Fit only the parent's outcome-independent
70% estimator partition. The four optional fields are mileage, transmission,
fuel and body condition; excluding a field excludes all of its coordinates.
Train the full model and all 15 group-reduced linear epsilon-SVRs on the same
estimator records with all four optional fields recorded. Report the resulting
sample restriction. Training medians, min/max scaling, category vocabularies
and target scaling use this common fitting sample only. No evaluation labels
or outcomes select preprocessing, domain, C or epsilon. Nonoptional missing
numeric values use the fitting median plus a missingness indicator; missing
nonoptional categories use an explicit token. Observed unknown categories use
a reserved unknown token, also included in categorical completion domains.
Mileage and battery range/capacity use log1p(max(value,0)). Known evaluation
numeric values are never clipped to the training range.

Use linear SVR, C=1, epsilon=.15 in training-normalized log-target units,
tol=1e-5 with no artificial iteration cap (max_iter=-1). Require convergence. All models have
an unregularized intercept. Coefficients with magnitude below 1e-10 count as
exact zero; retain every reduced model whose omitted groups are a subset of
the public missing groups and whose retained coefficient signs agree exactly
with the full model. Require the fully reduced model as in the equation-level
implementation; if it fails the sign check, record an explicit fallback.

Solve the two stages exactly as mixed-integer linear programs: missing
categorical groups have binary coordinates summing to one; the only continuous
optional field is mileage. Retain all three prespecified mileage domains:
free, normalized nonnegative, and normalized [0,1]. These are domain
sensitivities, not physical mileage bounds. Stage one minimizes y subject to
each retained model's lower margin. Stage two minimizes the sum of signed
missing-coordinate values while all model centers lie in [y*, y*+epsilon].
Return the FULL model evaluated at the second-stage imputation. Save both
objectives, retained-family size, solver status and imputed record. Infeasible,
unbounded or inconsistent-family records receive the SAME declared full-SVR
median/mode fallback as the ordinary baseline; fallback rows support no SMI
incentive guarantee. Never discard failing evaluation records.

Compare ordinary median/mode with the three grouped-SMI domains. All four
fields are withholdable, at most two originally recorded fields may be hidden,
and all legal reports are enumerated exactly. No query is purchased. Report
at capacity zero and identify the absence of acquisition: this is not a
matched querying-policy comparison at positive capacity. Natural missingness
and deliberate withholding yield the same public prediction input. Honest
ties retain disclosure. Cost is zero. One deterministic fit per source is not
three independent training seeds. Save the full 11-state price arrays, statuses,
coefficient family, cohort IDs and per-listing outcomes, plus fitting/source
hashes. Summarize honest and attacked currency MAE, log inflation, signed
honest bias, fallback coverage/reasons, imputation domain failures, and hiding.

A reduced-size execution smoke is software evidence only. Before manuscript
use, independently reconstruct cohorts and all predictions, reproduce the
two objectives by categorical enumeration plus continuous LPs, and recompute
legal best responses and summary arithmetic. Keep published-method adaptation
results separate from the earlier restricted one-field numerical diagnostic.
