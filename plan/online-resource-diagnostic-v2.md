# Online resource diagnostic, frozen before execution

Benchmark the completed parent run's four principal 10%-capacity methods:
masking/benefit, robust/no-feedback, SAV/benefit-output and full SAV-Val.
Use every scheduled source/seed and saved seller report. Require parent
completion; no fitting, new seller search, outcome tuning or source selection.

Implement the actual public-report path: encode and quote the current report,
score its publicly missing fields, choose at most one field per listing under
the same positive-score top-capacity rule, replay selected recorded values
through a separate environment callback, then quote the resulting public
reports. Do not time enumeration of all eleven private source states as online
inference. Check queries and final quotes against the completed parent's
saved outcome cells before collecting timings. Any disagreement fails the
benchmark rather than changing the saved seller reports or parent models.

Torch, CatBoost prediction and ExtraTrees scoring use four CPU threads.
For each saved batch use two warmups and twenty measured repetitions;
retain all component and total timings, model-file bytes, model/input hashes
and environment metadata. Dataset loading, model loading and preparation of
the stipulated seller reports are excluded. Each timed call includes current
report preprocessing, valuation, head scoring, allocation, replay overhead
and whole-batch final revaluation. No cached counterfactual prediction grid is
used. Replay overhead is a software callback, **not** physical inspection or
human seller response latency. This is a CPU inference diagnostic on a shared
workstation, not a production load test or an exclusive-hardware benchmark.

Record the parent's completed outer/deployment fit-stage timings separately.
Those aggregate timings cover the shared twelve-method fitting matrix, not
an attributable training cost for an individual method. Parent total wall time
also includes head reconstruction, evaluation and artifact I/O. Do not infer
per-method training speedups, energy consumption or memory peaks from these
aggregate numbers. Fair-tuning/retraining cost attribution remains separate.

An explicit execution-smoke flag uses one warmup/two repeats solely to check
the path on a completed smoke parent. It is labeled execution evidence and
must never replace the twenty-repeat final diagnostic.
