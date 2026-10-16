"""Seven added fitting seeds; same six RPL settings and fixed populations.

Original workers, manifests and checkpoints are immutable. This runner has its
own manuscript/source closure and never disables an earlier experiment guard.
"""
from pathlib import Path
import argparse, copy, fcntl, gc, hashlib, json, os, sys, time
import joblib
import numpy as np
import pandas as pd
import torch
from threadpoolctl import threadpool_limits
import run_completion_ablation_v6 as c
from run_recovery_path_learning_v1 import variants
from recovery_path_training_v1 import train_residual
from mechanism_diagnostics_v1 import recovery_diagnostics
from run_all import load_source, rank_subset, evaluate_method
from run_crossfit import fold_assignments, inner_split
from savval import FEATURES, ActionHeads, price_features

ROOT=c.ROOT
OUT=ROOT/'outputs/rpl-ten-seed-v2'
EXTRA=[101,211,307,401,503,601,701]
SOURCES=['synthetic','jucars','mucars']
DEPS=['experiments/run_rpl_ten_seed_v2.py','experiments/recovery_path_training_v1.py',
      'experiments/run_recovery_path_learning_v1.py','experiments/mechanism_diagnostics_v1.py',
      'experiments/run_completion_ablation_v6.py','experiments/savval.py',
      'experiments/run_all.py','experiments/run_crossfit.py']

class BoundedPredictor:
    """Inference-only resource wrapper; stored CatBoost weights stay intact."""
    def __init__(self,model):self.model=model
    def predict(self,*args,**kwargs):
        kwargs['thread_count']=2
        return self.model.predict(*args,**kwargs)
    def __getattr__(self,name):
        model=self.__dict__.get('model')
        if model is None:raise AttributeError(name)
        return getattr(model,name)

def guard(out=OUT):
    m=json.loads((Path(out)/'manifest.json').read_text())
    for p,h in m['dependency_sha256'].items(): assert c.sha(ROOT/p)==h,p
    assert c.sha(ROOT/'paper/innovation-addendum-v1.tex')==m['manuscript_sha256']
    return m

def parent(source,seed):
    run='nested-development-v2' if seed in [13,42,2026] else 'nested-seven-extra-seeds-v1'
    return ROOT/'outputs'/run/source/f'seed-{seed}'

def fit_stage(est,guide,columns,cfg,seed,directory,old,setting):
    directory.mkdir(parents=True,exist_ok=True)
    base=c.stage_check(old,est,guide,seed)
    inputs=dict(estimator=c.content(est),guidance=c.content(guide),base=c.sha(base),
                config=cfg,seed=seed,variant=setting)
    cp=directory/'completion.json'; path=directory/'model.joblib'
    if cp.exists():
        r=json.loads(cp.read_text()); assert r['inputs']==inputs and r['model_sha256']==c.sha(path)
        return path
    model,head,_=joblib.load(base); assert model.residual is None
    # CatBoost inference thread count changes scheduling only; smoke checks
    # require exact prediction identity against the saved four-thread base.
    model.backbone=BoundedPredictor(model.backbone);head.model.n_jobs=2
    logs=[];started=time.time()
    for i in range(2):
        rp=directory/f'round-{i+1}.json';mp=rp.with_suffix('.joblib')
        if rp.exists():
            r=json.loads(rp.read_text());assert r['inputs']==inputs and c.sha(mp)==r['sha256']
            model,head,logs=joblib.load(mp);continue
        trace=train_residual(model,price_features(est,columns),est.target_log.to_numpy(),
              cfg,seed+i,None,gap_weight=setting['beta'],epochs=cfg['residual_epochs']//2)
        head=c.head(model,guide,columns,cfg,seed)
        logs.append(dict(round=i+1,epochs=cfg['residual_epochs']//2,loss=trace))
        c.dump(mp,(model,head,logs));c.write(rp,dict(inputs=inputs,sha256=c.sha(mp)))
    c.dump(path,(model,head,'suppression'))
    c.write(cp,dict(status='fitted',inputs=inputs,model_sha256=c.sha(path),
                    rounds=logs,seconds=time.time()-started))
    return path

def pair(task):
    source,seed,cfg,outstr,smoke=task;assert seed in EXTRA and not smoke
    out=Path(outstr);guard(out);torch.set_num_threads(2)
    folder=out/source/f'seed-{seed}';folder.mkdir(parents=True,exist_ok=True)
    lock=(folder/'execution.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with threadpool_limits(limits=2):
        e,g,evaluation,_=load_source(source,cfg)
        train=rank_subset(pd.concat([e,g],ignore_index=True),len(e)+len(g),'sav-val-cf-training-order-v2')
        assigned=fold_assignments(train,3);old=parent(source,seed);columns=FEATURES[source]
        saved=pd.read_csv(old/'outer_assignments.csv')
        assert saved.listing_id.tolist()==train.listing_id.tolist()
        assert np.array_equal(assigned,saved.outer_fold)
        c.write(folder/'data_binding.json',dict(train=c.content(train),evaluation=c.content(evaluation),
                 original_assignments_sha256=c.sha(old/'outer_assignments.csv')))
        summaries=[]
        for name,v in variants().items():
            scfg=copy.deepcopy(cfg);scfg.update(gap_penalty_weight=v['beta'],
                gap_tolerance_log=v['tolerance'],feedback_rounds=2,recovery_path_weight=v['path_weight'])
            vd=folder/name;vd.mkdir(exist_ok=True);oof=np.empty((len(train),11))
            for fold in range(3):
                est,guide=inner_split(train.loc[assigned!=fold],cfg['head_fitting_fraction'])
                p=fit_stage(est,guide,columns,scfg,seed,vd/f'outer-{fold}',old/f'outer-{fold}',v)
                model,_,_=joblib.load(p)
                oof[assigned==fold]=model.predict(price_features(train.loc[assigned==fold],columns))[0]
                del model;gc.collect()
            est,guide=inner_split(train,cfg['head_fitting_fraction'])
            p=fit_stage(est,guide,columns,scfg,seed,vd/'deployment',old/'deployment_fit',v)
            np.savez_compressed(vd/'outer_predictions.npz',prediction=oof)
            modelpath=vd/'deployment_model.joblib';receipt=modelpath.with_suffix('.json')
            binding=dict(price_sha256=c.sha(p),oof_sha256=hashlib.sha256(oof.tobytes()).hexdigest(),
                         training=c.content(train),seed=seed,head_trees=cfg['head_trees'])
            if receipt.exists():
                r=json.loads(receipt.read_text());assert r['inputs']==binding and r['sha256']==c.sha(modelpath)
            else:
                model,_,kind=joblib.load(p);_,x,valid=model.predict(price_features(train,columns))
                head=ActionHeads(cfg['head_trees'],seed);head.model.n_jobs=2
                head.fit(x,oof,valid,train.target_log.to_numpy(),model.space,
                         reported_missing=model.space.reported_missing(train))
                c.dump(modelpath,(model,head,kind));c.write(receipt,dict(inputs=binding,sha256=c.sha(modelpath)))
            model,head,_=joblib.load(modelpath)
            pred,x,valid=model.predict(price_features(evaluation,columns))
            scores=head.score(x,pred,model.space,'suppression',reported_missing=model.space.reported_missing(evaluation))
            for budget in cfg['budgets']:
                cell=vd/f'evaluation-{round(budget*10000):04d}';cell.mkdir(exist_ok=True)
                cp=cell/'completion.json'
                inputs=dict(variant=v,model=c.sha(modelpath),evaluation=c.content(evaluation),budget=budget)
                if cp.exists():
                    r=json.loads(cp.read_text());assert r['inputs']==inputs and r['outcomes_sha256']==c.sha(cell/'outcomes.csv.gz')
                    summaries.append(r['summary']);continue
                rows,s=evaluate_method(name,model,head,'suppression',evaluation,columns,scfg,seed,budget)
                check=c.matrix_audit(pred,scores,valid,evaluation,rows,budget)
                s.update(method=name,dataset=source,beta=v['beta'],tolerance=v['tolerance'],
                         rounds=2,feedback=False,axis=v['axis'],path_weight=v['path_weight'])
                rows.to_csv(cell/'outcomes.csv.gz',index=False)
                c.write(cp,dict(status='completed_and_corroborated',inputs=inputs,summary=s,audit=check,
                    outcomes_sha256=c.sha(cell/'outcomes.csv.gz'),
                    recovery_paths=recovery_diagnostics(pred,valid,model.space,evaluation,rows)))
                summaries.append(s);c.write(folder/'progress.json',dict(status='running',completed_cells=len(summaries),expected_cells=18,last_variant=name,last_budget=budget))
                print('RPL10_CELL',source,seed,name,budget,flush=True)
            del model,head,pred,x,valid,scores;gc.collect()
        pd.DataFrame(summaries).to_csv(folder/'summary.csv',index=False)
        assert len(summaries)==18
        c.write(folder/'completion.json',dict(status='completed_and_corroborated',cells=18,summary_sha256=c.sha(folder/'summary.csv')))
        guard(out)
    return summaries

def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    cfg=copy.deepcopy(json.loads((c.PARENT/'run_manifest.json').read_text())['config'])
    cfg.update(seeds=[13,42,2026]+EXTRA,budgets=[0.,.1,.3])
    manifest=dict(config=cfg,expected_pairs=30,expected_cells=540,new_cells=378,reused_cells=162,
        dependency_sha256={p:c.sha(ROOT/p) for p in DEPS},manuscript_sha256=c.sha(ROOT/'paper/innovation-addendum-v1.tex'),
        settings=variants(),scope='posthoc ten-fitting-seed extension; fixed training and evaluation populations; no confirmatory or universal superiority claim')
    mp=OUT/'manifest.json'
    if mp.exists():assert json.loads(mp.read_text())==manifest
    else:c.write(mp,manifest)
    for source in SOURCES:
        (OUT/source).mkdir(exist_ok=True)
        for seed in [13,42,2026]:
            target=ROOT/'outputs/recovery-path-learning-v1'/source/f'seed-{seed}'
            link=OUT/source/f'seed-{seed}'
            if link.is_symlink():assert link.resolve()==target
            else:assert not link.exists();link.symlink_to(target,target_is_directory=True)
    return manifest

def main():
    p=argparse.ArgumentParser();p.add_argument('--ready-only',action='store_true');a=p.parse_args()
    m=prepare()
    if a.ready_only:print(json.dumps(dict(expected_cells=540,new_cells=378,reused_cells=162)));return
    sys.path.insert(0,str(ROOT/'notes/experiment-completion-v6'))
    import run_parallel_runtime_v1 as runtime
    folder=ROOT/'outputs/rpl-ten-seed-runtime-v2';folder.mkdir(exist_ok=True)
    lock=(folder/'execution.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    c.write(folder/'manifest.json',dict(script_sha256=c.sha(Path(__file__)),max_workers=4,threads_per_worker=2,
           total_thread_budget_with_auditor=9,scientific_manifest_sha256=c.sha(OUT/'manifest.json')))
    spec=dict(name='rpl_ten_seed',output=str(OUT.relative_to(ROOT)),script=str(Path(__file__).relative_to(ROOT)),
              script_sha256=c.sha(Path(__file__)),manifest_sha256=c.sha(OUT/'manifest.json'))
    try:
        runtime.stage(spec,folder,4,folder/'status.json')
        c.write(folder/'status.json',dict(status='computed_audit_pending',cells=540,time=time.time()))
    except BaseException:
        import traceback
        c.write(folder/'failure.json',dict(status='failed_preserving_checkpoints',traceback=traceback.format_exc(),time=time.time()))
        raise

if __name__=='__main__':main()
