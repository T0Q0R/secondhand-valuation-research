# Ten-seed original-protocol union

Source coverage: synthetic, jucars, mucars.
Every included source has all ten predetermined seeds. Other planned sources remain outside this staged union.

Intervals are exploratory unadjusted95% percentile intervals over1000 resamples.
The crossed seed/batch interval quantifies fitting-seed and shared-evaluation-batch variation on fixed training records, not training-population uncertainty.
sav_benefit_head is the original feedback-trained benefit-head variant, not the separately tuned ordinary-benefit robust comparator.

| Source | Reference | SAV inflation | Reference inflation | Relative reduction | Seed+batch interval |
|---|---|---:|---:|---:|---|
|synthetic|sav_benefit_head|0.021175|0.016847|-25.69%|[-0.007774, -0.001215]|
|synthetic|robust_no_feedback|0.021175|0.012084|-75.23%|[-0.012355, -0.006323]|
|synthetic|masking_benefit|0.021175|0.050328|57.93%|[0.024928, 0.033582]|
|synthetic|sav_no_gap|0.021175|0.038181|44.54%|[0.014282, 0.019794]|
|synthetic|sav_preaudit_attacker|0.021175|0.013619|-55.48%|[-0.010444, -0.004923]|
|jucars|sav_benefit_head|0.014988|0.016240|7.71%|[-0.000172, 0.002946]|
|jucars|robust_no_feedback|0.014988|0.012082|-24.05%|[-0.007025, 0.000777]|
|jucars|masking_benefit|0.014988|0.020018|25.13%|[0.001649, 0.007985]|
|jucars|sav_no_gap|0.014988|0.034576|56.65%|[0.016131, 0.023292]|
|jucars|sav_preaudit_attacker|0.014988|0.013951|-7.43%|[-0.002428, 0.000303]|
|mucars|sav_benefit_head|0.007340|0.007090|-3.53%|[-0.001092, 0.000488]|
|mucars|robust_no_feedback|0.007340|0.006511|-12.73%|[-0.001870, 0.000210]|
|mucars|masking_benefit|0.007340|0.047082|84.41%|[0.036708, 0.042906]|
|mucars|sav_no_gap|0.007340|0.022964|68.04%|[0.014036, 0.017120]|
|mucars|sav_preaudit_attacker|0.007340|0.007919|7.32%|[-0.000212, 0.001238]|

Positive differences favor SAV. Negative findings and all method/capacity cells are retained.
The audit checks recorded training/split bindings and metric/replay arithmetic; it does not establish unseen-market guarantees or retrain models independently.
