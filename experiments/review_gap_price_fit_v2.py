"""Exact no-feedback price updates without unused intermediate acquisition fits.

The final OOF acquisition head is still trained by the production runner.
Intermediate heads never enter policy=None residual updates or OOF prices.
Frozen source files and v1 checkpoints are not modified.
"""
from pathlib import Path
import gc,time,json
import joblib,numpy as np
import run_completion_ablation_v6 as c
from run_rpl_ten_seed_v2 import BoundedPredictor
from recovery_path_training_v1 import train_residual
from savval import price_features

def fit_stage(est,guide,columns,cfg,seed,directory,old,setting):
    assert setting['path_weight']==0 and not setting['feedback']
    directory.mkdir(parents=True,exist_ok=True);base=c.stage_check(old,est,guide,seed)
    inputs=dict(estimator=c.content(est),guidance=c.content(guide),base=c.sha(base),
                config=cfg,seed=seed,variant=setting)
    cp=directory/'completion.json';path=directory/'model.joblib'
    if cp.exists():
        r=json.loads(cp.read_text());assert r['inputs']==inputs and r['model_sha256']==c.sha(path)
        return path
    # Reuse any complete v1 stage, or the last complete residual round. No
    # partial/unbound model is trusted and no original file is overwritten.
    relative=directory.relative_to(c.ROOT/'outputs/review-gap-controls-v2')
    previous=c.ROOT/'outputs/review-gap-controls-v1'/relative
    prior_cp=previous/'completion.json'
    if prior_cp.exists():
        r=json.loads(prior_cp.read_text());assert r['inputs']==inputs
        p=previous/'model.joblib';assert r['model_sha256']==c.sha(p)
        path.symlink_to(p);c.write(cp,dict(**r,reused_v1=dict(path=str(p.relative_to(c.ROOT)),sha256=c.sha(p))))
        return path
    model,_,_=joblib.load(base);assert model.residual is None
    model.backbone=BoundedPredictor(model.backbone);logs=[];started=time.time()
    reuse_rounds=[]
    for i in range(2):
        rp=directory/f'round-{i+1}.json';mp=rp.with_suffix('.joblib')
        if rp.exists():
            r=json.loads(rp.read_text());assert r['inputs']==inputs and c.sha(mp)==r['sha256']
            model,_,logs=joblib.load(mp);continue
        old_rp=previous/rp.name;old_mp=previous/mp.name
        if old_rp.exists():
            r=json.loads(old_rp.read_text());assert r['inputs']==inputs and c.sha(old_mp)==r['sha256']
            model,_,logs=joblib.load(old_mp);mp.symlink_to(old_mp)
            c.write(rp,dict(**r,reused_v1=True));reuse_rounds.append(str(old_mp.relative_to(c.ROOT)));continue
        trace=train_residual(model,price_features(est,columns),est.target_log.to_numpy(),
              cfg,seed+i,None,gap_weight=setting['beta'],epochs=cfg['residual_epochs']//2)
        # Original intermediate prediction sets eval mode; no price parameters,
        # encoding or torch random state are changed by its head fitting.
        model.residual.eval()
        logs.append(dict(round=i+1,epochs=cfg['residual_epochs']//2,loss=trace))
        c.dump(mp,(model,None,logs));c.write(rp,dict(inputs=inputs,sha256=c.sha(mp),
           unused_intermediate_head_omitted=True))
    c.dump(path,(model,None,'suppression'))
    c.write(cp,dict(status='fitted_price_equivalent_intermediate_heads_omitted',inputs=inputs,
       model_sha256=c.sha(path),rounds=logs,seconds=time.time()-started,
       reused_rounds=reuse_rounds,final_oof_head_not_omitted=True))
    return path
