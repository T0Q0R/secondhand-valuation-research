# Reproducing the current development study

This guide describes the current development generation, not a completed final
submission package. See README.md for completed and unfinished study scopes.
Commands below run from `sav-val/`. Use Python 3.12 with the versions in
`requirements-lock.txt`; this workstation uses `../.venv-gdfs/bin/python`.
Model fitting can take hours. Completed output directories must be preserved.

For a separate source checkout, create the expected interpreter once:

```sh
python3.12 -m venv ../.venv-gdfs
../.venv-gdfs/bin/python -m pip install -r requirements-lock.txt
```

The local source package includes the two required parent manifest builders
alongside `sav-val/`. Public raw inputs are obtained from the source records
below; reconstruct them before starting a full real-source fit.

## Source inputs and reconstruction

The inherited datasets are [JUCars v2](https://doi.org/10.17632/ddcz486x5t.2)
and [MUCars v2](https://doi.org/10.17632/vjrbcb2rrt.2), both CC BY 4.0.
Use `cars_jordan.csv` and its `data_dictionary.csv` from JUCars, and
`cars_dataframe.csv` from MUCars. Raw bytes, builder bytes and the four
processed input hashes are pinned in `notes/source-reproduction-inputs-v1.json`.
The manifest builder code is in the parent directory's
`experiments/build_jucars_bvival_manifest.py` and
`experiments/build_mucars_bvival_manifest.py`. SAV-Val builds its own action
targets; the older BVI listing-action builder is not part of this pipeline.

```sh
../.venv-gdfs/bin/python experiments/rebuild_source_splits.py \
  --jucars-source ../experiments/data/external/jucars_2024_v2/cars_jordan.csv \
  --jucars-dictionary ../experiments/data/external/jucars_2024_v2/data_dictionary.csv \
  --mucars-source ../experiments/data/external/mucars_2024_v2/cars_dataframe.csv \
  --input-receipt notes/source-reproduction-inputs-v1.json \
  --output-root outputs/source-reconstruction-fresh
```

The wrapper imports the two inspected builders, writes only train/validation
splits and requires their CSV bytes to match the inherited inputs exactly.
It never opens or emits historical test labels. The completed local check is
`outputs/source-reconstruction-v1/reconstruction_completion.json`: JUCars
4,774/1,374 rows and MUCars 39,244/10,672 rows before model caps. This validates
source reconstruction; it is not another model fit or fresh confirmation.
The runner expects processed inputs at
`../experiments/data/processed/{jucars,mucars}_bvival_v1/splits/`.
For an independent checkout, reconstruct into a fresh directory and place its
`experiments/data/processed/` under the checkout's parent with that layout.

## Main nested study and ordinary-benefit reference

Make a new config that changes only the output destination:

```sh
../.venv-gdfs/bin/python - <<'PY'
import json
from pathlib import Path
source = Path('experiments/configs/nested-development-v2.json')
target = Path('experiments/configs/reproduction-fresh.json')
if target.exists():
    raise FileExistsError(target)
config = json.loads(source.read_text())
config['output'] = 'outputs/reproduction-fresh'
target.write_text(json.dumps(config, indent=2) + '\n')
PY
../.venv-gdfs/bin/python experiments/run_crossfit.py \
  --config experiments/configs/reproduction-fresh.json
../.venv-gdfs/bin/python experiments/analyze_nested.py \
  --run outputs/reproduction-fresh --output outputs/reproduction-fresh-audit
../.venv-gdfs/bin/python experiments/run_robust_benefit_reference.py \
  --parent outputs/reproduction-fresh --output outputs/reproduction-benefit-reference
../.venv-gdfs/bin/python experiments/analyze_robust_benefit_reference.py \
  --run outputs/reproduction-benefit-reference --output outputs/reproduction-benefit-reference-audit
```

The main study has 558 cells and the additional benefit reference 54. Each
source uses seeds 13, 42 and 2,026 and the same capped validation membership.
Output-path changes produce a new configuration binding. Floating-point
results may depend on library/hardware versions; preserved model bytes and
independent recomputation are the exact evidence for the archived generation.
The main `robust_no_feedback` method uses suppression-output acquisition;
`robust_benefit_no_feedback` uses benefit-output acquisition. Their honest
price predictors are identical, but induced attacks and queries can differ.

## Separate fixed-estimator and sensitivity studies

Use fresh destinations for each command. These reuse a completed parent;
they do not retroactively change its protocol or make its data confirmatory.

```sh
../.venv-gdfs/bin/python experiments/run_cdm_development.py \
  --parent outputs/reproduction-fresh --output outputs/reproduction-cdm
../.venv-gdfs/bin/python experiments/analyze_cdm_development.py \
  --run outputs/reproduction-cdm --output outputs/reproduction-cdm-audit
../.venv-gdfs/bin/python experiments/run_saved_diagnostics.py \
  --run outputs/reproduction-fresh --output outputs/reproduction-diagnostics
../.venv-gdfs/bin/python experiments/analyze_saved_diagnostics.py \
  --parent outputs/reproduction-fresh --run outputs/reproduction-diagnostics \
  --output outputs/reproduction-diagnostics-audit
```

CDM's complete matrix has 1,512 cells. The historical full result is a bound
union of seven initial pairs and two supplemental pairs; a new full-parent
run can directly execute all nine. The fixed-estimator protocol is
`plan/cdm-development-v1.md`. The finite demonstration and source-market
study have different utility units and must remain separate.

Other declared comparators/resources use `run_aco_comparator.py`,
`run_grouped_smi.py`, `analyze_grouped_smi_interval_cached.py`,
`benchmark_public_pipeline.py` and `analyze_resources_and_transfer.py`.
Read their `--help` and corresponding frozen plans before execution.
The cached SMI audit decodes arrays once and checks the same full domain;
its interval oracle was cross-checked against independent LP solutions.
Timing results from a busy shared workstation are descriptive.

## Tuning, tests and manuscript

`run_equal_tuning_size.py --parent <completed-parent> --output <fresh-output>`
executes the 972-cell three-trial size study. Its strong no-feedback control
uses the suppression output. The separate `run_equal_benefit_reference.py` implements benefit-specific
three-trial selection/refitting; its full matrix is still running. The original
size runner does not include that reference.
After completed tuning stages exist, run the separate reference extension:

```sh
../.venv-gdfs/bin/python experiments/run_equal_benefit_reference.py \
  --tuning outputs/reproduction-tuning --output outputs/reproduction-equal-benefit
../.venv-gdfs/bin/python experiments/analyze_equal_benefit_reference.py \
  --run outputs/reproduction-equal-benefit --output outputs/reproduction-equal-benefit-audit
```

For an already running tuning parent, `--follow` waits for its completed stage
receipts. Candidate weights are chosen with the benefit rule's own training-
internal objective, rather than copying suppression-rule choices. Static
backbone reuse resets the residual; only exact same-role/weight refits are
reused. The independent auditor reconstructs final OOF head targets and tree
fits as well as candidate losses and final allocations.

After independently auditing both studies, bind matched source cases and
all capacities before generating manuscript rows:

```sh
../.venv-gdfs/bin/python experiments/summarize_equal_benefit_reference.py \
  --run outputs/reproduction-equal-benefit \
  --audit outputs/reproduction-equal-benefit-audit \
  --tuning-audit outputs/reproduction-tuning-audit \
  --output outputs/reproduction-equal-benefit-contrasts
../.venv-gdfs/bin/python experiments/backfill_equal_benefit_tables.py \
  --statistics outputs/reproduction-equal-benefit-contrasts --paper paper \
  --receipt notes/reproduction-equal-benefit-table-receipt.json
```

The table binder includes both fixed and tuned roles for every captured
complete three-seed source/cap cohort; it excludes incomplete cohorts
explicitly and binds all three paired primary metrics.

Do not launch duplicate jobs against the currently live output directory.
Only resume after the original process has terminated, preserving code,
configuration, lock and stage receipts.

```sh
../.venv-gdfs/bin/python -m pytest tests -q
cd paper
/opt/homebrew/bin/tectonic main.tex
```

On other systems, use an installed Tectonic executable. The comprehensive
manuscript uses IEEEtran as its development format. A conditional journal
main plus full supplement uses the retrieved official Springer Nature template;
final journal selection/ranking verification remains pending.
Evidence backfill scripts generate table rows from completed audit CSVs;
manuscript QA receipts bind source snapshots, the compiled PDF and reviewed
page images. Partial audit receipts establish only their listed completed
cases. The full final evidence package and selected Q3 venue remain open.

## Common-profile diagnostic and conditional journal layout

The post-hoc plan is `plan/cdm-deviation-generalization-v1.md`. On a complete,
independently audited CDM source generation, run fresh destinations:

```sh
../.venv-gdfs/bin/python experiments/run_cdm_deviation_diagnostics.py \
  --run outputs/reproduction-cdm --audit outputs/reproduction-cdm-audit \
  --output outputs/reproduction-cdm-deviations
../.venv-gdfs/bin/python experiments/analyze_cdm_deviation_diagnostics.py \
  --run outputs/reproduction-cdm-deviations \
  --output outputs/reproduction-cdm-deviations-audit
../.venv-gdfs/bin/python experiments/summarize_cdm_deviation_diagnostics.py \
  --run outputs/reproduction-cdm-deviations \
  --audit outputs/reproduction-cdm-deviations-audit \
  --output outputs/reproduction-cdm-deviations-contrasts
../.venv-gdfs/bin/python experiments/backfill_cdm_deviation_tables.py \
  --statistics outputs/reproduction-cdm-deviations-contrasts --paper paper \
  --receipt notes/reproduction-cdm-deviations-table.json
```

The independent auditor uses a separate sorted-peer allocation oracle and
reconstructs source price/head scores, complete legal deviation matrices,
maximizers, tails and actual hard-cap queries. The table binder keeps all
four references and six source/price settings at primary capacity. Full CSVs
retain all capacities. These outcomes cannot replace the original endpoint.

`build_journal_draft.py --output <fresh-directory>` verifies the current
manuscript receipts and official-template archive hash, then flattens the
short main and comprehensive supplement into separate standalone TeX files.
Compile each with Tectonic. The template's unstarred-table measuring hook
conflicts with resizebox; starred floats preserve the vector table contents.
`render_development_pdf.py` requires the bundled document Python runtime
with pdfplumber/Pillow and local Poppler. Its receipt records geometric/font
checks separately from subsequent human-visible image review. No native
pdflatex or publisher upload compilation has been tested.

The main article uses journal-width vector panels with 9-point axis, tick and
legend text; its four figures are distinct from the wider supplement figures.
The figure generator copies the audited CSV bytes and retains every source,
seed and preset capacity. To regenerate layouts from fresh complete audits:

```sh
../.venv-gdfs/bin/python experiments/draw_journal_figures.py \
  --main-audit outputs/reproduction-main-audit \
  --cdm-audit outputs/reproduction-cdm-audit \
  --output paper/figures/reproduction-journal
../.venv-gdfs/bin/python experiments/build_journal_draft.py \
  --journal-figures paper/figures/reproduction-journal \
  --output paper/reproduction-journal-draft
```

The supplied manuscript sections and their evidence maps must still match.
New statistical generations require corresponding table backfill receipts;
historical absolute receipt locations are provenance, and the journal builder
checks section bytes in the current project after relocation.

`package_development_sources.py --output <fresh-directory> --journal-draft
<reviewed-paper-directory>` includes code, pinned inputs, all journal-figure
receipt files and the reviewed main/supplement. It excludes the raw CSVs and
full fitted-model/outcome collection. `verify_development_package.py` must run
from the copied `sav-val` directory using a fresh Python process. Its
`--original <original-project>` guard denies reads from the original paper,
notes, experiments, plan and tests. It runs the copied tests, records the
implementation module paths and reconstructs journal TeX/assets with exact
byte comparison against the packaged draft. This check does not replace
full experiment retraining.

## Inspecting completed evidence components

`artifacts/completed-evidence-components-v1.zip` has a self-contained
`evidence_manifest.json` plus an adjacent manifest/verification receipt. It
contains the finished main/reference/CDM/diagnostic/comparator/resource study
files and four processed train/validation inputs. The nine CDM pair directories
are regular archive files, including both underlying seven-pair/two-pair
provenance containers. Do not infer completion of the live tuning/benefit
extensions from this component. Archive-integrity checks are not retraining.

To build a fresh component archive after verifying the same completed sources:

```sh
../.venv-gdfs/bin/python experiments/package_completed_evidence.py \
  --output artifacts/completed-evidence-components-fresh.zip
```

The copied-source verifier denies both original project inputs and the actual
inherited data directory under the sibling experiments tree. Revision22
used an overly broad description of a guard that covered a hypothetical sibling
data directory; keep that archive immutable and use the corrected helper in
a fresh source package.

The current local combined-copy proof uses the copied
`experiments/verify_completed_evidence_audit.py`. After the source/evidence
archives are unpacked into a fresh common parent, it checks every component
file, blocks original directories, loads the copied processed inputs and
re-runs the complete main audit into a fresh destination. This workstation
verified558 cells and six identical numeric CSV tables; other components retain
their separately archived original-study audits.

To reproduce the reviewed two-figure supplementary addition, pass
`--training-size-figures paper/figures/training-size-effects-v5` to
`build_journal_draft.py`. The source packager includes this hash-bound bundle
when the reviewed journal build declares the two supplementary displays. The
copied-package verifier selects the same option and checks both figure PDFs
and the complete supplement source exactly.

The current source snapshot is `artifacts/reproduction-development-v2-revision28.zip`:
269 ZIP entries,49 copied tests and15 exact journal29 source/assets. Its adjacent
plot proof replays all144 size rows and six complete PNGs from copied recipe/data
snapshots, with fresh glyph/collision checks on six regenerated PDFs and actual
original source/outcome/data rejection probes. This is not fresh model fitting.
See `notes/source-package-current-reproduction-2026-10-07-v1.md`; generated
verification outputs are supplemental files rather than modifications to the ZIP.

That source snapshot freezes journal29. Current journal30/canonicalQA28 move
the unchanged AI-use disclosure into Methods; no new source archive is claimed
for that placement change. The independent BRC finite candidate is also outside
archive28. Use `brc-val/README.md` for its separate demo02 and rational audit;
demo01's numerical hard-budget failure and original sources are retained.

For a complete experimental archive, `package_completed_evidence.py` additionally
requires `--tuning-audit`, `--tuning-contrasts`, `--benefit-audit` and
`--benefit-contrasts`. All four must certify the full 972/324-cell studies and
all 27 exact source-size-seed cases; run, fitting-stage, audit and paired-statistic
receipts must match. Actual current partial inputs are rejected before archive
creation. This gate does not itself certify manuscript completion or Q3 ranking.
# Independent EMC candidate

## Public-state scale refinement

`outputs/emc-state-scale-development-v1` has a complete 1,080-cell run and
independent audit. The complete statistic generation is
`outputs/emc-state-scale-development-v1-contrasts-02`; its first generation
failed on a median-comparison selector and has no completion receipt.
All 4,032 retained metric contrasts, 6 median comparisons and 72 coverage
diagnostics remain development evidence. The fixed practical gate fails;
see `notes/emc-state-scale-results-2026-10-07-v1.md` and the frozen protocol
`plan/emc-state-scale-development-v1.md`.

Run from this project with the research dependencies installed; use fresh
output directories. The first command reuses the already fitted and verified
EMC-v1 parent. It does not retrain the parent base estimators or establish a
new market confirmation. The historical181-entry v1 bundle excludes the
scale refinement. The new376-entry `artifacts/emc-state-scale-evidence-v1.zip`
contains both generations. Its adjacent verification proves four copied tests,
byte-identical saved-model audits at810/1080 cells and explicit original-IO
denial probes. The separate statistics-copy proof regenerates all4,032 mean
contrasts,6 median contrasts,72 coverage diagnostics and the failed decision
gate, with all8 output files byte-identical. See the evidence note for exact
scope and the preserved failed metadata-read attempt. No full fresh fitting
or new-market confirmation is claimed.

```sh
python experiments/run_emc_scale_development.py --parent outputs/emc-development-v1 --output outputs/new-emc-scale-fit
python experiments/analyze_emc_scale_development.py --parent outputs/emc-development-v1 --run outputs/new-emc-scale-fit --output outputs/new-emc-scale-audit
python experiments/summarize_emc_scale_development.py --run outputs/new-emc-scale-fit --audit outputs/new-emc-scale-audit --output outputs/new-emc-scale-contrasts
python -m pytest tests/test_emc_certificates.py tests/test_emc_state_scale.py -q
```

Create a fresh local scale collection and verify every entry plus both saved-model
audits (the commands require the complete frozen output tree):

```sh
python experiments/package_emc_development.py --include-scale --output artifacts/new-emc-scale-evidence
python experiments/verify_emc_development_package.py --package artifacts/new-emc-scale-evidence --output artifacts/new-emc-scale-verification.json
```

The supplemental statistics proof is bound to the immutable archive and recorded
in `artifacts/emc-state-scale-evidence-v1/statistics-copy-proof.json`; its frozen
driver-v2 reruns the copied summarizer after denying original source/outcome
Python IO. It preserves the first failed proof driver and uses fresh outputs.
Source/CSV/model archive verification does not certify novelty, exchangeability,
individual coverage or final paper readiness.

## Original unit-scale candidate

The separately frozen experiment is `outputs/emc-development-v1` (810 cells).
It uses only inherited training CSVs split into estimator/head/calibration/
evaluation roles; source validation/test inputs are not read. It is retrospective
development, not a new market confirmation. See `plan/emc-development-v1.md`
and the complete positive/negative results in
`notes/emc-development-results-2026-10-07-v1.md`.

The local bundle `artifacts/emc-development-evidence-v2.zip` has a verified
manifest and a complete copied saved-model audit in its adjacent verification
receipt. Extract its inherited input tree alongside its `sav-val` directory.
From that copied directory, use the recorded dependencies and fresh outputs:

```sh
python -m pytest tests/test_emc_certificates.py -q
python experiments/analyze_emc_development.py --run outputs/emc-development-v1 --output outputs/new-copied-audit
python experiments/run_emc_development.py --output outputs/new-independent-fit
```

The last command performs fresh fitting; the audit command replays stored
models and allocation arithmetic. Current evidence proves only the latter
in an independent copy. The bundle excludes unfinished original studies and
does not replace their final combined evidence archive.

## Complete972/324 evidence and copied-delivery protocol

The full audit/statistics folders are now
`outputs/equal-tuning-size-development-v1-audit-full-01`,
`outputs/equal-tuning-size-development-v1-contrasts-full-01`,
`outputs/equal-benefit-size-reference-development-v1-audit-full-01` and
`outputs/equal-benefit-size-reference-development-v1-contrasts-full-01`.
All original raw fits,108 stages per study and54 independent BEN head refits
are archived; a copied saved-deployment replay does not repeat those fits.

Current paper regeneration:

```sh
../.venv-gdfs/bin/python experiments/build_journal_draft.py \
  --journal-figures paper/figures/journal-legible-v3 \
  --training-size-figures paper/figures/training-size-effects-v6 \
  --author-metadata notes/manuscript-author-metadata-v1.json \
  --conference-style-fix --fit-journal-displays \
  --output paper/journal-fresh-full
```

Use `assemble_completed_delivery.py` to merge the reviewed complete source ZIP
and completed-experimental evidence ZIP into a fresh folder, verifying every
ZIP/extracted hash and requiring exact shared-file identities. Then run
`verify_development_package.py` from the copied `sav-val/` to exercise copied
tests and exact current journal generation, and
`verify_full_extension_saved_replay.py` to verify all972/324 saved deployment
cells, with original-source/data IO denied and model fitting disabled.
Explicit four audit/contrast options select the full paths above;
`--original` names the original project and `--output` must be fresh.
The protocol is `plan/full-evidence-copy-replay-v1.md`. The initial complete local
copy run has passed; its receipts are in
`artifacts/completed-delivery-copy-v1/` and summarized in
`notes/completed-local-evidence-reproduction-v1.json`. Current-source prose
backfill is repackaged separately without altering experimental code/models. No public deposit or
new held-out market confirmation is implied.
