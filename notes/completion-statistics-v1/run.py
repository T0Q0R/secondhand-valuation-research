"""One-thread read-only paired analysis sidecar; never alters producer artifacts."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import argparse,fcntl,hashlib,json,time,traceback,functools
import numpy as np,pandas as pd
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'outputs/completion-statistics-v1'
JOBS={'ablation':('outputs/completion-ablation-v6',432),'parameters':('outputs/completion-parameters-v6',270),'stability':('outputs/completion-stability-v6',144),'sefa':('outputs/completion-sefa-v6-official',108),'mechanisms':('outputs/completion-mechanisms-v1',90)}
METRICS=['mean_positive_log_inflation','clean_mae','attack_mae','failed_query_fraction'];SEEDS=[13,42,2026]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,j):
 p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(j,indent=2)+'\n');t.replace(p)
@functools.lru_cache(maxsize=4)
def read_rows(path,expected):
 p=ROOT/path;assert sha(p)==expected
 return pd.read_csv(p,usecols=lambda k:k in ['method','budget','listing_id','batch','positive_log_inflation','clean_absolute_error','attack_absolute_error','action','query_succeeded'])
def original(source,seed,method,budget):
 folder=ROOT/'outputs/nested-development-v2'/source/f'seed-{seed}';receipt=json.loads((folder/'evaluation_completion.json').read_text());p=folder/'per_listing_outcomes.csv.gz';r=read_rows(str(p.relative_to(ROOT)),receipt['outcomes_sha256']);return r[(r.method==method)&np.isclose(r.budget,budget)].copy()
def cell_rows(cp):
 r=json.loads(cp.read_text());assert r['status']=='completed_and_corroborated'
 if 'outcomes_sha256' in r:return read_rows(str((cp.parent/'outcomes.csv.gz').relative_to(ROOT)),r['outcomes_sha256']).copy()
 if 'reused_original_outcomes' in r:
  u=r['reused_original_outcomes'];d=read_rows(u['path'],u['sha256']);return d[(d.method==u['method'])&np.isclose(d.budget,u['budget'])].copy()
 u=r['reused'];budget=r['inputs']['budget']
 if u['type']=='original':
  d=read_rows(u['outcomes'],u['sha256']);return d[(d.method==u['method'])&np.isclose(d.budget,budget)].copy()
 assert u['type']=='ablation';return cell_rows(ROOT/u['root']/'evaluation'/u['method']/f'budget-{round(budget*10000):04d}'/'completion.json')
def tensor(rows):
 assert len(rows)==1000 and rows.listing_id.is_unique and rows.query_succeeded.dtype.kind=='b'
 r=rows.sort_values(['batch','listing_id']).copy();r['failed_query_fraction']=((r.action>=0)&~r.query_succeeded).astype(float)
 r=r.rename(columns=dict(positive_log_inflation=METRICS[0],clean_absolute_error=METRICS[1],attack_absolute_error=METRICS[2]))
 assert (r.groupby('batch').size()==100).all() and r.batch.nunique()==10
 return r.groupby('batch',sort=True)[METRICS].mean().to_numpy(),list(zip(r.batch,r.listing_id))
def bootstrap(x,repetitions=4000):
 # x contrast×seed×batch×metric; common resamples preserve all pairings.
 rng=np.random.default_rng(20261014);ns=x.shape[1];nb=x.shape[2];si=rng.integers(ns,size=(repetitions,ns));bi=rng.integers(nb,size=(repetitions,nb))
 cross=x[:,si[:,:,None],bi[:,None,:],:].mean(axis=(2,3));seed=x.mean(axis=2)[:,si,:].mean(axis=2);batch=x.mean(axis=1)[:,bi,:].mean(axis=2);point=x.mean(axis=(1,2));sd=cross.std(axis=1,ddof=1)
 z=np.divide(abs(cross-point[:,None,:]),sd[:,None,:],out=np.zeros_like(cross),where=sd[:,None,:]>0);q=np.quantile(z.max(axis=(0,2)),.95)
 return dict(point=point,lower=np.quantile(cross,.025,axis=1),upper=np.quantile(cross,.975,axis=1),seed_sd=seed.std(axis=1,ddof=1),batch_sd=batch.std(axis=1,ddof=1),cross_sd=sd,joint_lower=point-q*sd,joint_upper=point+q*sd)
def pareto(table):
 records=[]
 means=table.groupby(['dataset','budget','method'])[METRICS].mean().reset_index()
 for _,g in means.groupby(['dataset','budget']):
  a=g[METRICS].to_numpy();dom=((a[:,None,:]<=a[None,:,:]).all(2)&(a[:,None,:]<a[None,:,:]).any(2)).any(0)
  g=g.copy();g['descriptive_nondominated']=~dom;records.append(g)
 return pd.concat(records,ignore_index=True)
def pairs_for(stage,methods):
 if stage=='ablation':return [('S1F1G1',m) for m in methods if m!='S1F1G1']
 if stage in ['parameters','stability']:return [('beta-0.5',m) for m in methods if m!='beta-0.5']
 if stage=='sefa':return [(ref,m) for m in methods for ref in ['masking_suppression','sav_val']]
 return [('epoch-weak',m) for m in methods if m not in ['epoch-weak','feedback-off']]+[('feedback-off',m) for m in methods if m!='feedback-off']+[('epoch-strong','batch-strong'),('batch-weak','batch-strong')]
def analyze(stage):
 path,count=JOBS[stage];root=ROOT/path;receipt=json.loads((root/'completion.json').read_text());assert receipt['status']=='completed_and_corroborated' and receipt['cells']==count and receipt['summary_sha256']==sha(root/'summary.csv')
 summary=pd.read_csv(root/'summary.csv');assert len(summary)==count
 indexed={};bindings={}
 for cp in root.glob('*/seed-*/**/completion.json'):
  r=json.loads(cp.read_text())
  if 'summary' not in r:continue
  s=r['summary'];key=(s['dataset'],int(s['seed']),float(s['budget']),s['method']);assert key not in indexed;indexed[key]=cp;bindings[str(cp.relative_to(ROOT))]=sha(cp)
 assert len(indexed)==count
 results=[];source_data=[]
 for (source,budget),g in summary.groupby(['dataset','budget']):
  methods=sorted(g.method.unique());pairs=pairs_for(stage,methods);needed=sorted(set(sum(([a,b] for a,b in pairs),[])));values={};ids=None
  for method in needed:
   seed_values=[]
   for seed in SEEDS:
    key=(source,seed,float(budget),method)
    if key in indexed:rr=cell_rows(indexed[key])
    elif stage=='stability':rr=cell_rows(ROOT/'outputs/completion-parameters-v6'/source/f'seed-{seed}'/'beta-0.5'/f'evaluation-{round(budget*10000):04d}'/'completion.json')
    else:rr=original(source,seed,method,budget)
    v,keys=tensor(rr)
    if ids is None:ids=keys
    assert keys==ids,'Seed/batch/listing pairing changed'
    seed_values.append(v)
    if key in indexed:
     s=json.loads(indexed[key].read_text())['summary'];assert np.allclose(v.mean(0),[s[m] for m in METRICS],atol=1e-7,rtol=1e-9),'Row-summary mismatch'
    for b,vec in enumerate(v):source_data.append(dict(dataset=source,budget=budget,method=method,seed=seed,batch=b,**dict(zip(METRICS,vec))))
   values[method]=np.stack(seed_values)
  x=np.stack([values[ref]-values[method] for ref,method in pairs]);est=bootstrap(x)
  for i,(ref,method) in enumerate(pairs):
   for m,metric in enumerate(METRICS):results.append(dict(dataset=source,budget=budget,reference=ref,intervention=method,metric=metric,**{k:float(v[i,m]) for k,v in est.items()},fitting_seeds=3,evaluation_batches=10,resamples=4000,family_contrasts=len(pairs)*len(METRICS)))
 out=OUT/stage;out.mkdir(parents=True,exist_ok=True);pd.DataFrame(results).to_csv(out/'paired_uncertainty.csv',index=False);batches=pd.DataFrame(source_data);batches.to_csv(out/'paired_batch_means.csv',index=False);pareto(summary).to_csv(out/'descriptive_pareto.csv',index=False)
 summary[['dataset','method','seed','budget','nonconverged_batch_fraction','max_remaining_response_regret']].to_csv(out/'convergence_all_cells.csv',index=False)
 write(out/'completion.json',dict(status='computed_and_row_summary_checked_interpretation_pending',stage=stage,cells=count,source_summary_sha256=sha(root/'summary.csv'),cell_receipts=bindings,artifacts={p.name:sha(p) for p in out.glob('*.csv')},scope='Exploratory crossed fitting-seed/batch bootstrap with3seeds/10batches; no nominal coverage/FWER guarantee;fixed training population;joint bands family=stage/source/budget/all listed contrasts×4metrics;no cross-family guarantee',sign='reference-intervention;positive decrease,not necessarily preferable for failed queries without accuracy/budget context'))
 read_rows.cache_clear()
def self_test():
 x=np.zeros((2,3,10,4));x[1]=2;z=bootstrap(x,100);assert np.allclose(z['point'][0],0) and np.allclose(z['lower'][1],2) and np.allclose(z['joint_upper'][1],2)
 p=pareto(pd.DataFrame([dict(dataset='toy',budget=.1,method=k,**dict(zip(METRICS,v))) for k,v in [('a',[1,1,1,1]),('b',[2,2,2,2]),('c',[0,3,0,3])]]));assert set(p.loc[p.descriptive_nondominated,'method'])=={'a','c'}
 # Exercise a real reused cell resolver and row/summary equality without refitting.
 cp=ROOT/'outputs/completion-ablation-v6/synthetic/seed-13/evaluation/S1F1G1/budget-1000/completion.json';v,_=tensor(cell_rows(cp));s=json.loads(cp.read_text())['summary'];assert np.allclose(v.mean(0),[s[m] for m in METRICS])
 print('PASS zero/constant contrast,paired tensor,real reused rows,and Pareto checks')
def main():
 p=argparse.ArgumentParser();p.add_argument('--self-test',action='store_true');a=p.parse_args()
 if a.self_test:self_test();return
 OUT.mkdir(exist_ok=True);lock=(OUT/'execution.lock').open('a+');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);cfg=json.loads((Path(__file__).parent/'launch.json').read_text());assert sha(Path(__file__))==cfg['script_sha256']
 try:
  for stage,(path,count) in JOBS.items():
   cp=ROOT/path/'completion.json';local=OUT/stage/'completion.json'
   while not cp.exists():
    monitor=ROOT/('outputs/mechanism-tail-v1' if stage=='mechanisms' else 'outputs/completion-parallel-runtime-v1');status=json.loads((monitor/'status.json').read_text())
    if (monitor/'failure.json').exists() or str(status['status']).startswith('failed'):raise RuntimeError('Producer failure;analysis stopped')
    if status['status'] in ['completed_scientific_visual_review_pending','computations_and_aggregate_checks_completed_scientific_visual_review_pending']:raise RuntimeError('Producer finished without required stage')
    os.kill(status['pid'],0);write(OUT/'status.json',dict(status='waiting_for_stage',stage=stage,pid=os.getpid(),threads=1,time=time.time()));time.sleep(30)
   if local.exists():
    r=json.loads(local.read_text());assert r['source_summary_sha256']==sha(ROOT/path/'summary.csv') and all(sha(local.parent/f)==h for f,h in r['artifacts'].items());continue
   write(OUT/'status.json',dict(status='analyzing',stage=stage,pid=os.getpid(),threads=1,time=time.time()));analyze(stage)
  write(OUT/'status.json',dict(status='completed_interpretation_visual_QA_pending',pid=os.getpid(),time=time.time(),paper_generated=False))
 except BaseException:
  failure=dict(status='failed_preserving_results',pid=os.getpid(),time=time.time(),traceback=traceback.format_exc());write(OUT/'failure.json',failure);write(OUT/'status.json',failure);raise
if __name__=='__main__':
 with threadpool_limits(limits=1):main()
