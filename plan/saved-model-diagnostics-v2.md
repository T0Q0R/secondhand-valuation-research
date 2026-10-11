# Frozen-model diagnostics after nested development v2

Prepare date: 2026-10-05, while corrected real-source development remains in progress. This is an explicitly retrospective follow-up, not a fresh confirmatory experiment. Run only after the parent experiment completes, using exactly its source generation and saved estimators.

All three sources and three seeds; common 10% batch capacity; identical evaluation membership and four controls (masking + ordinary benefit, robust without feedback, SAV-Val, ordinary-benefit counterpart). Sensitivities:

- Concealment costs 0.02 and 0.05 per hidden field, in stipulated log-quote payoff units; primary cost zero stays visible.
- Allowed maximum hidden fields one and three. The models remain trained with maximum two. Three-hidden evaluation is an explicit attack-extent shift, not retraining with three-hidden augmentation.
- Extra independently generated natural missingness probabilities 10% and 30%, same deterministic listing/field draws for every policy. These newly unavailable source values cannot be recovered and attempted queries still spend capacity. The target price stays unchanged.
- Original main-result strata with 0, 1, or 2+ naturally missing optional fields. Report counts, honest/attacked error, signed bias, query rate and failed-query rate; do not claim demographic fairness from these technical strata.
- Generic no-query disclosure-monotone closure of the common masking backbone. Its zero-uplift guarantee is a diagnostic; retain honest price error and upward bias, and disclose full-lattice mask generalization.

The script verifies that saved estimators reproduce parent honest quotes before changing a scenario, binds source/model bytes before and after, and stores per-listing results. Runtime is measured on the shared research workstation and must not be advertised as a controlled hardware efficiency benchmark.

Command: `../.venv-gdfs/bin/python experiments/run_saved_diagnostics.py --run outputs/nested-development-v2 --output outputs/saved-model-diagnostics-v2`.

These diagnostics do not replace a direct SMI reproduction, retrained source-size sensitivity, fair tuning, final paper evidence freeze, result auditing or manuscript QA. Do not silently drop the simpler robust control or choose a successful market/seed after outcomes.
