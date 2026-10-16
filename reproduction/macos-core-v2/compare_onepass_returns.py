"""Compare two one-pass returns; publish only aggregate/hash evidence."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

from run_onepass_diagnostic import compare


def load_return(path):
    expected = {f'threads-{t}-repeat-{i}.zip' for t in [1, 2] for i in [1, 2]}
    result = {}
    with zipfile.ZipFile(path) as archive:
        if not expected.issubset(archive.namelist()):
            raise ValueError('Incomplete one-pass return; inspect failure log first')
        if sum(i.file_size for i in archive.infolist()) > 256 * 1024**2:
            raise ValueError('Unexpectedly large one-pass return')
        summary = json.loads(archive.read('onepass-summary.json'))
        if summary['status'] != 'computed_diagnostic_cross_machine_comparison_pending':
            raise ValueError('One-pass diagnostic did not finish cleanly')
        for name in sorted(expected):
            with zipfile.ZipFile(io.BytesIO(archive.read(name))) as inner:
                if set(inner.namelist()) != {'trace.json', 'arrays.npz'}:
                    raise ValueError('Unexpected worker ZIP members')
                if sum(i.file_size for i in inner.infolist()) > 128 * 1024**2:
                    raise ValueError('Unexpectedly large worker payload')
                trace = json.loads(inner.read('trace.json'))
                if hashlib.sha256(inner.read('arrays.npz')).hexdigest() != trace['arrays_sha256']:
                    raise ValueError('Worker array payload hash mismatch')
                result[name] = trace
    return summary, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--external', type=Path, required=True)
    parser.add_argument('--local', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    external_summary, external = load_return(args.external)
    local_summary, local = load_return(args.local)
    root = Path(__file__).resolve().parents[2]
    known_contracts = {hashlib.sha256((root / 'reproduction' / name / 'contract.json').read_bytes()).hexdigest()
                       for name in ['macos-core-v2', 'windows-core-v1']}
    comparisons = {}
    for name in sorted(external):
        e, l = external[name], local[name]
        if e['source_contract_sha256'] not in known_contracts or l['source_contract_sha256'] not in known_contracts:
            raise ValueError('Unknown original fitting contract')
        for key in ['probe_sha256', 'frozen_training_sha256', 'threads', 'repeat']:
            if e[key] != l[key]:
                raise ValueError('Diagnostic binding mismatch: ' + key)
        if [(s['method'], s['stage'], s['original_fit_binding']) for s in e['stages']] != [(s['method'], s['stage'], s['original_fit_binding']) for s in l['stages']]:
            raise ValueError('Diagnostic fitting population/config mismatch')
        comparisons[name] = compare(e, l)
    report = dict(
        scope='Saved-backbone residual diagnostics only; no formal metric tolerance or reproduction status changes',
        external_archive_sha256=hashlib.sha256(args.external.read_bytes()).hexdigest(),
        local_archive_sha256=hashlib.sha256(args.local.read_bytes()).hexdigest(),
        external_summary=external_summary, local_summary=local_summary,
        paired_trace_comparisons=comparisons,
        environments={label: {key: values['threads-2-repeat-1.zip'][key]
                               for key in ['platform', 'python', 'versions', 'torch_build_config']}
                      for label, values in [('external', external), ('local', local)]},
        interpretation='The first differing recorded event bounds the observed divergence. It does not, by itself, identify a causal library, system or hardware change.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(comparisons, indent=2))


if __name__ == '__main__':
    main()
