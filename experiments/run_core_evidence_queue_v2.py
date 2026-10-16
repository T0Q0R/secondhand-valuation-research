"""Durable bounded-resource audit queue; records four-phase completion only
after independent statistic re-evaluation. No manuscript writes.
"""
from pathlib import Path
import argparse,fcntl,hashlib,json,multiprocessing as mp,os,subprocess,sys,time,traceback,zipfile,shutil
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[name]='1'
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'experiments'))
import core_evidence_audit_v2 as a

RUNTIME=ROOT/'outputs/core-evidence-runtime-v2'
STAGES=['rpl','mechanisms','sefa','gdfs','dime','efa','aco','rpl10']
FILES=['experiments/core_evidence_audit_v2.py','experiments/audit_core_aco_v2.py',
       'experiments/analyze_core_evidence_v2.py','experiments/check_core_statistics_v2.py',
       'experiments/run_core_evidence_queue_v2.py','experiments/run_rpl_ten_seed_v2.py',
       'experiments/savval.py','experiments/run_all.py','experiments/run_crossfit.py',
       'experiments/run_completion_sefa_v6.py','experiments/recent_acquisition_training_v1.py',
       'experiments/conditional_neighbor_head.py']

def source_guard(manifest):
    for p,h in manifest['source_hashes'].items():assert a.sha(ROOT/p)==h,p
    for p,h in manifest['producer_manifests'].items():assert a.sha(ROOT/p)==h,p

def worker(stage,source,seed,result):
    try:
        import torch
        from threadpoolctl import threadpool_limits
        torch.set_num_threads(1)
        with threadpool_limits(limits=1):r=a.audit_pair(stage,source,seed)
        a.write(result,r)
    except BaseException:
        a.write(result,dict(status='failed',stage=stage,dataset=source,seed=seed,traceback=traceback.format_exc()))
        raise

def producer_active():
    p=ROOT/'outputs/rpl-ten-seed-runtime-v2/status.json'
    r=a.read(p)
    if r.get('status')=='computed_audit_pending':return False
    if (p.parent/'failure.json').exists():raise RuntimeError('RPL producer failed; checkpoint evidence retained')
    return True

def memory_available():
    text=subprocess.check_output(['memory_pressure','-Q'],text=True)
    import re
    fraction=int(re.search(r'free percentage:\s*(\d+)%',text).group(1))/100
    total=int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True))
    return fraction*total/2**30

def audit_stage(stage,manifest):
    producer=ROOT/'outputs'/a.STAGES[stage];m=a.read(producer/'manifest.json')
    cfg=m['parent_config'] if stage=='aco' else m['config']
    todo=[(d,s) for d in cfg['datasets'] for s in cfg['seeds']]
    ctx=mp.get_context('spawn');active={};results=[]
    while todo or active:
        source_guard(manifest)
        for pid,(proc,key,rp) in list(active.items()):
            if proc.is_alive():continue
            proc.join();r=a.read(rp) if rp.exists() else {}
            if proc.exitcode or r.get('status')!='completed':
                for other,_,_ in active.values():
                    if other.is_alive():other.terminate();other.join()
                raise RuntimeError(f'Audit worker failed: {key}; see {rp}')
            results.append(r);del active[pid]
        limit=1 if producer_active() else 8
        if todo and len(active)<limit and (memory_available()>=6 or not active):
            key=todo.pop(0);rp=RUNTIME/'workers'/f'{stage}-{key[0]}-{key[1]}.json'
            proc=ctx.Process(target=worker,args=(stage,*key,rp));proc.start();active[proc.pid]=(proc,key,rp)
        a.write(RUNTIME/'status.json',dict(status='auditing',stage=stage,pid=os.getpid(),active_pids=list(active),
              completed_pairs=len(results),total_pairs=len(cfg['datasets'])*len(cfg['seeds']),
              audit_worker_limit=limit,threads_per_auditor=1,training_threads=8 if limit==1 else 0,
              memory_admission_gib=6,last_update=time.time()))
        time.sleep(3)
    expected={'rpl':162,'mechanisms':90,'sefa':108,'gdfs':108,'dime':108,'efa':108,'aco':144,'rpl10':540}[stage]
    assert sum(x['cells'] for x in results)==expected
    for phase in ['fit-audit','outcome-audit']:
        a.write(a.OUT/phase/stage/'completion.json',dict(status='completed',stage=stage,cells=expected,
             checker_sha256=a.sha(Path(a.__file__)),pairs=results,
             scope='shared data loading/model primitives; independent role reconstruction/head targets or integer allocation/all-legal-report utility re-derivation; not independent full-stack implementation'))

def sync_stage(stage,checkout):
    """Publish small stage evidence under explicit project progress policy.
    A failed push is recorded as pending and does not delete scientific results.
    """
    if checkout is None:return dict(status='pending_no_sync_checkout')
    import numpy as np
    def git(*args):return subprocess.check_output(['git','-C',str(checkout),*args],text=True,stderr=subprocess.STDOUT).strip()
    lock=(ROOT/'notes/core-evidence-v2/progress-sync.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX)
    try:
        assert git('remote','get-url','origin')=='https://github.com/T0Q0R/secondhand-valuation-research.git'
        if git('status','--porcelain'):raise RuntimeError('Sync checkout has unsynced changes; preserve for review')
        git('fetch','origin','main');git('merge','--ff-only','origin/main')
        relative=Path('notes/core-evidence-v2/completed-stages')/stage;target=checkout/relative;target.mkdir(parents=True,exist_ok=True)
        for phase in ['fit-audit','outcome-audit','analysis','statistics-check']:
            shutil.copy2(a.OUT/phase/stage/'completion.json',target/(phase+'-completion.json'))
        for filename in ['audited_cell_summaries.csv','paired_contrasts.csv','multiobjective_means.csv','contrast_keys.json']:
            shutil.copy2(a.OUT/'analysis'/stage/filename,target/filename)
        # Preserve exact bytes named in the analysis artifact receipt. These are
        # aggregate paired bootstrap tensors, not listing data/model weights.
        shutil.copy2(a.OUT/'analysis'/stage/'paired_tensors_and_draws.npz',target/'paired_tensors_and_draws.npz')
        for p in target.iterdir():
            if p.name in a.read(a.OUT/'analysis'/stage/'completion.json')['artifacts']:
                assert a.sha(p)==a.read(a.OUT/'analysis'/stage/'completion.json')['artifacts'][p.name]
        with zipfile.ZipFile(target/'audit-receipts.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
            # Receipts only: no source listings, prices per listing or model weights.
            for phase in ['fit-audit','outcome-audit']:
                for p in (a.OUT/phase/stage).rglob('*.json'):archive.write(p,str(p.relative_to(a.OUT)))
            for p in (a.OUT/'fit-audit/models').glob('*.json'):archive.write(p,str(p.relative_to(a.OUT)))
        assert (target/'audit-receipts.zip').stat().st_size<10_000_000
        stamp=time.strftime('%Y-%m-%dT%H:%M:%S%z')
        note=f'{stamp}：核心证据阶段{stage}四阶段复算完成；小型结果、配对张量/抽样索引与审计凭据已提交。共享加载/预测原语边界保留；区间属探索性，不是科学人工复核或投稿就绪。其他阶段以runtime状态为准。'
        original_local={f:a.sha(ROOT/f) for f in ['docs/PROGRESS.md','docs/STATUS.md','docs/STATUS.json']}
        p=checkout/'docs/PROGRESS.md';p.write_text(p.read_text()+'\n\n'+note+'\n')
        p=checkout/'docs/STATUS.md';p.write_text('# 最新：核心证据分阶段审计进度\n\n'+note+'\n\n'+p.read_text())
        p=checkout/'docs/STATUS.json';d=a.read(p);d.setdefault('core_evidence_v2',{}).setdefault('four_phase_completed_stages',[])
        if stage not in d['core_evidence_v2']['four_phase_completed_stages']:d['core_evidence_v2']['four_phase_completed_stages'].append(stage)
        p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
        git('add',str(relative),'docs/PROGRESS.md','docs/STATUS.md','docs/STATUS.json')
        git('commit','-m',f'Complete four-phase core evidence audit for {stage}')
        commit=git('rev-parse','HEAD');git('push','origin','main')
        assert git('ls-remote','origin','refs/heads/main').split()[0]==commit
        # Copy only the newly synchronized progress documents back to the shared workspace.
        for f in ['docs/PROGRESS.md','docs/STATUS.md','docs/STATUS.json']:
            if a.sha(ROOT/f)==original_local[f]:shutil.copy2(checkout/f,ROOT/f)
        return dict(status='pushed_and_read_back',commit=commit)
    except BaseException:
        return dict(status='pending_sync_failed_preserving_results',traceback=traceback.format_exc())

def main():
    p=argparse.ArgumentParser();p.add_argument('--sync-checkout',type=Path);args=p.parse_args()
    RUNTIME.mkdir(exist_ok=True);lock=(RUNTIME/'execution.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    manifest=dict(stages=STAGES,source_hashes={p:a.sha(ROOT/p) for p in FILES},
        producer_manifests={str((ROOT/'outputs'/n/'manifest.json').relative_to(ROOT)):a.sha(ROOT/'outputs'/n/'manifest.json') for n in a.STAGES.values()},
        cpu_policy='1 auditor while 4x2-thread training; then up to8 one-thread auditors; serial analysis/statistics',
        old_core_cells=828,added_rpl_cells=378,unique_target_cells=1206,all_1719_cells_upgraded=False)
    file=RUNTIME/'manifest.json'
    if file.exists():assert a.read(file)==manifest
    else:a.write(file,manifest)
    finished=[]
    try:
        for stage in STAGES:
            source_guard(manifest)
            if stage=='rpl10':
                while producer_active():
                    source_guard(manifest);a.write(RUNTIME/'status.json',dict(status='waiting_for_RPL_producer',stage=stage,pid=os.getpid(),last_update=time.time()));time.sleep(10)
                assert a.read(ROOT/'outputs/rpl-ten-seed-v2/completion.json')['cells']==540
            closure=RUNTIME/'stages'/stage/'completion.json'
            if closure.exists():
                saved=a.read(closure)
                for phase,h in saved['phase_completion_hashes'].items():assert a.sha(a.OUT/phase/stage/'completion.json')==h
                assert saved['source_closure_sha256']==a.sha(file)
                finished.append(stage);continue
            audit_stage(stage,manifest)
            for script in ['analyze_core_evidence_v2.py','check_core_statistics_v2.py']:
                a.write(RUNTIME/'status.json',dict(status='analysis_or_statistics',stage=stage,script=script,pid=os.getpid(),last_update=time.time()))
                subprocess.run([sys.executable,str(ROOT/'experiments'/script),'--stage',stage],check=True,cwd=ROOT)
            source_guard(manifest)
            phases={phase:a.sha(a.OUT/phase/stage/'completion.json') for phase in ['fit-audit','outcome-audit','analysis','statistics-check']}
            a.write(closure,dict(status='four_phases_completed_human_scientific_review_pending',stage=stage,phase_completion_hashes=phases,
                   manuscript_generated=False,source_closure_sha256=a.sha(file),completed_at_unix=time.time()))
            sync=sync_stage(stage,args.sync_checkout);a.write(RUNTIME/'sync'/f'{stage}.json',sync)
            finished.append(stage)
            (RUNTIME/'INTERNAL_REPORT.md').write_text('Completed four-phase computational audits: '+', '.join(finished)+'. Human scientific review and manuscript integration remain pending. No experiment exclusions; no claim of universal RPL superiority. Failed syncs are preserved under sync/.\n')
        a.write(RUNTIME/'completion.json',dict(status='core_computations_and_four_phase_checks_completed_scientific_review_pending',
                unique_audited_experiment_cells=1206,stages=finished,source_manifest_sha256=a.sha(file),manuscript_generated=False))
        a.write(RUNTIME/'status.json',dict(status='completed_scientific_review_pending',stages=finished,pid=os.getpid(),last_update=time.time()))
    except BaseException:
        for child in mp.active_children():child.terminate();child.join()
        r=dict(status='failed_preserving_all_checkpoints',completed_stages=finished,traceback=traceback.format_exc(),last_update=time.time())
        a.write(RUNTIME/'failure.json',r);a.write(RUNTIME/'status.json',r);raise
if __name__=='__main__':main()
