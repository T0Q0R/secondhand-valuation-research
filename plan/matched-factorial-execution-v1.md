# Full matched factorial execution contract

2026-10-08. Config: experiments/configs/matched-factorial-ten-seeds-v1.json.
Use original training/evaluation sources,3 outer folds,10 predetermined seeds,
24 cells/source/seed. Each cell has the same250-tree backbone architecture,
6 initial residual epochs and6 subsequent residual epochs in2 rounds, and
160-tree action heads. This totals12 residual epochs, matching the original
nominal update-epoch allowance while defining a new controlled intervention.
Do not interpret the initial-estimator factor as unchanged original SAV or
static-robust models. Head and optimizer reset schedules match across cells.
Initial masking/robust branches differ only in their declared objective;
subsequent training uses the common robust loss with/without policy feedback.

Cache the six no-feedback acquisition/allocation aliases explicitly rather
than refitting identical models.14 unique fitted models represent24 cells at
each outer/deployment stage. Actual head targets use whole-loop heldout
predictions. The same inner guidance IDs, minibatch permutations, loss weights,
training response allowance and update count apply within each matched fit.

Checkpoints bind training/guidance contents, seed, config and source hashes.
Resume only after authoritative process termination; take an exclusive lock.
Save each completed initial and final fit atomically; validate artifact hashes
before loading. Never treat a partial fit as completed or relabel smoke output.

Primary evaluation uses10% capacity, then all six original capacities including
zero-query controls. Full evaluation and independent audits remain required.
This config is frozen before any full matched-factorial outcomes; sources were
previously studied, so the experiment remains developmental/exploratory.
No claim of completed factorial evidence follows from a successful smoke run.
