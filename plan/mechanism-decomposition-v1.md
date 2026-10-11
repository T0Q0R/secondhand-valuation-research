# Frozen-model mechanism decomposition contract

2026-10-07. Prospective contract before generating this diagnostic's results.
Use the independently audited full CDM common-profile generation, all nine
source/seed pairs, both fixed price models, all five peer profiles, 1,000
listings per pair, and capacity 0.1. Compare suppression, benefit, risk and
the saved calibrated CDM mixture. No fitting, selection or retuning.

## Necessary correction to the original decomposition proposal

The proposed truthful-allocation anchor is degenerate in this environment.
A truthful seller's queried field is naturally absent; withholding another
field cannot make that queried field recoverable. Therefore frozen truthful
queries have zero own-quote effect. Labeling all remaining change as capacity
competition would conflate recovery with competition.

Instead, for every pure policy and candidate report h, compute its public
highest-scoring eligible field, and its quote after that query with capacity
relaxed. An ineligible/nonpositive score means no query even in this reference.
Let q0 be truthful quote, qh the unqueried hidden quote, qlocal the relaxed
quote and qactual the quote under the original full-batch hard capacity.
At the SAME maximizing h* of each evaluated policy mixture, record:

    estimation = qh - q0
    local_replay = E[qlocal] - qh
    capacity = E[qactual] - E[qlocal]
    total = estimation + local_replay + capacity.

Concealment cost is zero in this saved generation. Expectations precede
maximization. Preserve signed components; never maximize or clip them
separately. The reference relaxes capacity and is only a diagnostic. It is
not a feasible market policy, and component signs need not all be favorable.
With itemwise fixed pricing, truthful queries cannot change q0.

Store local/actual query probability, successful-recovery probability,
failed-query probability, hard-capacity exclusion, all winning states and
the existing envelope. Conditional failure rate is failed/query (undefined
when query=0); failed probability per listing is a different denominator.
The unit is a hypothetical unilateral deviation against one saved peer
profile, not a simultaneously feasible set of all sellers' winning reports.

Validate all numerical rows against saved audited envelope/winner matrices.
Retain saved winning reports when arithmetic rearrangement changes a tie;
require their optimality gap and payoff reconstruction error <=1e-10. The
initial run stopped on an argmax identity check at a measured 8.7e-19 tie;
its partial output remains preserved, and the corrected run uses a fresh path.
An independent script must use full stable sorting of each hypothetical
batch, rather than the generator's pairwise ranking formula. It must check
all rows, input hashes and diagnostic identities, and reject mutations.

This study diagnoses fixed masking/robust estimators and CDM's existing rules.
It does not isolate SAV feedback, identify real-seller behavior, validate OQBO
on an unseen market, or supply ten training seeds. Source summaries average
the three existing seeds; they are descriptive, not population inference.
