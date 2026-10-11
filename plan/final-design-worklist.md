# Final-evidence design worklist after development-v1

Status: in progress; **not a frozen final experiment protocol**. The user's complete objective remains algorithm + experiments + a complete Q3-oriented paper.

## Current completion audit,2026-10-07

All scheduled extension evidence is complete:972/324 cells,27 cases and108
stages per study,54 independent BEN head refits,1134 method/972 size/810 BEN
contrasts. Prior numeric rows are exactly preserved. Journal36 and canonical
QA33 now include all cohorts with full v6 figure QA, named provisional author
metadata, fixed conference style and bounded display heights. Failed staging
table-caption extraction and corrected source-spacing generations are preserved
with numerical/citation/table invariance proofs. Review33 resolves C1 and M2;
M3 human author/venue scope and N2 selected-venue layout remain.

The complete experimental archive contains17,343 files/6,600 materialized
links/6.527GB. The initial combined copy passes49 tests/18 exact assets,
all1296 saved deployment cells,558 main arithmetic cells and six full PNGs/
162 plot rows. Availability prose is unchanged in current journal36.
Earlier source ZIPv2/combined copyv2 pass49 copied tests,18 exact
journal35 assets and17,704 distinct-file hashes. The prior actual scientific
replay carries forward under79 unchanged scientific Python files and the
identical experimental ZIP. Current journal36 removes two AAAI bibliography
warnings without changing scientific text or any reference value. Three
reference pages were inspected and59 other rasters match the prior review.
Current source ZIPv4/combined copyv3 pass49 tests4.21s,18 exact current source
assets and17,713 distinct manifest-file checks; science replay carries forward
under79 identical scientific Python files and the same experimental ZIP.
SourceZIPv3's intermediate scan preparation is superseded and preserved.
Complete human author/venue/access review next. Prospective data, physical query costs, publication venue
criterion and final human declarations remain separate unresolved scopes.

The chronological material below records older partial states; it does not
reopen completed fitting or certify final publication readiness.

## Historical completion audit, 2026-10-06 (superseded by the current audit above)

The historical v1 table below is retained as withdrawn evidence. Corrected
nested v2 is complete and independently audited (558 cells, nine pairs).
The additional original robust/ordinary-benefit reference is complete (54
cells), and its results are distinct from the main suppression-output robust
control. MUCars meets the original fixed-setting criterion; synthetic and
JUCars do not. The protocol-v2 component criterion remains separate.

Full fixed-estimator CDM (1,512 cells, 108 calibration fits), saved-model
sensitivities/strata (225 cells), ACO adaptation (144), full-field SMI (12),
restricted SMI (12), and public resources/shared-report transfer are audited.
CDM does not consistently beat its risk control. The source-directed
train/validation reconstruction matches all four inherited input hashes.
The post-hoc common-profile CDM deviation diagnostic is also complete and
independently audited (1,512 cells, 108 cases, 576 paired contrasts).
Its robust-pricing tail gains against the calibration-selected pure rule
do not establish consistent superiority over risk. There are 30 verified
cited references. The new comprehensive PDF has 19 pages, with a completed
revision23 source/visual/evidence QA snapshot; the previous 18-page visual
review remains in revision11.
Conditional journal main/supplement preparation uses the official Springer
Nature template, eight displays and a short main text. The 18-page main and
22-page full supplement use fresh compilation and page review in journal revision27;
no venue is certified.

Open: the live 972-cell equal-trial size study (756 cells independently audited
in generation08 (all synthetic/JUCars sizes and MUCars1,000)), and the implemented, live 324-cell ordinary-benefit
selection/refitting extension (252 cells audited in generation05). A final source package,
evidence freeze, manuscript QA and venue/format/author review also remain open.
The historical source-only package revision11 passes39 copied-project tests.
The current development package revision26 adds current45 tests, complete
journal-figure receipts and reviewed main/supplement. Its adjacent independent
verification receipt records actual module paths and journal reconstruction
with original code, paper, outcome and data reads denied. It remains a
source snapshot, not the complete fitted-model/outcome collection.
Outer full-workflow CDM and currency-utility extensions are uncompleted separate
research scopes, not established contributions of its fixed-estimator study.
Do not mark the overall paper objective complete on the strength of partial
retraining results or the compiled development manuscript.

## Authoritative development evidence

**Correction, 2026-10-05:** the numbers in the following historical table are
withdrawn as evidence for a deployable verification policy. Development-v1
used the simulator's deliberate-concealment mask to determine action
availability. Real platforms cannot distinguish natural missingness from
concealment on this basis. See `notes/development-v1-correction.md`. Keep the
historical files intact; corrected conclusions must come from protocol v2.

`outputs/development-v1/completion.json`: completed in 799.37 seconds. Three datasets, seed 13, twelve model/policy variants, fifty-two method/capacity cells per dataset. The independent analyzer recomputed 156 cells and checked hard batch capacities and price-space errors. Source/config/contract bytes are archived under `source_snapshot/`; existing experiment results must not be overwritten.

At 10% available capacity, comparing full SAV-Val with its ordinary-benefit-head variant:

| Dataset | Positive log-price inflation reduction | Honest MAE change | Development threshold |
|---|---:|---:|---|
| Synthetic | 4.82% | +0.22% | Failed; interval crosses zero |
| JUCars | 39.54% | -0.37% | Passed for this development seed only |
| MUCars | 5.99% | +1.79% | Failed; interval crosses zero |

The no-feedback robust model beats the full model's inflation and attacked MAE in the synthetic setting. This must remain visible. No broad method-success claim is justified.

## Resolve before final freeze

### 1. Honest nested cross-fitting

The development estimator and action-head price-loss samples are disjoint, but the estimator's attack selection is guided by the head during feedback. In the ordinary-benefit variant, this guidance carries head-row outcome information indirectly. It is therefore inappropriate to call the final recycled head targets strictly out-of-estimator-sample without a stronger construction.

Implement outer three-fold acquisition-target generation. Within each outer training fold, split estimator-fitting and feedback-guidance records. Fit the entire estimator/head/feedback loop using only that outer training fold; predict all candidate states on the outer held-out fold. Collect outer predictions to construct final action targets. Use a head encoder fitted on the final development-training covariates, distinct from each fold's valuation encoder. Neither outer-held-out labels nor evaluation labels may enter the corresponding fitted loop. Fit final deployment estimators on full allowed training data using the same inner guidance split, and fit deployable heads from the collected outer predictions. Describe sample-size and prediction-distribution differences; do not hide them as exact estimator equivalence.

Reuse common backbones and state encodings within a split where valid. Save per-fold models and receipts so a completed fold is not repeated after an unrelated observation timeout or interruption.

### 2. Attack search and exploitability

The development seller search is unilateral coordinate response, two starts and five sweeps. Some synthetic batches retain sizable deviation gains. Capacity-induced competition can prevent a stable pure response; increasing sweeps alone is not a proof of equilibrium.

Add independent exact unilateral-deviation checks against the returned peer reports, cycle detection and stronger fixed attack restarts/sweeps. Report deviation-regret distribution and a unilateral deviation envelope alongside realized outcomes. If a mixed/randomized verification model is introduced, specify the seller's information about randomness and enforce hard capacity at actual query time; do not silently give it access to realized private draws. Keep the original deterministic policy as a matched control.

### 3. Direct comparator audit

The 2020 strategic-regression author manuscript is deposited as PMC8459828. Publisher PDF redirected to the abstract, PMC web tool returned a CAPTCHA, and the standard Europe PMC full-text endpoint returned HTTP 500. These observations are saved. Subsequently, complete NCBI BioC prose and 37 complete formula fragments from a truncated EFetch response were inspected. A clean-room equations (7)/(8) solver passes four tests. Source-market fitting, categorical/domain adaptation and direct evaluation remain open; see `notes/source-inspection/smi-equation-audit.md`.

The AAAI 2021 author repository `haoming-codes/str-withheld` was located. README and GPLv3 licence were retrieved. A subsequent `credit.py` fetch succeeded. Source inspection is pinned to commit 56869f6e5d8b68337d201c809e1e2a1d132441bb; it was not executed. A regression adaptation must be identified as an adaptation, and GPL requirements preserved if distributed.

The 2026 audit preprint's full HTML confirms that joint prediction/audit design is established prior work. Candidate novelty must be incremental post-reveal learning and empirically useful feedback, rather than auditing itself.

### 4. Final evidence and paper

Keep the full intended three-source study, three training seeds, four ablations, multiple budgets, concealment costs, maximum-hidden sensitivity, honest missingness, common-attack transfer, group safety and efficiency evidence. Use source-directed processed-data reconstruction and preserve original eligibility rules. Historical source tests are retrospective and cannot be advertised as new confirmatory tests.

Tune on development only, record an equal tuning allowance for the strongest controls, then freeze final code/config/splits and success rules. Do not choose a winning seed or market after opening final outcomes. If the full method remains dominated by a simpler robust estimator, revise the mechanism or narrow factual claims explicitly; do not fabricate a method increment.

27 distinct records are verified on primary sources/DOI metadata; citation scopes and receipts are saved. The empirical writing skill’s 25-reference-count gate is met; this does not imply 27 complete-paper readings. The current `paper/main.tex` is being expanded into a development draft, **not a finished paper**. Complete bibliography verification, two structural figures, result-dependent tables/plots, bounded prose, compilation and rendered QA. The user was asked whether “三区” means CAS or JCR; venue choice remains unsettled and is independent of implementation progress.

Completed-component evidence collectionv1 now archives saved models/outcomes/
calibration/analyses and four processed training/validation input files with
14,644 verified file hashes and materialized CDM links. Still add the full
live tuning/benefit extensions before final combined evidence freeze.
Current source-package data guard now covers the actual inherited experiments
tree; historical revision22 remains preserved with a correction receipt.

Current package26 actually passed 45 copied tests in 9.04 s and 15 exact journal
source/assets checks. The actual inherited data-path rejection probe passed.
Combined copied evidence additionally reaudited all558 main cells and regenerated
six byte-identical numeric CSV tables; no fresh model fitting was performed.

## Final-extension archive gate and new supplementary evidence

Two native paired-effect figures have been inserted into journal supplement
revision27, with all 126 source rows and all adverse effects retained. The
current 20-page technical draft, 18-page main and 22-page supplement were
freshly rendered and reviewed, including the updated MUCars table and figures. Native plot text is
9 points; the final integrated pages have a 6.974-point minimum, above 5 points.
The raw caption collision report is preserved with its documented multiline
font-run aggregation limitation. A corrected local parser passes the two pages
and still rejects an actual intentionally overlapping PDF. This correction
does not alter scientific data or collision thresholds.

Source archive26 contains 231 verified entries, passes 45 copied tests and
reconstructs 15 journal source/asset files exactly while original project and
inherited data reads are denied. This development source package excludes the
complete live fitted-model/outcome collections.

The final experimental archive mode now requires all 27 exact source-size-seed
cases in both extensions, 972/324 independently audited cells, 108 stages in
each study and 54 independently refitted ordinary-BEN deployment heads. Raw
run, stage, audit, manifest and paired-statistic hashes must agree. Actual
current partial inputs were rejected before an archive could be created. The
successful final packaging path remains unverified until the actual full
evidence exists. This gate does not replace final manuscript, author or Q3
venue review. Existing historical archives remain unchanged.

Ordinary-BEN audit generation05 is complete at252 cells/21 cases/84 stages
and42 independent deployment-head refits; paired statistics05 has630 contrasts.
Seven complete cohorts are retained, including both roles at MUCars1,000.
On this cohort tuned SAV lowers inflation by5.68%, below the original10%
effect-size criterion; fixed-weight SAV raises it by5.56%. Both tuned MAE
increase intervals cross zero. The broader source-size matrix remains open.

The prior long-job PIDs and tool sessions were confirmed absent without full
completion receipts. Frozen8/9 source hashes and all22 completed evaluation
receipts per study were checked before a same-generation resume. The resumed
logs explicitly reuse four existing fitting stages. This is a verified
terminal recovery, not a restart based on an observation timeout.
