"""Independent cohort/selection/OOS and allocator audit for tuning/size runs."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from threadpoolctl import threadpool_limits

from analyze_cdm_development import allocate_independent,candidate_quotes
from analyze_nested import read,require,sha
from analyze_saved_diagnostics import audit_cell
from run_all import load_source,rank_subset,write_json
from run_crossfit import fold_assignments,identifiers,inner_split
from savval import ACTIONS,FEATURES,price_features,stable_rank


METHODS=('robust_no_feedback','sav_val','sav_benefit_head')
GRID=(.25,.5,1.)


def close(a,b,why,tol=1e-8):
    require(np.allclose(a,b,atol=tol,rtol=0),why)


def audit_execution(pred,scores,valid,states,final,action,regret,space,config,budget):
    require(valid[np.arange(len(states)),states].all(),'Impossible report state')
    for start in range(0,len(states),config['batch_size']):
        stop=min(start+config['batch_size'],len(states))
        cap=int(np.floor(budget*(stop-start)))
        expected,selected=allocate_independent(scores[start:stop],states[start:stop],space,cap)
        require(np.array_equal(expected,final[start:stop]),'Independent final-state allocation')
        require(np.array_equal(selected,action[start:stop]),'Independent public query allocation')
        if start==0:
            quotes=candidate_quotes(pred[start:stop],scores[None,start:stop],states[start:stop],space,cap)[...,0]
            utilities=quotes-config['concealment_cost_log']*space.masks.sum(axis=1)[None]
            utilities=np.where(valid[start:stop],utilities,-np.inf)
            current=pred[np.arange(start,stop),final[start:stop]]-config['concealment_cost_log']*space.masks[states[start:stop]].sum(axis=1)
            close(np.maximum(utilities.max(axis=1)-current,0),regret[start:stop],'Independent first-batch regret',1e-9)


def stage_audit(folder,train,heldout,columns,config,seed,binding):
    done=read(folder/'completion.json')
    require(done['status']=='completed' and done['inputs']['binding']==binding,'Stage receipt')
    for name,digest in done['files'].items():require(sha(folder/name)==digest,'Stage artifact hash')
    # Reconstruct validation membership directly from the declared namespace.
    order=sorted(range(len(train)),key=lambda i:stable_rank(str(train.listing_id.iloc[i]),'sav-equal-tune-validation-v1'))
    ordered=train.iloc[order]
    count=int(np.floor(.2*len(train)))
    validation,fit=ordered.iloc[:count].copy(),ordered.iloc[count:].copy()
    estimator,guidance=inner_split(fit,config['head_fitting_fraction'])
    ref_est,ref_guide=inner_split(train,config['head_fitting_fraction'])
    parts={'train':train,'tuning_fit':fit,'tuning_validation':validation,
           'candidate_estimator':estimator,'candidate_guidance':guidance,
           'refit_estimator':ref_est,'refit_guidance':ref_guide}
    for name,frame in parts.items():
        expected=done['inputs'][name]
        require(expected['ids_sha256']==identifiers(frame) and expected['count']==len(frame),'Stage cohort membership')
        require(expected['content_sha256']==hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest(),'Stage source contents')
    held_ids=[] if heldout is None else heldout.listing_id.tolist()
    require(not set(held_ids)&set(train.listing_id),'Outer-held-out fitting row')
    require(done['inputs']['outer_holdout_ids_sha256']==hashlib.sha256('\n'.join(held_ids).encode()).hexdigest(),'Outer holdout binding')
    require(not set(validation.listing_id)&(set(estimator.listing_id)|set(guidance.listing_id)),'Validation label in candidate fit')
    for name,frame in [('stage_train',train),('tuning_validation',validation),('candidate_estimator',estimator),('candidate_guidance',guidance)]:
        require(pd.read_csv(folder/f'{name}_ids.csv').listing_id.astype(str).tolist()==frame.listing_id.astype(str).tolist(),'Stage ID file')
    trials=pd.read_csv(folder/'trials.csv')
    require(set(zip(trials.method,trials.gap_weight))=={(m,b) for m in METHODS for b in GRID} and len(trials)==9,'Equal complete trial matrix')
    saved=np.load(folder/'trial_validation.npz')
    models=joblib.load(folder/'trial_models.joblib')
    require(set(models)=={f'trial-{k}__{method}' for k in range(len(GRID)) for method in METHODS},'Complete trial model bank')
    for k,beta in enumerate(GRID):
        for method in METHODS:
            tag=f'trial-{k}__{method}'
            model,head,kind=models[tag]
            pred,x,valid=model.predict(price_features(validation,columns))
            stored={name:saved[f'{tag}::{name}'] for name in ['pred','scores','valid','target','states','final_state','action','regret']}
            close(pred,stored['pred'],'Trial prediction reconstruction',2e-6)
            require(np.array_equal(valid,stored['valid']),'Trial feasible concealment')
            close(validation.target_log.to_numpy(),stored['target'],'Training-internal validation labels')
            scores=head.score(x,stored['pred'],model.space,kind,reported_missing=model.space.reported_missing(validation))
            require(np.array_equal(np.isfinite(scores),np.isfinite(stored['scores'])),'Trial public score eligibility')
            finite=np.isfinite(scores)
            close(scores[finite],stored['scores'][finite],'Trial public score reconstruction',1e-10)
            audit_execution(stored['pred'],stored['scores'],stored['valid'],stored['states'],stored['final_state'],stored['action'],stored['regret'],model.space,config,.1)
            honest=np.mean((stored['pred'][:,0]-stored['target'])**2)
            attacked=np.mean((stored['pred'][np.arange(len(validation)),stored['final_state']]-stored['target'])**2)
            row=trials[(trials.method==method)&(trials.gap_weight==beta)].iloc[0]
            close(row.honest_squared_log_loss,honest,'Trial honest objective')
            close(row.attack_squared_log_loss,attacked,'Trial attacked objective')
            close(row.objective,honest+attacked,'Trial total objective')
    selection=read(folder/'selection.json')
    for method in METHODS:
        row=trials[trials.method==method].sort_values(['objective','gap_weight'],kind='stable').iloc[0]
        close(selection['chosen'][method],row.gap_weight,'Training-only selection')
    fitted=joblib.load(folder/'models.joblib')
    require(set(fitted)=={f'{kind}__{method}' for kind in ('fixed','tuned') for method in METHODS},'Complete fixed and tuned model bank')
    trace=read(folder/'training_trace.json')
    for method in METHODS:
        close(trace['refits']['logs'][f'fixed__{method}']['gap_weight'],.5,'Fixed weight')
        beta=selection['chosen'][method]
        tag=f'tuned__{method}' if beta!=.5 else f'fixed__{method}'
        close(trace['refits']['logs'][tag]['gap_weight'],beta,'Selected refit weight')
    return fitted,{'stage':folder.name,'trials':9,'outer_holdout_count':len(held_ids),
                   'training_validation_count':len(validation),'selection_verified':True}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--partial',action='store_true',help='Freeze and audit only completed case receipts at startup')
    args=parser.parse_args()
    run,output=args.run.resolve(),args.output.resolve()
    manifest=read(run/'manifest.json')
    config=manifest['config'];binding=manifest['binding']
    root_complete=run/'completion.json'
    done=read(root_complete) if root_complete.exists() else None
    root_digest=sha(root_complete) if done is not None else None
    if not args.partial:require(done is not None,'Complete source generation required')
    if done is not None:
        require(done['status']=='completed' and done['binding']==binding,'Complete source generation required')
        require(sha(run/'all_summary.csv')==done['summary_sha256'],'Global summary hash')
    for name,digest in manifest['source_hashes'].items():require(sha(run/'source_snapshot'/name)==digest,'Source snapshot binding')
    for name in ('run_all.py','run_crossfit.py','savval.py','analyze_nested.py'):
        require(sha(Path(__file__).with_name(name))==manifest['source_hashes'][name],'Current imported core differs from frozen study')
    # A live run may finish additional cases; this audit never absorbs them mid-pass.
    scheduled=[(dataset,size,seed) for dataset in config['datasets'] for size in manifest['sizes'] for seed in config['seeds']]
    cases=[]
    for dataset,size,seed in scheduled:
        folder=run/dataset/f'size-{size}'/f'seed-{seed}'
        receipt=folder/'evaluation_completion.json'
        if not receipt.exists():
            require(args.partial,'Scheduled evaluation incomplete')
            continue
        record=read(receipt)
        require(record['status']=='completed' and record['binding']==binding,'Completed case generation')
        stages={stage:sha(folder/stage/'completion.json') for stage in [*[f'outer-{fold}' for fold in range(config['outer_folds'])],'deployment_fit']}
        cases.append({'dataset':dataset,'size':size,'seed':seed,'receipt_sha256':sha(receipt),'stage_completions':stages})
    require(bool(cases),'No completed cases available to audit')
    case_keys={(c['dataset'],c['size'],c['seed']):c for c in cases}
    manifest_digest=sha(run/'manifest.json')
    require(not output.exists(),'Fresh audit output required')
    output.mkdir(parents=True)
    (output/'auditor_snapshot.py').write_bytes(Path(__file__).read_bytes())
    write_json(output/'input_binding.json',{'manifest_sha256':manifest_digest,'source_completion_sha256':root_digest,
                'binding':binding,'partial':args.partial,'cases':cases,'scheduled_cases':len(scheduled)})
    stages,cells,summary_frames=[],[],[]
    expected_cells=0
    torch.set_num_threads(4)
    with threadpool_limits(limits=4):
        for dataset in config['datasets']:
            for size in manifest['sizes']:
                local=dict(config,max_train=size)
                first,head,evaluation,_=load_source(dataset,local)
                train=rank_subset(pd.concat([first,head],ignore_index=True),len(first)+len(head),'sav-val-cf-training-order-v2')
                assigned=fold_assignments(train,local['outer_folds'])
                for seed in config['seeds']:
                    if (dataset,size,seed) not in case_keys:continue
                    folder=run/dataset/f'size-{size}'/f'seed-{seed}'
                    captured=case_keys[(dataset,size,seed)]
                    require(sha(folder/'evaluation_completion.json')==captured['receipt_sha256'],'Captured case changed')
                    receipt=read(folder/'evaluation_completion.json')
                    require(receipt['binding']==binding,'Evaluation binding')
                    for name,digest in receipt['files'].items():require(sha(folder/name)==digest,'Evaluation artifact hash')
                    assignment=pd.read_csv(folder/'outer_assignments.csv')
                    require(assignment.listing_id.tolist()==train.listing_id.tolist() and np.array_equal(assignment.outer_fold,assigned),'Outer assignments')
                    outer=np.load(folder/'outer_predictions.npz')
                    variant_names={f'{kind}__{method}' for kind in ('fixed','tuned') for method in METHODS}
                    require(set(outer.files)==variant_names,'Complete outer variant bank')
                    for fold in range(local['outer_folds']):
                        training,heldout=train.loc[assigned!=fold].copy(),train.loc[assigned==fold].copy()
                        fitted,row=stage_audit(folder/f'outer-{fold}',training,heldout,FEATURES[dataset],local,seed,binding)
                        stages.append({'dataset':dataset,'size':size,'seed':seed,**row})
                        for name,(model,_,_) in fitted.items():
                            pred=model.predict(price_features(heldout,FEATURES[dataset]))[0]
                            close(outer[name][assigned==fold],pred,'Outer out-of-loop prices',2e-6)
                    _,row=stage_audit(folder/'deployment_fit',train,None,FEATURES[dataset],local,seed,binding)
                    stages.append({'dataset':dataset,'size':size,'seed':seed,**row})
                    deployed=joblib.load(folder/'deployment_models.joblib')
                    require(set(deployed)==variant_names,'Complete deployed variant bank')
                    outcomes=pd.read_csv(folder/'outcomes.csv.gz')
                    summary=pd.read_csv(folder/'summary.csv')
                    require(len(summary)==len(variant_names)*len(local['budgets']) and
                            set(zip(summary.method,summary.budget))=={(name,budget) for name in variant_names for budget in local['budgets']},'Complete evaluation variant/capacity matrix')
                    require((summary.train_cap==size).all() and (summary.actual_train_count==len(train)).all(),'Summary source-size binding')
                    summary_frames.append(summary)
                    expected_cells+=len(summary)
                    for name,(model,head,kind) in deployed.items():
                        pred,x,valid=model.predict(price_features(evaluation,FEATURES[dataset]))
                        scores=head.score(x,pred,model.space,kind,reported_missing=model.space.reported_missing(evaluation))
                        for budget in local['budgets']:
                            rows=outcomes[(outcomes.method==name)&(outcomes.budget==budget)]
                            require(rows.listing_id.tolist()==evaluation.listing_id.tolist(),'Size evaluation membership/order')
                            close(rows.target_log,evaluation.target_log,'Evaluation labels')
                            report=summary[(summary.method==name)&(summary.budget==budget)].iloc[0]
                            count=audit_cell(rows,report,local['maximum_hidden'],local['batch_size'])
                            audit_execution(pred,scores,valid,rows.state.to_numpy(int),rows.final_state.to_numpy(int),rows.action.to_numpy(int),rows.best_response_regret_log.to_numpy(),model.space,local,budget)
                            close(rows.clean_prediction_log,pred[:,0],'Final honest prices',2e-6)
                            close(rows.attacked_prediction_log,pred[np.arange(len(rows)),rows.final_state.to_numpy(int)],'Final attacked prices',2e-6)
                            cells.append({'dataset':dataset,'size':size,'seed':seed,'method':name,'budget':budget,'rows':len(rows),'metrics':count})
                    require(sha(folder/'evaluation_completion.json')==captured['receipt_sha256'],'Captured case changed during audit')
                    for name,digest in receipt['files'].items():require(sha(folder/name)==digest,'Evaluation artifact changed during audit')
                    for stage,digest in captured['stage_completions'].items():
                        require(sha(folder/stage/'completion.json')==digest,'Captured fitting stage changed during audit')
    require(len(cells)==expected_cells,'Complete captured-case audited cell count')
    if done is not None:
        require(len(cells)==done['cells'],'Complete audited cell count')
        pd.testing.assert_frame_equal(pd.concat(summary_frames,ignore_index=True),pd.read_csv(run/'all_summary.csv'),check_dtype=False,rtol=1e-10,atol=1e-10)
    require(sha(run/'manifest.json')==manifest_digest,'Source manifest changed during audit')
    if root_digest is not None:require(sha(root_complete)==root_digest,'Completed source generation changed during audit')
    pd.DataFrame(stages).to_csv(output/'stages.csv',index=False)
    pd.DataFrame(cells).to_csv(output/'cells.csv',index=False)
    write_json(output/'completion.json',{'status':'completed','cells':len(cells),'stages':len(stages),
               'source_completion_sha256':root_digest,'auditor_sha256':sha(Path(__file__)),
               'partial':args.partial,'completed_cases_at_capture':len(cases),'scheduled_cases':len(scheduled),
               'all_scheduled_cases_completed':len(cases)==len(scheduled),'input_binding_sha256':sha(output/'input_binding.json'),
               'execution_smoke':manifest['execution_smoke'],'scope':'all trials/selection/cohorts/OOF predictions and evaluation arithmetic; exact first-batch deviations'})
    print(f'AUDITED TUNE-SIZE GENERATION {output}',flush=True)


if __name__=='__main__':main()
