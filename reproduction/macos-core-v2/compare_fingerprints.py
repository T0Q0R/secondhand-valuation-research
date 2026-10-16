"""Compare two read-only diagnostic ZIPs without fitting or loading pickles.

Only hashes, environment descriptions and aggregate numeric differences are
written. Model parameters and per-record arrays stay in the input archives.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

import numpy as np


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_archive(path):
    with zipfile.ZipFile(path) as archive:
        if len(archive.infolist()) != 2 or set(archive.namelist()) != {'diagnostic.json', 'arrays.npz'}:
            raise ValueError('Unexpected diagnostic ZIP members')
        if sum(item.file_size for item in archive.infolist()) > 64 * 1024**2:
            raise ValueError('Unexpectedly large diagnostic payload')
        metadata = json.loads(archive.read('diagnostic.json'))
        payload = archive.read('arrays.npz')
    if digest(payload) != metadata['arrays_sha256']:
        raise ValueError('Diagnostic array payload hash mismatch')
    with zipfile.ZipFile(io.BytesIO(payload)) as inner:
        if sum(item.file_size for item in inner.infolist()) > 128 * 1024**2:
            raise ValueError('Unexpectedly large expanded arrays')
    with np.load(io.BytesIO(payload), allow_pickle=False) as arrays:
        values = {key: arrays[key] for key in arrays.files}
    for model in metadata['models']:
        prefix = model['method'] + '__' + model['stage']
        names = {'base': model['base_sha256'], 'predicted': model['prediction_sha256'],
                 'tree_leaves': model['tree_leaf_sha256']}
        names.update({'residual__' + key: value
                      for key, value in model['residual_parameter_sha256'].items()})
        for suffix, expected in names.items():
            array = values[prefix + '__' + suffix]
            if array.dtype.hasobject or not np.isfinite(array).all():
                raise ValueError('Invalid numeric array')
            if digest(np.ascontiguousarray(array).tobytes()) != expected:
                raise ValueError(f'Array fingerprint mismatch: {prefix}/{suffix}')
    return metadata, values


def difference(a, b):
    if a.shape != b.shape or a.dtype != b.dtype:
        raise ValueError('Array shape or dtype mismatch')
    delta = np.abs(a.astype(np.float64) - b.astype(np.float64))
    return dict(shape=list(a.shape), dtype=str(a.dtype),
                exact_equal=bool(np.array_equal(a, b)),
                changed_entries=int(np.count_nonzero(a != b)),
                total_entries=int(a.size),
                maximum_absolute_difference=float(delta.max()),
                mean_absolute_difference=float(delta.mean()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--external', type=Path, required=True)
    parser.add_argument('--local', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    external, ea = load_archive(args.external)
    local, la = load_archive(args.local)
    for field in ['contract_sha256', 'source_runner_sha256', 'input_receipt']:
        if external[field] != local[field]:
            raise ValueError(f'Incompatible diagnostic bindings: {field}')
    if set(ea) != set(la):
        raise ValueError('Diagnostic array sets differ')
    em = {(m['method'], m['stage']): m for m in external['models']}
    lm = {(m['method'], m['stage']): m for m in local['models']}
    expected = {(method, stage) for method in ['path-0-gap-0.5', 'path-1-gap-0.5']
                for stage in ['outer-0', 'outer-1', 'outer-2', 'deployment']}
    if set(em) != expected or set(lm) != expected or len(external['models']) != 8 or len(local['models']) != 8:
        raise ValueError('Expected exactly eight distinct stage models')
    records = []
    for identity in sorted(expected):
        e, l = em[identity], lm[identity]
        prefix = '__'.join(identity)
        comparisons = {field: e[field] == l[field] for field in [
            'training_inputs', 'encoding_shape', 'encoding_sha256', 'valid_sha256',
            'tree_leaf_counts', 'tree_borders', 'tree_leaf_sha256',
            'base_sha256', 'prediction_sha256', 'residual_parameter_sha256']}
        arrays = {key[len(prefix) + 2:]: difference(ea[key], la[key])
                  for key in ea if key.startswith(prefix + '__')}
        records.append(dict(method=identity[0], stage=identity[1],
                            metadata_equal=comparisons, arrays=arrays))
    summary = dict(
        models=len(records),
        training_input_matches=sum(r['metadata_equal']['training_inputs'] for r in records),
        encoding_hash_matches=sum(r['metadata_equal']['encoding_sha256'] for r in records),
        valid_state_hash_matches=sum(r['metadata_equal']['valid_sha256'] for r in records),
        tree_structure_matches=sum(r['metadata_equal']['tree_leaf_counts'] and r['metadata_equal']['tree_borders'] for r in records),
        tree_leaf_exact_matches=sum(r['arrays']['tree_leaves']['exact_equal'] for r in records),
        base_prediction_exact_matches=sum(r['arrays']['base']['exact_equal'] for r in records),
        residual_parameter_hash_matches=sum(r['metadata_equal']['residual_parameter_sha256'] for r in records),
        final_prediction_exact_matches=sum(r['arrays']['predicted']['exact_equal'] for r in records),
        maximum_final_log_quote_difference=max(r['arrays']['predicted']['maximum_absolute_difference'] for r in records))
    report = dict(
        scope='Read-only eight saved synthetic price models, one fitting seed; no fitting, no response search, no tolerance changes',
        archive_sha256=dict(external=digest(args.external.read_bytes()), local=digest(args.local.read_bytes())),
        contract_sha256=external['contract_sha256'],
        diagnostic_runner_sha256=external['source_runner_sha256'],
        matched_source_population_bindings=external['input_receipt'],
        environments={name: {field: value[field] for field in ['platform', 'python', 'versions', 'torch_build_config']}
                      for name, value in [('external', external), ('local', local)]},
        torch_build_description_equal=external['torch_build_config'] == local['torch_build_config'],
        summary=summary, models=records,
        interpretation='Differences are present in saved residual-network parameters despite matching input, encoding, tree and base-prediction fingerprints. The specific first divergent training operation and its cause are not identified by these final checkpoints. External strict metric reproduction remains failed.')
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'fingerprint-comparison.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    with (args.output / 'model-differences.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['method', 'stage', 'component', 'exact_equal',
                'changed_entries', 'total_entries', 'maximum_absolute_difference', 'mean_absolute_difference'])
        writer.writeheader()
        for record in records:
            for component, value in record['arrays'].items():
                writer.writerow(dict(method=record['method'], stage=record['stage'], component=component,
                                     **{key: value[key] for key in writer.fieldnames[3:]}))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
