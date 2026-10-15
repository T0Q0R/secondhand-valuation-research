"""Fill the stability tail with one unchanged SEFA pair; stage lock prevents overlap."""
from pathlib import Path
import os,json,hashlib,fcntl,sys,time,traceback
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'experiments'))
OUT=ROOT/'outputs/compute-prefetch-v1'
def write(name,value):
 p=OUT/name;t=p.with_suffix('.tmp');t.write_text(json.dumps(value,indent=2)+'\n');t.replace(p)
def main():
 OUT.mkdir(exist_ok=True);own=(OUT/'execution.lock').open('a+');fcntl.flock(own,fcntl.LOCK_EX|fcntl.LOCK_NB)
 s=json.loads((ROOT/'outputs/completion-parallel-runtime-v1/status.json').read_text())
 assert s['stage']=='stability' and not s['remaining_pairs'] and len(s['active_pids'])<=3
 os.kill(s['pid'],0)
 runtime=json.loads((ROOT/'notes/experiment-completion-v6/parallel-runtime-config-v1.json').read_text());spec=next(x for x in runtime['stages'] if x['name']=='sefa2025')
 out=ROOT/spec['output'];stage_lock=(out/'execution.lock').open('a+');fcntl.flock(stage_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 # Holding the same global stage lock makes the original scheduler wait at transition.
 # It will then discover this verified completed pair and skip it.
 for p,h in [(ROOT/spec['script'],spec['script_sha256']),(out/'manifest.json',spec['manifest_sha256'])]:assert hashlib.sha256(p.read_bytes()).hexdigest()==h
 manifest=json.loads((out/'manifest.json').read_text());cfg=manifest['config'];assert not manifest['smoke_only']
 source,seed=cfg['datasets'][0],cfg['seeds'][0]
 state=dict(status='running_one_sefa_pair',pid=os.getpid(),source=source,seed=seed,threads=2,stage_lock_held=True,original_scheduler=s['pid'],started=time.time());write('status.json',state)
 import run_completion_sefa_v6 as module
 result=module.pair((source,seed,cfg,str(out),False))
 receipt=json.loads((out/source/f'seed-{seed}'/'completion.json').read_text());assert receipt['cells']==2*len(cfg['budgets']) and receipt['status']=='completed_and_corroborated'
 state.update(status='completed_pair_released_to_original_scheduler',cells=len(result),finished=time.time());write('status.json',state);write('completion.json',state)
if __name__=='__main__':
 try:main()
 except BaseException:
  OUT.mkdir(exist_ok=True);write('failure.json',dict(status='failed_preserving_checkpoints',traceback=traceback.format_exc(),time=time.time()));raise
