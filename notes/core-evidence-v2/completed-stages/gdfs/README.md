Four-phase computational evidence; human scientific review remains pending. Shared loader/model primitives are disclosed. These are aggregate batch/bootstrap artifacts, not source listings or model weights.

To independently re-evaluate the paired statistics from a public clone, run:

```sh
python experiments/check_core_statistics_v2.py --stage gdfs --analysis-dir notes/core-evidence-v2/completed-stages/gdfs --analysis-receipt analysis-completion.json
```

The checker validates every saved analysis artifact hash before reconstructing all resamples. Full fit/outcome execution additionally requires the legitimately reconstructed source data and original model artifacts.
