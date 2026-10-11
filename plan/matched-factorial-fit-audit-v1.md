# Independent factorial fit audit

9 October 2026. Audit immutable completed fits without changing the live trainer.
Default coverage is every configured source/seed pair. `--completed-only` freezes
the set of currently completed nested fits at audit start and labels the result
as partial coverage; it cannot establish completion of the full experiment.

Reload source records and check training/evaluation separation and bound content.
Reconstruct outer assignments and inner estimator/guidance partitions directly
from the published SHA-256 ranking salts. Check all 24 cell aliases, 14 unique
fits, all stage/model/checkpoint hashes, matched update counts, exact minibatch
permutation hashes, objective/feedback flags, and valid query-mass bounds.
Recompute every held-out prediction with its saved outer model and compare it
to the stored out-of-fold matrix. Check that held-out IDs occur in neither the
estimator nor the guidance partition of their outer fit.

Independently construct deployment-head inputs and suppression/benefit/risk
targets from these held-out matrices, using explicit eligible item/state/action
indices. Refit the ExtraTrees heads with their declared hyperparameters and seed,
then compare every tree's topology, thresholds and values to the saved head.
This validates deployment target provenance and head fitting, not just target
summary statistics. Do not call the training head's matrix or fit helpers.

Preserve per-pair audit checkpoints with input/model/code bindings so the later
full audit can reuse independently checked completed pairs. A changed artifact
invalidates the checkpoint. Read-only audit may run beside a live trainer only
for fits whose completion files already exist; do not read unfinished fits.

Test the audit on the completed end-to-end execution fixture before applying it
to the full-size fits. Reject corrupted split IDs, permutations and held-out
predictions through the same checking functions. This receipt audit does not
independently reproduce every optimizer step or establish real-world performance;
the gradient-loss check and final-outcome audit remain separate requirements.
