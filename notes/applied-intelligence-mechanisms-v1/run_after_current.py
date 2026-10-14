"""Detached append-only queue; never changes or interrupts existing runtime."""
from pathlib import Path
import fcntl,hashlib,json,os,subprocess,time,traceback,argparse
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,j):
 tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(j,indent=2)+'\n');tmp.replace(p)
def prerequisite(config):
 root=ROOT/config['predecessor_output'];status=json.loads((root/'status.json').read_text())
 if (root/'failure.json').exists() or str(status.get('status','')).startswith('failed'):raise RuntimeError('Predecessor failed; appended computation not started')
 done=status.get('status')=='computations_and_aggregate_checks_completed_scientific_visual_review_pending'
 if done:
  assert sha(root/'manifest.json')==config['predecessor_manifest_sha256']
  for stage in config['predecessor_stages']:
   folder=ROOT/stage['output'];r=json.loads((folder/'completion.json').read_text());assert r['status']=='completed_and_corroborated' and r['cells']==stage['cells'] and r['summary_sha256']==sha(folder/'summary.csv')
  assert (ROOT/'outputs/completion-analysis-v6/completion.json').exists()
  return True
 try:os.kill(config['predecessor_pid'],0)
 except ProcessLookupError:raise RuntimeError('Predecessor exited without completed status; preserve queue for inspection')
 return False

def main():
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);a=p.parse_args();cfg=json.loads(a.config.read_text());out=ROOT/cfg['tail_output'];out.mkdir(parents=True,exist_ok=True);lock=(out/'execution.lock').open('a+');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 status=dict(status='waiting_for_existing_four_stages_and_checks',pid=os.getpid(),started=time.time(),config_sha256=sha(a.config),predecessor_pid=cfg['predecessor_pid']);write(out/'status.json',status)
 try:
  while not prerequisite(cfg):time.sleep(30)
  for file,h in cfg['frozen_files'].items():assert sha(ROOT/file)==h,file
  env=os.environ.copy();env.update(OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2')
  with (out/'execution.log').open('ab',buffering=0) as log:
   process=subprocess.Popen(['../.venv-gdfs/bin/python',cfg['runtime_script'],'--config',cfg['runtime_config']],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
   status.update(status='running_appended_mechanism_stage',child_pid=process.pid,started_computation=time.time());write(out/'status.json',status);rc=process.wait()
  if rc:raise RuntimeError(f'Mechanism runtime failed:{rc};check its failure receipt')
  status.update(status='completed_scientific_visual_review_pending',finished=time.time());write(out/'status.json',status)
 except BaseException:
  status.update(status='failed_preserving_checkpoints',traceback=traceback.format_exc(),time=time.time());write(out/'failure.json',status);write(out/'status.json',status);raise
if __name__=='__main__':main()
