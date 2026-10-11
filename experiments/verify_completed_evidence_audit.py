"""Re-audit all 558 main cells from a copied source/evidence collection."""
from __future__ import annotations

import argparse
import builtins
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import sys


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    original, output = args.original.resolve(), args.output.resolve()
    project = Path(__file__).resolve().parents[1]
    assert project != original and Path.cwd().resolve() == project and not output.exists()
    manifest = json.loads((project.parent/'evidence_manifest.json').read_text())
    # Verify every materialized evidence byte before installing the read guard.
    for key, digest in manifest['files'].items():
        assert sha(project.parent/key) == digest, key
    denied = [original/name for name in ('paper', 'notes', 'experiments', 'plan', 'tests', 'outputs')]
    denied += [original.parent/'data', original.parent/'experiments']
    attempts = []
    def guard(open_function):
        def checked(path, *positional, **keywords):
            if isinstance(path, (str, bytes, os.PathLike)):
                resolved = Path(os.fsdecode(path)).resolve()
                if any(resolved.is_relative_to(folder) for folder in denied):
                    attempts.append(str(resolved))
                    raise PermissionError('Original project access denied: '+str(resolved))
            return open_function(path, *positional, **keywords)
        return checked
    builtins.open, io.open = guard(builtins.open), guard(io.open)
    probe = original.parent/'experiments/data/processed/jucars_bvival_v1/splits/train.csv'
    try:
        with probe.open('rb'):
            raise AssertionError('Actual inherited source directory was not denied')
    except PermissionError:
        rejected_probe = attempts.pop()
        assert rejected_probe == str(probe.resolve())
    sys.path = [str(project/'experiments'), str(project), *[
        p for p in sys.path if p and not any(Path(p).resolve().is_relative_to(d) for d in denied)]]
    from run_all import load_source
    assert Path(sys.modules['run_all'].__file__).resolve().is_relative_to(project/'experiments')
    config = json.loads((project/'outputs/nested-development-v2/run_manifest.json').read_text())['config']
    pinned = json.loads((project/'notes/source-reproduction-inputs-v1.json').read_text())
    inputs = {}
    for name in ('jucars', 'mucars'):
        _, _, evaluation, provenance = load_source(name, config)
        for role, checksum in [('train', 'train_sha256'), ('validation', 'validation_sha256')]:
            path = Path(provenance['source_'+role]).resolve()
            assert path.is_relative_to(project.parent/'experiments/data/processed')
            assert provenance[checksum] == pinned['processed_sha256'][name+'/'+role+'.csv']
        assert len(evaluation) == 1000 and provenance['original_test_labels_read'] is False
        inputs[name] = provenance
    generated = project/'outputs/relocated-main-audit-proof'
    assert not generated.exists()
    sys.argv = ['analyze_nested.py', '--run', str(project/'outputs/nested-development-v2'),
                '--output', str(generated)]
    runpy.run_path(str(project/'experiments/analyze_nested.py'), run_name='__main__')
    result = json.loads((generated/'analysis_completion.json').read_text())
    assert result['run_complete'] is True and result['audited_cells'] == 558
    expected = project/'outputs/nested-development-v2-audit-01'
    identical = {}
    for name, digest in result['outputs'].items():
        if name.endswith('.csv'):
            assert sha(expected/name) == digest, ('Relocated result changed', name)
            identical[name] = digest
    assert len(identical) == 6 and not attempts
    output.write_text(json.dumps({'status': 'verified', 'main_cells_reaudited': 558,
        'copied_project': str(project), 'actual_source_inputs': inputs,
        'original_read_denial_roots': [str(p) for p in denied],
        'actual_inherited_data_guard_rejection_probe': rejected_probe,
        'denied_original_access_attempts': attempts,
        'six_exact_numeric_analysis_tables': identical,
        'relocated_analysis_receipt_sha256': sha(generated/'analysis_completion.json'),
        'scope': 'Complete archived main-cell arithmetic/fold-receipt audit and actual copied input loading; no fresh model fitting or claim about live extension completion.'},
        indent=2, sort_keys=True)+'\n')
    print('Copied completed main evidence reaudited; actual data inputs came from the copy.', flush=True)


if __name__ == '__main__':
    main()
