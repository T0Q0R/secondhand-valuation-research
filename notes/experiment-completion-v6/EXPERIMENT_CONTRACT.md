# Experiment-first completion contract

User instruction2026-10-14: complete classical/recent relevant baselines, parameter choices/sensitivity, single and combined component ablations, and curves before spending further work on manuscript generation. The36-page/six-figure source is frozen at SHA256 bf799e53b6ba4cbebf84ec78d6c2c3ffe581e6a9a21a8f4e312dd2646f656a24. No further LaTeX generation until required evidence and checks are complete. New result plots may be produced as evidence without rewriting the paper.

## Existing evidence is reusable, not pending

The inventory binds actual receipt and summary files rather than trusting stale planning CSVs. Twelve original methods/variants span3sources/10fitting seeds and1860method-capacity cells. Completed24-cell matched factorial has4320cells and later complete independent outcome/head/statistical checks. SMI2020 adaptation12cells/94527oracle cases, ACO2024 adaptation144cells, equal-budget tuning/training-size972cells and ordinary-benefit324cells are already executed. Original single removals (suppression vs benefit, zero gap, preaudit response, static robust) exist, but this does not establish a fully controlled three-component combination ablation or all-parameter sensitivity.

## Missing controlled ablation

Candidate under evaluation remains SAV; no performance/novelty outcome is predetermined. The three axes are actual replaceable components, not three asserted innovations:

A suppression-target acquisition versus ordinary-benefit acquisition;
B policy-feedback training versus no policy-feedback training;
C gap regularization beta.5 versus beta0.

Evaluate all2^3=8 combinations, including every single/two/all removal, on synthetic/JUCars/MUCars, same original training/validation ordering, seeds13/42/2026 and budgets0/.01/.05/.1/.2/.3 (432cells). Preserve honest/attacked error, inflation, signed bias, failed queries and unilateral regret. Fixed conventional foundation includes mask augmentation, supervised/attacked error terms and anchoring; “all removed” does not mean native CatBoost.

Keep total12epochs, two6-epoch optimizer runs, head refresh schedule and response-search budget identical. Important confound: original static robust has a single12-epoch optimizer run, whereas full SAV has two6-epoch runs with optimizer reset. A controlled feedback-off branch must therefore be refitted with the two-round schedule; do not relabel the old static model as that clean ablation. Exact feedback-on SUP/beta.5, BEN/beta.5 and SUP/beta0 models/OOF predictions can be reused only after cohort/model/source binding. New unique fits per outer/deployment stage are no-feedback/beta.5, no-feedback/beta0 and feedback/BEN/beta0; SUP/BEN no-feedback score branches share their identical estimator. Three outer folds remain mandatory; no held-out outcomes enter estimator/guide fitting or head-target generation.

## Parameter adequacy and choice rationale

Existing tuning grid .25/.5/1 and three training-size levels supplies useful evidence but is not every globally fixed-beta full-pipeline curve. Candidate trials use an80% internal split and foldwise chosen models: do not silently present these as uniform-beta deployment fits.

After controlled ablation, complete uniform gap beta sensitivity at0/.1/.25/.5/1/2, tolerance0/.01/.02/.05/.1, and feedback rounds0/1/2/4 with a constant12-epoch total and explicitly matched optimizer-reset controls. Settings sharing exact models may reuse them. Primary sensitivity comparisons use the same3source×3seed pairs; retain original10-seed primary study separately. Select any revised default solely on nested training-internal data with a declared equal trial allowance and tie rule, never by the retrospective evaluation ranking. Report whether the inherited .5/.02/2 settings were engineering defaults or supported by that selection; do not invent a priori justifications. Optimization stability (learning rate/epochs) and action-head capacity are additional checks if the substantive sensitivities expose instability, not an uncontrolled Cartesian grid of every numeric constant.

## Classical and recent baseline coverage

Classical references already include native/masking CatBoost, no-query, seeded random/fixed/risk and ordinary benefit plus static robust and linear/SVR/SMI adaptations. Confirm actual cohort, query budget, input-information and training-budget compatibility; absence of a fashionable baseline does not justify a false method identity.

Recent candidates require primary-source/code checks: GDFS/DIME2023, ACO2024, SEFA2025, explainability-driven AFA2025 and L2M2025/preprint revised2026. At least one2025+ executable relevant approach must be evaluated if its assumptions/code support a lawful, faithful regression adaptation. Record task/regression versus classification, mixed feature groups, naturally failed acquisitions, per-record versus shared-batch capacity, data leakage, available code/license and any pretrained-data boundary. Implement official code where compatible; all interface/one-query adaptations must be labeled as such. A nondeployable oracle using held-out values is excluded with a documented scientific reason, never replaced by a weak local proxy carrying the original paper's name. Nonapplicable methods are explicitly documented rather than counted as executed.

## Execution and completion gate

No duplicate old job or immutable output overwrite. First run bounded smoke/identity and leakage checks, then write frozen config and start resumable tasks. Target2CPU workers with bounded model/BLAS threads and at least4GiB memory headroom on the16GiB machine; scale only after observed memory/timing. Save fit, outer prediction, head, evaluation-cell and analysis checkpoints plus failure/nonconvergence states. Respect actual task locks; old PIDs are historical. Estimate ETA from measured completed-stage throughput, not guesses.

Evidence is sufficient for paper backfill only when each required item is completed or scientifically inapplicable with explicit reason, new outputs are independently corroborated, paired uncertainty/metric units and performance/runtime/robustness curves are saved, and the negative/heterogeneous findings remain visible. This gate is not a claim of new algorithm superiority, public release, author approval, SCI acceptance or fresh-cohort confirmation.

## Additional stability coverage frozen before execution

To directly address parameter completeness, add16one-factor variations at primary budget.1: anchor weight0/.125/.5/1(default.25), adversarial-error weight0/.25/1/2(default.5), learning rate.0003/.003(default.001), total epochs6/24(default12), head trees80/320(default160), residual width32/128(default64). Three sources/three seeds imply144cells and576nested price fits. Each variation changes only its declared factor; role separation, original training cohorts, two optimizer rounds and the other engineering defaults remain fixed. The full-data smoke changes width/head/epochs together solely to validate propagation, not as a scientific sensitivity result. It rejected an initial deployment-head160-vs80 bug; fixed generation passes width32/trees80/6total epochs and outcome utility replay.

Core270cells, additional stability144cells and recentSEFA108cells run sequentially after the432-cell ablation, two workers per stage.954evaluation cells include reused exact branches, not954new independent experiments. Automatic aggregate export verifies hashes/counts, paired ablations and factorial interactions, retains failed/nonconverged evidence and writes an internal handoff. Three-seed ranges are not95%intervals. Any failure stops dependent jobs. No paper writing/generation or public release occurs in the queue. New curve rendering/scientific QA and GitHub upload of future finished checkpoints await the next active collaborator.
