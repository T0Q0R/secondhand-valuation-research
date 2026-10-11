"""Recover a confirmed-terminal CDM generation without changing its protocol.

Completed budget units are hash-checked and reused. Incomplete units are
archived whole. The original runner/mechanism/config bytes remain frozen.
"""
from __future__ import annotations

import argparse
import fcntl
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from threadpoolctl import threadpool_limits

from analyze_nested import read, require, sha
from cdm_mechanism import POLICIES, policy_scores
from run_all import fit_heads, load_source, rank_subset, write_json
from run_cdm_development import PRICES, evaluate, fit_probabilities
from run_crossfit import identifiers, inner_split
from savval import FEATURES, price_features


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',type=Path,required=True)
    args=parser.parse_args()
    run=args.run.resolve()
    manifest=read(run/'manifest.json')
    require(not (run/'completion.json').exists(),'Completed generation is immutable')
    # The caller must have independently confirmed that the earlier process and
    # handle are absent. The lock prevents concurrent recovery invocations.
    lock=(run/'recovery.lock').open('a+')
    fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    root=Path(__file__).parents[1]
    original_files={}
    for name,digest in manifest['source_hashes'].items():
        source=(root/'plan'/name if name.endswith('.md') else
                root/'tests'/name if name.startswith('test_') else root/'experiments'/name)
        require(sha(source)==digest,'Frozen source changed; recovery rejected')
        require(sha(run/'source_snapshot'/name)==digest,'Original snapshot binding')
        original_files[name]=source
    parent=Path(manifest['parent_path'])
    parent_manifest=read(parent/'run_manifest.json')
    require(parent_manifest['binding']==manifest['parent_binding'],'Parent generation binding')
    require(parent_manifest['config']==manifest['parent_config'],'Parent configuration')
    config=manifest['config']
    recovery=run/'resume_receipts'/f'resume-{time.time_ns()}'
    recovery.mkdir(parents=True)
    driver_hash=sha(Path(__file__))
    (recovery/'driver_snapshot.py').write_bytes(Path(__file__).read_bytes())
    write_json(recovery/'start.json',{'driver_sha256':driver_hash,'parent_binding':manifest['parent_binding'],
               'original_manifest_sha256':sha(run/'manifest.json'),
               'scope':'same frozen policy/config/pairs; completed budgets reused, incomplete budgets archived'})
    summaries,completed_pairs,events=[],[],[]
    torch.set_num_threads(4)
    started=time.time()
    with threadpool_limits(limits=4):
        for dataset in config['datasets']:
            seeds=[s for d,s in manifest['pairs'] if d==dataset]
            if not seeds: continue
            first,old_head,evaluation,provenance=load_source(dataset,manifest['parent_config'])
            estimator,guidance=inner_split(pd.concat([first,old_head],ignore_index=True),config['head_fitting_fraction'])
            ordered=rank_subset(guidance,len(guidance),'cdm-head-calibration-v1')
            cut=len(ordered)//2
            head_frame,calibration=ordered.iloc[:cut].copy(),ordered.iloc[cut:].copy()
            if manifest['execution_smoke']:
                head_frame,calibration,evaluation=head_frame.iloc[:64].copy(),calibration.iloc[:64].copy(),evaluation.iloc[:64].copy()
            parts=[set(f.listing_id) for f in (estimator,head_frame,calibration,evaluation)]
            require(all(not parts[i]&parts[j] for i in range(4) for j in range(i)),'Disjoint cohorts')
            for seed in seeds:
                print(f'RECOVER CDM {dataset}/{seed}',flush=True)
                saved=parent/dataset/f'seed-{seed}'
                fit=read(saved/'deployment_fit/fit_completion.json')
                require(fit['inputs']['estimator_ids']==identifiers(estimator),'Parent estimator cohort')
                require(fit['inputs']['guidance_ids']==identifiers(guidance),'Parent guidance cohort')
                own=run/dataset/f'seed-{seed}'
                own.mkdir(parents=True,exist_ok=True)
                data={'provenance':provenance,'estimator_ids_sha256':identifiers(estimator),
                      'guidance_ids_sha256':identifiers(guidance),'head_ids_sha256':identifiers(head_frame),
                      'calibration_ids_sha256':identifiers(calibration),'evaluation_ids_sha256':identifiers(evaluation)}
                if (own/'data_audit.json').exists():
                    require(read(own/'data_audit.json')==data,'Source/cohort changed during recovery')
                else: write_json(own/'data_audit.json',data)
                for name,frame in [('head',head_frame),('calibration',calibration),('evaluation',evaluation)]:
                    path=own/f'{name}_ids.csv'
                    if path.exists():
                        require(pd.read_csv(path).listing_id.astype(str).tolist()==frame.listing_id.astype(str).tolist(),'Stored cohort order')
                    else: frame[['listing_id']].to_csv(path,index=False)
                for price_name,price_key in PRICES.items():
                    model_path=saved/'deployment_fit/models'/f'{price_key}.joblib'
                    model_hash=sha(model_path)
                    require(model_hash==fit['files'][f'models/{price_key}.joblib'],'Parent estimator hash')
                    model,_,_=joblib.load(model_path)
                    folder=own/price_name
                    ready=folder.exists() and all((folder/name).exists() for name in
                         ('head.joblib','calibration_arrays.npz','evaluation_arrays.npz'))
                    if folder.exists() and not ready:
                        require(not any(folder.glob('budget-*/completion.json')),'Completed budget without inference artifacts')
                        archive=folder.with_name(folder.name+f'-incomplete-{time.time_ns()}')
                        folder.rename(archive)
                        events.append({'archived':str(archive.relative_to(run))})
                    if not ready:
                        folder.mkdir()
                        head=fit_heads(model,head_frame,FEATURES[dataset],config,seed)
                        joblib.dump(head,folder/'head.joblib',compress=3)
                        arrays=[]
                        for name,frame in [('calibration',calibration),('evaluation',evaluation)]:
                            pred,x,valid=model.predict(price_features(frame,FEATURES[dataset]))
                            scores=policy_scores(frame.listing_id,x,pred,model.space.reported_missing(frame),model.space,head)
                            np.savez_compressed(folder/f'{name}_arrays.npz',pred=pred,scores=scores,valid=valid,target_log=frame.target_log.to_numpy())
                            arrays.append((pred,scores,valid))
                        events.append({'new_inference':str(folder.relative_to(run))})
                    else:
                        head=joblib.load(folder/'head.joblib')
                        arrays=[]
                        for name,frame in [('calibration',calibration),('evaluation',evaluation)]:
                            stored=np.load(folder/f'{name}_arrays.npz')
                            pred,x,valid=model.predict(price_features(frame,FEATURES[dataset]))
                            require(np.allclose(pred,stored['pred'],atol=2e-6,rtol=0),'Saved price reconstruction')
                            require(np.array_equal(valid,stored['valid']),'Saved legal hiding states')
                            require(np.array_equal(frame.target_log.to_numpy(),stored['target_log']),'Saved source outcomes')
                            rebuilt=policy_scores(frame.listing_id,x,stored['pred'],model.space.reported_missing(frame),model.space,head)
                            require(np.array_equal(np.isfinite(rebuilt),np.isfinite(stored['scores'])),'Saved public query availability')
                            finite=np.isfinite(rebuilt)
                            require(np.allclose(rebuilt[finite],stored['scores'][finite],rtol=0,atol=1e-10),'Saved public scores')
                            arrays.append((stored['pred'],stored['scores'],stored['valid']))
                        events.append({'reused_inference':str(folder.relative_to(run)),
                                       'hashes':{name:sha(folder/name) for name in ('head.joblib','calibration_arrays.npz','evaluation_arrays.npz')}})
                    for budget in config['budgets']:
                        budget_folder=folder/f'budget-{int(round(budget*10000)):04d}'
                        receipt=budget_folder/'completion.json'
                        if receipt.exists():
                            done=read(receipt)
                            require(done['status']=='completed' and done['cells']==len(POLICIES)+2,'Complete budget unit')
                            for name,digest in done['files'].items():
                                require(sha(budget_folder/name)==digest,'Completed budget hash changed')
                            events.append({'reused_budget':str(budget_folder.relative_to(run)),
                                           'receipt_sha256':sha(receipt)})
                            print(f'  reuse {price_name}/{budget}',flush=True)
                        else:
                            if budget_folder.exists():
                                archive=budget_folder.with_name(budget_folder.name+f'-incomplete-{time.time_ns()}')
                                budget_folder.rename(archive)
                                events.append({'archived':str(archive.relative_to(run))})
                            budget_folder.mkdir()
                            print(f'  execute {price_name}/{budget}',flush=True)
                            solution=fit_probabilities(*arrays[0],calibration,model.space,config,budget,budget_folder/'fit')
                            strategies=[(name,np.eye(len(POLICIES))[k]) for k,name in enumerate(POLICIES)]
                            strategies += [('uniform',np.full(len(POLICIES),1/len(POLICIES))),('cdm',np.asarray(solution['probabilities']))]
                            for name,alpha in strategies:
                                evaluate(*arrays[1],evaluation,model.space,config,budget,alpha,name,seed,budget_folder/name)
                            write_json(receipt,{'status':'completed','budget':budget,'price':price_name,'cells':len(strategies),
                                       'files':{str(p.relative_to(budget_folder)):sha(p) for p in budget_folder.rglob('*')
                                                 if p.is_file() and p.name!='completion.json'}})
                            events.append({'completed_budget':str(budget_folder.relative_to(run)),'receipt_sha256':sha(receipt)})
                        for name in [*POLICIES,'uniform','cdm']:
                            row=read(budget_folder/name/'summary.json')
                            summaries.append({'dataset':dataset,'price':price_name,**row})
                        write_json(recovery/'progress.json',events)
                    require(sha(model_path)==model_hash,'Parent price model mutated')
                    expected_binding={'parent_model_path':str(model_path),'parent_model_sha256':model_hash,
                                      'head_sha256':sha(folder/'head.joblib'),'head_summary':head.target_summary}
                    if (folder/'model_binding.json').exists():
                        require(read(folder/'model_binding.json')==expected_binding,'Price/head binding changed')
                    else: write_json(folder/'model_binding.json',expected_binding)
                completed_pairs.append([dataset,seed])
                pair_done={'status':'completed','parent_binding':manifest['parent_binding'],'dataset':dataset,'seed':seed,
                           'price_count':len(PRICES),'budget_count':len(config['budgets']),
                           'cells':len(PRICES)*len(config['budgets'])*(len(POLICIES)+2)}
                if (own/'completion.json').exists():
                    require(read(own/'completion.json')==pair_done,'Completed pair changed')
                else: write_json(own/'completion.json',pair_done)
                pd.DataFrame(summaries).to_csv(run/'all_summary.csv',index=False)
                print(f'COMPLETED RECOVERED CDM {dataset}/{seed}',flush=True)
    require(all(sha(p)==manifest['source_hashes'][name] for name,p in original_files.items()),'Frozen source changed during recovery')
    require(sha(Path(__file__))==driver_hash,'Recovery driver changed during execution')
    scheduled=len(manifest['parent_config']['datasets'])*len(manifest['parent_config']['seeds'])
    write_json(recovery/'completion.json',{'status':'completed','driver_sha256':driver_hash,'events':events,
               'seconds':time.time()-started,'summary_sha256':sha(run/'all_summary.csv')})
    write_json(run/'completion.json',{'status':'completed','pairs':completed_pairs,'cells':len(summaries),
               'seconds_this_recovery':time.time()-started,
               'all_scheduled_pairs_completed':len(completed_pairs)==scheduled and not manifest['execution_smoke'],
               'execution_smoke':manifest['execution_smoke'],'summary_sha256':sha(run/'all_summary.csv'),
               'recovery_receipt':str((recovery/'completion.json').relative_to(run))})
    print(f'COMPLETED RECOVERED CDM GENERATION {run}',flush=True)


if __name__=='__main__': main()
