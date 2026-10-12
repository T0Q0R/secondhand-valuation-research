"""Run independent future pairs through the unchanged, frozen fit auditor."""
import fcntl
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments'))
import audit_matched_factorial_fits as audit

def main():
    worker = int(sys.argv[1])
    parent_pid = int(sys.argv[2])
    run = ROOT / 'outputs/matched-factorial-ten-seeds-v1'
    formal = ROOT / 'outputs/matched-factorial-ten-seeds-v1-pipeline/fit-audit'
    isolated = ROOT / 'outputs/side-parallel-fit-audit' / f'worker-{worker}'
    isolated.mkdir(parents=True, exist_ok=True)
    lock = (isolated / 'execution.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    inputs = audit.read(formal / 'inputs.json')
    manifest = audit.read(run / 'manifest.json')
    cfg = manifest['config']
    audit.torch.set_num_threads(1 if len(sys.argv) > 3 else 2)
    def validate():
        os.kill(parent_pid, 0)
        assert audit.sha(run / 'manifest.json') == inputs['run_manifest_sha256']
        assert audit.sha(Path(audit.__file__)) == inputs['checker_sha256']
        for name, digest in manifest['source_hashes'].items():
            assert audit.sha(run / 'source_snapshot' / name) == digest
            assert audit.sha(ROOT / 'experiments' / name) == digest
    validate()
    audit.write(isolated / 'inputs.json', inputs)
    e, g, evaluation, provenance = audit.load_source('jucars', cfg)
    train = audit.pd.concat([e, g], ignore_index=True)
    seeds = [int(s) for s in sys.argv[3:]] if len(sys.argv) > 3 else list(reversed(cfg['seeds']))[worker::2]
    assert set(seeds) <= set(cfg['seeds'])
    for seed in seeds:
        validate()
        target = formal / 'jucars' / f'seed-{seed}.json'
        if target.exists():
            print(f'SKIP existing jucars/{seed}', flush=True)
            continue
        print(f'START jucars/{seed}', flush=True)
        result = audit.audit_pair(run, 'jucars', seed, cfg, train, evaluation, provenance)
        validate()
        assert result['status'] == 'completed'
        assert (result['dataset'], result['seed']) == ('jucars', seed)
        assert all(audit.sha(Path(p)) == h for p, h in result['bound_files'].items())
        checkpoint = isolated / 'jucars' / f'seed-{seed}.json'
        audit.write(checkpoint, result)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Atomic publication of a fully checked receipt, never replacing a receipt.
        try:
            os.link(checkpoint, target)
        except FileExistsError:
            old = audit.read(target)
            assert old == result
        print(f'PUBLISHED jucars/{seed}', flush=True)
    audit.write(isolated / 'completion.json', {'status': 'completed', 'seeds': seeds})

if __name__ == '__main__':
    main()
