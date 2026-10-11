"""Verify tests and journal reconstruction inside a relocated source package."""
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
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--journal', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    original, output = args.original.resolve(), args.output.resolve()
    assert project != original and Path.cwd().resolve() == project
    assert not output.exists(), 'Fresh verification receipt required'
    manifest_path = project.parent/'package_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for name, digest in manifest['files'].items():
        assert sha(project.parent/name) == digest, name
    denied = [original/name for name in ('paper', 'notes', 'experiments', 'plan', 'tests', 'outputs')]
    # run_all.load_source reads inherited splits below the sibling experiments
    # directory; denying only a hypothetical sibling data directory misses it.
    denied.extend([original.parent/'data', original.parent/'experiments'])
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
        require_probe = attempts.pop()
        assert require_probe == str(probe.resolve())
    # This process runs the copied helper and keeps imports within the copy.
    sys.path = [str(project), str(project/'experiments'), *[
        entry for entry in sys.path
        if entry and not any(Path(entry).resolve().is_relative_to(folder) for folder in denied)]]
    import pytest

    imported = {}
    test_count = {}
    class ImportAudit:
        def pytest_sessionfinish(self, session, exitstatus):
            test_count['collected'] = session.testscollected
            test_count['failed'] = session.testsfailed
            for name, module in list(sys.modules.items()):
                location = getattr(module, '__file__', None)
                if not location:
                    continue
                path = Path(location).resolve()
                assert not any(path.is_relative_to(folder) for folder in denied), (name, path)
                if path.is_relative_to(project/'experiments') and path.suffix == '.py':
                    imported[name] = {'path': str(path), 'sha256': sha(path)}

    exitcode = pytest.main(['tests', '-q', '-p', 'no:cacheprovider'], plugins=[ImportAudit()])
    assert exitcode == 0, 'Copied-package tests failed'
    required = {'savval', 'equal_tuning', 'equal_benefit_reference', 'cdm_mechanism',
                'grouped_smi_interval_oracle', 'run_all', 'run_crossfit'}
    assert required <= set(imported), 'Expected implementation modules were not loaded'
    expected = project/'paper'/args.journal
    generated = project/'paper'/'journal-relocation-proof'
    assert not generated.exists()
    sys.argv = ['build_journal_draft.py', '--output', str(generated)]
    expected_build=json.loads((expected/'build_receipt.json').read_text())
    # Rebase the exact reviewed receipt generation into this copy. Never open
    # absolute source paths recorded by the original build.
    maps=expected_build.get('evidence_receipts') or {
        name:digest for name,digest in expected_build['input_hashes'].items()
        if Path(name).name.startswith('manuscript-') and '-evidence-revision' in Path(name).name}
    assert len(maps)==7
    copied_maps=[]
    for name,digest in maps.items():
        path=project/'notes'/Path(name).name
        assert sha(path)==digest
        copied_maps.append(path)
    sys.argv.extend(['--evidence-receipts',*[str(path) for path in copied_maps]])
    if expected_build.get('author_metadata_sha256'):
        names=[name for name,digest in expected_build['input_hashes'].items()
               if Path(name).name.startswith('manuscript-author-metadata-') and
               digest==expected_build['author_metadata_sha256']]
        assert len(names)==1
        author=project/'notes'/Path(names[0]).name
        assert sha(author)==expected_build['author_metadata_sha256']
        sys.argv.extend(['--author-metadata',str(author)])
    if expected_build.get('conference_style_repair'):
        sys.argv.append('--conference-style-fix')
    if expected_build.get('display_height_bounds'):
        sys.argv.append('--fit-journal-displays')
    if expected_build.get('supplement_extra_display_items',0):
        assert expected_build['supplement_extra_display_items']==2
        bundle=project/'paper'/expected_build.get('supplement_figure_bundle','figures/training-size-effects-v3')
        assert bundle.resolve().is_relative_to(project/'paper/figures')
        sys.argv.extend(['--training-size-figures',str(bundle)])
    runpy.run_path(str(project/'experiments/build_journal_draft.py'), run_name='__main__')
    binding = json.loads((generated/'build_receipt.json').read_text())
    compared = {}
    for name, digest in binding['files'].items():
        assert sha(generated/name) == digest
        if (expected/name).exists():
            assert sha(expected/name) == digest, ('Relocated draft bytes differ', name)
            compared[name] = digest
    assert {'main.tex', 'supplement.tex', 'sn-jnl.cls', 'sn-nature.bst', 'ref.bib'} <= set(compared)
    if expected_build.get('supplement_extra_display_items',0):
        assert {'training_size_tuned.pdf','training_size_fixed.pdf'} <= set(compared)
    if expected_build.get('conference_style_repair'):
        assert 'sn-nature-compatible.bst' in compared
    assert all(not any(Path(name).resolve().is_relative_to(folder) for folder in denied)
               for name in binding['input_hashes'])
    assert not attempts, 'Original source read was attempted'
    result = {'status': 'verified', 'copied_project': str(project),
              'manifest_sha256': sha(manifest_path), 'pytest_exitcode': int(exitcode),
              'pytest_tests': test_count,
              'test_files': {str(p.relative_to(project)): sha(p) for p in sorted((project/'tests').glob('*.py'))},
              'loaded_implementation_modules': imported,
              'original_read_denial_roots': [str(p) for p in denied],
              'actual_inherited_data_guard_rejection_probe': require_probe,
              'denied_original_access_attempts': attempts,
              'exact_relocated_journal_files': compared,
              'relocated_build_receipt_sha256': sha(generated/'build_receipt.json'),
              'scope': 'Source-package tests and exact journal-source/assets reconstruction; no full experiment retraining.'}
    output.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print('Copied tests and original-read-denied journal reconstruction verified.', flush=True)


if __name__ == '__main__':
    main()
