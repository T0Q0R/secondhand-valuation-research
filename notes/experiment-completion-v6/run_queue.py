"""Local two-worker experiment queue. It never writes a manuscript or claims results."""
from pathlib import Path
import fcntl,hashlib,json,os,subprocess,time
ROOT=Path(__file__).resolve().parents[2];NOTES=Path(__file__).parent;OUT=ROOT/'outputs/completion-queue-v6';OUT.mkdir(exist_ok=True)
def write(p,j):
 tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(j,indent=2)+'\n');tmp.replace(p)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def alive(pid):
 try:os.kill(pid,0);return True
 except ProcessLookupError:return False

def main():
 lock=(OUT/'execution.lock').open('a+');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);manifest=json.loads((NOTES/'queue-launch.json').read_text());status=dict(status='waiting_for_ablation',started_unix=time.time(),pid=os.getpid(),stages=[]);write(OUT/'status.json',status)
 while not (ROOT/'outputs/completion-ablation-v6/completion.json').exists():
  if (ROOT/'outputs/completion-ablation-v6/failure.json').exists():raise RuntimeError('Ablation has a failure receipt; dependent queue stopped')
  if not alive(manifest['ablation_pid']):raise RuntimeError('Ablation exited without completion; dependent queue stopped')
  time.sleep(20)
 completion=json.loads((ROOT/'outputs/completion-ablation-v6/completion.json').read_text());assert completion['cells']==432 and completion['status']=='completed_and_corroborated'
 for stage in manifest['stages']:
  output=ROOT/stage['output'];script=ROOT/stage['script'];assert sha(script)==stage['script_sha256'];frozen=json.loads((output/'manifest.json').read_text());assert sha(output/'manifest.json')==stage['manifest_sha256'];env=os.environ.copy();env.update(OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2');output.mkdir(exist_ok=True)
  if not (output/'completion.json').exists():
   with (output/'execution.log').open('ab',buffering=0) as log:
    process=subprocess.Popen(['../.venv-gdfs/bin/python',str(script),'--output',str(output),'--workers','2'],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT);status.update(status='running',current_stage=stage['name'],child_pid=process.pid,last_update=time.time());write(OUT/'status.json',status)
    rc=process.wait()
   if rc!=0:raise RuntimeError(f"{stage['name']} failed, exit{rc}; see frozen failure receipt")
  done=json.loads((output/'completion.json').read_text());assert done['status']=='completed_and_corroborated' and done['cells']==frozen['expected_cells'];status['stages'].append(dict(name=stage['name'],completion_sha256=sha(output/'completion.json'),cells=done['cells'],time=time.time()));write(OUT/'status.json',status)
 analysis=manifest['analysis'];script=ROOT/analysis['script'];assert sha(script)==analysis['script_sha256'];status.update(status='checking_results',current_stage='aggregate_analysis',last_update=time.time());write(OUT/'status.json',status)
 with (OUT/'analysis.log').open('ab',buffering=0) as log:
  rc=subprocess.call(['../.venv-gdfs/bin/python',str(script),'--output',str(ROOT/analysis['output'])],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
 if rc!=0:raise RuntimeError('Aggregate integrity/coverage analysis failed; no paper generation allowed')
 status.update(status='computations_and_aggregate_checks_completed_scientific_visual_review_pending',last_update=time.time());write(OUT/'status.json',status)
if __name__=='__main__':
 try:main()
 except Exception as exc:
  failure=dict(status='failed_preserving_all_checkpoints',error=repr(exc),time=time.time());write(OUT/'failure.json',failure);write(OUT/'status.json',failure);raise
