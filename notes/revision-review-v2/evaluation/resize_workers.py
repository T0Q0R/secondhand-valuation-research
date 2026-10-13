"""Freeze, validate durable checkpoints, terminate old group, resume at 8 workers."""
from pathlib import Path
import argparse, datetime, fcntl, hashlib, json, os, signal, subprocess, time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'outputs/review-expanded-primary-v2'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def atomic(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)

def group_members(pgid):
    rows = subprocess.check_output(['ps','-axo','pid,pgid,state'],text=True).splitlines()[1:]
    return [(int(a),c) for row in rows if len(v:=row.split()) == 3
            for a,b,c in [v] if int(b) == pgid and not c.startswith('Z')]

def main(old, workers):
    assert workers == 8 and os.getpgid(old) == old
    command = subprocess.check_output(['ps','-p',str(old),'-o','command='],text=True).strip()
    expected = str(HERE / 'expanded_evaluation.py')
    assert expected in command and '--workers 6' in command, command
    assert not (OUT/'completion.json').exists(), 'Producer is already complete.'
    frozen = {str(HERE/'expanded_evaluation.py'):sha(HERE/'expanded_evaluation.py'),
              str(ROOT/'experiments/matched_factorial_evaluation.py'):sha(ROOT/'experiments/matched_factorial_evaluation.py'),
              str(OUT/'manifest.json'):sha(OUT/'manifest.json')}
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    index = HERE / ('resize-checkpoints-' + stamp + '.json')
    receipt = HERE / 'resize-to-eight-receipt.json'
    os.killpg(old, signal.SIGSTOP)
    terminated = False
    try:
        time.sleep(.25)
        members = group_members(old)
        assert members and all(state.startswith('T') for _,state in members), members
        good = {}; invalid = []; batches = cells = 0
        for p in sorted(OUT.glob('*/seed-*/**/completion.json')):
            try:
                value = json.loads(p.read_text())
            except (ValueError, UnicodeError):
                invalid.append(p); continue
            if p.parent.name.startswith('batch-'):
                assert value['status'] == 'completed'
                assert sha(p.parent/'arrays.npz') == value['arrays_sha256'], str(p)
                assert sha(p.parent/'outcomes.csv.gz') == value['outcomes_sha256'], str(p)
                assert sha(p.parent.parent/'inputs.json') == value['inputs_sha256'], str(p)
                batches += 1
            else:
                assert sha(p.parent/'summary.json') == value['summary_sha256'], str(p)
                assert sha(p.parent/'inputs.json') == value['inputs_sha256'], str(p)
                for name, digest in value['batch_receipts'].items():
                    assert sha(p.parent/name) == digest, str(p)
                cells += 1
            good[str(p.relative_to(ROOT))] = sha(p)
        atomic(index, {'frozen_receipt_hashes':good,'cells':cells,'batches':batches,
                       'invalid_incomplete_receipts':[str(p.relative_to(ROOT)) for p in invalid]})
        atomic(receipt, {'status':'checkpoints_verified_before_restart','old_pid':old,
                        'old_workers':6,'new_workers':workers,'completed_cells':cells,
                        'completed_batches':batches,'checkpoint_index':str(index.relative_to(ROOT)),
                        'checkpoint_index_sha256':sha(index),'frozen_source_hashes':frozen,
                        'wrapper_sha256':sha(HERE/'resume_expanded.py'),
                        'started_at_utc':stamp,'old_group_members':members,
                        'scope':'scheduler/checkpoint-only change; exact completed summaries preserved; unfinished batches resumed'})
        os.killpg(old, signal.SIGTERM)
        os.killpg(old, signal.SIGCONT)
        deadline = time.monotonic() + 10
        while group_members(old) and time.monotonic() < deadline: time.sleep(.1)
        assert not group_members(old), 'Old processes still live; no new writer started.'
        terminated = True
        with (OUT/'execution.lock').open('r+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            fcntl.flock(lock,fcntl.LOCK_UN)
        for p in invalid: p.rename(p.with_name('interrupted-' + stamp + '-' + p.name))
        for name,digest in frozen.items(): assert sha(Path(name)) == digest
        env = dict(os.environ)
        for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS']:
            env[key] = '1'
        python = ROOT.parent/'.venv-gdfs/bin/python'
        log = OUT/'controller-eight.log'
        with log.open('ab',buffering=0) as output:
            process = subprocess.Popen([str(python),str(HERE/'resume_expanded.py'),'--workers',str(workers)],
                        cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
        r=json.loads(receipt.read_text());r.update(status='resumed_pending_worker_observation',new_pid=process.pid,new_process_group=process.pid,
            log=str(log),all_frozen_hashes_unchanged=True)
        atomic(receipt,r)
        runtime = json.loads((HERE/'running-processes.json').read_text())
        for entry in runtime['processes']:
            if entry['kind']=='expanded':
                entry.update(previous_pid=old,pid=process.pid,process_group=process.pid,workers=workers,
                             log=str(log),entrypoint=str(HERE/'resume_expanded.py'))
        runtime['resize_receipt']=str(receipt.relative_to(ROOT));atomic(HERE/'running-processes.json',runtime)
        print(json.dumps(r),flush=True)
    except BaseException:
        if not terminated:
            try: os.killpg(old,signal.SIGCONT)
            except ProcessLookupError: pass
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--old-pid',type=int,required=True);p.add_argument('--workers',type=int,default=8)
    a=p.parse_args();main(a.old_pid,a.workers)
