"""Complete allowance-matched ordinary-benefit reference, optionally follow tuning."""
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
from equal_benefit_reference import VARIANTS,fit_stage
from run_all import evaluate_method,load_source,rank_subset,write_json
from run_crossfit import deployable_heads,fold_assignments,identifiers
from savval import FEATURES,price_features

def wait_receipt(path,follow):
    announced=False
    while not path.exists():
        require(follow,f'Parent work incomplete: {path}')
        if not announced:print(f'WAIT FOR COMPLETED PARENT {path}',flush=True);announced=True
        time.sleep(15)
    return read(path)

def main():
    parser=argparse.ArgumentParser()
    for name in ('tuning','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--follow',action='store_true',help='Wait for parent stage receipts; never edit/restart parent')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();tuning,output=args.tuning.resolve(),args.output.resolve()
    tm=read(tuning/'manifest.json');config=tm['config']
    if not args.follow:require((tuning/'completion.json').exists(),'Completed tuning parent or explicit follow required')
    for name,digest in tm['source_hashes'].items():require(sha(tuning/'source_snapshot'/name)==digest,'Parent source snapshot')
    for name in ('run_all.py','run_crossfit.py','savval.py','analyze_nested.py','equal_tuning.py'):
        require(sha(Path(__file__).with_name(name))==tm['source_hashes'][name],'Imported frozen parent core changed')
    sources=[Path(__file__),Path(__file__).with_name('equal_benefit_reference.py'),
        *[Path(__file__).with_name(n) for n in ('run_all.py','run_crossfit.py','savval.py','analyze_nested.py','equal_tuning.py')],
        Path(__file__).parents[1]/'plan/equal-benefit-reference-v1.md',
        Path(__file__).parents[1]/'tests/test_equal_benefit.py']
    hashes={p.name:sha(p) for p in sources}
    binding=hashlib.sha256(json.dumps({'sources':hashes,'tuning_manifest_sha256':sha(tuning/'manifest.json'),
                                     'config':config,'sizes':tm['sizes']},sort_keys=True).encode()).hexdigest()
    manifest={'binding':binding,'tuning_path':str(tuning),'tuning_binding':tm['binding'],
        'tuning_manifest_sha256':sha(tuning/'manifest.json'),'main_parent_binding':tm['parent_binding'],
        'config':config,'sizes':tm['sizes'],'source_hashes':hashes,'execution_smoke':tm['execution_smoke'],
        'scope':'three trial benefit-specific training-internal selection and nested refit; retrospective extension'}
    if output.exists() and not args.resume:raise FileExistsError('Fresh output or verified-terminal resume required')
    require(not (output/'completion.json').exists(),'Completed extension immutable')
    output.mkdir(parents=True,exist_ok=True);lock=(output/'execution.lock').open('a+')
    fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (output/'manifest.json').exists():require(read(output/'manifest.json')==manifest,'Frozen extension generation changed')
    else:
        write_json(output/'manifest.json',manifest);snap=output/'source_snapshot';snap.mkdir()
        for p in sources:(snap/p.name).write_bytes(p.read_bytes())
    started=time.time();summaries=[];cases=[];torch.set_num_threads(4)
    with threadpool_limits(limits=4):
        for dataset in config['datasets']:
            for size in tm['sizes']:
                local=dict(config,max_train=size)
                first,head,evaluation,provenance=load_source(dataset,local)
                train=rank_subset(pd.concat([first,head],ignore_index=True),len(first)+len(head),'sav-val-cf-training-order-v2')
                assigned=fold_assignments(train,local['outer_folds'])
                for seed in config['seeds']:
                    folder=output/dataset/f'size-{size}'/f'seed-{seed}'
                    parent_case=tuning/dataset/f'size-{size}'/f'seed-{seed}'
                    folder.mkdir(parents=True,exist_ok=True);receipt=folder/'evaluation_completion.json'
                    if receipt.exists():
                        done=read(receipt);require(done['status']=='completed' and done['binding']==binding,'Extension case generation')
                        for name,digest in done['files'].items():require(sha(folder/name)==digest,'Extension case artifact')
                        rows=pd.read_csv(folder/'summary.csv').to_dict('records');summaries.extend(rows)
                        cases.append([dataset,size,seed]);continue
                    print(f'EQUAL BENEFIT {dataset}/{size}/{seed}',flush=True)
                    outer={tag:np.empty((len(train),11)) for tag in VARIANTS};folds=[]
                    for fold in range(local['outer_folds']):
                        training,heldout=train.loc[assigned!=fold].copy(),train.loc[assigned==fold].copy()
                        stage=f'outer-{fold}';wait_receipt(parent_case/stage/'completion.json',args.follow)
                        fitted=fit_stage(training,heldout.listing_id.tolist(),FEATURES[dataset],local,seed,
                                         parent_case/stage,folder/stage,binding,tm['binding'])
                        for tag,(model,_,_) in fitted.items():outer[tag][assigned==fold]=model.predict(price_features(heldout,FEATURES[dataset]))[0]
                        folds.append({'fold':fold,'train_ids_sha256':identifiers(training),'heldout_ids_sha256':identifiers(heldout),
                                      'heldout_outcomes_enter_selection_or_fit':False})
                        del fitted
                    np.savez_compressed(folder/'outer_predictions.npz',**outer)
                    pd.DataFrame({'listing_id':train.listing_id,'outer_fold':assigned}).to_csv(folder/'outer_assignments.csv',index=False)
                    stage='deployment_fit';wait_receipt(parent_case/stage/'completion.json',args.follow)
                    fitted=fit_stage(train,[],FEATURES[dataset],local,seed,parent_case/stage,folder/stage,binding,tm['binding'])
                    parent_done=wait_receipt(parent_case/'evaluation_completion.json',args.follow)
                    require(parent_done['status']=='completed' and parent_done['binding']==tm['binding'],'Parent case complete binding')
                    for name,digest in parent_done['files'].items():require(sha(parent_case/name)==digest,'Completed parent case binding')
                    with np.load(parent_case/'outer_predictions.npz') as bank:
                        require(np.allclose(outer[VARIANTS[0]],bank['fixed__robust_no_feedback'],atol=2e-6,rtol=0),
                                'Fixed reference uses same nested static prices')
                    write_json(folder/'outer_audit.json',{'folds':folds,'actual_train_count':len(train),'provenance':provenance,
                        'training_ids_sha256':identifiers(train),'evaluation_ids_sha256':identifiers(evaluation),
                        'parent_case_receipt_sha256':sha(parent_case/'evaluation_completion.json')})
                    deployed=deployable_heads(fitted,outer,train,FEATURES[dataset],local,seed)
                    joblib.dump(deployed,folder/'deployment_models.joblib',compress=3);outcomes=[];rows=[]
                    for tag,(model,head,kind) in deployed.items():
                        require(kind=='benefit','Ordinary-benefit evaluation output')
                        for budget in local['budgets']:
                            listing,row=evaluate_method(tag,model,head,kind,evaluation,FEATURES[dataset],local,seed,budget)
                            listing['train_cap']=size;listing['actual_train_count']=len(train);outcomes.append(listing)
                            rows.append({'dataset':dataset,'train_cap':size,'actual_train_count':len(train),**row})
                    pd.concat(outcomes,ignore_index=True).to_csv(folder/'outcomes.csv.gz',index=False)
                    pd.DataFrame(rows).to_csv(folder/'summary.csv',index=False)
                    names=['outer_predictions.npz','outer_assignments.csv','outer_audit.json','deployment_models.joblib','outcomes.csv.gz','summary.csv']
                    write_json(receipt,{'status':'completed','binding':binding,
                        'parent_case_receipt_sha256':sha(parent_case/'evaluation_completion.json'),
                        'stage_completions':{name:sha(folder/name/'completion.json') for name in [*[f'outer-{f}' for f in range(local['outer_folds'])],'deployment_fit']},
                        'files':{name:sha(folder/name) for name in names}})
                    summaries.extend(rows);cases.append([dataset,size,seed]);pd.DataFrame(summaries).to_csv(output/'all_summary.csv',index=False)
                    print(f'COMPLETED EQUAL BENEFIT {dataset}/{size}/{seed}',flush=True)
    require(hashes=={p.name:sha(p) for p in sources},'Frozen extension sources changed')
    require(sha(tuning/'manifest.json')==manifest['tuning_manifest_sha256'],'Tuning generation changed')
    expected=len(config['datasets'])*len(tm['sizes'])*len(config['seeds'])*len(VARIANTS)*len(config['budgets'])
    require(len(summaries)==expected,'All scheduled reference cells')
    write_json(output/'completion.json',{'status':'completed','binding':binding,'cells':len(summaries),'cases':cases,
        'execution_smoke':tm['execution_smoke'],'seconds':time.time()-started,'summary_sha256':sha(output/'all_summary.csv'),
        'tuning_manifest_sha256':manifest['tuning_manifest_sha256']})
    print(f'COMPLETED FULL EQUAL BENEFIT REFERENCE {output}',flush=True)

if __name__=='__main__':main()
