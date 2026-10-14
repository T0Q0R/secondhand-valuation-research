"""Runtime-only four-process scheduler; all frozen scientific workers unmodified.
Scientific manifests/checkpoints stay immutable; concurrency has separate provenance.
"""
from pathlib import Path
import argparse,fcntl,hashlib,importlib,json,multiprocessing as mp,os,re,subprocess,sys,time,traceback
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'experiments'))
ACTIVE_RUNTIME=None
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(obj,indent=2)+'\n');tmp.replace(p)
def memory():
 text=subprocess.run(['memory_pressure','-Q'],capture_output=True,text=True,check=True).stdout;match=re.search(r'free percentage:\s*(\d+)%',text);assert match,text
 total=int(subprocess.run(['sysctl','-n','hw.memsize'],capture_output=True,text=True,check=True).stdout);return dict(free_percent=int(match.group(1)),estimated_reclaimable_gib=total*int(match.group(1))/100/2**30)
def run_pair(module_name,task,receipt):
 try:
  module=importlib.import_module(module_name);function=module.worker if module_name=='run_completion_ablation_v6' else module.pair
  function(task);write(receipt,dict(status='worker_returned',pair=task[:2],pid=os.getpid(),time=time.time()))
 except BaseException:
  write(receipt,dict(status='failed',pair=task[:2],pid=os.getpid(),traceback=traceback.format_exc(),time=time.time()));raise

def verified_pair(folder,expected):
 p=folder/'completion.json'
 if not p.exists():return False
 r=json.loads(p.read_text());assert r['status']=='completed_and_corroborated' and r['cells']==expected;assert sha(folder/'summary.csv')==r['summary_sha256'];return True

def collect(output,cfg,cells_per_pair,expected):
 import pandas as pd
 parts=[]
 for source in cfg['datasets']:
  for seed in cfg['seeds']:
   folder=output/source/f'seed-{seed}';assert verified_pair(folder,cells_per_pair);parts.append(pd.read_csv(folder/'summary.csv'))
 table=pd.concat(parts,ignore_index=True);assert len(table)==expected and not table.duplicated(['dataset','seed','method','budget']).any();tmp=output/'summary.csv.tmp';table.to_csv(tmp,index=False);tmp.replace(output/'summary.csv');return len(table)

def stage(spec,runtime,limit,status_path):
 import pandas as pd
 output=ROOT/spec['output'];module_path=ROOT/spec['script'];assert sha(module_path)==spec['script_sha256'];manifest_path=output/'manifest.json';assert sha(manifest_path)==spec['manifest_sha256'];manifest=json.loads(manifest_path.read_text());cfg=manifest['config'];expected=manifest['expected_cells'];pairs=len(cfg['datasets'])*len(cfg['seeds']);per_pair=expected//pairs;module_name=module_path.stem;smoke=manifest.get('smoke_only',False);lock=(output/'execution.lock').open('a+');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 if (output/'completion.json').exists():
  old=json.loads((output/'completion.json').read_text());assert old['cells']==expected and old['summary_sha256']==sha(output/'summary.csv');return
 pending=[]
 for source in cfg['datasets']:
  for seed in cfg['seeds']:
   if not verified_pair(output/source/f'seed-{seed}',per_pair):pending.append((source,seed,cfg,str(output),smoke))
 ctx=mp.get_context('spawn');active={};finished=pairs-len(pending);started=time.time();last_wait=0;max_active=0
 print('STAGE',spec['name'],'remaining_pairs',len(pending),'max_workers',limit,flush=True)
 while pending or active:
  for pid,(process,task,receipt) in list(active.items()):
   if process.is_alive():continue
   process.join();result=json.loads(receipt.read_text()) if receipt.exists() else {}
   if process.exitcode!=0 or result.get('status')!='worker_returned':
    failure=dict(status='failed',pair=task[:2],exitcode=process.exitcode,receipt=str(receipt),remaining_pairs=[x[:2] for x in pending],active_pids=[x for x in active if x!=pid],time=time.time());write(runtime/'failure.json',failure)
    # Stop only this scheduler's remaining workers; completed checkpoints survive.
    for other,(proc,_,_) in active.items():
     if other!=pid and proc.is_alive():proc.terminate();proc.join()
    raise RuntimeError(f"{spec['name']} worker failed: {failure}")
   assert verified_pair(output/task[0]/f'seed-{task[1]}',per_pair);finished+=1;del active[pid]
  mem=memory()
  if pending and len(active)<limit and (mem['estimated_reclaimable_gib']>=6 or not active):
   # The6GiB admission threshold aims to retain4GiB after another~2GiB worker.
   # It is an admission guard, not a hard OS memory reservation.
   task=pending.pop(0);receipt=runtime/'workers'/f"{spec['name']}-{task[0]}-{task[1]}.json";proc=ctx.Process(target=run_pair,args=(module_name,task,receipt));proc.start();active[proc.pid]=(proc,task,receipt);max_active=max(max_active,len(active));print('START',spec['name'],task[:2],proc.pid,mem,flush=True)
  if time.time()-last_wait>10:
   state=dict(status='running',stage=spec['name'],pid=os.getpid(),active_pids=list(active),active_pairs=[x[1][:2] for x in active.values()],remaining_pairs=[t[:2] for t in pending],completed_pairs=finished,expected_pairs=pairs,max_workers=limit,threads_per_worker=2,cpu_thread_budget=limit*2,memory=mem,last_update=time.time());write(status_path,state);last_wait=time.time()
  time.sleep(3)
 count=collect(output,cfg,per_pair,expected);result=dict(status='completed_and_corroborated',cells=count,summary_sha256=sha(output/'summary.csv'),manifest_sha256=sha(manifest_path),smoke_only=smoke,runtime_override_receipt=str((runtime/'manifest.json').relative_to(ROOT)),maximum_observed_processes=max_active)
 if module_name=='run_completion_ablation_v6':result['pairs']=pairs
 write(output/'completion.json',result);write(runtime/f"{spec['name']}-completion.json",dict(**result,seconds=time.time()-started));print('STAGE_DONE',spec['name'],count,flush=True)

def main():
 global ACTIVE_RUNTIME
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);a=p.parse_args();config=json.loads(a.config.read_text());runtime=ROOT/config['runtime_output'];runtime.mkdir(parents=True,exist_ok=True);lock=(runtime/'execution.lock').open('a+');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 ACTIVE_RUNTIME=runtime
 os.environ.update(OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2');manifest=dict(config=config,config_sha256=sha(a.config),runtime_script_sha256=sha(Path(__file__)),scientific_workers_modified=False)
 mpth=runtime/'manifest.json'
 if mpth.exists():assert json.loads(mpth.read_text())==manifest
 else:write(mpth,manifest)
 status_path=runtime/'status.json'
 for item in config['stages']:stage(item,runtime,config['max_workers'],status_path)
 if config.get('analysis'):
  analysis=config['analysis'];script=ROOT/analysis['script'];assert sha(script)==analysis['script_sha256'];write(status_path,dict(status='checking_results',pid=os.getpid(),time=time.time()))
  with (runtime/'analysis.log').open('ab',buffering=0) as log:
   rc=subprocess.call(['../.venv-gdfs/bin/python',str(script),'--output',str(ROOT/analysis['output'])],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
  if rc!=0:raise RuntimeError('Aggregate checking failed; see analysis.log')
 write(status_path,dict(status='computations_and_aggregate_checks_completed_scientific_visual_review_pending',pid=os.getpid(),time=time.time(),manuscript_generated=False));print('QUEUE_DONE',flush=True)
if __name__=='__main__':
 try:main()
 except BaseException:
  # A separate runtime failure never rewrites a frozen scientific manifest.
  for child in mp.active_children():child.terminate();child.join()
  if ACTIVE_RUNTIME is not None:
   failure=dict(status='failed_preserving_all_checkpoints',traceback=traceback.format_exc(),time=time.time());write(ACTIVE_RUNTIME/'failure.json',failure);write(ACTIVE_RUNTIME/'status.json',failure)
  traceback.print_exc();raise
