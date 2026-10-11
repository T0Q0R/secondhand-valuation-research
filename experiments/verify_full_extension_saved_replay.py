"""Replay all 1296 extension cells from a copied complete evidence collection.

This checks saved deployment quotes, independently constructed public head
scores, allocations, recorded-value replay, metrics and first-batch deviations.
It does not repeat trial selection, OOF fitting or the 54 independent head
refits already recorded by the complete original audits. No fresh fit is allowed.
"""
from __future__ import annotations

import argparse
import builtins
import hashlib
import importlib.machinery
import io
import json
import os
from pathlib import Path
import sys


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    for name in ('tuning-audit', 'tuning-contrasts', 'benefit-audit', 'benefit-contrasts'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    original, output = args.original.resolve(), args.output.resolve()
    assert project != original and Path.cwd().resolve() == project
    assert not output.exists(), 'Fresh saved-model replay output required'
    # Capture this script before installing guards, including import-loader IO.
    verifier_sha256 = sha(Path(__file__))
    manifests = {}
    for name in ('package_manifest.json', 'evidence_manifest.json'):
        path = project.parent/name
        record = json.loads(path.read_text())
        for relative, digest in record['files'].items():
            assert sha(project.parent/relative) == digest, (name, relative)
        manifests[name] = {'sha256': sha(path), 'verified_files': len(record['files'])}
    evidence = json.loads((project.parent/'evidence_manifest.json').read_text())
    assert evidence['full_tuning_and_benefit_extensions_included'] is True
    # A copied collection may live under original/artifacts; deny the actual
    # source/data directories rather than that parent containing the copy.
    denied = [original/name for name in ('experiments', 'outputs', 'notes', 'paper', 'plan', 'tests')]
    denied += [original.parent/'experiments', original.parent/'data']
    denied += [original/name for name in ('README.md', 'REPRODUCING.md', 'paper.config.yaml', 'requirements-lock.txt')]
    attempts = []

    def checked_path(path):
        if isinstance(path, (str, bytes, os.PathLike)):
            resolved = Path(os.fsdecode(path)).resolve()
            if any(resolved.is_relative_to(folder) for folder in denied):
                attempts.append(str(resolved))
                raise PermissionError('Original project read denied: '+str(resolved))

    def guarded(function):
        def checked(path, *positional, **keywords):
            checked_path(path)
            return function(path, *positional, **keywords)
        return checked

    builtins.open, io.open = guarded(builtins.open), guarded(io.open)
    original_loader = importlib.machinery.SourceFileLoader.get_data

    def loader_read(self, path):
        checked_path(path)
        return original_loader(self, path)

    importlib.machinery.SourceFileLoader.get_data = loader_read
    probes = []
    for path in (original/'experiments/savval.py',
                 original.parent/'experiments/data/processed/jucars_bvival_v1/splits/train.csv'):
        try:
            path.read_bytes()
        except PermissionError:
            probes.append(attempts.pop())
        else:
            raise AssertionError('Actual original source/data read was not denied')
    sys.path = [str(project/'experiments'), str(project), *[
        entry for entry in sys.path if entry and
        not any(Path(entry).resolve().is_relative_to(folder) for folder in denied)]]

    import joblib
    import numpy as np
    import pandas as pd
    import torch
    from catboost import CatBoostRegressor
    from sklearn.ensemble import ExtraTreesRegressor
    from threadpoolctl import threadpool_limits
    from analyze_cdm_development import candidate_quotes
    from analyze_equal_tuning_size import audit_execution, close
    from analyze_nested import read, require
    from analyze_resources_and_transfer import scores_independent
    from analyze_saved_diagnostics import audit_cell
    from package_completed_evidence import full_extension_components
    from run_all import load_source
    from savval import ActionHeads, Encoder, FEATURES, Valuator, price_features

    fit_attempts = []

    def reject_fit(*positional, **keywords):
        fit_attempts.append('Fresh fitting attempted')
        raise RuntimeError('Fresh fitting disabled in saved-model replay')

    ExtraTreesRegressor.fit = reject_fit
    CatBoostRegressor.fit = reject_fit
    ActionHeads.fit = reject_fit
    Encoder.fit = reject_fit
    Valuator.train_residual = reject_fit
    torch.optim.Adam.step = reject_fit
    torch.optim.AdamW.step = reject_fit
    try:
        ExtraTreesRegressor().fit([[0], [1]], [0, 1])
    except RuntimeError:
        assert fit_attempts.pop() == 'Fresh fitting attempted'
    else:
        raise AssertionError('Fresh-fitting guard did not reject its actual probe')
    # This gate accepts only complete matched raw -> audit -> statistics chains.
    components = full_extension_components(args)
    assert len(components) == 6
    output.mkdir(parents=True)
    (output/'verifier_snapshot.py').write_bytes(Path(__file__).read_bytes())
    tuning = project/'outputs/equal-tuning-size-development-v1'
    benefit = project/'outputs/equal-benefit-size-reference-development-v1'
    manifest = read(tuning/'manifest.json')
    config = manifest['config']
    pinned = read(project/'notes/source-reproduction-inputs-v1.json')
    inputs, checks = [], []
    expected_kinds = {'sav_val': 'suppression', 'sav_benefit_head': 'benefit',
                      'robust_no_feedback': 'suppression',
                      'robust_benefit_no_feedback': 'benefit'}
    torch.set_num_threads(4)
    with threadpool_limits(limits=4):
        for dataset in config['datasets']:
            for size in manifest['sizes']:
                local = dict(config, max_train=size)
                first, guidance, evaluation, provenance = load_source(dataset, local)
                assert len(evaluation) == 1000
                if dataset != 'synthetic':
                    assert provenance['original_test_labels_read'] is False
                    for role in ('train', 'validation'):
                        path = Path(provenance['source_'+role]).resolve()
                        assert path.is_relative_to(project.parent/'experiments/data/processed')
                        assert provenance[role+'_sha256'] == pinned['processed_sha256'][dataset+'/'+role+'.csv']
                inputs.append({'dataset': dataset, 'size': size, 'provenance': provenance})
                for seed in config['seeds']:
                    for role, run in (('tuning', tuning), ('ordinary_BEN', benefit)):
                        folder = run/dataset/f'size-{size}'/f'seed-{seed}'
                        done = read(folder/'evaluation_completion.json')
                        for name, digest in done['files'].items():
                            assert sha(folder/name) == digest, (role, folder, name)
                        deployed = joblib.load(folder/'deployment_models.joblib')
                        methods = ('robust_no_feedback', 'sav_val', 'sav_benefit_head') if role == 'tuning' else ('robust_benefit_no_feedback',)
                        expected = {f'{variant}__{method}' for variant in ('fixed', 'tuned') for method in methods}
                        assert set(deployed) == expected
                        outcomes = pd.read_csv(folder/'outcomes.csv.gz')
                        summary = pd.read_csv(folder/'summary.csv')
                        assert len(summary) == len(expected)*6
                        assert (summary.actual_train_count == len(first)+len(guidance)).all()
                        for name, (model, head, kind) in deployed.items():
                            assert kind == expected_kinds[name.split('__')[1]]
                            pred, x, valid = model.predict(price_features(evaluation, FEATURES[dataset]))
                            scores = scores_independent(head, x, pred,
                                model.space.reported_missing(evaluation), kind)
                            for budget in config['budgets']:
                                rows = outcomes[(outcomes.method == name) & (outcomes.budget == budget)].reset_index(drop=True)
                                assert rows.listing_id.tolist() == evaluation.listing_id.tolist()
                                close(rows.target_log, evaluation.target_log, 'Copied source targets')
                                report = summary[(summary.method == name) & (summary.budget == budget)]
                                assert len(report) == 1
                                metric_count = audit_cell(rows, report.iloc[0], local['maximum_hidden'], local['batch_size'])
                                audit_execution(pred, scores, valid, rows.state.to_numpy(int),
                                    rows.final_state.to_numpy(int), rows.action.to_numpy(int),
                                    rows.best_response_regret_log.to_numpy(), model.space, local, budget)
                                close(rows.clean_prediction_log, pred[:, 0], 'Copied honest quotes', 2e-6)
                                close(rows.attacked_prediction_log, pred[np.arange(len(rows)), rows.final_state.to_numpy(int)], 'Copied attacked quotes', 2e-6)
                                stop = local['batch_size']
                                quotes = candidate_quotes(pred[:stop], scores[None, :stop],
                                    rows.state.iloc[:stop].to_numpy(int), model.space,
                                    int(np.floor(budget*stop)))[..., 0]
                                envelope = np.maximum(np.where(valid[:stop], quotes, -np.inf).max(axis=1)-pred[:stop, 0], 0)
                                close(rows.unilateral_inflation_envelope_log.iloc[:stop], envelope, 'Copied first-batch unilateral envelope', 1e-8)
                                checks.append({'study': role, 'dataset': dataset, 'size': size,
                                    'seed': seed, 'method': name, 'budget': budget,
                                    'rows': len(rows), 'metrics': metric_count})
                        print(f'REPLAYED COMPLETE EXTENSION {role}/{dataset}/{size}/{seed}', flush=True)
    data = pd.DataFrame(checks)
    assert len(data) == 1296
    assert data.groupby('study').size().to_dict() == {'ordinary_BEN': 324, 'tuning': 972}
    assert int(data.rows.sum()) == 1296000
    assert not fit_attempts and not attempts
    modules = {}
    for name in ('savval', 'run_all', 'analyze_equal_tuning_size',
                 'analyze_resources_and_transfer', 'analyze_saved_diagnostics',
                 'package_completed_evidence'):
        path = Path(sys.modules[name].__file__).resolve()
        assert path.is_relative_to(project/'experiments'), (name, path)
        modules[name] = {'path': str(path), 'sha256': sha(path)}
    data.to_csv(output/'cell_checks.csv', index=False)
    record = {'status': 'completed', 'tuning_cells_replayed': 972,
        'ordinary_BEN_cells_replayed': 324, 'outcome_rows_replayed': 1296000,
        'copied_collection_manifests': manifests, 'source_inputs': inputs,
        'loaded_copied_modules': modules, 'original_read_denial_probes': probes,
        'unexpected_original_read_attempts': attempts, 'fresh_fitting_attempts': fit_attempts,
        'actual_extra_trees_fit_guard_probe_rejected': True,
        'verifier_sha256': verifier_sha256,
        'cell_checks_sha256': sha(output/'cell_checks.csv'),
        'scope': 'All complete extension saved deployment models/outcomes replayed with independently constructed public scores and allocation/metric/first-batch deviation checks. Python IO/import-loader guards, not OS sandboxing. No fresh fitting or repetition of original full trial/OOF/head-refit audits.'}
    (output/'completion.json').write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')
    print('COMPLETED FULL EXTENSION SAVED-MODEL COPY REPLAY', flush=True)


if __name__ == '__main__':
    main()
