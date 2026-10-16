"""Local arithmetic-path stress probe on frozen first/third batch fixtures.

No training updates, no original result replacement, no claim of cross-machine
validation. Identical float32 checkpoint parameters are promoted to float64 to
isolate precision from random initialization changes. The loss AST is extracted
unchanged from the frozen training source.
"""
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import zipfile

for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']:
    os.environ[key] = '1'
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments'))
sys.path.insert(0, str(ROOT / 'reproduction/windows-core-v1'))
import numpy as np
import pandas as pd
import torch
from threadpoolctl import threadpool_limits
from portable_split import fold_assignments, inner_split
from run_all import load_source, rank_subset
from savval import FEATURES, StateSpace, price_features


def sha(data):
    return hashlib.sha256(data).hexdigest()


def loss_program(source):
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'train_residual')
    loop = next(n for n in ast.walk(function) if isinstance(n, ast.For)
                and isinstance(n.target, ast.Name) and n.target.id == 'start')
    def assignment(node, name):
        return isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
    begin = next(i for i, n in enumerate(loop.body) if assignment(n, 'rows'))
    end = next(i for i, n in enumerate(loop.body) if assignment(n, 'loss'))
    body = loop.body[begin:end + 1]
    return compile(ast.Module(body=body, type_ignores=[]), '<frozen-loss-AST>', 'exec')


def main():
    started = time.time()
    here = Path(__file__).resolve().parent
    contract = json.loads((here / 'contract.json').read_text())
    for name, expected in contract['scientific_source_sha256'].items():
        if sha((ROOT / name).read_bytes()) != expected:
            raise ValueError('Frozen scientific source mismatch: ' + name)
    archive = ROOT.parent / 'external-reproduction-private-v1/local-onepass-return-v1.zip'
    with zipfile.ZipFile(archive) as outer:
        with zipfile.ZipFile(io.BytesIO(outer.read('threads-2-repeat-1.zip'))) as inner:
            trace = json.loads(inner.read('trace.json'))
            payload = inner.read('arrays.npz')
    if sha(payload) != trace['arrays_sha256']:
        raise ValueError('Fixture payload hash mismatch')
    with np.load(io.BytesIO(payload), allow_pickle=False) as loaded:
        arrays = {key: loaded[key] for key in loaded.files}
    source = (ROOT / 'experiments/recovery_path_training_v1.py').read_text()
    program = loss_program(source)
    cfg = contract['config']
    est, guide, _, _ = load_source('synthetic', cfg)
    train = rank_subset(pd.concat([est, guide], ignore_index=True), len(est) + len(guide),
                        'sav-val-cf-training-order-v2')
    assigned, space = fold_assignments(train, 3), StateSpace.build(2)
    results = []
    previous_determinism = torch.are_deterministic_algorithms_enabled()
    try:
        for stage in trace['stages']:
            method, name = stage['method'], stage['stage']
            selected = train if name == 'deployment' else train.loc[assigned != int(name[-1])]
            fitted, _ = inner_split(selected, cfg['head_fitting_fraction'])
            _, valid = space.materialize(price_features(fitted, FEATURES['synthetic']))
            for step in [0, 2]:
                prefix = method + '__' + name + '__round-0__step-' + str(step) + '__'
                before, backward = prefix + 'before_backward__', prefix + 'after_backward__'
                idx = arrays[before + 'idx']
                for dtype in [torch.float32, torch.float64]:
                    row = dict(method=method, stage=name, step=step, dtype=str(dtype), paths={})
                    baseline = None
                    for path in ['native', 'chunks_127', 'chunks_17', 'separate_bias', 'deterministic_native']:
                        torch.use_deterministic_algorithms(path == 'deterministic_native')
                        model = torch.nn.Sequential(torch.nn.Linear(43, 64), torch.nn.ReLU(),
                            torch.nn.Linear(64, 64), torch.nn.ReLU(), torch.nn.Linear(64, 1)).to(dtype=dtype)
                        state = {key: torch.tensor(arrays[before + 'parameter__' + key], dtype=dtype)
                                 for key in model.state_dict()}
                        model.load_state_dict(state)
                        bx = torch.tensor(arrays[before + 'bx'], dtype=dtype)
                        bb = torch.tensor(arrays[before + 'bb'], dtype=dtype)
                        by = torch.tensor(arrays[before + 'by'], dtype=dtype)
                        x = bx.reshape(-1, bx.shape[-1])
                        if path.startswith('chunks_'):
                            correction = torch.cat([model(block) for block in x.split(int(path.split('_')[1]))])
                        elif path == 'separate_bias':
                            correction = x
                            for layer in model:
                                correction = correction @ layer.weight.T + layer.bias if isinstance(layer, torch.nn.Linear) else layer(correction)
                        else:
                            correction = model(x)
                        predicted = bb + correction.reshape(bb.shape)
                        final_states = np.argmax(np.where(valid[idx], predicted.detach().numpy(), -np.inf), axis=1)
                        namespace = dict(torch=torch, np=np, self=SimpleNamespace(space=space),
                            predicted=predicted, final_states=final_states, idx=idx, by=by, bb=bb,
                            valid=valid, config=dict(cfg, recovery_path_weight=float(method.split('-')[1])), beta=.5)
                        exec(program, namespace)
                        loss = namespace['loss']
                        loss.backward()
                        gradients = {key: value.grad.detach().numpy().copy() for key, value in model.named_parameters()}
                        result = dict(predicted=predicted.detach().numpy(), gradients=gradients, states=final_states,
                                      loss=float(loss.detach()))
                        if path == 'native':
                            baseline = result
                            if dtype == torch.float32:
                                if not np.array_equal(result['predicted'], arrays[before + 'predicted']):
                                    raise ValueError('Native FP32 forward did not reproduce archived fixture')
                                for key, grad in gradients.items():
                                    if not np.array_equal(grad, arrays[backward + 'gradient__' + key]):
                                        raise ValueError('Native FP32 backward did not reproduce archived fixture')
                        row['paths'][path] = dict(
                            maximum_gradient_change_vs_native=max(float(np.max(np.abs(value.astype(np.float64) - baseline['gradients'][key].astype(np.float64)))) for key, value in gradients.items()),
                            maximum_log_quote_change_vs_native=float(np.max(np.abs(result['predicted'].astype(np.float64) - baseline['predicted'].astype(np.float64)))),
                            selected_state_changes_vs_native=int(np.count_nonzero(final_states != baseline['states'])),
                            loss_change_vs_native=abs(result['loss'] - baseline['loss']))
                    results.append(row)
    finally:
        torch.use_deterministic_algorithms(previous_determinism)
    summary = {}
    for dtype in ['torch.float32', 'torch.float64']:
        rows = [r for r in results if r['dtype'] == dtype]
        summary[dtype] = dict(fixtures=len(rows),
            maximum_gradient_path_sensitivity=max(v['maximum_gradient_change_vs_native'] for r in rows for k, v in r['paths'].items() if k != 'deterministic_native'),
            maximum_prediction_path_sensitivity=max(v['maximum_log_quote_change_vs_native'] for r in rows for k, v in r['paths'].items() if k != 'deterministic_native'),
            maximum_deterministic_flag_gradient_change=max(r['paths']['deterministic_native']['maximum_gradient_change_vs_native'] for r in rows))
    report = dict(scope='Local algebraic-path stress proxy, first/third archived batches of8 saved stages; no model training updates, no external FP64 execution',
        input_archive_sha256=sha(archive.read_bytes()), frozen_training_sha256=sha(source.encode()),
        source_sha256=sha(Path(__file__).read_bytes()), threads=1, elapsed_seconds=time.time()-started,
        native_fp32_matches_all16_archived_forward_backward_fixtures=True,
        initial_parameters='Identical archived float32 values promoted, not freshly drawn at a different dtype',
        loss='Unchanged AST extracted from frozen training function', summary=summary, fixtures=results,
        limitations=['Chunking/bias decomposition stresses local arithmetic order; it is not a replay of the other CPU/backend.',
                     'Reduced local FP64 sensitivity does not prove cross-machine matching, full-training stability or unchanged scientific performance.',
                     'No optimizer update, price/backbone/head fit, formal market response, or original tolerance was changed.'])
    output = ROOT / 'notes/numerical-stability-v1'
    output.mkdir(exist_ok=True)
    (output / 'precision-proxy-results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))
    print('Elapsed seconds', report['elapsed_seconds'])


if __name__ == '__main__':
    torch.set_num_threads(1)
    with threadpool_limits(limits=1):
        main()
