# Current research delivery and reproduction entry

Updated 2026-10-13 (Asia/Shanghai). This is the current extension status; the 2026-10-07
submission-readiness notes describe the earlier frozen manuscript. Their statement
that no computation remained does not describe the present factorial extension.

## Current scientific deliverable

The editable manuscript is [innovation-addendum-v1.tex](paper/innovation-addendum-v1.tex).
It now defines the data cohorts, advertised-price target, stochastic outcome
metrics and unilateral audits. The integrated draft is undergoing substantive scientific revision.
The editor compiler successfully checked this source after the latest edit.

Candidate contributions are the precision frontier under explicit information
and accuracy constraints, auditable verification-path decomposition, and a
controlled study of heterogeneous effects. LPs, randomization, water filling and
the minimum operator are established tools. The fixed-mixture separation is
restricted: a context-aware library can close it. No universal superiority or
first-result claim is justified by the current evidence.

## Reproduction map

Run from this project directory in the scientific environment and use fresh
output paths. Do not restart an existing live producer or alter its bound sources.

| Component | Instructions | Verified receipt |
|---|---|---|
| Finite observable-report oracle | [oqbo-val/README.md](oqbo-val/README.md) | [independently_audited_finite_oracle](oqbo-val/outputs/finite-demo-01-audit-01/completion.json) |
| Compact marginal oracle | [oqbo-val/REPRODUCING-COMPACT.md](oqbo-val/REPRODUCING-COMPACT.md) | [completed](oqbo-val/outputs/compact-v1-audit/completion.json) |
| Restricted fixed-mixture separation | [oqbo-val/README.md](oqbo-val/README.md) | [completed](oqbo-val/outputs/context-mixture-gap-v1/completion.json) |
| Context-aware library closes the separation | [oqbo-val/README.md](oqbo-val/README.md) | [completed](oqbo-val/outputs/context-rule-library-v1/completion.json) |
| Conditional stability checks | [REPRODUCING_STABILITY.md](REPRODUCING_STABILITY.md) | [completed_exact_finite_checks](oqbo-val/outputs/score-stability-v1/completion.json) |
| Saved-profile stability check | [REPRODUCING_STABILITY.md](REPRODUCING_STABILITY.md) | [completed](outputs/allocation-stability-full-v1-check/completion.json) |
| Original ten-seed statistics check | [REPRODUCING.md](REPRODUCING.md) | [completed](outputs/ten-seed-three-source-union-v1-statistics-check/completion.json) |
| Frozen-model allocation statistics check | [REPRODUCING.md](REPRODUCING.md) | [completed](outputs/minimax-response-full-v1-statistics-check/completion.json) |

The original-study guide does not by itself reproduce every extension. For the
controlled factorial, use [REPRODUCING_MATCHED_FACTORIAL.md](REPRODUCING_MATCHED_FACTORIAL.md);
its automatic handoff is the active route. Saved receipts and their hashes are
indexed in [the delivery snapshot](notes/current-delivery-evidence-v1.json).
Receipts verify the documented scope, not every optimizer step or scientific novelty.

## Computation completed; manuscript revision in progress

The full training/evaluation run and all four verification stages completed on
2026-10-13 (Asia/Shanghai): 30/30 source/seed pairs, 4320 evaluation cells,
4,320,000 outcome records, and 45,372,960 legal unilateral deviations. The
pipeline receipt is outputs/matched-factorial-ten-seeds-v1-pipeline/completion.json.
No partial 14/30 status or old process identifier represents the current state.

A 26-page integrated draft was delivered and compiled. A subsequent detailed
scientific review identified theory/experiment scope, joint inference, evaluation
coverage, metric degeneracy, audit shared primitives and deployment concerns.
These revisions are in progress under notes/revision-review-v2/review-tracker.json.
Prior hashes and receipts remain evidence for the historical frozen run.

## Work needed for the user's full goal

1. Address scientific review A–I with recorded analyses and text changes; the
   original factorial and all four verification stages are already complete.
2. Integrate checked results, practical guidance and figures into one submission
   manuscript; inspect the final rendered layout and references.
3. Complete a clean-environment reproduction and a current evidence package.
   Historical archives do not contain every new component. Public release,
   software licensing and a repository/DOI remain unresolved.
4. The user specified Chinese Academy of Sciences third quartile. Confirm the
   applicable edition/category and the target journal's current requirements. The earlier Scientific Reports screening is conditional, not
   proof of an applicable institutional classification.
5. Finalize corresponding author, contributions, funding, conflicts and author
   approval, including the AI assistance disclosure. These cannot be invented.

The full goal is still in progress. Completion of computation alone does not
mean submission readiness or journal acceptance.
