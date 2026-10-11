"""Hash-bound nested equal tuning and retrained source-size sensitivity."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from threadpoolctl import threadpool_limits

from analyze_nested import read,require,sha
from equal_tuning import GRID,METHODS,choose_weights,fit_group,tuning_split,validation_score
from run_all import evaluate_method,load_source,rank_subset,write_json
from run_crossfit import deployable_heads,fold_assignments,identifiers,inner_split
from savval import FEATURES,price_features


VARIANTS=[f'{kind}__{m}' for kind in ('fixed','tuned') for m in METHODS]


def id_receipt(frame):
    return {'ids_sha256':identifiers(frame),'count':len(frame),
            'content_sha256':hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()}


def fit_stage(train,columns,config,seed,directory,binding,heldout_ids=()):
    a,v=tuning_split(train)
    trial_estimator,trial_guidance=inner_split(a,config['head_fitting_fraction'])
    estimator,guidance=inner_split(train,config['head_fitting_fraction'])
    forbidden=set(heldout_ids)
    require(not forbidden&set(train.listing_id),'Outer-held-out row in stage')
    require(not set(v.listing_id)&(set(trial_estimator.listing_id)|set(trial_guidance.listing_id)),'Tuning-validation row enters candidate fit')
    inputs={'binding':binding,'seed':seed,'train':id_receipt(train),'tuning_fit':id_receipt(a),
            'tuning_validation':id_receipt(v),'candidate_estimator':id_receipt(trial_estimator),
            'candidate_guidance':id_receipt(trial_guidance),'refit_estimator':id_receipt(estimator),
            'refit_guidance':id_receipt(guidance),'outer_holdout_ids_sha256':hashlib.sha256('\n'.join(heldout_ids).encode()).hexdigest()}
    receipt=directory/'completion.json'
    if receipt.exists():
        complete=read(receipt)
        require(complete['inputs']==inputs,'Stage inputs changed')
        for name,digest in complete['files'].items():require(sha(directory/name)==digest,'Stage artifact changed')
        print(f'  REUSE {directory.name}',flush=True)
        return joblib.load(directory/'models.joblib')
    if directory.exists():
        directory.rename(directory.with_name(directory.name+f'-incomplete-{time.time_ns()}'))
    directory.mkdir(parents=True)
    started=time.time()
    rows=[]
    # Nine residual candidates share one training-only backbone and initial head.
    weights={f'trial-{k}__{m}':beta for k,beta in enumerate(GRID) for m in METHODS}
    candidates,candidate_trace=fit_group(trial_estimator,trial_guidance,columns,config,seed,weights)
    trial_evidence={}
    for k,beta in enumerate(GRID):
        for method in METHODS:
            tag=f'trial-{k}__{method}'
            row,evidence=validation_score(candidates[tag],v,columns,config,return_evidence=True)
            trial_evidence.update({f'{tag}::{name}':value for name,value in evidence.items()})
            rows.append({'method':method,'gap_weight':beta,**row})
    joblib.dump(candidates,directory/'trial_models.joblib',compress=3)
    np.savez_compressed(directory/'trial_validation.npz',**trial_evidence)
    del candidates
    chosen=choose_weights(rows)
    refit_weights={f'fixed__{m}':.5 for m in METHODS}
    refit_weights.update({f'tuned__{m}':beta for m,beta in chosen.items() if beta!=.5})
    refitted,refit_trace=fit_group(estimator,guidance,columns,config,seed,refit_weights)
    for method,beta in chosen.items():
        if beta==.5:refitted[f'tuned__{method}']=refitted[f'fixed__{method}']
    joblib.dump(refitted,directory/'models.joblib',compress=3)
    pd.DataFrame(rows).to_csv(directory/'trials.csv',index=False)
    write_json(directory/'selection.json',{'grid':list(GRID),'chosen':chosen,'objective':'honest plus attacked squared log loss at .1','validation_is_training_internal':True})
    write_json(directory/'training_trace.json',{'candidates':candidate_trace,'refits':refit_trace})
    train[['listing_id']].to_csv(directory/'stage_train_ids.csv',index=False)
    v[['listing_id']].to_csv(directory/'tuning_validation_ids.csv',index=False)
    trial_estimator[['listing_id']].to_csv(directory/'candidate_estimator_ids.csv',index=False)
    trial_guidance[['listing_id']].to_csv(directory/'candidate_guidance_ids.csv',index=False)
    write_json(receipt,{'status':'completed','inputs':inputs,'seconds':time.time()-started,
               'files':{p.name:sha(p) for p in directory.iterdir() if p.is_file() and p.name!='completion.json'}})
    return refitted


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--parent',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--execution-smoke',action='store_true')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    parent,output=args.parent.resolve(),args.output.resolve()
    parent_manifest=read(parent/'run_manifest.json')
    for name in ('run_all.py','run_crossfit.py','savval.py'):
        require(sha(Path(__file__).with_name(name))==parent_manifest['source_hashes'][name],'Parent core generation')
    config=dict(parent_manifest['config'])
    sizes=[1000,2500,config['max_train']]
    if args.execution_smoke:
        sizes=[240]
        config.update({'datasets':['synthetic'],'seeds':[13],'max_evaluation':64,
                       'catboost_iterations':20,'head_trees':24,'residual_epochs':2,
                       'budgets':[.1]})
    sources=[Path(__file__),Path(__file__).with_name('equal_tuning.py'),
             *[Path(__file__).with_name(n) for n in ['run_all.py','run_crossfit.py','savval.py','analyze_nested.py']],
             Path(__file__).parents[1]/'plan/equal-tuning-size-v1.md',
             Path(__file__).parents[1]/'tests/test_equal_tuning.py']
    hashes={p.name:sha(p) for p in sources}
    binding=hashlib.sha256(json.dumps({'hashes':hashes,'config':config,'sizes':sizes},sort_keys=True).encode()).hexdigest()
    if output.exists() and not args.resume:raise FileExistsError('Fresh output or confirmed-terminal resume required')
    require(not (output/'completion.json').exists(),'Completed run immutable')
    output.mkdir(parents=True,exist_ok=True)
    lock=(output/'execution.lock').open('a+')
    fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    manifest={'parent_binding':parent_manifest['binding'],'config':config,'sizes':sizes,
              'source_hashes':hashes,'binding':binding,'execution_smoke':args.execution_smoke,
              'scope':'nested equal-budget selection and retraining; retrospective development'}
    if (output/'manifest.json').exists():require(read(output/'manifest.json')==manifest,'Frozen generation changed')
    else:
        write_json(output/'manifest.json',manifest)
        snap=output/'source_snapshot';snap.mkdir()
        for p in sources:(snap/p.name).write_bytes(p.read_bytes())
    summaries=[]
    started=time.time()
    torch.set_num_threads(4)
    with threadpool_limits(limits=4):
        for dataset in config['datasets']:
            for size in sizes:
                local=dict(config,max_train=size)
                first,head,evaluation,provenance=load_source(dataset,local)
                train=rank_subset(pd.concat([first,head],ignore_index=True),len(first)+len(head),'sav-val-cf-training-order-v2')
                assigned=fold_assignments(train,local['outer_folds'])
                for seed in local['seeds']:
                    folder=output/dataset/f'size-{size}'/f'seed-{seed}'
                    folder.mkdir(parents=True,exist_ok=True)
                    receipt=folder/'evaluation_completion.json'
                    if receipt.exists():
                        done=read(receipt)
                        require(done['binding']==binding,'Evaluation generation')
                        for name,digest in done['files'].items():require(sha(folder/name)==digest,'Evaluation artifact changed')
                        summaries.extend(pd.read_csv(folder/'summary.csv').to_dict('records'))
                        continue
                    print(f'TUNE-SIZE {dataset}/{size}/{seed}',flush=True)
                    outer={name:np.empty((len(train),11)) for name in VARIANTS}
                    fold_receipts=[]
                    for fold in range(local['outer_folds']):
                        training,heldout=train.loc[assigned!=fold].copy(),train.loc[assigned==fold].copy()
                        fitted=fit_stage(training,FEATURES[dataset],local,seed,folder/f'outer-{fold}',binding,heldout.listing_id.tolist())
                        for name,(model,_,_) in fitted.items():
                            outer[name][assigned==fold]=model.predict(price_features(heldout,FEATURES[dataset]))[0]
                        fold_receipts.append({'fold':fold,'training':id_receipt(training),'heldout':id_receipt(heldout),
                                              'heldout_outcomes_enter_fitting_or_selection':False})
                        del fitted
                    np.savez_compressed(folder/'outer_predictions.npz',**outer)
                    pd.DataFrame({'listing_id':train.listing_id,'outer_fold':assigned}).to_csv(folder/'outer_assignments.csv',index=False)
                    write_json(folder/'outer_audit.json',{'folds':fold_receipts,'actual_train_count':len(train),'provenance':provenance,
                               'training_ids_sha256':identifiers(train),'evaluation_ids_sha256':identifiers(evaluation)})
                    fitted=fit_stage(train,FEATURES[dataset],local,seed,folder/'deployment_fit',binding)
                    deployed=deployable_heads(fitted,outer,train,FEATURES[dataset],local,seed)
                    joblib.dump(deployed,folder/'deployment_models.joblib',compress=3)
                    outcomes,rows=[],[]
                    for name,(model,head,kind) in deployed.items():
                        for budget in local['budgets']:
                            result,row=evaluate_method(name,model,head,kind,evaluation,FEATURES[dataset],local,seed,budget)
                            result['train_cap']=size;result['actual_train_count']=len(train)
                            outcomes.append(result)
                            rows.append({'dataset':dataset,'train_cap':size,'actual_train_count':len(train),**row})
                    pd.concat(outcomes,ignore_index=True).to_csv(folder/'outcomes.csv.gz',index=False)
                    pd.DataFrame(rows).to_csv(folder/'summary.csv',index=False)
                    write_json(receipt,{'status':'completed','binding':binding,
                               'files':{name:sha(folder/name) for name in ['outer_predictions.npz','outer_assignments.csv','outer_audit.json','deployment_models.joblib','outcomes.csv.gz','summary.csv']}})
                    summaries.extend(rows)
                    pd.DataFrame(summaries).to_csv(output/'all_summary.csv',index=False)
                    print(f'COMPLETED TUNE-SIZE {dataset}/{size}/{seed}',flush=True)
    require({p.name:sha(p) for p in sources}==hashes,'Frozen sources changed')
    write_json(output/'completion.json',{'status':'completed','binding':binding,'cells':len(summaries),
               'execution_smoke':args.execution_smoke,'seconds':time.time()-started,'summary_sha256':sha(output/'all_summary.csv')})
    print(f'COMPLETED TUNE-SIZE GENERATION {output}',flush=True)


if __name__=='__main__':main()
