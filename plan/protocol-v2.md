# SAV-Val protocol v2: public action availability and nested target generation

Status: development validation, not final confirmatory evidence. Date: 2026-10-05.

The complete user objective remains implemented algorithm, meaningful experiments and a finished Q3-oriented manuscript. This contract corrects development-v1 and supplements the final-design worklist; it does not redefine completion around another pilot.

## Public query rule

The platform observes reported fields, missingness, its before-query prediction and action identity. It cannot observe whether missingness was natural or deliberate. Every reported-missing field may be queried. If no recorded value existed, the simulated query fails, spends one capacity unit and leaves the reported state unchanged. Simulation-only masks, available source values, honest-reference quotes and reveal outcomes are used only by the training-target construction and seller/environment replay. Action scores must be invariant between observationally identical reported states.

The random-priority control uses a listing/field priority fixed across report candidates, gated by public missingness; its priority is known to the attacker. No hidden-randomness deterrence is claimed.

Development-v1 action gating used the deliberate mask and omitted failed natural-missing queries. Its numeric results remain archived, but are withdrawn as evidence for deployable verification.

## Nested cross-fitting

Assign all selected training records to three outcome-independent balanced outer folds. Each complete fitting loop uses only the outer training records: split those into supervised-price fitting and feedback-guidance fitting; fit common backbones; fit guidance heads; alternate residual and guidance updates. Generate all reported-state quotes on the outer holdout without passing its outcomes into any fitted loop. Assemble the outer predictions and fit deployment heads from these predictions, reported-state encodings, and training outcomes. Head encodings use the deployment valuation encoder and only pre-query information. This estimator-encoding sample-size mismatch is disclosed rather than called exact equivalence.

Outer loop models, split-ID hashes, predictions, assignment files and completion receipts are saved. A terminal run may explicitly resume completed hash-bound folds. Never start a second job merely because observation timed out. Completed source/config snapshots and results are immutable.

## Stronger seller response and independent checking

Development v2 uses twenty sweeps and four starts (honest, pre-query maximizer and two seeded feasible reports), retaining ties and detecting repeated profiles. An independent exhaustive checker re-runs the actual allocator for every feasible unilateral deviation at the returned peer reports. It must agree with the search's regret. Report mean/max regret, repeated-profile flags, query failure, and the maximum unilateral quote envelope. The envelope holds peers fixed; it is not a jointly attainable batch outcome or a global equilibrium bound.

Main development batches contain 100 records, with a final shorter batch. This realizes 1%, 5%, 10%, 20% and 30% capacities as nonzero integer slots, avoiding the zero-slot 1% point of 64-record batches. Every method receives the same batch membership and capacity; the allocator optimizes within batches and does not claim cross-batch global optimality. Capacity is floor(fraction times batch size), and failed queries count as used slots.

## Study scope

Retain synthetic, JUCars and MUCars; seeds 13, 42 and 2026; the twelve development model/policy variants and four targeted ablations; budgets 0%, 1%, 5%, 10%, 20%, 30%; honest MAE/RMSLE, attack MAE/RMSLE, price inflation, signed bias, actual capacity, failed queries and conditional batch-cluster intervals. The crossfit development uses the same maximum 5,000 source-training and 1,000 validation records for direct diagnosis of the corrected mechanism. It is not the final data-size, attack-cost or group-safety experiment.

Primary success criterion remains at least 10% relative lower positive log-price inflation than the ordinary-benefit-head counterpart, positive paired batch-cluster interval, and no more than 5% worse honest MAE. Do not promote successful datasets/seeds or change the criterion after results. None of the old source tests becomes fresh confirmation through this correction.

Final work still includes source-size/attack-cost/hidden-count/natural-missingness contrasts, direct-prior implementation audit, appropriate final freeze, sufficient verified citations, venue standard resolution and full rendered-paper QA.
