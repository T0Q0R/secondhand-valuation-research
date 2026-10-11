"""Benefit-specific three-trial selection with exact static-model reuse."""
from __future__ import annotations
import copy
import hashlib
import time
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from analyze_nested import read,require,sha
from equal_tuning import GRID,tuning_split,validation_score
from run_all import fit_heads,write_json
from run_crossfit import identifiers,inner_split
from savval import price_features

METHOD='robust_benefit_no_feedback'
VARIANTS=tuple(f'{role}__{METHOD}' for role in ('fixed','tuned'))

def id_receipt(frame):
    return {'ids_sha256':identifiers(frame),'count':len(frame),
            'content_sha256':hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()}

def choose_weight(trials):
    require(len(trials)==len(GRID) and {r['gap_weight'] for r in trials}==set(GRID),
            'Exactly three distinct declared benefit trials required')
    require(all(np.isfinite(r['objective']) for r in trials),'Finite candidate objectives required')
    return min(trials,key=lambda r:(r['objective'],GRID.index(r['gap_weight'])))['gap_weight']

def reusable_tag(beta,parent_beta):
    require(beta in GRID and parent_beta in GRID,'Declared gap-weight grid')
    if beta==.5:return 'fixed__robust_no_feedback'
    if beta==parent_beta:return 'tuned__robust_no_feedback'
    return None

def refit_static(fixed,estimator,guidance,columns,config,seed,beta):
    """Reuse the identical training-only backbone, reset the neural residual."""
    model=copy.deepcopy(fixed)
    model.residual=None
    local=dict(config,gap_penalty_weight=beta)
    trace=model.train_residual(price_features(estimator,columns),estimator.target_log.to_numpy(),
                               local,seed,policy=None)
    head=fit_heads(model,guidance,columns,local,seed)
    return (model,head,'benefit'),trace

def verify_parent_stage(folder,train,heldout,config,seed,tuning_binding):
    done=read(folder/'completion.json')
    require(done['status']=='completed','Completed parent fitting stage')
    for name,digest in done['files'].items():require(sha(folder/name)==digest,'Parent stage artifact binding')
    fit,validation=tuning_split(train)
    estimator,guidance=inner_split(fit,config['head_fitting_fraction'])
    refit_estimator,refit_guidance=inner_split(train,config['head_fitting_fraction'])
    parts={'train':train,'tuning_fit':fit,'tuning_validation':validation,'candidate_estimator':estimator,
           'candidate_guidance':guidance,'refit_estimator':refit_estimator,'refit_guidance':refit_guidance}
    expected={name:id_receipt(frame) for name,frame in parts.items()}
    expected.update(binding=tuning_binding,seed=seed,
        outer_holdout_ids_sha256=hashlib.sha256('\n'.join(heldout).encode()).hexdigest())
    require(done['inputs']==expected,'Parent stage exact fitting roles/contents/seed')
    require(not set(heldout)&set(train.listing_id),'Outer-held-out row enters selection/refit')
    require(not set(validation.listing_id)&(set(estimator.listing_id)|set(guidance.listing_id)),
            'Validation label enters candidate fitting')
    return done,validation,refit_estimator,refit_guidance

def fit_stage(train,heldout,columns,config,seed,parent_stage,directory,binding,tuning_binding):
    parent_done,validation,estimator,guidance=verify_parent_stage(
        parent_stage,train,heldout,config,seed,tuning_binding)
    parent_digest=sha(parent_stage/'completion.json')
    inputs={'binding':binding,'parent_stage_path':str(parent_stage),'parent_stage_receipt_sha256':parent_digest,
            'parent_inputs':parent_done['inputs'],'evaluated_head_output':'benefit'}
    receipt=directory/'completion.json'
    if receipt.exists():
        done=read(receipt);require(done['status']=='completed' and done['inputs']==inputs,'Extension stage inputs')
        for name,digest in done['files'].items():require(sha(directory/name)==digest,'Extension stage artifact changed')
        return joblib.load(directory/'models.joblib')
    if directory.exists():directory.rename(directory.with_name(directory.name+f'-incomplete-{time.time_ns()}'))
    directory.mkdir(parents=True);started=time.time();rows=[];bank={}
    candidates=joblib.load(parent_stage/'trial_models.joblib')
    for k,beta in enumerate(GRID):
        parent_tag=f'trial-{k}__robust_no_feedback'
        model,head,kind=candidates[parent_tag];require(kind=='suppression','Actual static parent candidate kind')
        score,evidence=validation_score((model,head,'benefit'),validation,columns,config,return_evidence=True)
        tag=f'trial-{k}'
        bank.update({f'{tag}::{name}':value for name,value in evidence.items()})
        rows.append({'method':METHOD,'gap_weight':beta,'parent_trial_tag':parent_tag,**score})
    del candidates
    selected=choose_weight(rows)
    parent_models=joblib.load(parent_stage/'models.joblib')
    parent_choice=read(parent_stage/'selection.json')['chosen']['robust_no_feedback']
    trace=read(parent_stage/'training_trace.json')['refits']['logs']
    require(trace['fixed__robust_no_feedback']['gap_weight']==.5,'Fixed static refit weight')
    parent_selected_tag='fixed__robust_no_feedback' if parent_choice==.5 else 'tuned__robust_no_feedback'
    require(trace[parent_selected_tag]['gap_weight']==parent_choice,'Parent selected refit weight')
    fixed_model,fixed_head,fixed_kind=parent_models['fixed__robust_no_feedback']
    require(fixed_kind=='suppression','Actual fixed parent kind')
    models={VARIANTS[0]:(fixed_model,fixed_head,'benefit')}
    reused=reusable_tag(selected,parent_choice);refit_started=time.time();training=None
    if reused is not None:
        model,head,kind=parent_models[reused];require(kind=='suppression','Actual reused parent kind')
        models[VARIANTS[1]]=(model,head,'benefit')
    else:
        models[VARIANTS[1]],training=refit_static(fixed_model,estimator,guidance,columns,config,seed,selected)
    pd.DataFrame(rows).to_csv(directory/'trials.csv',index=False)
    np.savez_compressed(directory/'trial_validation.npz',**bank)
    joblib.dump(models,directory/'models.joblib',compress=3)
    write_json(directory/'selection.json',{'grid':list(GRID),'chosen_gap_weight':selected,
        'objective':'honest plus attacked squared log loss at .1','head_output':'benefit',
        'validation_is_training_internal':True,'parent_suppression_choice':parent_choice})
    write_json(directory/'refit_provenance.json',{'fixed_parent_model_tag':'fixed__robust_no_feedback',
        'tuned_parent_model_tag':reused,'tuned_gap_weight':selected,'new_residual_fit':reused is None,
        'training_only_backbone_reused':True,'new_training_trace':training,
        'refit_or_reuse_seconds':time.time()-refit_started,
        'source_models_sha256':parent_done['files']['models.joblib'],
        'source_candidates_sha256':parent_done['files']['trial_models.joblib'],
        'cost_scope':'new scoring and optional residual/head fit only; original model costs remain in parent receipts'})
    for name,frame in [('stage_train',train),('tuning_validation',validation),
                       ('refit_estimator',estimator),('refit_guidance',guidance)]:
        frame[['listing_id']].to_csv(directory/f'{name}_ids.csv',index=False)
    require(sha(parent_stage/'completion.json')==parent_digest,'Parent stage changed during extension')
    for name,digest in parent_done['files'].items():require(sha(parent_stage/name)==digest,'Parent stage changed during extension')
    write_json(receipt,{'status':'completed','inputs':inputs,'seconds':time.time()-started,
        'files':{p.name:sha(p) for p in directory.iterdir() if p.is_file() and p.name!='completion.json'}})
    print(f'  BENEFIT {directory.name} selected={selected} parent={parent_choice} new_refit={reused is None}',flush=True)
    return models
