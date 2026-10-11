# Matched factorial evidence pipeline

This extension tests two initial training objectives, three acquisition scores,
two feedback settings and two allocation rules under a common training schedule.
The full configuration has three sources, ten seeds and six capacities: 4320
method/capacity cells. It is exploratory development on fixed training records.
The original SAV experiments, frozen-model allocation comparison and new
factorial models are separate studies and must not be merged as interchangeable
method results.

## Execution and interruption

Run from the `sav-val` directory with its established Python environment. The
source snapshots and manifests bind the configuration and dependencies. Do not
edit training sources while a run is live. On a fresh output location:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ../.venv-gdfs/bin/python -u experiments/run_matched_factorial.py --config experiments/configs/matched-factorial-ten-seeds-v1.json
```

The existing output is intentionally protected from overwriting. After confirming
that the exact prior process has terminated, the same command with `--resume`
reuses hash-bound completed fits and evaluations. A missing log update or an
observation timeout is not evidence of termination. Exclusive locks reject a
concurrent duplicate process. An interrupted, uncommitted fit can require
recomputation; completed checkpoints preserve their inputs and model hashes.

## Three separate verification stages

After every configured fit has completed, reconstruct partitions and all held-out
predictions, check matched update receipts, and independently refit the deployment
heads from the reconstructed targets:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ../.venv-gdfs/bin/python -u experiments/audit_matched_factorial_fits.py --run outputs/matched-factorial-ten-seeds-v1 --output outputs/matched-factorial-ten-seeds-v1-fit-audit
```

The fit auditor may be started earlier with `--completed-only` and a distinct
output. That freezes a partial set of completed fits, never the whole experiment.
A later audit can pass `--reuse` with that earlier audit directory. Reuse checks
the checker, run and every bound artifact; it is not a bypass for missing pairs.
The auditor compares all decision-tree structures and values, not just a few
head predictions. It does not independently replay every optimizer step.

After the full run has its completion receipt and aggregate summary, reconstruct
all final allocations, replay outcomes, legal unilateral deviations and metrics.
The auditor also derives each convergence flag from independently recomputed
regrets using the frozen strict threshold of 1e-7, and checks the summary row
count, maximum regret and nonconverged-batch count:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ../.venv-gdfs/bin/python experiments/audit_matched_factorial_results.py --run outputs/matched-factorial-ten-seeds-v1 --output outputs/matched-factorial-ten-seeds-v1-audit
```

The outcome auditor holds an exclusive output-directory lock and writes atomic
per-batch checkpoints. After an authoritative process termination, rerun the
same command and output path. It rechecks input/source hashes, model predictions,
listing IDs, targets and batch artifacts before reusing an audited replay.
Changed inputs or checkpoint bindings are rejected. Do not restart a live
process merely because an observation timed out. Older output directories
without these checkpoint bindings should be retained as historical evidence;
use a fresh directory for this version.

The interruption/resume check uses the completed small execution fixture:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ../.venv-gdfs/bin/python experiments/check_outcome_audit_resume.py --run outputs/matched-factorial-end-to-end-smoke-v1 --completed-audit outputs/matched-factorial-end-to-end-smoke-v1-audit-resume-v2 --output outputs/matched-factorial-outcome-resume-check-reproduction
```

The referenced completed audit can be regenerated with the outcome-audit command
above using the fixture's run path and a fresh output directory. This check
injects an interruption after one durable batch, verifies resumed coverage,
checks completed reuse without replay, and rejects altered input/checkpoint
bindings and concurrent writers. It validates 48 cells, 960 outcomes and 10,032
legal unilateral deviations, not the full study's scientific conclusions.

Use the current auditor, whose completion receipt binds each audited cell. Earlier
receipts without `cell_completion_hashes` do not satisfy the analysis input gate.
Do not label a small execution fixture or partially audited set as full evidence.

Only after both full audits complete:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ../.venv-gdfs/bin/python experiments/analyze_matched_factorial.py --run outputs/matched-factorial-ten-seeds-v1 --fit-audit outputs/matched-factorial-ten-seeds-v1-fit-audit --outcome-audit outputs/matched-factorial-ten-seeds-v1-audit --output outputs/matched-factorial-ten-seeds-v1-analysis
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ../.venv-gdfs/bin/python experiments/check_matched_factorial_statistics.py --run outputs/matched-factorial-ten-seeds-v1 --analysis outputs/matched-factorial-ten-seeds-v1-analysis --output outputs/matched-factorial-ten-seeds-v1-statistics-check
```

Analysis exports 58 factor contrasts and six additional joint-policy contrasts
per source/capacity, each for eight recorded metrics. `contrast_components.csv`
retains the exact contributing cell means and coefficients. Shared seed/batch
draws and complete tensors are saved. The checker rereads raw outcomes, validates
the factor semantics and uses count-weighted bootstrap reconstruction. Full
coverage requires 9216 metric-contrast rows, including all 1044 factor contrasts
and 108 additional joint-policy contrasts before multiplying by eight metrics.

## Interpretation

The nominal 95% intervals use 1000 crossed fitting-seed/shared-batch resamples;
they are exploratory and unadjusted. They condition on existing training records,
do not establish nominal coverage with ten batches and do not estimate variation
over new training populations. Signed bias is retained as a diagnostic; a smaller
signed value is not automatically better. Failed queries and attacked MAE remain
visible even when inflation and honest error meet the point improvement criterion.
Pareto flags describe point estimates and are not tests of certain dominance.

A positive feedback/allocation interaction is insufficient to claim a beneficial
joint mechanism. It can coexist with harmful feedback under both allocators or
zero gain over the starting policy. The exact statistical fixtures in
`experiments/check_factorial_contrast_semantics.py` explicitly exercise these
cases, nondegenerate crossed resampling and the consequence of losing pairing.

## Current validation scope

The completed end-to-end execution fixture has 48 method/capacity cells and 960
outcomes. Its renewed outcome audit binds all cells; the fit audit reproduces
840 held-out predictions and fourteen deployment heads. Its analysis and
independent checker agree on 1024 metric-contrast rows. These counts validate the
pipeline, not the full experiment's scientific effects. Full-run completion and
audit receipts remain the authoritative gates for a paper performance claim.

The separate fixed-profile sensitivity diagnostic is documented in
`REPRODUCING_STABILITY.md`. It does not replace either full factorial audit
or supply evidence of feedback effects.

This document describes the local evidence pipeline. It does not claim a clean
Docker reproduction, a public repository, a DOI or a released dataset license.

## Bound automatic completion pipeline

`experiments/complete_factorial_pipeline.py` sequences the four full-run stages.
It binds the run manifest and participating source files, holds an exclusive
pipeline lock, and stops on any failed stage or binding mismatch. The completed
execution fixture at `outputs/matched-factorial-pipeline-smoke-v2` passed all four
stages, including 1,024 independently checked metric-contrast rows.

For a completed run, use a fresh pipeline directory:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ../.venv-gdfs/bin/python -u experiments/complete_factorial_pipeline.py --run outputs/matched-factorial-ten-seeds-v1 --fit-reuse outputs/matched-factorial-ten-seeds-v1-fit-audit-prefix-v2 --output outputs/matched-factorial-ten-seeds-v1-pipeline
```

The currently launched instance additionally uses `--producer-pid 17657`.
That PID is a session-specific observation, not a portable reproduction setting.
The waiter records the producer's start time and command, observes that exact
identity until termination, then requires the full completion receipt and
matching summary hash. It never starts or restarts training. A missing completion
receipt, changed PID identity, unreadable process state or changed source stops
the pipeline instead of being treated as successful training.

Formal outputs are inside `outputs/matched-factorial-ten-seeds-v1-pipeline`:
`fit-audit`, `outcome-audit`, `analysis` and `statistics-check`. Inspect
`status.json`, each stage's log, and the final `completion.json`. While this
pipeline is live, do not edit files bound in its `inputs.json`. Earlier manual
commands in this document remain valid alternatives; do not launch a competing
audit against the same output directory.

After authoritative termination, resumable auditors can reuse their bound
checkpoints. An incomplete derived analysis/check directory requires inspection;
it is not silently deleted or overwritten. A completed pipeline proves the
configured audit/analysis stages, not manuscript integration, publication,
external reproducibility or journal acceptance.
