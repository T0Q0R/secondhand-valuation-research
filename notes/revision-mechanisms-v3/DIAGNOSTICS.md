# Frozen-outcome mechanism diagnostics (post-hoc, 2026-10-14)

Run `../.venv-gdfs/bin/python notes/revision-mechanisms-v3/diagnose.py` from sav-val. No models are trained and no seller responses are recomputed. Existing immutable outcomes and batch means are hash-bound in completion.json. paired_differences.npz is sufficient for redoing the conditional variance calculations without models or listing records.

## Seed and batch variance

For paired differences Y (S seeds by B batches), seed bootstrap weights U and normalized record-weighted batch bootstrap weights V are independent. Let m=E[V], C=Cov(V), r=Ym-mean(Ym), col=mean_seed(Y), R=Y-col-r. The exact conditional bootstrap variance is:

- seed main: sum(r²)/S²;
- batch main: col' C col;
- interaction: sum_s R_s' C R_s / S².

The script calculates the exact batch-weight moments by conditioning on the multinomial count of the unequal final batch; it does not treat that batch as a full 100-record batch. Two independent exhaustive 2x2 resampling oracles check both equal and unequal weights. The capped and expanded first-ten-batch differences agree within 2e-15.

For MUCars masking/suppression top-B and minimax, seed-main shares are 90.97% / 87.42% capped and 98.39% / 98.28% uncapped. Width-ratio inversion does not identify these components because seed effects also change with the cohort and the percentile intervals use different draws. Under the empirical conditional distribution, a hypothetical 30 rather than 10 independent seed draws projects standard deviations to 58.27% / 58.34% of their current values; this is a design calculation, not evidence from 20 new fitted models. Removing only batch resampling noise gives a conditional standard-deviation floor near 99.2% of the current value. New data from a different population can change these quantities. These calculations do not estimate uncertainty from sampling new training populations. A crossing-zero interval does not establish equivalence; no equivalence margin was specified.

## Cost and concealment

For a listing, write C=c*k (k hidden fields), G=max(expected quote - honest quote,0), N=max(best legal utility - truthful utility,0), and rho=best legal utility - returned utility. Truthful utility equals the frozen honest quote because queries to naturally missing fields leave it unchanged. Then:

`C-rho <= G-N <= C`.

Consequently batch mean C lies between max(mean(G)-mean(N),0) and min(max(mean(G)-mean(N)+max(rho),0),2*mean(c)). At zero regret this is equality. Uniform-cost hidden-field bounds divide these by c. Heterogeneous costs range in [.01,.03), so hidden-field bounds use C/.03 and C/.01, not C/mean(c). Positive-cost states were not saved: these are identified bounds, never fabricated counts. The inequality is checked on 768 exhaustive toy utility/return-state cases, including suboptimal returned states. All 20 nonconverged positive-cost batches remain in the 1,440-row diagnostic.

Synthetic top-B, three seeds: zero-cost hidden fields are directly observed as .996 / .957 (no feedback / feedback). Uniform .02 gives bounds [.129978,.165480] / [.130429,.180596]. Net deviation declines by about 77.52% / 81.09% relative to zero cost. Uniform .02 failure per listing is .094667 / .094; at capacity .1 this implies at least 94.67% / 94% of actual queries fail (a lower bound; exact total query use was not saved). Heterogeneous failure is .094 / .093. The feedback inflation difference changes sign from -.000907904 at zero cost to +.000315929 at uniform .02. This co-occurs with strong concealment deterrence; the diagnostics do not causally separate deterrence from response reallocation, changed peer competition, or feedback quality. Both real sources retain adverse feedback inflation directions in all declared cost regimes. Per-source, per-allocator and per-feedback results are retained, not selected by sign.
