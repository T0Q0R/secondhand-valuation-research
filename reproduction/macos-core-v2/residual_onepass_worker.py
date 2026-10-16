"""Trace complete frozen residual fitting on all8 saved backbones; no backbone refitting.

Calls the unchanged frozen training function, observing its line events. The
original checkpoints and results are read-only. This is a diagnostic, never a
replacement fit or a new performance result.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import inspect
import io
import json
import os
import platform
import sys
import zipfile

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
from portable_split import fold_assignments, inner_split, verify_split_origin
from run_all import load_source, rank_subset
from savval import FEATURES, price_features
from recovery_path_training_v1 import train_residual


def sha(data):
    return hashlib.sha256(data).hexdigest()


def content(frame):
    return sha(frame.to_csv(index=False, lineterminator='\n').encode('utf-8'))


class OneThreadBackbone:
    def __init__(self, model):
        self.model = model

    def predict(self, *args, **kwargs):
        return self.model.predict(*args, **dict(kwargs, thread_count=1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--threads', type=int, choices=[1, 2], required=True)
    parser.add_argument('--repeat', type=int, choices=[1, 2], required=True)
    args = parser.parse_args()
    torch.set_num_threads(args.threads)
    run, output = args.run.resolve(), args.output.resolve()
    if output.exists() or output.is_relative_to(run) or output.is_relative_to(ROOT):
        raise ValueError('Use a new diagnostic ZIP outside the repository and original run')
    receipt = json.loads((run / 'inputs.json').read_text(encoding='utf-8'))
    contracts = [ROOT / 'reproduction' / directory / 'contract.json'
                 for directory in ['macos-core-v2', 'windows-core-v1']]
    matches = [p for p in contracts if sha(p.read_bytes()) == receipt['contract_sha256']]
    if len(matches) != 1:
        raise ValueError('Unknown source run contract')
    contract = json.loads(matches[0].read_text(encoding='utf-8'))
    for name, expected in contract['scientific_source_sha256'].items():
        if sha((ROOT / name).read_bytes()) != expected:
            raise ValueError(f'Frozen source mismatch: {name}')
    if receipt['seed'] != 13:
        raise ValueError('This diagnostic is fixed at seed13')
    verify_split_origin(ROOT / 'experiments/run_crossfit.py')
    cfg = contract['config']
    est, guide, evaluation, _ = load_source('synthetic', cfg)
    train = rank_subset(pd.concat([est, guide], ignore_index=True), len(est) + len(guide),
                        'sav-val-cf-training-order-v2')
    if content(train) != contract['population_bindings']['synthetic']['training']:
        raise ValueError('Training population mismatch')
    assigned = fold_assignments(train, 3)
    lines, first_line = inspect.getsourcelines(train_residual)
    checkpoints = {}
    for offset, line in enumerate(lines):
        stripped = line.strip()
        for name, marker in [('initial', 'optimizer = torch.optim.AdamW('),
                             ('before_backward', 'loss.backward()'),
                             ('after_backward', 'nn.utils.clip_grad_norm_('),
                             ('after_clip', 'optimizer.step()'),
                             ('after_update', 'total += float(loss.detach())')]:
            if stripped.startswith(marker):
                checkpoints[first_line + offset] = name
    if len(checkpoints) != 5:
        raise RuntimeError('Frozen training trace markers changed')
    records, arrays, stages = [], {}, []

    def capture(prefix, label, value, detail):
        if torch.is_tensor(value):
            value = value.detach().cpu().numpy()
        value = np.ascontiguousarray(value)
        record = dict(sha256=sha(value.tobytes()), shape=list(value.shape), dtype=str(value.dtype))
        if detail:
            arrays[prefix + '__' + label] = value.copy()
        return record

    for weight in [0., 1.]:
        for fold in [0, 1, 2, None]:
            method = f'path-{weight:g}-gap-0.5'
            stage = 'deployment' if fold is None else f'outer-{fold}'
            directory = run / 'synthetic' / method / stage
            completion = json.loads((directory / 'completion.json').read_text(encoding='utf-8'))
            model_path = directory / 'model.joblib'
            if sha(model_path.read_bytes()) != completion['model_sha256']:
                raise ValueError('Saved checkpoint model hash mismatch')
            fit_rows, guidance = inner_split(train if fold is None else train.loc[assigned != fold], cfg['head_fitting_fraction'])
            expected = dict(estimator=content(fit_rows), guidance=content(guidance), seed=13,
                            path_weight=weight, config=cfg)
            if completion['inputs'] != expected:
                raise ValueError('Saved fitting roles/config mismatch')
            model, _, _ = joblib.load(model_path)  # Only the user's own trusted saved checkpoints.
            saved_parameters = {key: value.detach().clone() for key, value in model.residual.state_dict().items()}
            model.residual = None
            model.backbone = OneThreadBackbone(model.backbone)
            prefix = method + '__' + stage
            step = -1

            def trace(frame, event, argument):
                nonlocal step
                if frame.f_code is not train_residual.__code__:
                    return None
                if event != 'line' or frame.f_lineno not in checkpoints:
                    return trace
                label = checkpoints[frame.f_lineno]
                local = frame.f_locals
                if label == 'before_backward':
                    step += 1
                key = prefix + '__round-' + str(round_number) + '__step-' + str(step) + '__' + label
                detail = step < 3
                state = {name: capture(key, 'parameter__' + name, value, detail)
                         for name, value in model.residual.state_dict().items()}
                item = dict(method=method, stage=stage, round=round_number, step=step, event=label, parameters=state,
                            torch_rng_sha256=sha(torch.get_rng_state().numpy().tobytes()))
                if label != 'initial':
                    item['values'] = {name: capture(key, name, local[name], detail)
                                      for name in ['idx', 'bx', 'bb', 'by', 'final_states',
                                                   'predicted', 'natural', 'adversarial', 'gap',
                                                   'anchoring', 'path_loss', 'loss']}
                    item['gradients'] = {name: capture(key, 'gradient__' + name, param.grad, detail)
                                         for name, param in model.residual.named_parameters()
                                         if param.grad is not None}
                records.append(item)
                return trace

            round_logs = []
            for round_number in [0, 1]:
                step = -1
                previous_trace = sys.gettrace()
                try:
                    sys.settrace(trace)
                    epoch_log = train_residual(model, price_features(fit_rows, FEATURES['synthetic']),
                        fit_rows.target_log.to_numpy(), dict(cfg, recovery_path_weight=weight),
                        13 + round_number, None, gap_weight=.5, epochs=6)
                finally:
                    sys.settrace(previous_trace)
                round_logs.append(epoch_log)
            final_parameters = {key: value.detach().clone() for key, value in model.residual.state_dict().items()}
            parameter_hashes = {key: sha(value.numpy().tobytes()) for key, value in final_parameters.items()}
            equality = all(torch.equal(final_parameters[key], value) for key, value in saved_parameters.items())
            maximum_difference = max(float((final_parameters[key] - value).abs().max())
                                     for key, value in saved_parameters.items())
            pred, _, _ = model.predict(price_features(evaluation, FEATURES['synthetic']))
            for key, value in saved_parameters.items():
                model.residual.state_dict()[key].copy_(value)
            original_pred, _, _ = model.predict(price_features(evaluation, FEATURES['synthetic']))
            observer_control = None
            if fold == 0 and weight == 0. and args.repeat == 1:
                # Same objective without observation must produce the same fit.
                model.residual = None
                for round_number in [0, 1]:
                    train_residual(model, price_features(fit_rows, FEATURES['synthetic']),
                        fit_rows.target_log.to_numpy(), dict(cfg, recovery_path_weight=weight),
                        13 + round_number, None, gap_weight=.5, epochs=6)
                observer_control = all(torch.equal(model.residual.state_dict()[key], value)
                                       for key, value in final_parameters.items())
                if not observer_control:
                    raise RuntimeError('Tracing changed the residual fit; diagnostic invalid')
            stages.append(dict(method=method, stage=stage, original_fit_binding=expected,
                rounds=2, epochs_per_round=6, completed_batches_per_round=step + 1,
                epoch_logs=round_logs, final_parameter_sha256=parameter_hashes,
                saved_parameter_exact_equal=equality, saved_parameter_maximum_difference=maximum_difference,
                saved_log_quote_maximum_difference=float(np.max(np.abs(pred - original_pred))),
                final_evaluation_prediction_sha256=sha(np.ascontiguousarray(pred).tobytes()),
                observer_control_exact_equal=observer_control))
            print('TRACED_FULL_RESIDUAL', args.threads, args.repeat, method, stage,
                  'saved_parameter_match', equality, flush=True)
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **arrays)
    payload = buffer.getvalue()
    result = dict(scope='Diagnostic complete 12 residual epochs on8 saved backbones; no backbone/head refit and no original result changes, no performance claim',
                  source_contract_sha256=receipt['contract_sha256'],
                  probe_sha256=sha(Path(__file__).read_bytes()),
                  frozen_training_sha256=sha((ROOT / 'experiments/recovery_path_training_v1.py').read_bytes()),
                  platform=platform.platform(), python=sys.version, threads=args.threads, repeat=args.repeat,
                  versions={m: importlib.metadata.version(m) for m in ['numpy', 'pandas', 'torch', 'scikit-learn', 'catboost']},
                  torch_build_config=torch.__config__.show(), stages=stages, records=records,
                  arrays_sha256=sha(payload))
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('trace.json', json.dumps(result, indent=2) + '\n')
        archive.writestr('arrays.npz', payload)
    print('SAVED', output, 'bytes', output.stat().st_size, flush=True)


if __name__ == '__main__':
    torch.set_num_threads(1)
    with threadpool_limits(limits=(int(sys.argv[sys.argv.index("--threads") + 1]) if "--threads" in sys.argv else 1)):
        main()
