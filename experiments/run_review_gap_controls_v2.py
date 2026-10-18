"""Equivalent faster stronger-gap controls; immutable v1 checkpoints preserved.

New versions use the frozen RPL fit routine without calling its obsolete paper
guard. Dependencies are bound by this runner's own manifest. No tolerance edits.
"""
from pathlib import Path
import argparse, copy, fcntl, gc, hashlib, json, os, sys, time, traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
import joblib
import numpy as np
import pandas as pd
import torch
from threadpoolctl import threadpool_limits
import run_completion_ablation_v6 as c
import run_rpl_ten_seed_v2 as prior
from review_gap_price_fit_v2 import fit_stage as fit_price_stage
from run_all import load_source, rank_subset, evaluate_method
from run_crossfit import fold_assignments, inner_split
from savval import FEATURES, ActionHeads, price_features

ROOT=c.ROOT
OUT=ROOT/'outputs/review-gap-controls-v2'
REF=ROOT/'outputs/rpl-ten-seed-v2'
SEEDS=[13,42,2026,101,211,307,401,503,601,701]
DEPS=['experiments/'+p for p in ['run_review_gap_controls_v2.py','review_gap_price_fit_v2.py',
 'run_rpl_ten_seed_v2.py','run_recovery_path_learning_v1.py',
 'recovery_path_training_v1.py','run_completion_ablation_v6.py',
 'savval.py','run_all.py','run_crossfit.py']]

def data(source,cfg,seed):
    e,g,ev,provenance=load_source(source,cfg)
    train=rank_subset(pd.concat([e,g],ignore_index=True),len(e)+len(g),'sav-val-cf-training-order-v2')
    old=prior.parent(source,seed)
    saved=pd.read_csv(old/'outer_assignments.csv')
    assigned=fold_assignments(train,3)
    assert train.listing_id.tolist()==saved.listing_id.tolist()
    assert np.array_equal(assigned,saved.outer_fold)
    return train,ev,assigned,old

def guard():
    m=json.loads((OUT/'manifest.json').read_text())
    assert all(c.sha(ROOT/p)==h for p,h in m['dependency_sha256'].items())
    assert c.sha(REF/'summary.csv')==m['reference_summary_sha256']
    return m

def prepare():
    OUT.mkdir(exist_ok=True)
    cfg=copy.deepcopy(json.loads((REF/'manifest.json').read_text())['config'])
    assert cfg['residual_epochs']==12 and cfg['outer_folds']==3
    m=dict(config=cfg,seeds=SEEDS,budgets=[.1],new_betas=[1.,2.,4.],
      candidate_grids={'rpl':[0.,.1,.5,1.],'gap':[.5,1.,2.,4.]},
      selection=dict(data='training three-fold OOF predictions only',
        criterion='minimum mean max legal zero-query positive log gain',
        constraint='OOF honest currency MAE <= 1.05 * common beta.5/lambda0 OOF MAE',
        fallback='minimum honest MAE; constraint failure reported',
        ties='criterion, honest MAE, candidate order'),
      expected_new_fits=360,expected_new_cells=90,
      runtime_optimization='omit unused intermediate heads only; final OOF head unchanged',
      previous_run_manifest_sha256=c.sha(ROOT/'outputs/review-gap-controls-v1/manifest.json'),
      dependency_sha256={p:c.sha(ROOT/p) for p in DEPS},
      reference_summary_sha256=c.sha(REF/'summary.csv'),
      reference_manifest_sha256=c.sha(REF/'manifest.json'),
      protocol_sha256=c.sha(ROOT/'notes/review-improvement-v1/PLAN.zh.md'),
      baseline_manuscript_sha256=c.sha(ROOT/'paper/innovation-addendum-v1.tex'),
      scope='retrospective fixed-population comparison, not preregistration or full four-phase audit')
    p=OUT/'manifest.json'
    if p.exists():
        existing=json.loads(p.read_text())
        # Manuscript may be revised while this independent immutable run proceeds.
        m['baseline_manuscript_sha256']=existing['baseline_manuscript_sha256']
        assert m==existing
    else:c.write(p,m)
    # Only completed, checksum-bound pair checkpoints are reused wholesale.
    previous=ROOT/'outputs/review-gap-controls-v1'
    for source in ['synthetic','jucars','mucars']:
        (OUT/source).mkdir(exist_ok=True)
        for seed in SEEDS:
            origin=previous/source/f'seed-{seed}';target=OUT/source/f'seed-{seed}'
            cp=origin/'completion.json'
            if cp.exists() and not target.exists():
                record=json.loads(cp.read_text())
                assert record['summary_sha256']==c.sha(origin/'summary.csv')
                assert record['selection_sha256']==c.sha(origin/'training-selection.json')
                target.symlink_to(origin,target_is_directory=True)
    return m

def oof_metrics(pred,train,space):
    # Legal states are derived independently from field availability and masks.
    available=train.loc[:,list(__import__('savval').ACTIONS)].notna().to_numpy()
    valid=~(space.masks[None,:,:]&~available[:,None,:]).any(2)
    honest=pred[:,0].astype(float)
    gain=np.maximum(np.where(valid,pred,-np.inf).max(1)-honest,0)
    return dict(oof_max_gain=float(gain.mean()),
       oof_honest_mae=float(np.abs(np.expm1(honest)-np.expm1(train.target_log.to_numpy())).mean()),
       oof_rows=len(train),oof_pred_sha256=hashlib.sha256(pred.tobytes()).hexdigest())

def reference_candidates(source,seed,train):
    rows=[];folder=REF/source/f'seed-{seed}'
    for weight in [0.,.1,.5,1.]:
        name=f'path-{weight:g}-gap-0.5';vd=folder/name
        if weight==0 and seed in [13,42,2026]:
            ab=ROOT/'outputs/completion-ablation-v6'/source/f'seed-{seed}'
            pred=np.load(ab/'outer_predictions.npz')['off_gap']
            mp=ab/'deployment_models/off_gap.joblib'
            receipt=json.loads(mp.with_suffix('.json').read_text())
            assert c.sha(mp)==receipt['model_sha256']
        else:
            mp=vd/'deployment_model.joblib';pred=np.load(vd/'outer_predictions.npz')['prediction']
            receipt=json.loads(mp.with_suffix('.json').read_text())
            assert c.sha(mp)==receipt['sha256']
        model,_,_=joblib.load(mp)
        row=dict(source=source,seed=seed,method=name,beta=.5,path_weight=weight,
                 model_sha256=c.sha(mp),model_path=str(mp.relative_to(ROOT)),**oof_metrics(pred,train,model.space))
        rows.append(row);del model;gc.collect()
    return rows

def choose(rows,family):
    candidates=[r for r in rows if (r['beta']==.5 if family=='rpl' else r['path_weight']==0)]
    assert len(candidates)==4
    baseline=next(r for r in candidates if r['beta']==.5 and r['path_weight']==0)
    threshold=1.05*baseline['oof_honest_mae']
    feasible=[r for r in candidates if r['oof_honest_mae']<=threshold]
    if feasible:chosen=min(feasible,key=lambda r:(r['oof_max_gain'],r['oof_honest_mae'],candidates.index(r)))
    else:chosen=min(candidates,key=lambda r:(r['oof_honest_mae'],r['oof_max_gain'],candidates.index(r)))
    return dict(family=family,selected_method=chosen['method'],constraint_met=bool(feasible),
       honest_mae_limit=threshold,selection_uses_evaluation=False,**chosen)

def pair(task):
    source,seed=task;torch.set_num_threads(2);manifest=guard();cfg=manifest['config']
    folder=OUT/source/f'seed-{seed}';folder.mkdir(parents=True,exist_ok=True)
    lock=(folder/'execution.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with threadpool_limits(limits=2):
        train,ev,assigned,old=data(source,cfg,seed);columns=FEATURES[source]
        c.write(folder/'data-binding.json',dict(train=c.content(train),evaluation=c.content(ev),
           assignments_sha256=c.sha(old/'outer_assignments.csv')))
        candidates=reference_candidates(source,seed,train)
        for beta in manifest['new_betas']:
            name=f'path-0-gap-{beta:g}';vd=folder/name;vd.mkdir(exist_ok=True)
            v=dict(beta=beta,path_weight=0.,tolerance=.02,rounds=2,feedback=False,axis='matched_stronger_gap')
            scfg=copy.deepcopy(cfg);scfg.update(gap_penalty_weight=beta,recovery_path_weight=0.,
                                               feedback_rounds=2,gap_tolerance_log=.02)
            oof=np.empty((len(train),11))
            for fold in range(3):
                est,guide=inner_split(train.loc[assigned!=fold],cfg['head_fitting_fraction'])
                assert not set(train.loc[assigned==fold,'listing_id'])&(set(est.listing_id)|set(guide.listing_id))
                p=fit_price_stage(est,guide,columns,scfg,seed,vd/f'outer-{fold}',old/f'outer-{fold}',v)
                model,_,_=joblib.load(p)
                oof[assigned==fold]=model.predict(price_features(train.loc[assigned==fold],columns))[0]
                del model;gc.collect()
                print('GAP_FIT',source,seed,beta,fold,flush=True)
            est,guide=inner_split(train,cfg['head_fitting_fraction'])
            p=fit_price_stage(est,guide,columns,scfg,seed,vd/'deployment',old/'deployment_fit',v)
            np.savez_compressed(vd/'outer_predictions.npz',prediction=oof)
            mp=vd/'deployment_model.joblib';rp=mp.with_suffix('.json')
            binding=dict(price_sha256=c.sha(p),oof_sha256=hashlib.sha256(oof.tobytes()).hexdigest(),
                         training=c.content(train),seed=seed,head_trees=cfg['head_trees'])
            if rp.exists():
                receipt=json.loads(rp.read_text());assert receipt['inputs']==binding and receipt['sha256']==c.sha(mp)
            else:
                model,_,kind=joblib.load(p);_,x,valid=model.predict(price_features(train,columns))
                head=ActionHeads(cfg['head_trees'],seed);head.model.n_jobs=2
                head.fit(x,oof,valid,train.target_log.to_numpy(),model.space,
                         reported_missing=model.space.reported_missing(train))
                c.dump(mp,(model,head,kind));c.write(rp,dict(inputs=binding,sha256=c.sha(mp)))
            model,head,_=joblib.load(mp)
            candidates.append(dict(source=source,seed=seed,method=name,beta=beta,path_weight=0.,
                 model_sha256=c.sha(mp),model_path=str(mp.relative_to(ROOT)),**oof_metrics(oof,train,model.space)))
            del model,head;gc.collect()
        # Written and hashed before any evaluation rows are accessed below.
        selection=dict(status='training_only_selection_fixed',candidates=candidates,
                       choices=[choose(candidates,f) for f in ['rpl','gap']])
        selection_path=folder/'training-selection.json'
        if selection_path.exists():assert json.loads(selection_path.read_text())==selection
        else:c.write(selection_path,selection)
        summaries=[]
        for candidate in candidates:
            if candidate['beta']==.5:continue
            name=candidate['method'];vd=folder/name;mp=ROOT/candidate['model_path']
            cell=vd/'evaluation-1000';cell.mkdir(exist_ok=True);cp=cell/'completion.json'
            inputs=dict(model=c.sha(mp),evaluation=c.content(ev),budget=.1,
                        training_selection_sha256=c.sha(selection_path))
            if cp.exists():
                record=json.loads(cp.read_text());assert record['inputs']==inputs
                assert c.sha(cell/'outcomes.csv.gz')==record['outcomes_sha256'];summaries.append(record['summary']);continue
            model,head,_=joblib.load(mp);pred,x,valid=model.predict(price_features(ev,columns))
            scores=head.score(x,pred,model.space,'suppression',reported_missing=model.space.reported_missing(ev))
            rows,summary=evaluate_method(name,model,head,'suppression',ev,columns,cfg,seed,.1)
            audit=c.matrix_audit(pred,scores,valid,ev,rows,.1)
            # Independently reaggregate every reported scalar that drives comparison.
            for col,key in [('positive_log_inflation','mean_positive_log_inflation'),
                            ('clean_absolute_error','clean_mae'),('attack_absolute_error','attack_mae')]:
                assert np.isclose(rows[col].mean(),summary[key],atol=1e-8,rtol=1e-12)
            summary.update(dataset=source,beta=candidate['beta'],path_weight=0.,axis='matched_stronger_gap')
            rows.to_csv(cell/'outcomes.csv.gz',index=False)
            c.write(cp,dict(status='computed_independent_outcome_check_passed',inputs=inputs,
                 outcomes_sha256=c.sha(cell/'outcomes.csv.gz'),summary=summary,audit=audit))
            summaries.append(summary);print('GAP_CELL',source,seed,name,flush=True)
            del model,head,pred,x,valid,scores;gc.collect()
        pd.DataFrame(summaries).to_csv(folder/'summary.csv',index=False)
        c.write(folder/'completion.json',dict(status='computed_outcomes_checked',cells=3,
            summary_sha256=c.sha(folder/'summary.csv'),selection_sha256=c.sha(selection_path)))
        guard();return summaries

def smoke():
    torch.set_num_threads(2);m=guard();cfg=m['config'];source='synthetic';seed=101
    with threadpool_limits(limits=2):
        train,ev,assigned,old=data(source,cfg,seed)
        est,guide=inner_split(train.loc[assigned!=0],cfg['head_fitting_fraction'])
        name='path-0.5-gap-0.5';v=json.loads((REF/'manifest.json').read_text())['settings'][name]
        scfg=copy.deepcopy(cfg);scfg.update(gap_penalty_weight=.5,gap_tolerance_log=.02,
                                          feedback_rounds=2,recovery_path_weight=.5)
        p=fit_price_stage(est,guide,FEATURES[source],scfg,seed,OUT/'engineering-smoke',old/'outer-0',v)
        model,_,_=joblib.load(p);ref,_,_=joblib.load(REF/source/f'seed-{seed}'/name/'outer-0/model.joblib')
        public=price_features(ev,FEATURES[source]);a=model.predict(public)[0];b=ref.predict(public)[0]
        assert np.array_equal(a,b)
        rows=reference_candidates(source,seed,train)
        for beta in [1.,2.,4.]:
            fake=dict(rows[0]);fake.update(beta=beta,method=f'path-0-gap-{beta:g}',oof_max_gain=rows[0]['oof_max_gain']+beta)
            rows.append(fake)
        assert choose(rows,'gap')['selected_method']=='path-0-gap-0.5'
        assert choose(rows,'rpl')['selection_uses_evaluation'] is False
        c.write(OUT/'engineering-check.json',dict(status='passed',exact_prediction_identity=True,
          reference_model_sha256=c.sha(REF/source/f'seed-{seed}'/name/'outer-0/model.joblib'),
          new_model_sha256=c.sha(p),prediction_shape=list(a.shape),selection_contract_checked=True,
          scope='full single-stage replay at existing lambda.5 plus selection unit checks, not all new fits'))
    print('ENGINEERING_CHECK_PASSED',flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--smoke',action='store_true')
    p.add_argument('--workers',type=int,default=2);a=p.parse_args();prepare()
    assert 1<=a.workers<=3
    if a.prepare:return
    if a.smoke:raise ValueError('Run notes/review-improvement-v1/check_price_equivalence_v2.py instead')
    assert json.loads((OUT/'engineering-check.json').read_text())['status']=='passed'
    lock=(OUT/'execution.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    completed=[];tasks=[]
    for source in ['synthetic','jucars','mucars']:
        for seed in SEEDS:
            cp=OUT/source/f'seed-{seed}'/'completion.json'
            if cp.exists():
                record=json.loads(cp.read_text());sp=cp.with_name('summary.csv');assert c.sha(sp)==record['summary_sha256']
                completed.extend(pd.read_csv(sp).to_dict('records'))
            else:tasks.append((source,seed))
    try:
        with ProcessPoolExecutor(max_workers=a.workers) as pool:
            futures={pool.submit(pair,t):t for t in tasks}
            for future in as_completed(futures):
                completed.extend(future.result());pd.DataFrame(completed).to_csv(OUT/'summary.csv',index=False)
                c.write(OUT/'status.json',dict(status='running',cells=len(completed),expected_cells=90,
                   workers=a.workers,threads_per_worker=2,pid=os.getpid(),last_pair=futures[future],time=time.time()))
        assert len(completed)==90
        c.write(OUT/'completion.json',dict(status='computed_outcomes_checked_analysis_pending',cells=90,
          summary_sha256=c.sha(OUT/'summary.csv'),manifest_sha256=c.sha(OUT/'manifest.json')))
        c.write(OUT/'status.json',dict(status='computed_outcomes_checked_analysis_pending',cells=90,time=time.time()))
    except BaseException:
        c.write(OUT/'failure.json',dict(status='failed_preserving_checkpoints',traceback=traceback.format_exc(),time=time.time()))
        raise

if __name__=='__main__':main()
