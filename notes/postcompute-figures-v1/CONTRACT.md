Python backend reused from existing project workflow. Original figures, no external template.

Figure evidence map:
1 RPL: paired inflation reduction versus paired honest-error and failure costs across all predefined positive path weights; three fitting seeds, mean and full seed range, budget.1/gap.5. Other budgets and gap ablation stay in source table and paper table. No significance claims.
2 Mechanisms: weak/strong search and epoch/batch refresh, all five methods, source-specific seed points; budget.1. Does stronger search rescue feedback? Range is not CI.
3 Recent methods: capacity curves for all five families(defaultACO25), risk/benefit simple controls, two identical frozen price backends, three sources, mean and full seed range. All nonconverged outcomes retained. Solid/dashed and markers supplement color. Honest errors omitted from this plot because identical within backend; full4metrics remain source tables.
4 Factorial: all8 combinations of suppression/feedback/gap, source-specific paired inflation differences from S1F1G1, all3seed points. No single-component attribution from unmatched models.
5 Parameters: inflation sensitivity to gap weight/tolerance/feedback rounds, two capacities, original weak feedback; means/ranges of3seeds. Default not selected from held-out outcomes.
6 Stability: six remaining hyperparameters at primarycapacity, inflation normalized to matched default; plot actual settings, no fabricated defaults. Anchoring/attack-loss/learning-rate/epochs/trees/width default inserted from exactly matching factorial baseline. Means and seed ranges.

EditablePDF/SVG,300dpiPNG; no smoothing/interpolation beyond straight lines between evaluated settings. Independent unit is fitting seed(n=3), shared fixed populations. No erased failed/nonconverged outcomes. Rendered geometry/font/collision audit and visual inspection required. Repeated source panels are deliberate small multiples to display heterogeneity; they are not independent replication or separate claims.
