from pathlib import Path
import json,hashlib,fcntl,subprocess,os,time,traceback
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'outputs/recent-five-queue-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,j):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(j,indent=2)+'\n');t.replace(p)
def main():
 OUT.mkdir(exist_ok=True);lock=(OUT/'execution.lock').open('a+');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);cfg=json.loads((Path(__file__).parent/'queue.json').read_text());status=dict(status='waiting_for_recovery_path_learning',pid=os.getpid(),time=time.time());write(OUT/'status.json',status)
 try:
  while True:
   predecessor=ROOT/'outputs/recovery-path-learning-queue-v1';s=json.loads((predecessor/'status.json').read_text())
   if (predecessor/'failure.json').exists() or s['status'].startswith('failed'):raise RuntimeError('Recovery path learning queue failed')
   if s['status']=='completed_interpretation_visual_QA_pending':break
   os.kill(s['pid'],0);time.sleep(30)
  r=json.loads((ROOT/'outputs/recovery-path-learning-v1/completion.json').read_text());assert r['cells']==162 and r['summary_sha256']==sha(ROOT/'outputs/recovery-path-learning-v1/summary.csv');assert (ROOT/'outputs/recovery-path-learning-analysis-v1/completion.json').exists()
  assert all(sha(ROOT/p)==h for p,h in cfg['frozen_files'].items())
  with (OUT/'execution.log').open('ab',buffering=0) as log:
   p=subprocess.Popen(['../.venv-gdfs/bin/python','notes/experiment-completion-v6/run_parallel_runtime_v1.py','--config','notes/recent-five-v1/runtime.json'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT);status.update(status='running_recent_three_baselines',child_pid=p.pid);write(OUT/'status.json',status);rc=p.wait()
  assert rc==0;status.update(status='completed_interpretation_visual_QA_pending',finished=time.time());write(OUT/'status.json',status)
 except BaseException:
  status.update(status='failed_preserving_checkpoints',traceback=traceback.format_exc());write(OUT/'failure.json',status);write(OUT/'status.json',status);raise
if __name__=='__main__':main()
