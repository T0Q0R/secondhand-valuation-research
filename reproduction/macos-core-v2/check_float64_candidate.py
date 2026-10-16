"""Bounded local engineering check: two RPL arms, one fold, two repeats.

Reuses existing frozen backbones, runs12 residual epochs only; no acquisition
refit, formal market response, or new method performance claim.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import zipfile
import io

for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']:
    os.environ[key] = '1'
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments'))
sys.path.insert(0, str(ROOT / 'reproduction/windows-core-v1'))
import joblib
import numpy as np
import pandas as pd
import torch
from threadpoolctl import threadpool_limits
from portable_split import fold_assignments, inner_split
from run_all import load_source, rank_subset
from savval import FEATURES, price_features
from float64_candidate import Float64Valuator, train_float64_residual


def main():
    started = time.time()
    here = Path(__file__).resolve().parent
    contract = json.loads((here / 'contract.json').read_text())
    def loss_ast(path):
        tree = ast.parse(path.read_text())
        assignment = next(node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'loss' for t in node.targets))
        return ast.dump(assignment, include_attributes=False)
    if loss_ast(here / 'float64_candidate.py') != loss_ast(ROOT / 'experiments/recovery_path_training_v1.py'):
        raise ValueError('Candidate loss expression differs from frozen source')
    with zipfile.ZipFile(ROOT.parent / 'external-reproduction-private-v1/local-onepass-return-v1.zip') as outer:
        with zipfile.ZipFile(io.BytesIO(outer.read('threads-2-repeat-1.zip'))) as inner:
            with np.load(io.BytesIO(inner.read('arrays.npz')), allow_pickle=False) as packed:
                initials = {k: packed[k] for k in packed.files if '__round-0__step--1__initial__parameter__' in k}
    cfg = contract['config']
    est, guide, evaluation, _ = load_source('synthetic', cfg)
    train = rank_subset(pd.concat([est, guide], ignore_index=True), len(est) + len(guide), 'sav-val-cf-training-order-v2')
    fold = fold_assignments(train, 3)
    estimator, _ = inner_split(train.loc[fold != 0], cfg['head_fitting_fraction'])
    rows = []
    for weight in [0., 1.]:
        method = f'path-{weight:g}-gap-0.5'
        source = ROOT.parent / 'external-rpl-local-diagnostic-v1/synthetic' / method / 'outer-0/model.joblib'
        original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        original, _, _ = joblib.load(source)
        hashes = []
        for repeat in [1, 2]:
            candidate = Float64Valuator.from_frozen_backbone(original)
            x = price_features(estimator, FEATURES['synthetic'])
            config = dict(cfg, recovery_path_weight=weight)
            train_float64_residual(candidate, x, estimator.target_log.to_numpy(), config, 13, None, gap_weight=.5, epochs=0)
            for key, parameter in candidate.residual.state_dict().items():
                saved = initials[method + '__outer-0__round-0__step--1__initial__parameter__' + key]
                if not np.array_equal(parameter.numpy(), saved.astype(np.float64)):
                    raise ValueError('Promoted initialization differs from original float32 values')
            candidate.residual = None
            logs = []
            for round_number in [0, 1]:
                logs.extend(train_float64_residual(candidate, x, estimator.target_log.to_numpy(), config,
                    13 + round_number, None, gap_weight=.5, epochs=6))
            if len(logs) != 12 or not all(np.isfinite(row['loss']) for row in logs):
                raise ValueError('Non-finite or incomplete candidate fitting')
            predictions, encoded, valid = candidate.predict(price_features(evaluation, FEATURES['synthetic']))
            if not np.isfinite(predictions).all() or encoded.dtype != np.float64:
                raise ValueError('Candidate dtype/prediction check failed')
            if any(p.dtype != torch.float64 or not torch.isfinite(p).all() for p in candidate.residual.parameters()):
                raise ValueError('Candidate parameter dtype/finite check failed')
            digest = hashlib.sha256(b''.join(v.detach().numpy().tobytes() for v in candidate.residual.state_dict().values())).hexdigest()
            hashes.append(digest)
            rows.append(dict(path_weight=weight, fold=0, repeat=repeat, residual_epochs=12,
                             parameter_sha256=digest, finite_predictions=True, promoted_initialization_matches=True))
        if hashes[0] != hashes[1]:
            raise ValueError('Local float64 candidate repeats differ')
        if hashlib.sha256(source.read_bytes()).hexdigest() != original_hash:
            raise ValueError('Original model file changed')
    report = dict(status='bounded_local_engineering_passed_cross_machine_and_performance_unvalidated',
        scope='One synthetic fitting seed, outer-fold0, two arms and two repeat12-epoch residual fits; no head/refit or market-response evaluation',
        elapsed_seconds=time.time()-started, threads=1, loss_expression_ast_unchanged=True,
        source_sha256=hashlib.sha256((here / 'float64_candidate.py').read_bytes()).hexdigest(), checks=rows,
        original_checkpoint_files_unchanged=True, original_frozen_results_replaced=False,
        cross_machine_execution=False, scientific_effect_equivalence_established=False)
    output = ROOT / 'notes/numerical-stability-v1'
    output.mkdir(exist_ok=True)
    (output / 'candidate-engineering.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    torch.set_num_threads(1)
    with threadpool_limits(limits=1):
        main()
