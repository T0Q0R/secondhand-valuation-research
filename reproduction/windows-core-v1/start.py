"""Run the fixed synthetic core, retain logs, and package small return evidence.

Standard library only. Does not install packages, change scientific parameters,
copy model weights into the return ZIP, or discard numerical mismatches.
"""
import argparse
import ctypes
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path,
                        default=ROOT.parent / 'external-rpl-windows-synthetic')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Choose an output folder outside the repository')
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError('Use 64-bit Python 3.12')
    output.mkdir(parents=True, exist_ok=True)
    lock = output / '.run.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError(f'Run lock exists: {lock}. Check that no previous run is active before removing a stale lock.') from None
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(dict(pid=os.getpid(), host=platform.node(),
                       started=datetime.datetime.now().astimezone().isoformat()), stream)
    log_path = output / 'external-rpl-windows.log'
    env = dict(os.environ, PYTHONUTF8='1', PYTHONUNBUFFERED='1')
    command = [sys.executable, '-u', str(HERE / 'run_from_scratch.py'),
               '--dataset', 'synthetic', '--output', str(output)]
    exit_code = 1
    child = None
    try:
        if os.name == 'nt':
            # Prevent idle system sleep during this run; restore in finally.
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        with log_path.open('a', encoding='utf-8', newline='\n') as log:
            log.write('\nRUN_START ' + datetime.datetime.now().astimezone().isoformat() + '\n')
            log.flush()
            for check_only in [True, False]:
                current = command + (['--check-only'] if check_only else [])
                child = subprocess.Popen(current, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True,
                                         encoding='utf-8', errors='replace', env=env)
                for line in child.stdout:
                    print(line, end='', flush=True)
                    log.write(line)
                    log.flush()
                exit_code = child.wait()
                if exit_code:
                    break
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait()
        if os.name == 'nt':
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        lock.unlink(missing_ok=True)
        # Every invocation gets a distinct archive, including failures.
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        archive = output.parent / f'external-rpl-windows-return-{stamp}.zip'
        files = ['external-training-receipt.json', 'summary.csv',
                 'reference-comparison.csv', 'runtime-environment.json',
                 'inputs.json', 'external-rpl-windows.log']
        manifest = dict(exit_code=exit_code, platform=platform.platform(),
                        launcher_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        scope='Core synthetic subset only; inspect receipt, not process exit alone',
                        files={})
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
            for name in files:
                path = output / name
                if path.is_file():
                    manifest['files'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
                    bundle.write(path, name)
            bundle.writestr('return-manifest.json', json.dumps(manifest, indent=2))
        print(f'RETURN_ZIP {archive}', flush=True)
        print('Send this ZIP back even if the receipt reports numerical differences.', flush=True)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
