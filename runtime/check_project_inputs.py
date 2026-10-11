"""Read-only check of portable source builders and inherited input bytes.

Does not train, rebuild data, or inspect historical test labels.
"""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--parent-root', type=Path)
    args = parser.parse_args()
    root = args.repository_root.resolve()
    parent = args.parent_root.resolve() if args.parent_root else root.parent
    receipt = json.loads((root / 'notes/source-reproduction-inputs-v1.json').read_text())
    checks = []
    for name, expected in receipt['builder_sha256'].items():
        for label, path in [('bundled_builder', root / 'source_inputs' / name),
                            ('installed_builder', parent / 'experiments' / name)]:
            checks.append((label, path, expected))
    for name, expected in receipt['processed_sha256'].items():
        source, file = name.split('/')
        path = parent / 'experiments/data/processed' / (source + '_bvival_v1') / 'splits' / file
        checks.append(('processed_train_or_validation', path, expected))
    results = []
    for label, path, expected in checks:
        state = 'missing' if not path.is_file() else ('matched' if digest(path) == expected else 'hash_mismatch')
        results.append({'kind': label, 'path': str(path), 'status': state})
    passed = all(row['status'] == 'matched' for row in results)
    print(json.dumps({'status': 'passed' if passed else 'not_ready', 'checks': results,
                      'historical_test_labels_read': False, 'training_performed': False}, indent=2))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
