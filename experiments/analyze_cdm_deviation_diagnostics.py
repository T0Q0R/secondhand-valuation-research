"""Independent all-matrix and public-score audit of common-profile deviations."""
from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from threadpoolctl import threadpool_limits

from analyze_nested import read, require, sha
from analyze_cdm_development import candidate_quotes, allocate_independent, scores_independent, close
from run_all import load_source, write_json
from savval import StateSpace, FEATURES, price_features


def independent_measures(values):
    values = np.asarray(values, float).ravel()
    descending = np.sort(values)[::-1]
    mass = len(values) * .05
    weights = np.clip(mass - np.arange(len(values)), 0, 1) / mass
    return {'mean_envelope': float(np.mean(values)),
            'maximum_envelope': float(np.max(values)),
            'p95_envelope': float(np.quantile(values, .95)),
            'cvar95_envelope': float(descending @ weights)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); run, output = args.run.resolve(), args.output.resolve()
    manifest, completed = read(run/'manifest.json'), read(run/'completion.json')
    require(completed['status'] == 'completed', 'Completed diagnostic generation')
    require(sha(run/'manifest.json') == completed['manifest_sha256'], 'Diagnostic manifest binding')
    for name, digest in completed['files'].items():
        require(sha(run/name) == digest, 'Diagnostic output binding')
    for path, digest in manifest['root_input_hashes'].items():
        require(sha(Path(path)) == digest, 'Original source generation unchanged')
    for path, digest in manifest['source_hashes'].items():
        require(sha(run/'source_snapshot'/Path(path).name) == digest, 'Diagnostic source snapshot')
    require(not output.exists(), 'Fresh independent audit')
    output.mkdir(parents=True)
    (output/'auditor_snapshot.py').write_bytes(Path(__file__).read_bytes())
    auditor_sources = {str(Path(__file__).resolve()): sha(Path(__file__)),
                       str(Path(__file__).with_name('analyze_cdm_development.py').resolve()):
                       sha(Path(__file__).with_name('analyze_cdm_development.py'))}
    write_json(output/'input_binding.json', {'manifest_sha256': sha(run/'manifest.json'),
               'completion_sha256': sha(run/'completion.json'), 'auditor_sources': auditor_sources})
    original = Path(manifest['source_run']); original_manifest = read(original/'manifest.json')
    require(manifest['methods'] == original_manifest['policies'] + ['uniform', 'cdm'], 'All original methods')
    expected_pairs = [['synthetic', 13]] if manifest['execution_smoke'] else original_manifest['pairs']
    expected_budgets = [0., .1] if manifest['execution_smoke'] else original_manifest['config']['budgets']
    require(manifest['pairs'] == expected_pairs and manifest['budgets'] == expected_budgets,
            'Preserved source/seed/capacity scope')
    scheduled = {(d, s, p, b) for d, s in expected_pairs for p in original_manifest['prices']
                 for b in expected_budgets}
    captured = [(c['dataset'], c['seed'], c['price'], c['budget']) for c in completed['case_receipts']]
    require(len(captured) == len(scheduled) and set(captured) == scheduled, 'Every scheduled case exactly once')
    summaries = pd.read_csv(run/'summary.csv'); batch_summary = pd.read_csv(run/'batch_summary.csv')
    space = StateSpace.build(manifest['maximum_hidden']); source_frames = {}
    for dataset, _ in manifest['pairs']:
        if dataset not in source_frames:
            _, _, frame, _ = load_source(dataset, original_manifest['parent_config'])
            source_frames[dataset] = frame
    checked, matrix_checks, allocation_checks = [], 0, 0
    arrays_cache, model_files = {}, {}
    torch.set_num_threads(4)
    with threadpool_limits(limits=4):
        for case_record in completed['case_receipts']:
            dataset, seed, price, budget = (case_record[k] for k in ('dataset', 'seed', 'price', 'budget'))
            tag = f'budget-{int(round(budget*10000)):04d}'
            case = run/dataset/f'seed-{seed}'/price/tag
            require(sha(case/'completion.json') == case_record['receipt_sha256'], 'Complete captured case')
            receipt, binding = read(case/'completion.json'), read(case/'input_binding.json')
            for name, digest in receipt['files'].items():
                require(sha(case/name) == digest, 'Case diagnostic bytes')
            for path, digest in binding['files'].items():
                require(sha(Path(path)) == digest, 'Original case inputs')
            key = (dataset, seed, price)
            folder = original/dataset/f'seed-{seed}'/price
            if key not in arrays_cache:
                model_binding = read(folder/'model_binding.json')
                model_path = Path(model_binding['parent_model_path'])
                require(sha(model_path) == model_binding['parent_model_sha256'], 'Frozen price model')
                model_files[str(model_path)] = model_binding['parent_model_sha256']
                require(sha(folder/'head.joblib') == model_binding['head_sha256'], 'Frozen public-score head')
                model, _, _ = joblib.load(model_path); head = joblib.load(folder/'head.joblib')
                frame = source_frames[dataset]
                ids = pd.read_csv(folder.parent/'evaluation_ids.csv').listing_id.astype(str).tolist()
                require(ids == frame.listing_id.astype(str).tolist(), 'Source evaluation membership')
                with np.load(folder/'evaluation_arrays.npz') as stored:
                    pred, scores, valid = (stored[k] for k in ('pred', 'scores', 'valid'))
                actual, x, actual_valid = model.predict(price_features(frame, FEATURES[dataset]))
                close(pred, actual, 'Immutable prediction reconstruction', 2e-6)
                require(np.array_equal(valid, actual_valid), 'Legal reports from original observed fields')
                rebuilt = scores_independent(frame.listing_id, x, actual,
                                              space.reported_missing(frame), space, head)
                require(np.array_equal(np.isfinite(scores), np.isfinite(rebuilt)), 'Public score eligibility')
                close(scores[np.isfinite(rebuilt)], rebuilt[np.isfinite(rebuilt)], 'Independent raw public-score input', 1e-10)
                arrays_cache[key] = (pred, scores, valid, ids)
            pred, scores, valid, ids = arrays_cache[key]
            n = len(binding['listing_ids'])
            require(binding['listing_ids'] == ids[:n], 'Diagnostic cohort prefix')
            old = folder/tag; solution = read(old/'fit/solution.json')
            k = len(original_manifest['policies'])
            alpha = np.vstack((np.eye(k), np.full(k, 1/k), solution['probabilities']))
            require(binding['calibration_selected_pure'] == solution['best_training_pure_policy'],
                    'No held-out reference selection')
            with np.load(case/'deviations.npz') as stored:
                saved = {name: stored[name] for name in stored.files}
            close(saved['probabilities'], alpha, 'Immutable probability choices', 1e-12)
            reports = []
            for method in ('suppression', 'benefit'):
                frame = pd.read_csv(old/method/'outcomes.csv.gz')
                require(frame.listing_id.astype(str).tolist() == ids, 'Saved response membership')
                reports.append(frame.state.to_numpy(int))
            profiles = read(case/'profiles.json'); require(len(profiles) == 5*int(np.ceil(n/manifest['batch_size'])),
                                                         'Every fixed profile in every batch')
            profile_keys = [(p['batch'], p['profile']) for p in profiles]
            scheduled_profiles = {(b, p) for b in range(int(np.ceil(n/manifest['batch_size']))) for p in range(5)}
            require(len(profile_keys) == len(scheduled_profiles) and set(profile_keys) == scheduled_profiles,
                    'Every common profile exactly once')
            matrices, locators, envelopes, best_states, entry_locators = [], [], [], [], []
            case_batches = {}
            for profile in profiles:
                batch, scenario, start = (profile[k] for k in ('batch', 'profile', 'start'))
                require(start == batch*manifest['batch_size'] and scenario in range(5), 'Profile locator')
                stop = min(start+manifest['batch_size'], n)
                legal = valid[start:stop]
                generator = np.random.default_rng(603)
                bank = [np.zeros(stop-start, int),
                        np.argmax(np.where(legal, pred[start:stop], -np.inf), axis=1),
                        np.array([generator.choice(np.flatnonzero(v)) for v in legal]),
                        reports[0][start:stop], reports[1][start:stop]]
                states = np.asarray(profile['states'], int)
                require(np.array_equal(states, bank[scenario]), 'Independently reconstructed common profile')
                cap = int(np.floor(budget*(stop-start)))
                quotes = candidate_quotes(pred[start:stop], scores[:, start:stop], states, space, cap)
                signed = quotes - quotes[:, 0:1, :] - manifest['cost']*space.masks.sum(axis=1)[None, :, None]
                matrices.append(signed[legal]); where = np.argwhere(legal)
                locators.append(np.c_[np.full(len(where), batch), np.full(len(where), scenario),
                                       where[:, 0]+start, where[:, 1]])
                expected = signed @ alpha.T
                expected[~legal] = -np.inf
                envelope = np.maximum(np.max(expected, axis=1), 0.)
                envelopes.append(envelope); best_states.append(expected.argmax(axis=1))
                entry_locators.append(np.c_[np.full(stop-start, batch), np.full(stop-start, scenario),
                                            np.arange(start, stop)])
                case_batches.setdefault(batch, []).append(envelope)
                for rule in range(k):
                    _, actions = allocate_independent(scores[rule, start:stop], states, space, cap)
                    require(int((actions >= 0).sum()) == profile['query_counts'][rule], 'Actual profile query count')
                    require((actions >= 0).sum() <= cap, 'Hard capacity includes unsuccessful queries')
                    allocation_checks += 1
                matrix_checks += 1
            close(np.concatenate(matrices), saved['matrix'], 'Every signed candidate-deviation row', 1e-10)
            require(np.array_equal(np.concatenate(locators), saved['locator']), 'Every legal report locator')
            close(np.concatenate(envelopes), saved['envelopes'], 'Expectation-before-max envelopes', 1e-10)
            require(np.array_equal(np.concatenate(best_states), saved['best_states']), 'Maximizing report/tie convention')
            require(np.array_equal(np.concatenate(entry_locators), saved['entry_locator']), 'Equal listing/profile weights')
            values = np.concatenate(envelopes)
            selected = summaries[(summaries.dataset == dataset)&(summaries.seed == seed)&
                                 (summaries.price == price)&(summaries.budget == budget)]
            require(len(selected) == len(manifest['methods']), 'Every retained diagnostic method')
            for j, method in enumerate(manifest['methods']):
                row = selected[selected.method == method]; require(len(row) == 1, 'Unique method summary')
                stats = independent_measures(values[:, j])
                for name, value in stats.items(): close(row.iloc[0][name], value, 'Whole-case '+name, 1e-10)
                checked.append({'dataset': dataset, 'seed': seed, 'price': price, 'budget': budget,
                                'method': method, **stats})
                for batch, block in case_batches.items():
                    row = batch_summary[(batch_summary.dataset == dataset)&(batch_summary.seed == seed)&
                                        (batch_summary.price == price)&(batch_summary.budget == budget)&
                                        (batch_summary.batch == batch)&(batch_summary.method == method)]
                    require(len(row) == 1, 'Every paired batch summary')
                    for name, value in independent_measures(np.concatenate(block)[:, j]).items():
                        close(row.iloc[0][name], value, 'Batch '+name, 1e-10)
            for path, digest in binding['files'].items():
                require(sha(Path(path)) == digest, 'Case inputs unchanged during audit')
            print(f'AUDITED COMMON-PROFILE DIAGNOSTIC {dataset}/{seed}/{price}/{budget}', flush=True)
    require(len(checked) == completed['cells'] == len(summaries), 'Complete method-cell scope')
    pd.DataFrame(checked).to_csv(output/'audited_summary.csv', index=False)
    for path, digest in {**manifest['root_input_hashes'], **auditor_sources, **model_files}.items():
        require(sha(Path(path)) == digest, 'Source/auditor unchanged at completion')
    require(sha(run/'completion.json') == read(output/'input_binding.json')['completion_sha256'], 'Diagnostic generation unchanged')
    write_json(output/'completion.json', {'status': 'completed', 'execution_smoke': manifest['execution_smoke'],
               'cells': len(checked), 'cases': completed['cases'], 'matrix_profiles': matrix_checks,
               'actual_profile_rule_allocations': allocation_checks,
               'input_binding_sha256': sha(output/'input_binding.json'),
               'files': {p.name: sha(p) for p in output.iterdir() if p.is_file()},
               'scope': 'all source-score reconstructions, profiles, legal rows, mixtures, '
                        'maximizing states and whole-case/batch tail metrics; no unseen-market guarantee'})
    print('COMPLETED INDEPENDENT COMMON-PROFILE DEVIATION AUDIT', flush=True)


if __name__ == '__main__':
    main()
