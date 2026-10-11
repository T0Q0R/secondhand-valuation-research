"""Post-hoc common-profile deviation matrices from frozen CDM predictions."""
from __future__ import annotations

import argparse
from pathlib import Path
import time

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from analyze_nested import read, require, sha
from cdm_mechanism import Market
from cdm_deviation_diagnostics import PROFILE_NAMES, envelopes, measures, profile_bank
from run_all import write_json
from savval import StateSpace


def main():
    parser = argparse.ArgumentParser()
    for name in ('run', 'audit', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--execution-smoke', action='store_true')
    args = parser.parse_args()
    run, audit, output = (p.resolve() for p in (args.run, args.audit, args.output))
    manifest, completed, audited = (read(p) for p in
                                  (run/'manifest.json', run/'completion.json', audit/'completion.json'))
    require(completed['status'] == audited['status'] == 'completed', 'Completed source and independent audit')
    require(completed['all_scheduled_pairs_completed'] and audited['all_scheduled_pairs_completed'],
            'Complete nine-pair CDM input')
    require(not audited['execution_smoke'] and audited['cells'] == 1512, 'Full source evidence')
    require(audited['parent_completion_sha256'] == sha(run/'completion.json'), 'Matching audited generation')
    for name, digest in audited['files'].items():
        require(sha(audit/name) == digest, 'Independent source audit output binding')
    require(not output.exists(), 'Fresh diagnostic generation')
    output.mkdir(parents=True)
    sources = [Path(__file__), Path(__file__).with_name('cdm_deviation_diagnostics.py'),
               Path(__file__).with_name('cdm_mechanism.py'), Path(__file__).with_name('savval.py'),
               Path('plan/cdm-deviation-generalization-v1.md'),
               Path('tests/test_cdm_deviation_diagnostics.py')]
    source_hashes = {str(p.resolve()): sha(p) for p in sources}
    snapshot = output/'source_snapshot'; snapshot.mkdir()
    for p in sources:
        (snapshot/p.name).write_bytes(p.read_bytes())
    root_files = {str(p): sha(p) for p in (run/'manifest.json', run/'completion.json', audit/'completion.json')}
    config = manifest['config']
    pairs = [['synthetic', 13]] if args.execution_smoke else manifest['pairs']
    budgets = [0., .1] if args.execution_smoke else config['budgets']
    methods = manifest['policies'] + ['uniform', 'cdm']
    write_json(output/'manifest.json', {'source_run': str(run), 'source_audit': str(audit),
               'root_input_hashes': root_files, 'source_hashes': source_hashes,
               'pairs': pairs, 'budgets': budgets, 'prices': list(manifest['prices']),
               'methods': methods, 'profile_names': list(PROFILE_NAMES),
               'execution_smoke': args.execution_smoke, 'batch_size': config['batch_size'],
               'evaluation_limit': 200 if args.execution_smoke else None,
               'maximum_hidden': config['maximum_hidden'], 'cost': config['concealment_cost_log'],
               'scope': 'post-hoc common-profile deviation diagnostic; no training or retuning; '
                        'does not replace the primary mean-inflation outcome'})
    space = StateSpace.build(config['maximum_hidden'])
    rows, batch_rows, case_receipts = [], [], []
    begun = time.time()
    with threadpool_limits(limits=4):
        for dataset, seed in pairs:
            pair = run/dataset/f'seed-{seed}'
            ids_all = pd.read_csv(pair/'evaluation_ids.csv').listing_id.astype(str).tolist()
            for price in manifest['prices']:
                price_root = pair/price
                with np.load(price_root/'evaluation_arrays.npz') as stored:
                    pred, scores, valid = (stored[key] for key in ('pred', 'scores', 'valid'))
                n = min(len(pred), 200) if args.execution_smoke else len(pred)
                pred, scores, valid = pred[:n], scores[:, :n], valid[:n]
                ids = ids_all[:n]
                require(len(ids) == n and valid[:, 0].all(), 'Evaluation cohort and truthful legality')
                for budget in budgets:
                    old = price_root/f'budget-{int(round(budget*10000)):04d}'
                    old_done = read(old/'completion.json')
                    require(old_done['status'] == 'completed', 'Completed saved policy outcomes')
                    inputs = [pair/'evaluation_ids.csv', pair/'completion.json',
                              price_root/'evaluation_arrays.npz', price_root/'model_binding.json',
                              price_root/'head.joblib', old/'completion.json', old/'fit/solution.json',
                              old/'suppression/outcomes.csv.gz', old/'benefit/outcomes.csv.gz']
                    hashes = {str(p): sha(p) for p in inputs}
                    for rel in ('fit/solution.json', 'suppression/outcomes.csv.gz', 'benefit/outcomes.csv.gz'):
                        require(sha(old/rel) == old_done['files'][rel], 'Saved profile/probability receipt')
                    controls = []
                    for method in ('suppression', 'benefit'):
                        reports = pd.read_csv(old/method/'outcomes.csv.gz')
                        require(reports.listing_id.astype(str).tolist() == ids_all, 'Ordered saved response cohort')
                        controls.append(reports.state.to_numpy(int)[:n])
                    solution = read(old/'fit/solution.json')
                    k = len(manifest['policies'])
                    probabilities = np.vstack((np.eye(k), np.full(k, 1/k), solution['probabilities']))
                    require(probabilities.shape == (14, 12) and np.allclose(probabilities.sum(axis=1), 1)
                            and (probabilities >= -1e-12).all(),
                            'Original fourteen method weights')
                    case = output/dataset/f'seed-{seed}'/price/f'budget-{int(round(budget*10000)):04d}'
                    case.mkdir(parents=True)
                    write_json(case/'input_binding.json', {'files': hashes, 'listing_ids': ids,
                               'calibration_selected_pure': solution['best_training_pure_policy']})
                    matrices, locators, values, best_states, entry_locators, profiles = [], [], [], [], [], []
                    for batch, start in enumerate(range(0, n, config['batch_size'])):
                        stop = min(start + config['batch_size'], n)
                        block_pred, block_valid = pred[start:stop], valid[start:stop]
                        states_bank = profile_bank(block_pred, block_valid, controls[0][start:stop], controls[1][start:stop])
                        market = Market(block_pred, scores[:, start:stop], block_valid, space,
                                        int(np.floor(budget*(stop-start))), config['concealment_cost_log'])
                        batch_entries = []
                        for profile, states in enumerate(states_bank):
                            signed_rows, where = market.deviation_matrix(states)
                            signed_grid = np.zeros((stop-start, pred.shape[1], k))
                            signed_grid[block_valid] = signed_rows
                            envelope, best = envelopes(signed_grid, block_valid, probabilities)
                            matrices.append(signed_rows)
                            locators.append(np.c_[np.full(len(where), batch), np.full(len(where), profile),
                                                   where[:, 0] + start, where[:, 1]])
                            values.append(envelope); best_states.append(best)
                            entry_locators.append(np.c_[np.full(stop-start, batch), np.full(stop-start, profile),
                                                        np.arange(start, stop)])
                            _, _, profile_actions = market.execute(states)
                            queries = (profile_actions >= 0).sum(axis=0)
                            require((queries <= market.capacity).all(), 'Common-profile actual hard capacity')
                            profiles.append({'batch': batch, 'profile': profile, 'start': start,
                                             'states': states.tolist(), 'query_counts': queries.tolist()})
                            batch_entries.append(envelope)
                        stacked = np.concatenate(batch_entries)
                        for j, method in enumerate(methods):
                            batch_rows.append({'dataset': dataset, 'seed': seed, 'price': price,
                                               'budget': budget, 'batch': batch, 'method': method,
                                               **measures(stacked[:, j])})
                    all_values = np.concatenate(values)
                    for j, method in enumerate(methods):
                        rows.append({'dataset': dataset, 'seed': seed, 'price': price, 'budget': budget,
                                     'method': method, 'n': n, 'profile_entries': len(all_values),
                                     'calibration_selected_pure': solution['best_training_pure_policy'],
                                     **measures(all_values[:, j])})
                    np.savez_compressed(case/'deviations.npz', matrix=np.concatenate(matrices),
                                        locator=np.concatenate(locators), envelopes=all_values,
                                        best_states=np.concatenate(best_states), entry_locator=np.concatenate(entry_locators),
                                        probabilities=probabilities)
                    write_json(case/'profiles.json', profiles)
                    require(all(sha(Path(p)) == digest for p, digest in hashes.items()), 'Immutable case inputs')
                    write_json(case/'completion.json', {'status': 'completed', 'method_cells': len(methods),
                               'input_binding_sha256': sha(case/'input_binding.json'),
                               'files': {p.name: sha(p) for p in case.iterdir() if p.is_file()}})
                    case_receipts.append({'dataset': dataset, 'seed': seed, 'price': price, 'budget': budget,
                                          'receipt_sha256': sha(case/'completion.json')})
                    print(f'COMPLETED COMMON-PROFILE DIAGNOSTIC {dataset}/{seed}/{price}/{budget}', flush=True)
    pd.DataFrame(rows).to_csv(output/'summary.csv', index=False)
    pd.DataFrame(batch_rows).to_csv(output/'batch_summary.csv', index=False)
    require(all(sha(Path(p)) == digest for p, digest in {**root_files, **source_hashes}.items()),
            'Frozen source/root inputs unchanged')
    write_json(output/'completion.json', {'status': 'completed', 'execution_smoke': args.execution_smoke,
               'cells': len(rows), 'cases': len(case_receipts), 'case_receipts': case_receipts,
               'seconds': time.time()-begun, 'manifest_sha256': sha(output/'manifest.json'),
               'files': {p.name: sha(p) for p in output.iterdir() if p.is_file()},
               'scope': 'all captured common-profile matrices and method envelopes; independent audit required'})
    print('COMPLETED CDM COMMON-PROFILE DEVIATION GENERATION', flush=True)


if __name__ == '__main__':
    main()
