"""Descriptive matched-arm impact of the archived external numerical mismatch.

No new fitting, tests, confidence intervals or acceptance-threshold changes.
One fitting seed remains one seed; diagnostic repeats are not new replication.
"""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    with path.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    return rows


def main():
    base = ROOT / 'notes/external-reproduction-synthetic-v1'
    contract_path = ROOT / 'reproduction/macos-core-v2/contract.json'
    contract = json.loads(contract_path.read_text())
    reference = ROOT / 'reproduction/macos-core-v2/expected-core-values.csv'
    if digest(reference) != contract['reference_summary_sha256']:
        raise ValueError('Original reference summary changed')
    expected = {(float(b), method) for b in [0., .1, .3]
                for method in ['path-0-gap-0.5', 'path-1-gap-0.5']}
    reference_rows = {(float(x['budget']), x['method']): x for x in read(reference)
                      if x['dataset'] == 'synthetic' and int(x['seed']) == 13}
    if set(reference_rows) != expected:
        raise ValueError('Incomplete reference subset')
    outcomes, strict, hashes = [], {}, {}
    for label, directory in [('external', 'returned'), ('local', 'local-fresh')]:
        summary_path = base / directory / 'summary.csv'
        receipt = json.loads((summary_path.parent / 'external-training-receipt.json').read_text())
        if digest(summary_path) != receipt['summary_sha256'] or receipt['contract_sha256'] != digest(contract_path):
            raise ValueError('Input summary or contract hash mismatch')
        hashes[label] = digest(summary_path)
        rows = read(summary_path)
        keyed = {(float(x['budget']), x['method']): x for x in rows}
        if len(rows) != 6 or set(keyed) != expected:
            raise ValueError('Expected six unique matched cells')
        if any(x['dataset'] != 'synthetic' or int(x['seed']) != 13 or int(x['n']) != 1000 for x in rows):
            raise ValueError('Wrong population/seed')
        strict[label] = {}
        for metric in contract['comparison_metrics']:
            differences = [abs(float(keyed[k][metric]) - float(reference_rows[k][metric])) for k in expected]
            passed = [abs(float(keyed[k][metric]) - float(reference_rows[k][metric])) <=
                      contract['metric_atol'] + contract['metric_rtol'] * abs(float(reference_rows[k][metric])) for k in expected]
            strict[label][metric] = dict(cells_within_original_tolerance=sum(passed), cells=6,
                                         maximum_absolute_difference=max(differences))
        for budget in [0., .1, .3]:
            a, b = keyed[(budget, 'path-0-gap-0.5')], keyed[(budget, 'path-1-gap-0.5')]
            reduction = 100 * (1 - float(b['mean_positive_log_inflation']) / float(a['mean_positive_log_inflation']))
            honest = 100 * (float(b['clean_mae']) / float(a['clean_mae']) - 1)
            attacked = 100 * (float(b['attack_mae']) / float(a['attack_mae']) - 1)
            envelope_reduction = 100 * (1 - float(b['mean_unilateral_inflation_envelope_log']) / float(a['mean_unilateral_inflation_envelope_log']))
            outcomes.append(dict(machine=label, budget=budget,
                inflation_reduction_percent=reduction, honest_mae_change_percent=honest,
                attacked_mae_change_percent=attacked,
                failed_query_change_percentage_points=100 * (float(b['failed_query_fraction']) - float(a['failed_query_fraction'])),
                fixed_peer_unilateral_envelope_reduction_percent=envelope_reduction,
                maximum_remaining_unilateral_regret=float(b['max_remaining_response_regret']),
                nonconverged_batches=round(10 * float(b['nonconverged_batch_fraction'])),
                batches=10,
                descriptive_legacy_10pct_5pct_screen=reduction >= 10 and honest <= 5,
                pareto_dominates_on_inflation_honest_attack_failed_queries=(reduction >= 0 and honest <= 0 and attacked <= 0 and float(b['failed_query_fraction']) <= float(a['failed_query_fraction']))))
    output = base / 'impact-assessment'
    output.mkdir(exist_ok=True)
    with (output / 'matched-effects.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(outcomes[0]))
        writer.writeheader()
        writer.writerows(outcomes)
    report = dict(
        scope='Post-hoc descriptive comparison; synthetic fixed cohort, seed13 only, two platforms, three paired capacities',
        training_seeds_per_platform=1, evaluation_listings_shared_across_methods=1000,
        batches_shared_across_methods=10, independent_seed_replication_added_by_onepass_repeats=0,
        summary_sha256=hashes, original_strict_tolerance=dict(atol=contract['metric_atol'], rtol=contract['metric_rtol']),
        strict_checks_recomputed=strict,
        matched_effects=outcomes,
        legacy_screen_scope='Uses the study existing 10% inflation/5% honest-MAE descriptive screen post hoc on a new subset; not a prespecified RPL/external acceptance rule, not a replacement for original numerical tolerance.',
        envelope_scope='Maximum unilateral quote for each seller fixing the returned peer reports, from archived exhaustive unilateral audit; not a bound over arbitrary simultaneous deviations or all equilibria.',
        inferential_tests_performed=False, confidence_intervals_computed=False,
        limitations=['One fitting seed and one synthetic cohort cannot establish general scientific-effect equivalence or all-source ranking stability.',
                     'Honest MAE and failed-query costs retain their adverse tradeoffs; there is no Pareto dominance on the four reported objectives.',
                     'Residual-regret magnitudes and nonconverged-batch counts differ; no incentive compatibility or converged-equilibrium guarantee is established.',
                     'Full core audit and ten-seed production remain separate work.'],
        decision='Retain all old evidence and strict numerical failure; no additional external manual diagnostics. Keep existing ten-seed/core audits running, then integrate the bounded scientific effect and numerical reproducibility limitations. Do not alter frozen training, relax tolerances or upgrade to universal superiority.')
    (output / 'impact-assessment.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(outcomes, indent=2))


if __name__ == '__main__':
    main()
