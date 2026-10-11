"""Archive completed study components, materializing the CDM union's links."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = {
    'nested-development-v2': ('completion.json', None),
    'nested-development-v2-audit-01': ('analysis_completion.json', 558),
    'robust-benefit-reference-v1': ('completion.json', 54),
    'robust-benefit-reference-v1-audit': ('completion.json', 54),
    'cdm-development-v1-full-union-01': ('completion.json', 1512),
    'cdm-development-v1-full-union-01-audit': ('completion.json', 1512),
    'cdm-development-v1-contrasts-full-01': ('completion.json', None),
    'cdm-public-equivalence-full-v1-01': ('completion.json', None),
    'cdm-deviation-generalization-full-v1': ('completion.json', 1512),
    'cdm-deviation-generalization-full-v1-audit': ('completion.json', 1512),
    'cdm-deviation-generalization-full-v1-contrasts': ('completion.json', None),
    'saved-model-diagnostics-v2': ('completion.json', None),
    'saved-model-diagnostics-v2-audit': ('analysis_completion.json', 225),
    'aco1-development-v2': ('completion.json', 144),
    'aco1-development-v2-audit': ('analysis_completion.json', 144),
    'grouped-smi-development-v2': ('completion.json', 12),
    'grouped-smi-development-v2-interval-cached-audit': ('completion.json', None),
    'numeric-smi-development-v2': ('completion.json', None),
    'numeric-smi-development-v2-audit-02': ('analysis_completion.json', 12),
    'online-resource-development-v2': ('completion.json', None),
    'online-resource-and-transfer-v2-audit': ('completion.json', None),
}
PROVENANCE = ('cdm-development-v1-partial-01', 'cdm-development-v1-supplement-01')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def walk(path, ancestors=frozenset()):
    real = path.resolve(strict=True)
    assert real not in ancestors, ('Cyclic evidence link', path)
    assert real.is_relative_to(ROOT/'outputs'), ('Outside evidence directory', path)
    if path.is_dir():
        for child in sorted(path.iterdir()):
            if child.name == '__pycache__' or child.name.endswith('.lock'):
                continue
            yield from walk(child, ancestors | {real})
    elif path.is_file():
        yield path
    else:
        raise ValueError('Unsupported evidence entry: '+str(path))


def full_extension_components(args):
    """Accept full studies only, with exact run -> audit -> contrast bindings."""
    requested = [args.tuning_audit, args.tuning_contrasts,
                 args.benefit_audit, args.benefit_contrasts]
    if not any(requested):
        return {}
    assert all(requested), 'All four full extension audit/contrast folders are required'
    paths = [path.resolve(strict=True) for path in requested]
    assert all(path.parent == ROOT/'outputs' for path in paths), 'Direct output components required'
    records = [json.loads((path/'completion.json').read_text()) for path in paths]
    ta, tc, ba, bc = records
    for path, record in zip(paths, records):
        assert record.get('status') == 'completed', ('Incomplete extension analysis', path.name)
        assert record.get('execution_smoke') is False, ('Smoke evidence excluded', path.name)
        complete = record.get('all_scheduled_cases_completed',
                              record.get('all_scheduled_cases_complete'))
        assert complete is True, ('Partial extension cannot enter full archive', path.name)
    assert ta['cells'] == tc['cells'] == 972, 'Full 972-cell tuning matrix required'
    assert ta['completed_cases_at_capture'] == ta['scheduled_cases'] == 27
    assert ta['stages'] == 108, 'All 27 tuning cases and four stages required'
    assert ba['cells'] == bc['reference_cells'] == 324, 'Full 324-cell benefit matrix required'
    assert ba['cases'] == bc['cases'] == 27 and ba['stages'] == 108
    assert ba['independently_refitted_deployment_heads'] == 54
    tuning = ROOT/'outputs/equal-tuning-size-development-v1'
    benefit = ROOT/'outputs/equal-benefit-size-reference-development-v1'
    for folder, count in [(tuning, 972), (benefit, 324)]:
        done = json.loads((folder/'completion.json').read_text())
        assert done['status'] == 'completed' and done['execution_smoke'] is False
        assert done['cells'] == count, ('Full raw generation required', folder.name)
        assert sha(folder/'all_summary.csv') == done['summary_sha256']
    assert ta['source_completion_sha256'] == sha(tuning/'completion.json')
    assert ba['source_completion_sha256'] == sha(benefit/'completion.json')
    assert tc['audit_completion_sha256'] == sha(paths[0]/'completion.json')
    assert bc['reference_audit_sha256'] == sha(paths[2]/'completion.json')
    assert bc['tuning_audit_sha256'] == sha(paths[0]/'completion.json')
    for folder, done in [(paths[0], ta), (paths[2], ba)]:
        assert sha(folder/'input_binding.json') == done['input_binding_sha256']
        inputs = json.loads((folder/'input_binding.json').read_text())
        assert len(inputs['cases']) == 27
    assert tc['input_binding_sha256'] == ta['input_binding_sha256']
    tm = json.loads((tuning/'manifest.json').read_text())
    bm = json.loads((benefit/'manifest.json').read_text())
    assert set(tm['config']['datasets']) == {'synthetic', 'jucars', 'mucars'}
    assert set(tm['config']['seeds']) == {13, 42, 2026}
    assert set(tm['sizes']) == {1000, 2500, 5000}
    assert tm['config']['budgets'] == [0, .01, .05, .1, .2, .3]
    assert bm['tuning_manifest_sha256'] == sha(tuning/'manifest.json')
    expected = {(d, n, s) for d in tm['config']['datasets']
                for n in tm['sizes'] for s in tm['config']['seeds']}
    assert len(expected) == 27
    for run, audit in [(tuning, paths[0]), (benefit, paths[2])]:
        inputs = json.loads((audit/'input_binding.json').read_text())
        manifest = json.loads((run/'manifest.json').read_text())
        assert inputs['manifest_sha256'] == sha(run/'manifest.json')
        assert inputs['binding'] == manifest['binding']
        assert inputs['source_completion_sha256'] == sha(run/'completion.json')
        assert {(v['dataset'], v['size'], v['seed']) for v in inputs['cases']} == expected
        for case in inputs['cases']:
            folder = run/case['dataset']/f"size-{case['size']}"/f"seed-{case['seed']}"
            assert sha(folder/'evaluation_completion.json') == case['receipt_sha256']
            for stage, digest in case['stage_completions'].items():
                assert sha(folder/stage/'completion.json') == digest
    return {tuning.name: ('completion.json', 972), benefit.name: ('completion.json', 324),
            paths[0].name: ('completion.json', 972), paths[1].name: ('completion.json', 972),
            paths[2].name: ('completion.json', 324), paths[3].name: ('completion.json', None)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    for name in ('tuning-audit', 'tuning-contrasts', 'benefit-audit', 'benefit-contrasts'):
        parser.add_argument('--'+name, type=Path)
    args = parser.parse_args()
    extensions = full_extension_components(args)
    components = {**COMPONENTS, **extensions}
    archive = args.output.resolve()
    manifest_path = archive.with_suffix('.manifest.json')
    assert not archive.exists() and not manifest_path.exists(), 'Fresh component archive required'
    archive.parent.mkdir(parents=True, exist_ok=True)
    bindings = {}
    for name, (receipt, cells) in components.items():
        folder = ROOT/'outputs'/name
        record = json.loads((folder/receipt).read_text())
        assert record.get('status') == 'completed' or record.get('run_complete') is True, name
        assert record.get('execution_smoke') is not True, name
        if cells is not None:
            count = record.get('cells', record.get('audited_cells'))
            assert count == cells, (name, count, cells)
        for field in ('files', 'outputs'):
            for relative, digest in record.get(field, {}).items():
                assert sha(folder/relative) == digest, (name, relative)
        if 'summary_sha256' in record:
            summaries = [p for p in folder.glob('*.csv')
                         if sha(p) == record['summary_sha256']]
            assert summaries, ('Declared summary checksum has no matching CSV', name)
        bindings[name] = {'receipt': receipt, 'sha256': sha(folder/receipt),
                          'verified_cell_count': cells}
    # These two immutable source containers jointly supply all nine union pairs.
    for name in PROVENANCE:
        p = ROOT/'outputs'/name/'completion.json'
        assert json.loads(p.read_text())['status'] == 'completed'
        bindings[name] = {'receipt': 'completion.json', 'sha256': sha(p),
                          'scope': 'Underlying seven-pair/two-pair provenance, not a separate nine-pair study'}
    files = {}
    for name in [*components, *PROVENANCE]:
        for path in walk(ROOT/'outputs'/name):
            key = 'sav-val/'+path.relative_to(ROOT).as_posix()
            assert key not in files
            files[key] = path
    # Include only the four processed train/validation splits used by the runs.
    pinned = json.loads((ROOT/'notes/source-reproduction-inputs-v1.json').read_text())
    for key, digest in pinned['processed_sha256'].items():
        dataset, filename = key.split('/')
        path = ROOT.parent/'experiments/data/processed'/f'{dataset}_bvival_v1'/'splits'/filename
        assert sha(path) == digest, key
        files['experiments/data/processed/'+f'{dataset}_bvival_v1/splits/'+filename] = path
    files['sav-val/notes/source-reproduction-inputs-v1.json'] = ROOT/'notes/source-reproduction-inputs-v1.json'
    files['sav-val/experiments/package_completed_evidence.py'] = Path(__file__)
    hashes, materialized = {}, {}
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zipped:
        for index, (key, path) in enumerate(sorted(files.items()), 1):
            before = sha(path)
            zipped.write(path, key)
            assert sha(path) == before, ('Evidence changed while packaging', key)
            hashes[key] = before
            if path.resolve() != path.absolute():
                materialized[key] = str(path.resolve())
            if index % 100 == 0:
                print(f'ARCHIVED {index}/{len(files)} completed evidence files', flush=True)
        manifest = {'status': ('completed_experimental_evidence_archive' if extensions
                               else 'completed_study_component_archive'), 'components': bindings,
                    'files': hashes, 'materialized_link_files': materialized,
                    'source_dois': pinned['source_dois'], 'reused_data_license': pinned['license'],
                    'scope': 'Full saved models/outcomes/calibration/analysis of the named completed components plus their four checksum-bound processed train/validation inputs. No original test split included.',
                    'full_tuning_and_benefit_extensions_included': bool(extensions),
                    'remaining': ('Final manuscript/source-package/format/author and venue/ranking review remain separate. This is a local experimental archive, not a public deposit or proof of a completed paper.' if extensions else
                                  'The live972-cell tuning and324-cell benefit extensions, final combined collection, author review and venue/ranking remain incomplete. This component is not the final study or a public deposit. Source licensing is a later release decision.')}
        encoded = (json.dumps(manifest, indent=2, sort_keys=True)+'\n').encode()
        zipped.writestr('evidence_manifest.json', encoded)
    manifest_path.write_bytes(encoded)
    print(json.dumps({'status': 'created', 'archive': str(archive), 'files': len(hashes),
                      'bytes': archive.stat().st_size, 'materialized_files': len(materialized)}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
