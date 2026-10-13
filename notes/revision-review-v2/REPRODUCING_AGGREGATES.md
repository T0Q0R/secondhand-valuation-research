# Bounded aggregate replay

This recipe replays the post-hoc simultaneous sensitivity and threshold grids. It does **not** train models, create a confirmatory cohort, certify finite-sample FWER, or replicate all 4.32 million production records. The completed receipt covers a fresh virtual environment and isolated input tree **on the same physical machine**.

Extract `paper/revision-delivery-v2.zip` into a fresh directory, preserving its project-relative paths. The archive provides the frozen analysis manifest, NPZ tensor, contrast specifications and CSV, plus the earlier allocation contrast CSV/receipt. The script validates their recorded SHA-256 bindings before resampling. It writes only into the extracted revision statistics directory.

Use Python 3.12 and a new environment. Packages tested in the isolated run are pinned in `aggregate-requirements.txt`:

```sh
python3.12 -m venv .aggregate-env
.aggregate-env/bin/python -m pip install -r notes/revision-review-v2/aggregate-requirements.txt
.aggregate-env/bin/python notes/revision-review-v2/statistics/joint_intervals.py
```

Expected: 20,000 crossed resamples, RNG 2026101307, 1,536 primary rows; adverse core-inflation bands 31/27/20 under families 36/108/1536 and 31/27/19 under source-wise Bonferroni sensitivity. Compare numeric table values with the archived CSV at relative/absolute tolerance 1e-12 and compare threshold-grid values exactly. `isolated-replay-receipt.json` records the completed comparison, not a guarantee that every future package version or machine will be bit-identical.

The original full training protocol remains `REPRODUCING_MATCHED_FACTORIAL.md`; public source-data access, weights availability, dependency/runtime provisioning and external end-to-end reproduction remain distinct requirements. No license for unpublished project code is implied by this private evidence package.
