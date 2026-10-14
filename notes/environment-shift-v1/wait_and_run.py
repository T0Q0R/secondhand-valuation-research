from pathlib import Path
import json,hashlib,fcntl,subprocess,os,time,traceback
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'outputs/environment-shift-queue-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,j):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(j,indent=2)+'\n');t.replace(p)
def main():
 OUT.mkdir(exist_ok=True);lock=(OUT/'execution.lock').open('a+');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);cfg=json.loads((Path(__file__).parent/'queue.json').read_text());status=dict(status='waiting_for_mechanism_queue',pid=os.getpid(),time=time.time());write(OUT/'status.json',status)
 try:
  while True:
   predecessor=ROOT/'outputs/mechanism-tail-v1';s=json.loads((predecessor/'status.json').read_text())
   if (predecessor/'failure.json').exists() or s['status'].startswith('failed'):raise RuntimeError('Mechanism queue failed')
   if s['status']=='completed_scientific_visual_review_pending':break
   os.kill(s['pid'],0);time.sleep(30)
  r=json.loads((ROOT/'outputs/completion-mechanisms-v1/completion.json').read_text());assert r['cells']==90 and r['summary_sha256']==sha(ROOT/'outputs/completion-mechanisms-v1/summary.csv');assert (ROOT/'outputs/mechanism-analysis-v1/completion.json').exists()
  assert all(sha(ROOT/p)==h for p,h in cfg['frozen_files'].items())
  with (OUT/'execution.log').open('ab',buffering=0) as log:
   p=subprocess.Popen(['../.venv-gdfs/bin/python','notes/experiment-completion-v6/run_parallel_runtime_v1.py','--config','notes/environment-shift-v1/runtime.json'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT);status.update(status='running_environment_shift',child_pid=p.pid);write(OUT/'status.json',status);rc=p.wait()
  assert rc==0;status.update(status='completed_interpretation_visual_QA_pending',finished=time.time());write(OUT/'status.json',status)
 except BaseException:
  status.update(status='failed_preserving_checkpoints',traceback=traceback.format_exc());write(OUT/'failure.json',status);write(OUT/'status.json',status);raise
if __name__=='__main__':main()
