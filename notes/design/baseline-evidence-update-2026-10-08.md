# Current direct-baseline evidence index

This update supersedes the pending-status descriptions for Strategic SVR and
ACO in the historical baselines.csv. Preserve that old planning snapshot;
do not rerun completed experiments merely because its labels are stale.

| Comparator | Existing execution | Evidence and limits |
|---|---|---|
| Whole-field SMI adaptation | outputs/grouped-smi-development-v2 | 12 cells across3sources;1 deterministic fitting generation per source; no-query control. Independent interval/categorical audit covers94,527 cases. It is an adaptation with categorical groups and fallback, not the authors' original Weka execution. |
| ACO-1 adaptation | outputs/aco1-development-v2 | 144 cells across9source/seed pairs. Audit outputs/aco1-development-v2-audit; read scope in manuscript direct_comparator_results.tex. Not an unchanged execution of the original classification system. |
| Public-score minimax | outputs/minimax-response-full-v1 |108cells computed; full independent audit currently running. No manuscript performance claim before audit/analysis. |
| Matched24-cell factorial | outputs/matched-factorial-ten-seeds-v1 |Full experiment currently running; initial-objective factor differs from original saved SAV fits.|

Receipt verification for the existing SMI output is recorded in
notes/existing-direct-baseline-binding-v1.json. It checks saved source and
payload hashes; it is not a new statistical replication or model refit.

## Novelty boundary

Zhang, Liu and Li (2020), Predictive Analytics with Strategically Missing Data,
INFORMS Journal on Computing32(4):1143–1156, DOI10.1287/ijoc.2019.0947,
already addresses strategic missingness in regression through support-margin
imputation. Continuous regression itself is therefore not a new contribution.
The paper's original margins and our uniform honest-quote-error condition are
not interchangeable assumptions. Our candidate contribution must rest on the
specific failed-but-charged verification model, constrained precision frontier,
and rigorously evaluated mechanism effects. This comparison does not establish
priority for that frontier.

Official bibliographic/abstract source:
https://pubsonline.informs.org/doi/abs/10.1287/ijoc.2019.0947
The main manuscript already cites and evaluates an SMI adaptation. The current
addendum needs the same boundary so its standalone story does not omit it.

## 9 October completion update

The public-score minimax run is now independently audited on all 108 cells and 108000 outcomes; all 18 statistical contrasts pass independent reconstruction. See outputs/minimax-response-full-v1-statistics-check. Only two contrasts pass the fixed point gate, while ten increase inflation. The earlier pending row records its 8 October status, not the current state. Full matched-factorial training is still running. Additional primary-source boundaries for feedback learning, SERM and randomized strategic risk are in notes/closest-prior-joint-update-2026-10-09.md.
