"""Resumable full validation at 10%, using frozen models and evaluator unchanged."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse, fcntl, hashlib, json, os, sys, time
import joblib
import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments'))
from savval import FEATURES, price_features
from matched_factorial_evaluation import evaluate_cell

RUN = ROOT / 'outputs/matched-factorial-ten-seeds-v1'
OUT = ROOT / 'outputs/review-expanded-primary-v2'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n'); tmp.replace(path)

def load_full(source):
    path = ROOT.parent / 'experiments/data/processed' / (source + '_bvival_v1') / 'splits/validation.csv'
    frame = pd.read_csv(path)
    ranks = frame.listing_id.astype(str).map(lambda x: hashlib.sha256(('sav-val-evaluation-order-v1|' + x).encode()).hexdigest())
    return frame.loc[ranks.sort_values(kind='stable').index].reset_index(drop=True)

def worker(task):
    source, seed, fit_id, cells = task
    torch.set_num_threads(1)
    receipt = OUT / 'worker-receipts' / source / f'seed-{seed}' / (fit_id + '.json')
    if receipt.exists():
        record = json.loads(receipt.read_text())
        assert record['status'] == 'completed'
        assert record['script_sha256'] == sha(Path(__file__))
        return record['summaries']
    manifest = json.loads((RUN / 'manifest.json').read_text()); config = manifest['config']
    pair = RUN / source / f'seed-{seed}'
    model_path = pair / 'fit/deployment_models' / (fit_id + '.joblib')
    wanted = json.loads((pair / 'fit/completion.json').read_text())['deployment_model_hashes'][fit_id]
    assert sha(model_path) == wanted
    frame = load_full(source)
    model, head = joblib.load(model_path)
    # Score at most 1000 records at once, including the exact old first chunk.
    # This bounds encoder/head temporary memory while retaining frozen models.
    kinds = sorted({cell[1] for cell in cells})
    pred_chunks, valid_chunks = [], []
    score_chunks = {kind: [] for kind in kinds}
    for start in range(0, len(frame), 1000):
        chunk = frame.iloc[start:start + 1000]
        pp, encoded, vv = model.predict(price_features(chunk, FEATURES[source]))
        pred_chunks.append(pp); valid_chunks.append(vv)
        for kind in kinds:
            score_chunks[kind].append(head.score(encoded, pp, model.space, kind, reported_missing=model.space.reported_missing(chunk)))
    pred, valid = np.concatenate(pred_chunks), np.concatenate(valid_chunks)
    score_cache = {kind: np.concatenate(values) for kind, values in score_chunks.items()}
    summaries = []
    for initial, score, feedback, allocation in cells:
        old = pair / 'evaluation/budget-1000' / initial / score / feedback / allocation
        scores = score_cache[score]
        folder = OUT / source / f'seed-{seed}' / initial / score / feedback / allocation
        folder.mkdir(parents=True, exist_ok=True)
        binding = {'model_sha256': wanted, 'budget': .1, 'allocation': allocation,
                   'evaluation_content': hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest(),
                   'sweeps': config['attacker_sweeps'], 'restarts': config['attacker_restarts'],
                   'batch_size': config['batch_size'], 'cost': config['concealment_cost_log']}
        if (folder / 'inputs.json').exists(): assert json.loads((folder / 'inputs.json').read_text()) == binding
        else: write(folder / 'inputs.json', binding)
        # Reuse the already audited exact 1000-record prefix, preserving bytes.
        for b in range(10):
            source_folder = old / f'batch-{b}'
            z = np.load(source_folder / 'arrays.npz'); lo, hi = b * 100, (b + 1) * 100
            assert np.allclose(pred[lo:hi], z['pred'], atol=2e-6, rtol=0)
            assert np.array_equal(valid[lo:hi], z['valid'])
            finite = np.isfinite(scores[lo:hi]); assert np.array_equal(finite, np.isfinite(z['scores']))
            assert np.allclose(scores[lo:hi][finite], z['scores'][finite], atol=1e-7, rtol=1e-8)
            f = pd.read_csv(source_folder / 'outcomes.csv.gz')
            assert f.listing_id.astype(str).tolist() == frame.listing_id.iloc[lo:hi].astype(str).tolist()
            target = folder / f'batch-{b}'; target.mkdir(exist_ok=True)
            for name in ('arrays.npz', 'outcomes.csv.gz'):
                if not (target / name).exists(): (target / name).symlink_to((source_folder / name).resolve())
            original = json.loads((source_folder / 'completion.json').read_text())
            write(target / 'completion.json', {**original, 'inputs_sha256': sha(folder / 'inputs.json'),
                                               'reused_prefix_receipt': str(source_folder / 'completion.json'),
                                               'reused_prefix_receipt_sha256': sha(source_folder / 'completion.json')})
        result = evaluate_cell(pred, scores, valid, frame, model.space, config, .1, allocation, folder, wanted)
        summaries.append({'dataset': source, 'seed': seed, 'fit_id': fit_id, 'initial_objective': initial,
                          'score': score, 'feedback': feedback, **result})
    assert sha(model_path) == wanted
    write(receipt, {'status': 'completed', 'script_sha256': sha(Path(__file__)), 'model_sha256': wanted, 'summaries': summaries})
    return summaries

def main(workers):
    OUT.mkdir(parents=True, exist_ok=True)
    lock = (OUT / 'execution.lock').open('w'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    manifest = json.loads((RUN / 'manifest.json').read_text())
    for name, value in manifest['source_hashes'].items(): assert sha(ROOT / 'experiments' / name) == value
    tasks = []
    for source in ('jucars', 'mucars'):
        for seed in manifest['config']['seeds']:
            mapping = json.loads((RUN / source / f'seed-{seed}/fit/cell_mapping.json').read_text())
            grouped = {}
            for row in mapping: grouped.setdefault(row['fit_id'], []).append(row['cell'])
            for fit_id, cells in grouped.items(): tasks.append((source, seed, fit_id, cells))
    binding = {'sources': ['jucars', 'mucars'], 'seeds': manifest['config']['seeds'], 'budget': .1,
               'frozen_manifest_sha256': sha(RUN / 'manifest.json'), 'script_sha256': sha(Path(__file__)),
               'full_validation_counts': {'jucars': 1374, 'mucars': 10672}, 'batches': {'jucars': 14, 'mucars': 107},
               'partial_last_batches': {'jucars': 74, 'mucars': 72}, 'no_retraining': True,
               'expected_cells': 480, 'expected_unique_fit_tasks': 280, 'status': 'running'}
    if (OUT / 'manifest.json').exists(): assert json.loads((OUT / 'manifest.json').read_text()) == binding
    else: write(OUT / 'manifest.json', binding)
    started = time.time(); rows = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(worker, task) for task in tasks]
        for future in as_completed(futures):
            rows.extend(future.result())
            pd.DataFrame(rows).to_csv(OUT / 'partial_summary.csv', index=False)
            write(OUT / 'progress.json', {'completed_cells': len(rows), 'expected_cells': 480, 'seconds_this_process': time.time() - started})
            print(f'EXPANDED CELLS {len(rows)}/480', flush=True)
    assert len(rows) == 480
    pd.DataFrame(rows).to_csv(OUT / 'summary.csv', index=False)
    write(OUT / 'completion.json', {'status': 'completed_pending_corroborating_audit', 'cells': 480,
                                   'summary_sha256': sha(OUT / 'summary.csv'), 'manifest_sha256': sha(OUT / 'manifest.json')})

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--workers', type=int, default=6)
    main(parser.parse_args().workers)
