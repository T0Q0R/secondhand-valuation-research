# Conditional allocation-stability evidence

Run commands from the `sav-val` directory with the project's scientific Python
environment. The original completed outputs are retained; use fresh output
paths when reproducing. These checks do not train models or modify the frozen
factorial source closure.

## Analytic and exact finite checks

The proof and three boundary examples are in
`notes/design/随机核验的条件稳定性-v1.md`, with the English statement in
`paper/innovation-addendum-v1.tex`. The finite checker supplements the proof;
it is not an empirical comparison or an exhaustive proof over real inputs.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ../.venv-gdfs/bin/python oqbo-val/check_score_stability.py --output oqbo-val/outputs/score-stability-reproduction
```

Expected scope: 2,916 score-pair/budget cases, 510 active-set changes, 108
linear-program/production comparisons and twelve scales for each of three
boundary examples. Inspect `completion.json`, `exact_pairs.csv` and
`boundary_cases.json`. A probability bound requires a common strictly positive
score floor and fixed selected fields. It does not apply across field switches,
changing eligibility, adapted peer responses or individual sampling outcomes.

## Saved-profile diagnostic

Prerequisites are the completed 108-cell frozen-model allocation study at
`outputs/minimax-response-full-v1` and its independent outcome audit at
`outputs/minimax-response-full-v1-audit`. This is a different study from the
ongoing matched-feedback factorial experiment. The analysis verifies the parent
completion and all 1,080 batch receipts before using saved scores and predictions.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ../.venv-gdfs/bin/python experiments/analyze_allocation_stability.py --run outputs/minimax-response-full-v1 --audit outputs/minimax-response-full-v1-audit --output outputs/allocation-stability-reproduction
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ../.venv-gdfs/bin/python experiments/check_allocation_stability.py --run outputs/minimax-response-full-v1 --analysis outputs/allocation-stability-reproduction --output outputs/allocation-stability-reproduction-check
```

Inspect both completion receipts. The analysis intentionally records
`completed_pending_independent_check`; the separate checker must report
`completed`. Expected coverage is 4,320 batch/radius rows and 144 groups of
30 batch executions. `input_binding.json` retains input hashes.
`batch_certificates.csv` includes failures to certify and undefined radii;
`coverage.csv` retains source, price model, score rule and generating allocator.
No failed condition is dropped from the denominator.

For radii 0.001, 0.01, 0.05 and 0.1 times the median positive score, the original
checked outputs contain 471, 401, 267 and 244 sufficient minimax certificates,
respectively, out of 1,080 cases per radius. Nontrivial probability bounds number
468, 353, 245 and 242. The corresponding sufficient top-B local-constancy counts
are 401, 212, 53 and 39. A constancy certificate and a nonzero sensitivity bound
are different guarantees; these counts do not rank the methods' stability.

The independent checker uses exact fractions of represented scores and radii
for the conditions, while displayed quote bounds have a numerical tolerance of
1e-12. Query-recovery spans are reconstructed for every eligible item, including
items not queried in the saved top-B realization. The radii are hypothetical,
not estimates of model error. Repeated seeds and allocators share observations;
these case counts are not independent statistical sample sizes. Failure to
certify does not establish instability, and stability does not establish lower
inflation, prediction error or query failure.

This local reproduction route does not establish a clean-environment Docker
run, public release, repository DOI or journal readiness.
