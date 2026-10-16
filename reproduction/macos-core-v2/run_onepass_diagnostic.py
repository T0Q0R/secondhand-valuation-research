"""One command: complete residual replay, repetition/thread checks, one return ZIP.

Does not alter original training artifacts, tolerances, source code or packages.
Four isolated child processes run sequentially; at most two compute threads.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def trace_metadata(path):
    with zipfile.ZipFile(path) as archive:
        if set(archive.namelist()) != {'trace.json', 'arrays.npz'}:
            raise ValueError('Unexpected worker ZIP members')
        result = json.loads(archive.read('trace.json'))
        if hashlib.sha256(archive.read('arrays.npz')).hexdigest() != result['arrays_sha256']:
            raise ValueError('Worker array payload hash mismatch')
        return result


def compare(left, right):
    def stages(item):
        return {(s['method'], s['stage']): s for s in item['stages']}
    a, b = stages(left), stages(right)
    if set(a) != set(b):
        raise ValueError('Stage identity mismatch')
    first = None
    if len(left['records']) != len(right['records']):
        raise ValueError('Trace length mismatch')
    for x, y in zip(left['records'], right['records']):
        identity = ['method', 'stage', 'round', 'step', 'event']
        if any(x[k] != y[k] for k in identity):
            raise ValueError('Trace event ordering mismatch')
        if x != y:
            groups = [k for k in ['parameters', 'values', 'gradients', 'torch_rng_sha256'] if x.get(k) != y.get(k)]
            first = dict(**{k: x[k] for k in identity}, differing_groups=groups)
            break
    return dict(final_parameters_matching=sum(a[k]['final_parameter_sha256'] == b[k]['final_parameter_sha256'] for k in a),
                total_models=len(a), first_differing_trace_event=first)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--work', type=Path)
    args = parser.parse_args()
    run = args.run.resolve()
    if not run.is_dir():
        raise ValueError('Original run folder does not exist')
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    output = args.output.resolve() if args.output else run.parent / f'external-rpl-onepass-return-{stamp}.zip'
    work = args.work.resolve() if args.work else run.parent / f'external-rpl-onepass-work-{stamp}'
    if output.exists() or output.is_relative_to(ROOT) or output.is_relative_to(run):
        raise ValueError('Use a new output ZIP outside repository/original results')
    if work.is_relative_to(ROOT) or work.is_relative_to(run) or output.is_relative_to(work):
        raise ValueError('Use a separate work folder outside repository/original results')
    work.mkdir(parents=True, exist_ok=True)
    worker = HERE / 'residual_onepass_worker.py'
    input_files = [run / 'inputs.json']
    for method in ['path-0-gap-0.5', 'path-1-gap-0.5']:
        for stage in ['outer-0', 'outer-1', 'outer-2', 'deployment']:
            input_files.extend(run / 'synthetic' / method / stage / name
                               for name in ['completion.json', 'model.joblib'])
    original_hashes = {str(p.relative_to(run)): digest(p) for p in input_files}
    binding = dict(original_sha256=original_hashes, worker_sha256=digest(worker),
                   launcher_sha256=digest(Path(__file__)),
                   python=sys.version, platform=platform.platform(),
                   plan=[dict(threads=t, repeat=i) for t in [2, 1] for i in [1, 2]])
    binding_path = work / 'binding.json'
    if binding_path.exists():
        if json.loads(binding_path.read_text(encoding='utf-8')) != binding:
            raise ValueError('Work folder belongs to different inputs/code/environment')
    else:
        binding_path.write_text(json.dumps(binding, indent=2), encoding='utf-8')
    lock = work / '.run.lock'
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        raise RuntimeError('Diagnostic work folder already locked; do not launch twice') from None
    os.close(fd)
    started = time.time()
    metadata = {}
    log_path = work / 'onepass.log'
    status = dict(status='running', original_frozen_results_overwritten=False,
                  strict_tolerance_changed=False, scope='Eight saved synthetic backbones, seed13, residual replay only')
    code, child = 1, None
    try:
        with log_path.open('a', encoding='utf-8', newline='\n') as log:
            for task in binding['plan']:
                key = f"threads-{task['threads']}-repeat-{task['repeat']}"
                archive_path = work / (key + '.zip')
                if archive_path.exists():
                    existing = trace_metadata(archive_path)
                    if existing['probe_sha256'] != binding['worker_sha256'] or any(existing[k] != task[k] for k in ['threads', 'repeat']):
                        raise ValueError('Incompatible saved diagnostic stage')
                    metadata[key] = existing
                    print('REUSE_DIAGNOSTIC', key, flush=True)
                    continue
                command = [sys.executable, '-u', str(worker), '--run', str(run),
                           '--output', str(archive_path), '--threads', str(task['threads']),
                           '--repeat', str(task['repeat'])]
                print('ONEPASS_START', key, flush=True)
                child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding='utf-8', errors='replace',
                    env=dict(os.environ, PYTHONUTF8='1', PYTHONUNBUFFERED='1'))
                for line in child.stdout:
                    print(line, end='', flush=True)
                    log.write(line)
                    log.flush()
                if child.wait() != 0:
                    raise RuntimeError('Diagnostic subprocess failed; retained log and completed stages')
                metadata[key] = trace_metadata(archive_path)
        comparisons = {}
        for t in [2, 1]:
            comparisons[f'repeatability_threads_{t}'] = compare(metadata[f'threads-{t}-repeat-1'], metadata[f'threads-{t}-repeat-2'])
        comparisons['two_vs_one_thread'] = compare(metadata['threads-2-repeat-1'], metadata['threads-1-repeat-1'])
        status.update(status='computed_diagnostic_cross_machine_comparison_pending', comparisons=comparisons,
            saved_original_parameter_matches={key: sum(s['saved_parameter_exact_equal'] for s in item['stages']) for key, item in metadata.items()},
            models_per_run=8, full_residual_replays=32, epochs_per_model=12,
            observer_control_matches={key: [s['observer_control_exact_equal'] for s in item['stages'] if s['observer_control_exact_equal'] is not None] for key, item in metadata.items()})
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        status.update(status='diagnostic_failed_review_required', error=type(error).__name__ + ': ' + str(error))
        print(status['error'], flush=True)
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait()
        lock.unlink(missing_ok=True)
        status['elapsed_seconds'] = time.time() - started
        status['original_checkpoint_hashes_unchanged'] = all(p.is_file() and digest(p) == original_hashes[str(p.relative_to(run))] for p in input_files)
        if not status['original_checkpoint_hashes_unchanged']:
            status['status'] = 'original_checkpoint_change_detected_review_required'
            code = 1
        (work / 'onepass-summary.json').write_text(json.dumps(status, indent=2) + '\n', encoding='utf-8')
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(work.iterdir()):
                if path.is_file() and path.name in {'binding.json', 'onepass.log', 'onepass-summary.json'}:
                    bundle.write(path, path.name)
                elif path.is_file() and path.name in {f'threads-{t}-repeat-{i}.zip' for t in [1, 2] for i in [1, 2]}:
                    bundle.write(path, path.name)
        print('ONEPASS_RETURN_ZIP', output, flush=True)
        print('Return this one ZIP, including failures; it does not certify strict external reproduction.', flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
