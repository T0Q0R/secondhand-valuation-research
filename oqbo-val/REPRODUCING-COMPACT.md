# Compact OQBO reproduction

Use Python3.12 and the pinned packages in requirements-compact.txt. Versions
record the tested local environment; a new clean/container environment has
not been independently verified. Run commands from the extracted archive root.
The package includes original32-case oracle inputs and all theoretical outputs.
No vehicle data or training models are required for these constructed checks.

```sh
python oqbo-val/compact_oracle.py --output oqbo-val/outputs/compact-reproduction
python oqbo-val/audit_compact_oracle.py --run oqbo-val/outputs/compact-reproduction --output oqbo-val/outputs/compact-reproduction-audit
python oqbo-val/check_context_mixture_gap.py --output oqbo-val/outputs/context-gap-reproduction
```

Expected counts: compact57 cases,56 enumeration comparisons,3200 exact field
marginals,16000 hard-budget draws. Gap26 exact cases,16 complete-subset LP
pairs,257274 context/item rows,largest ratio440/41. LP floating values may
vary within stated tolerances. The gap check currently emits a SciPy sparse
interface deprecation warning; saved runs finished successfully.

The compact representation is restricted to item-local utility, unit costs,
nonadaptive allocation and at most one queried field per item. The large
fixture is algebraic, not a vehicle-performance result. No first-in-literature,
clean-container or whole-paper completion claim is made.
