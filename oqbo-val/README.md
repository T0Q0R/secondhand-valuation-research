# OQBO-Val: observable-report budget oracle

New independent theoretical audit work,2026-10-07. The primary manuscript and
its empirical artifacts remain frozen. See
`../notes/design/创新候选-OQBO-Val.md` for definitions, proof and novelty limits,
and `../plan/oqbo-v1-contract.md` for the pre-computation contract.

```sh
../.venv-gdfs/bin/python oqbo-val/finite_oracle.py --output oqbo-val/outputs/finite-demo-01
../.venv-gdfs/bin/python oqbo-val/independent_audit.py \
  --run oqbo-val/outputs/finite-demo-01 \
  --output oqbo-val/outputs/finite-demo-01-audit-01
```

Run from `sav-val/` and use fresh output names for a repeat. The saved32-case
run and independent audit pass. Utility is linear, artificially constructed
quote units, not the empirical study's log-price utility. The privileged
recoverability oracle is not deployable under the same information. The
precision frontier assumes uniform honest absolute-error bounds and
verification-neutral quotes; it does not follow from MAE alone. Full-LP
certificates are numerical1e-8 checks; the analytical witness/lottery is
checked with exact fractions. These results do not certify novelty or unseen
world generalization.

## Compact formulation and contextual gap (2026-10-08)

`compact_oracle.py` implements the exact field-marginal reduction for item-local
utility, unit query costs and at most one queried field per item.
`audit_compact_oracle.py` independently enumerates small allocations, checks LP
dual certificates, and verifies the interval sampler's rational marginals.
`check_context_mixture_gap.py` checks the fixed-global-mixture separation family
using rational witnesses and independent complete-subset LPs.

```sh
../.venv-gdfs/bin/python oqbo-val/compact_oracle.py --output oqbo-val/outputs/compact-v1
../.venv-gdfs/bin/python oqbo-val/audit_compact_oracle.py --run oqbo-val/outputs/compact-v1 --output oqbo-val/outputs/compact-v1-audit
../.venv-gdfs/bin/python oqbo-val/check_context_mixture_gap.py --output oqbo-val/outputs/context-mixture-gap-v1
```

Use fresh output paths when repeating these commands. The saved compact audit
passes57 cases,56 full-enumeration comparisons,3,200 exact field marginals and
16,000 hard-budget draws. The gap family passes26 rational cases and16 full-LP
pairs. Large algebraic fixtures are not real-source efficacy studies. Marginal
optimization is established prior work; the application-specific theorems still
require novelty review. See `../notes/design/紧凑OQBO与固定混合差距.md`.
