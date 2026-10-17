"""Summarize audited ten-seed evidence and preserve paired figure source data.

No model fitting, new response search, bootstrap, or manuscript modification.
"""
from pathlib import Path
import os
for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']:
    os.environ[key] = '1'
os.nice(10)
import hashlib, json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent
STAGE = ROOT / 'outputs/core-evidence-audit-v2/analysis/rpl10'
M = 'mean_positive_log_inflation'
METRICS = [M, 'clean_mae', 'attack_mae', 'failed_query_fraction']


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    receipt = json.loads((STAGE / 'completion.json').read_text())
    assert receipt['cells'] == 540 and receipt['fitting_seeds'] == 10
    for name, digest in receipt['artifacts'].items():
        assert sha(STAGE / name) == digest, name
    d = pd.read_csv(STAGE / 'audited_cell_summaries.csv')
    c = pd.read_csv(STAGE / 'paired_contrasts.csv')
    assert len(d) == 540 and not d.duplicated(['dataset', 'seed', 'method', 'budget']).any()
    assert d.groupby(['dataset', 'method', 'budget']).seed.nunique().eq(10).all()
    pairs = []
    for _, row in d.iterrows():
        weight, gap = map(float, row.method.removeprefix('path-').split('-gap-'))
        reference = f'path-0-gap-{gap:g}'
        r = d[(d.dataset == row.dataset) & (d.seed == row.seed) &
              (d.budget == row.budget) & (d.method == reference)]
        assert len(r) == 1
        r = r.iloc[0]
        assert all(r[m] > 0 for m in METRICS[:3])
        result = dict(dataset=row.dataset, seed=int(row.seed), method=row.method,
            reference=reference, budget=float(row.budget), path_weight=weight, gap_weight=gap,
            inflation_reduction_pct=100*(1-row[M]/r[M]),
            honest_mae_change_pct=100*(row.clean_mae/r.clean_mae-1),
            attacked_mae_change_pct=100*(row.attack_mae/r.attack_mae-1),
            failed_query_change_pp=100*(row.failed_query_fraction-r.failed_query_fraction))
        pairs.append(result)
    paired = pd.DataFrame(pairs)
    paired.to_csv(OUT / 'paired_seed_changes.csv', index=False)
    primary = []
    for source in ['synthetic', 'jucars', 'mucars']:
        part = d[(d.dataset == source) & (d.budget == .1)]
        means = part.groupby('method')[METRICS].mean()
        r, v = means.loc['path-0-gap-0.5'], means.loc['path-1-gap-0.5']
        z = paired[(paired.dataset == source) & (paired.budget == .1) &
                   (paired.method == 'path-1-gap-0.5')]
        q = c[(c.dataset == source) & (c.budget == .1) &
              (c.candidate == 'path-1-gap-0.5') & (c.metric == M)].iloc[0]
        primary.append(dict(dataset=source, fitting_seeds=10,
            inflation_reduction_ratio_of_means_pct=100*(1-v[M]/r[M]),
            honest_mae_change_ratio_of_means_pct=100*(v.clean_mae/r.clean_mae-1),
            attacked_mae_change_ratio_of_means_pct=100*(v.attack_mae/r.attack_mae-1),
            failed_query_change_pp=100*(v.failed_query_fraction-r.failed_query_fraction),
            seeds_with_lower_inflation=int((z.inflation_reduction_pct>0).sum()),
            absolute_inflation_improvement=q.reference_minus_candidate,
            marginal_lower=q.lower, marginal_upper=q.upper,
            exploratory_simultaneous_lower=q.simultaneous_lower,
            exploratory_simultaneous_upper=q.simultaneous_upper))
    pd.DataFrame(primary).to_csv(OUT / 'primary_effects.csv', index=False)
    convergence = d[['dataset','seed','method','budget','nonconverged_batch_fraction',
                     'max_remaining_response_regret','mean_remaining_response_regret']].copy()
    convergence.to_csv(OUT / 'convergence_all_cells.csv', index=False)
    report = dict(status='descriptive_scientific_review_completed_figure_update_pending',
        stage_receipt_sha256=sha(STAGE/'completion.json'), primary_effects=primary,
        retained_cells=540, paired_rows=len(paired), excluded_nonconverged_cells=0,
        cells_with_nonconverged_batches=int((d.nonconverged_batch_fraction>0).sum()),
        nonconverged_batch_replays=int(round(10*d.nonconverged_batch_fraction.sum())),
        maximum_remaining_unilateral_regret_log=float(d.max_remaining_response_regret.max()),
        uncertainty='Existing4000 crossed resamples only, fixed fitting/evaluation populations; exploratory, no finite-sample FWER certificate',
        ratio_convention='Headline percentages are ratios of means. Individual-seed plots use paired seed ratios; these are explicitly distinct.',
        manuscript_modified=False, new_training_or_response_search=False,
        input_hashes={str(p.relative_to(ROOT)):sha(p) for p in [STAGE/'audited_cell_summaries.csv',STAGE/'paired_contrasts.csv']})
    (OUT/'review.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
