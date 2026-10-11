"""Merge complete source and experimental ZIPs with exact overlap checks."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def members(archive, kind):
    names = archive.namelist()
    assert len(names) == len(set(names)), 'Duplicate ZIP entries'
    manifest_name = 'package_manifest.json' if kind == 'source' else 'evidence_manifest.json'
    candidates = [name for name in names if PurePosixPath(name).name == manifest_name]
    assert len(candidates) == 1, 'One collection manifest required'
    name = candidates[0]
    record = json.loads(archive.read(name))
    if kind == 'source':
        assert record['status'] == 'development_source_package'
        assert record.get('all_scheduled_extensions_in_reviewed_manuscript') is True, 'Complete reviewed source required'
    else:
        assert record['status'] == 'completed_experimental_evidence_archive'
        assert record.get('full_tuning_and_benefit_extensions_included') is True, 'Complete experimental evidence required'
    prefix = PurePosixPath(name).parent
    expected = {str(prefix/PurePosixPath(key)): key for key in record['files']}
    assert set(names) == set(expected) | {name}, 'Unmapped ZIP entries'
    for full_name in names:
        part = PurePosixPath(full_name)
        assert not part.is_absolute() and '..' not in part.parts and '\\' not in full_name
        mode = archive.getinfo(full_name).external_attr >> 16
        assert mode & 0o170000 != 0o120000, 'Materialized regular files required'
    return record, expected, name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert not output.exists(), 'Fresh complete delivery directory required'
    source_sha, evidence_sha = sha(args.source), sha(args.evidence)
    with zipfile.ZipFile(args.source) as source, zipfile.ZipFile(args.evidence) as evidence:
        source_record, source_members, source_manifest = members(source, 'source')
        evidence_record, evidence_members, evidence_manifest = members(evidence, 'evidence')
        shared = set(source_record['files']) & set(evidence_record['files'])
        assert all(source_record['files'][key] == evidence_record['files'][key] for key in shared), 'Source/evidence overlap changed'
        output.mkdir(parents=True)
        verified = {}
        for kind, archive, record, lookup, manifest in (
            ('source', source, source_record, source_members, source_manifest),
            ('evidence', evidence, evidence_record, evidence_members, evidence_manifest)):
            for index, (member, relative) in enumerate(sorted(lookup.items()), 1):
                value = archive.read(member)
                expected = record['files'][relative]
                assert digest(value) == expected, ('ZIP byte mismatch', kind, relative)
                destination = output/relative
                assert destination.resolve().is_relative_to(output)
                if destination.exists():
                    assert relative in shared and sha(destination) == expected
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(value)
                    assert sha(destination) == expected
                verified[relative] = expected
                if index % 100 == 0:
                    print(f'ASSEMBLED {kind} {index}/{len(lookup)}', flush=True)
            destination = output/PurePosixPath(manifest).name
            destination.write_bytes(archive.read(manifest))
        assert sha(args.source) == source_sha and sha(args.evidence) == evidence_sha
        receipt = {'status': 'assembled_complete_local_delivery',
            'source_archive_sha256': source_sha, 'evidence_archive_sha256': evidence_sha,
            'source_files': len(source_members), 'evidence_files': len(evidence_members),
            'union_files': len(verified), 'identical_shared_files': sorted(shared),
            'source_manifest_sha256': sha(output/'package_manifest.json'),
            'evidence_manifest_sha256': sha(output/'evidence_manifest.json'),
            'assembler_sha256': sha(Path(__file__)),
            'scope': 'Every ZIP and extracted file checksum verified, exact overlaps only. Complete reviewed source and full experimental archive assembled locally; saved-model/figure/test replay remains a separate check, no publication or new fitting.'}
        (output/'assembly_receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True)+'\n')
    print('ASSEMBLED COMPLETE LOCAL DELIVERY', flush=True)


if __name__ == '__main__':
    main()
