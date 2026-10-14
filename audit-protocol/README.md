# Controlled valuation audit protocol, version 1.0

This is an explicit, reusable post-hoc protocol artifact: a machine-readable worked contract (`secondhand-audit.json`), a standard-library validator (`validate_protocol.py`), and a completed validation receipt. It documents this study after development; it is not a preregistration, a new estimation method, or evidence of external reproduction. Freeze a new contract before looking at outcomes in a prospective study.

## Run the worked example

From the sav-val project root:

```sh
python3 audit-protocol/validate_protocol.py --self-test
```

A clean checkout needs the files inside `notes/revision-mechanisms-v3/diagnostic-evidence.zip` extracted at project-relative paths, plus the committed final-record pilot files and `notes/revision-review-v2/evaluation/expanded-completion-summary.json`. No model, raw listing, Python numerical library or network is needed to validate these six directly bound artifacts. The full evidence receipts also list raw input/model hashes, which the lightweight validator does not transitively check or reproduce.

Exit 0 means contract/accounting checks and direct file bindings pass. Any absent file, changed hash, wrong CSV columns/counts or inconsistent receipt status exits nonzero. Six deliberately invalid contracts test capacity, dropping nonconverged outcomes, false confirmation, hashes, row counts and path traversal; all must be rejected. Passing does not establish scientific validity, complete auditor independence, model correctness, causality, statistical coverage or fairness.

## Reuse the protocol

1. **Declare the estimand and units.** Separate training records, fitting randomness, evaluation listings, response batches and repeated method outcomes. Record advertised versus transaction labels and source-specific price units. Freeze row ordering, train/head/evaluation separation, data access route and hashes. A new held-out cohort has a different evidential status from expanding an already examined cohort.
2. **Match the comparison.** Factor estimator, query acquisition, feedback and allocation; hold non-target factors fixed. Save shared seed/batch pairing. Include ordinary-benefit and risk controls. Report zero-query differences before attributing gains to acquisition. Keep each candidate's development history.
3. **Specify the game.** Declare feasible concealments, costs, charged failed queries, locking time, batch capacity including tails, query successes, ties and all response starts/sweep limits. Save states, queries and expected quotes for new runs; the historical positive-cost run lacks states and therefore permits only concealment bounds.
4. **Check the returned solution.** Retain every cell, failed query, response cycle and nonconverged batch. Enumerate all legal unilateral deviations when feasible, report maximum remaining regret and mark the finite action/peer scope. Do not replace nonconverged profiles with zero outcomes or call finite unilateral checks global equilibrium certificates.
5. **Audit recovery and predictive cost.** Record pre-query, recovered and honest anchors; detect adverse partial recovery. Jointly report inflation, honest/attacked MAE, failed queries and net deviation, including constant-quote degeneracy and any coverage/abstention. For final-record alternatives, publish the actual completion domain, coverage and shared-support errors.
6. **Quantify uncertainty and heterogeneity.** Use shared method draws, preserve seed/batch dependence, weight partial batches, declare multiplicity families and threshold sensitivity. Conditional fitting-seed variance is not training-population variance. Crossing zero does not prove equivalence. Record primary versus post-hoc analysis status and retain opposite directions.
7. **Bind evidence and report scope.** Save immutable source/config/model/outcome/receipt hashes. State exactly which primitives the auditor shares and independently implements; probe state enumeration and allocation independently. Publish direct and transitive evidence dependencies separately, plus an explicit list of unavailable artifacts and reproduction boundaries. Update progress after each completed stage.

For a different study, copy and adapt the JSON, define outcome units, point artifacts at the new results, and change the validator's worked-example scientific constraints intentionally. Its current constraints (four factors, two hidden fields, charged failures, private retrospective example) are explicit assertions of this example, not universal best practices. Do not simply edit an outcome hash to make a failed audit green; explain and version the changed scientific artifact and rerun the relevant producer/checker.

## Outputs and boundaries

`validation-receipt.json` binds validator/contract hashes and the six checked artifacts. Each underlying completion receipt defines its own larger provenance closure. Frozen original production/audit sources are preserved. Private storage, same-machine aggregate replay and a public external training reproduction are distinct milestones. No public license, release, DOI, author approval or submission is asserted here.
