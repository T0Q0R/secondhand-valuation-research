# Research contract, v1, 2026-10-05

## Objective and authorization

Implement the proposed counterfactual-withholding-gain method, conduct meaningful simulated and public-data experiments, and produce a complete, evidence-grounded applied-AI paper aimed at a currently verified Q3 journal. Acceptance is not an achievable local guarantee. The user has authorized design, implementation, experiments and writing; no repeated planning approval is required.

## Claims and nearest work

C0 (hypothesis): learning post-verification suppression value and feeding policy-aware withholding responses back into valuation improves the accuracy/manipulation/budget frontier over robust valuation plus ordinary information-value acquisition.

C1 (hypothesis): coupling contributes beyond an uplift penalty, masking augmentation, or a suppression head used alone.

C2 (hypothesis): improvements survive honest-data error/bias constraints and different withholding/budget/market settings.

Strategic missing-data regression already exists: Zhang, Liu and Li, *Predictive Analytics with Strategically Missing Data*, DOI 10.1287/ijoc.2019.0947. Strategic-withholding classification: Krishnaswamy et al., AAAI 2021, DOI 10.1609/aaai.v35i6.16694. Joint classifier/audit design is explicitly prior work: Ebrahimi and Franceschetti, arXiv:2609.22534 (2026 preprint). Non-greedy acquisition: Valancius et al., ICML 2024, https://proceedings.mlr.press/v235/valancius24a.html. These identities were inspected in the conversation, but complete manuscript citation verification remains open. The generic combination of auditing and strategic prediction is not the novelty claim.

## Threat model

Four manipulable recorded fields: mileage, transmission, fuel type and body condition. A seller may additionally hide at most two fields whose values existed in the source. It cannot modify values, reveal naturally unavailable values, modify identity fields, or observe ground-truth price through the policy. Mileage/fuel aliases are excluded. The primary simulated objective is to maximize final log-price after the known verification policy, with zero concealment cost; positive concealment costs are sensitivity scenarios. This is a stipulated seller incentive, not an observed behavioral finding.

Each batch shares a hard unit-cost verification capacity. At most one withheld field is revealed per listing. Honest reports have no deliberately withheld field and receive no action. A capacity-aware unilateral best-response search accounts for verification avoidance. Search iterations, restarts, convergence and remaining deviation regret are reported; no exact global optimum, incentive compatibility or Nash-equilibrium guarantee is claimed without proof.

## Method

Mask-augmented CatBoost supplies a common backbone. A small neural residual learns normal price error, error under adaptive withholding, and positive price-gap penalties relative to the same estimator's full-report prediction. The full-report prediction is supervised and regularized toward the fixed backbone; the gap penalty alone is insufficient to prevent price collapse.

An honest sample split separates estimator-fitting records from action-head-fitting records in development. Heads see only the reported state, pre-action prediction and action identity. Their targets are out-of-estimator-sample price-suppression gain (positive upward gap before minus after reveal), squared-log-loss reduction, and pre-reveal risk. Alternate heads and estimator updates for a fixed number of rounds. Full multi-fold cross-fitting and hyperparameter selection are required before final evidence, not assumed from the development split.

## Data and evidence status

1. Synthetic depreciation/condition/mileage generator with a known price mechanism and independent generation seeds; mechanism/size/seed contract frozen before evaluation.
2. JUCars-2024 v2, 10.17632/ddcz486x5t.2, existing processed train/validation for development. Recorded asking prices and seller-reported values only.
3. MUCars-2024 v2, 10.17632/vjrbcb2rrt.2, existing processed train/validation for development. Original duplicate/quality filtering is inherited and must be disclosed.

Historical source-test outcomes have been examined in the previous project. Reuse is retrospective, never fresh confirmatory evidence. The initial runner must not open original source-test label files. Initial synthetic and public validation results are development evidence. A separate frozen final evaluation and sensitivity protocol will follow development; no successful subset is promoted after opening.

## Comparison set and ablations

Same estimator/head records, feature allowlists, split boundaries and capacities for all methods. Select 4--8 baselines from a recorded landscape; development includes native CatBoost, masking-only CatBoost without verification, random/fixed-field/benefit/uncertainty policies, suppression-only, robust valuation with ordinary benefit acquisition, and the full coupled method. Never label a local proxy as an official prior method. Direct strategic-regression and acquisition implementations must be assessed before journal claims.

Required four ablations: remove suppression-value head; remove gap penalty; remove feedback coupling; replace adaptive post-policy attacker by a pre-verification attacker. Retain null and unfavorable outcomes.

## Evaluation and success

Primary budget 10%; full curve 0%, 1%, 5%, 10%, 20%, 30%. Report clean/attacked RMSLE and native-currency MAE, positive final-price inflation vs honest prediction, signed and downward price bias, fraction hiding, field mix, actual used capacity, attacker regret, training/inference time and model size. Compare policies under their own adaptive attackers and under a common transferred attacker to separate deterrence from error changes.

Prespecified candidate success: at least 10% lower mean positive log-price inflation than robust valuation plus ordinary acquisition at 10% budget, with a positive paired **batch-cluster** bootstrap interval, and no more than 5% relative worsening in honest MAE. These are research design thresholds, not expected results. Also report price inflation relative to labels and the corresponding risk--bias tradeoff; lowering every quote is not success. Seeds are stability checks, not independent listings. Cluster resampling conditions on fitted estimators and batch allocation; a bootstrap does not establish population equilibrium or real seller response.

## Paper completion requirements

Runnable source-directed reproduction, three training seeds, final data/attack/budget contrasts, direct-competitor audit, four ablations, confidence intervals, verified references, two structural figures, evidence-derived plots/tables, rendered full LaTeX/PDF manuscript and limitations. Current journal scope/indexing/quartile must be verified from an appropriate source; a previous project's journal choice is not current proof. No fabricated results and no acceptance claim.
