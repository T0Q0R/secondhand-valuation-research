"""Operational checkpoint guard; preserve completed cells while resizing workers.

Import-time installation also runs in multiprocessing spawn children. The frozen
producer and evaluator sources, manifests, algorithm and RNG remain unchanged.
"""
from pathlib import Path
import argparse, hashlib, json
import expanded_evaluation as producer

original_evaluate = producer.evaluate_cell

def checkpoint_evaluate(pred, scores, valid, frame, space, config, budget,
                        allocation, out, model_hash):
    cp = out / 'completion.json'
    if not cp.exists():
        return original_evaluate(pred, scores, valid, frame, space, config,
                                 budget, allocation, out, model_hash)
    done = json.loads(cp.read_text())
    inputs = json.loads((out / 'inputs.json').read_text())
    assert inputs['model_sha256'] == model_hash
    assert inputs['allocation'] == allocation and inputs['budget'] == budget
    assert inputs['cost'] == config['concealment_cost_log']
    assert inputs['sweeps'] == config['attacker_sweeps']
    assert inputs['restarts'] == config['attacker_restarts']
    assert inputs['batch_size'] == config['batch_size']
    assert inputs['evaluation_content'] == hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()
    assert producer.sha(out / 'inputs.json') == done['inputs_sha256']
    assert producer.sha(out / 'summary.json') == done['summary_sha256']
    assert len(done['batch_receipts']) == (len(frame) + config['batch_size'] - 1) // config['batch_size']
    for name, digest in done['batch_receipts'].items():
        bp = out / name
        assert producer.sha(bp) == digest
        b = json.loads(bp.read_text())
        assert b['inputs_sha256'] == done['inputs_sha256']
        assert producer.sha(bp.parent / 'arrays.npz') == b['arrays_sha256']
        assert producer.sha(bp.parent / 'outcomes.csv.gz') == b['outcomes_sha256']
    # Return the exact recorded summary; no rounding/reaggregation or rewriting.
    return json.loads((out / 'summary.json').read_text())

producer.evaluate_cell = checkpoint_evaluate

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=8)
    producer.main(parser.parse_args().workers)
