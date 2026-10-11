"""Independent role/selection/OOF-head and response audit for benefit extension."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import ExtraTreesRegressor
from threadpoolctl import threadpool_limits
from analyze_cdm_development import candidate_quotes
from analyze_equal_tuning_size import audit_execution
from analyze_nested import read,require,sha
from analyze_resources_and_transfer import scores_independent
from analyze_saved_diagnostics import audit_cell
from run_all import load_source,rank_subset,write_json
from run_crossfit import fold_assignments,identifiers,inner_split
from savval import ACTIONS,FEATURES,price_features,stable_rank

GRID=(.25,.5,1.)
METHOD='robust_benefit_no_feedback'
VARIANTS=tuple(f'{role}__{METHOD}' for role in ('fixed','tuned'))

def close(a,b,why,tol=1e-8):
    require(np.allclose(a,b,atol=tol,rtol=0,equal_nan=True),why)

def files_checked(folder,receipt='completion.json'):
    done=read(folder/receipt);require(done['status']=='completed','Completed artifact receipt')
    for name,digest in done['files'].items():require(sha(folder/name)==digest,'Artifact file binding')
    return done

def id_receipt(frame):
    return {'ids_sha256':identifiers(frame),'count':len(frame),
            'content_sha256':hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()}

def stage_audit(folder,parent,train,heldout,columns,config,seed,binding,tuning_binding):
    done=files_checked(folder);source=files_checked(parent)
    require(done['inputs']['binding']==binding and done['inputs']['evaluated_head_output']=='benefit','Stage generation/output')
    require(done['inputs']['parent_stage_path']==str(parent) and
            done['inputs']['parent_stage_receipt_sha256']==sha(parent/'completion.json'),'Parent stage identity')
    require(done['inputs']['parent_inputs']==source['inputs'],'Exact parent stage input reuse')
    ordered=train.iloc[sorted(range(len(train)),key=lambda i:stable_rank(str(train.listing_id.iloc[i]),'sav-equal-tune-validation-v1'))]
    count=int(np.floor(.2*len(train)));validation,fit=ordered.iloc[:count].copy(),ordered.iloc[count:].copy()
    candidate_est,candidate_guide=inner_split(fit,config['head_fitting_fraction'])
    refit_est,refit_guide=inner_split(train,config['head_fitting_fraction'])
    parts={'train':train,'tuning_fit':fit,'tuning_validation':validation,'candidate_estimator':candidate_est,
        'candidate_guidance':candidate_guide,'refit_estimator':refit_est,'refit_guidance':refit_guide}
    expected={name:id_receipt(frame) for name,frame in parts.items()}
    expected.update(binding=tuning_binding,seed=seed,outer_holdout_ids_sha256=hashlib.sha256('\n'.join(heldout).encode()).hexdigest())
    require(source['inputs']==expected,'Exact independent fitting/selection roles')
    require(not set(heldout)&set(train.listing_id),'Held-out outcomes enter own stage')
    require(not set(validation.listing_id)&(set(candidate_est.listing_id)|set(candidate_guide.listing_id)),'Candidate validation enters fitting')
    for name,frame in [('stage_train',train),('tuning_validation',validation),('refit_estimator',refit_est),('refit_guidance',refit_guide)]:
        require(pd.read_csv(folder/f'{name}_ids.csv').listing_id.astype(str).tolist()==frame.listing_id.astype(str).tolist(),'Extension role ID file')
    trials=pd.read_csv(folder/'trials.csv');require(len(trials)==3 and set(trials.gap_weight)==set(GRID),'Exactly three trials')
    require((trials.method==METHOD).all(),'Benefit reference trial identity')
    candidates=joblib.load(parent/'trial_models.joblib')
    candidate_trace=read(parent/'training_trace.json')['candidates']['logs']
    with np.load(folder/'trial_validation.npz') as arrays:
        require(set(arrays.files)=={f'trial-{k}::{name}' for k in range(3) for name in
            ('pred','scores','valid','target','states','final_state','action','regret')},'Complete validation evidence arrays')
        for k,beta in enumerate(GRID):
            parent_tag=f'trial-{k}__robust_no_feedback';model,head,kind=candidates[parent_tag]
            require(kind=='suppression','Original candidate output declared honestly')
            require(candidate_trace[parent_tag]['gap_weight']==beta and
                len(candidate_trace[parent_tag]['training'])==config['residual_epochs'],
                'Candidate weight and equal static epoch allowance')
            pred,x,valid=model.predict(price_features(validation,columns))
            stored={name:arrays[f'trial-{k}::{name}'] for name in ('pred','scores','valid','target','states','final_state','action','regret')}
            close(pred,stored['pred'],'Reused candidate price predictions',2e-6)
            require(np.array_equal(valid,stored['valid']),'Candidate legal reports')
            close(stored['target'],validation.target_log,'Candidate training-internal target')
            scores=scores_independent(head,x,pred,model.space.reported_missing(validation),'benefit')
            require(np.array_equal(np.isfinite(scores),np.isfinite(stored['scores'])),'Independent benefit eligibility')
            finite=np.isfinite(scores);close(scores[finite],stored['scores'][finite],'Independent benefit head outputs',1e-10)
            audit_execution(pred,scores,valid,stored['states'],stored['final_state'],stored['action'],stored['regret'],model.space,config,.1)
            honest=float(np.mean((pred[:,0]-stored['target'])**2))
            attacked=float(np.mean((pred[np.arange(len(pred)),stored['final_state']]-stored['target'])**2))
            row=trials[trials.gap_weight==beta];require(len(row)==1 and row.iloc[0].parent_trial_tag==parent_tag,'Exact candidate weight/tag')
            row=row.iloc[0];close(row.honest_squared_log_loss,honest,'Benefit honest objective')
            close(row.attack_squared_log_loss,attacked,'Benefit attacked objective');close(row.objective,honest+attacked,'Benefit total objective')
    del candidates
    selection=read(folder/'selection.json');chosen=trials.sort_values(['objective','gap_weight'],kind='stable').iloc[0].gap_weight
    require(selection['grid']==list(GRID) and selection['chosen_gap_weight']==chosen and selection['head_output']=='benefit',
            'Independent three-trial grid selection')
    parent_choice=read(parent/'selection.json')['chosen']['robust_no_feedback']
    require(selection['parent_suppression_choice']==parent_choice,'Distinct suppression selection provenance')
    models=joblib.load(folder/'models.joblib');original=joblib.load(parent/'models.joblib')
    require(set(models)==set(VARIANTS) and all(t[2]=='benefit' for t in models.values()),'Fixed/tuned benefit models')
    reuse='fixed__robust_no_feedback' if chosen==.5 else ('tuned__robust_no_feedback' if chosen==parent_choice else None)
    provenance=read(folder/'refit_provenance.json')
    require(provenance['tuned_parent_model_tag']==reuse and provenance['new_residual_fit']==(reuse is None),'Correct exact-weight reuse or new refit')
    require(provenance['tuned_gap_weight']==chosen and provenance['training_only_backbone_reused'],'Selected refit weight/backbone')
    require(provenance['source_models_sha256']==source['files']['models.joblib'] and
            provenance['source_candidates_sha256']==source['files']['trial_models.joblib'],'Original fit source binding')
    comparisons=[(VARIANTS[0],'fixed__robust_no_feedback')]
    if reuse is not None:comparisons.append((VARIANTS[1],reuse))
    else:
        trace=provenance['new_training_trace'];require(len(trace)==config['residual_epochs'] and
            [row['epoch'] for row in trace]==list(range(1,config['residual_epochs']+1)),'Equal residual epoch allowance')
    public=price_features(train,columns)
    for name,parent_name in comparisons:
        model,head,_=models[name];old,old_head,old_kind=original[parent_name];require(old_kind=='suppression','Reused original kind')
        close(model.predict(public)[0],old.predict(public)[0],'Exact same-role static reuse',2e-6)
        require(head.target_summary==old_head.target_summary,'Exact same-role guidance head reuse')
        for key,value in model.residual.state_dict().items():
            require(torch.equal(value,old.residual.state_dict()[key]),'Reused residual parameter identity')
    # Every refit shares the same training-only CatBoost, including a new weight.
    base=original['fixed__robust_no_feedback'][0]
    for model,_,_ in models.values():
        close(model.arrays(public)[1],base.arrays(public)[1],'Same-role frozen price backbone',1e-9)
    return models,{'stage':folder.name,'trials':3,'chosen_gap_weight':chosen,
        'parent_suppression_choice':parent_choice,'new_residual_fit':reuse is None,'outer_holdout_count':len(heldout)}

def head_audit(model,head,bank,train,columns,config,seed):
    """Refit ExtraTrees from independently constructed OOF targets and inputs."""
    _,x,valid=model.predict(price_features(train,columns));missing=model.space.reported_missing(train)
    n,s,d=x.shape;inputs=np.column_stack((np.repeat(x.reshape(n*s,d),4,axis=0),
        np.repeat(bank.reshape(-1),4),np.tile(np.eye(4,dtype=np.float32),(n*s,1))))
    after=bank[:,model.space.query_next];before=bank[:,:,None];anchor=bank[:,0,None,None]
    y=train.target_log.to_numpy()[:,None,None]
    suppression=np.maximum(before-anchor,0)-np.maximum(after-anchor,0)
    benefit=(before-y)**2-(after-y)**2
    risk=np.broadcast_to((before-y)**2,after.shape)
    targets=np.stack((suppression,benefit,risk),axis=-1);available=valid[:,:,None]&missing
    params=head.model.get_params()
    require(params['n_estimators']==config['head_trees'] and params['max_depth']==12 and
            params['min_samples_leaf']==12 and params['random_state']==seed,'Declared final head allowance')
    independent=ExtraTreesRegressor(n_estimators=config['head_trees'],max_depth=12,
        min_samples_leaf=12,random_state=seed,n_jobs=4)
    independent.fit(inputs[available.ravel()],targets.reshape(-1,3)[available.ravel()])
    require(len(independent.estimators_)==len(head.model.estimators_),'Final head tree count')
    for expected,actual in zip(independent.estimators_,head.model.estimators_):
        require(np.array_equal(expected.tree_.feature,actual.tree_.feature),'OOF-only head feature splits')
        close(expected.tree_.threshold,actual.tree_.threshold,'OOF-only head thresholds',1e-12)
        close(expected.tree_.value,actual.tree_.value,'OOF-only head leaf targets',1e-10)
    require(head.target_summary['records']==n and head.target_summary['action_states']==int(available.sum()),'Head target membership')
    close(head.target_summary['mean_suppression'],suppression[available].mean(),'OOF suppression target summary')
    close(head.target_summary['mean_benefit'],benefit[available].mean(),'OOF benefit target summary')
    require(head.fixed_benefit_field==int(np.nanargmax(np.nanmean(np.where(available,benefit,np.nan),axis=(0,1)))),
            'Training-only fixed benefit field')

def main():
    parser=argparse.ArgumentParser()
    for name in ('run','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--partial',action='store_true')
    args=parser.parse_args();run,output=args.run.resolve(),args.output.resolve()
    manifest=read(run/'manifest.json');config=manifest['config'];tuning=Path(manifest['tuning_path'])
    require(sha(tuning/'manifest.json')==manifest['tuning_manifest_sha256'],'Common tuning generation')
    for name,digest in manifest['source_hashes'].items():require(sha(run/'source_snapshot'/name)==digest,'Extension source snapshot')
    for name in ('run_all.py','run_crossfit.py','savval.py','analyze_nested.py'):
        require(sha(Path(__file__).with_name(name))==manifest['source_hashes'][name],'Imported core frozen')
    scheduled=[(d,n,s) for d in config['datasets'] for n in manifest['sizes'] for s in config['seeds']]
    cases=[]
    for dataset,size,seed in scheduled:
        folder=run/dataset/f'size-{size}'/f'seed-{seed}';receipt=folder/'evaluation_completion.json'
        if not receipt.exists():require(args.partial,'Complete extension required');continue
        done=files_checked(folder,'evaluation_completion.json');require(done['binding']==manifest['binding'],'Captured case binding')
        cases.append({'dataset':dataset,'size':size,'seed':seed,'receipt_sha256':sha(receipt),
                      'stage_completions':done['stage_completions']})
    require(cases and not output.exists(),'Nonempty fresh audit');output.mkdir(parents=True)
    sources=[Path(__file__),*[Path(__file__).with_name(n) for n in
        ('analyze_equal_tuning_size.py','analyze_resources_and_transfer.py','analyze_cdm_development.py',
         'analyze_saved_diagnostics.py','analyze_nested.py','run_all.py','run_crossfit.py','savval.py')]]
    source_hashes={p.name:sha(p) for p in sources};snap=output/'source_snapshot';snap.mkdir()
    for p in sources:(snap/p.name).write_bytes(p.read_bytes())
    root=run/'completion.json';root_digest=sha(root) if root.exists() else None
    input_binding={'manifest_sha256':sha(run/'manifest.json'),'binding':manifest['binding'],
        'tuning_manifest_sha256':manifest['tuning_manifest_sha256'],'cases':cases,'scheduled_cases':len(scheduled),
        'source_completion_sha256':root_digest,'partial':args.partial}
    write_json(output/'input_binding.json',input_binding);checks=[];stages=[];summaries=[];torch.set_num_threads(4)
    with threadpool_limits(limits=4):
        for case in cases:
            dataset,size,seed=case['dataset'],case['size'],case['seed'];local=dict(config,max_train=size)
            first,guidance,evaluation,_=load_source(dataset,local)
            train=rank_subset(pd.concat([first,guidance],ignore_index=True),len(first)+len(guidance),'sav-val-cf-training-order-v2')
            assigned=fold_assignments(train,local['outer_folds'])
            folder=run/dataset/f'size-{size}'/f'seed-{seed}';parent=tuning/dataset/f'size-{size}'/f'seed-{seed}'
            done=files_checked(folder,'evaluation_completion.json');old=files_checked(parent,'evaluation_completion.json')
            require(done['parent_case_receipt_sha256']==sha(parent/'evaluation_completion.json'),'Completed parent case binding')
            assignment=pd.read_csv(folder/'outer_assignments.csv');require(assignment.listing_id.tolist()==train.listing_id.tolist() and
                np.array_equal(assignment.outer_fold,assigned),'Independent outer membership')
            with np.load(folder/'outer_predictions.npz') as loaded:outer={name:loaded[name] for name in loaded.files}
            require(set(outer)==set(VARIANTS),'Complete reference OOF bank')
            for fold in range(local['outer_folds']):
                stage=f'outer-{fold}';training,heldout=train.loc[assigned!=fold].copy(),train.loc[assigned==fold].copy()
                fitted,row=stage_audit(folder/stage,parent/stage,training,heldout.listing_id.tolist(),FEATURES[dataset],
                    local,seed,manifest['binding'],manifest['tuning_binding'])
                stages.append({'dataset':dataset,'size':size,'seed':seed,**row})
                for name,(model,_,_) in fitted.items():close(outer[name][assigned==fold],model.predict(price_features(heldout,FEATURES[dataset]))[0],'Own-fold selected/refitted OOF quotes',2e-6)
            deployment_fits,row=stage_audit(folder/'deployment_fit',parent/'deployment_fit',train,[],FEATURES[dataset],
                local,seed,manifest['binding'],manifest['tuning_binding']);stages.append({'dataset':dataset,'size':size,'seed':seed,**row})
            with np.load(parent/'outer_predictions.npz') as old_outer:close(outer[VARIANTS[0]],old_outer['fixed__robust_no_feedback'],'Fixed parent OOF prices',2e-6)
            deployed=joblib.load(folder/'deployment_models.joblib');require(set(deployed)==set(VARIANTS),'Final reference models')
            outcomes=pd.read_csv(folder/'outcomes.csv.gz');summary=pd.read_csv(folder/'summary.csv');summaries.append(summary)
            require(len(summary)==len(VARIANTS)*len(local['budgets']) and set(zip(summary.method,summary.budget))==
                {(m,b) for m in VARIANTS for b in local['budgets']},'Every reference variant/budget')
            require((summary.dataset==dataset).all() and (summary.seed==seed).all() and
                (summary.train_cap==size).all() and (summary.actual_train_count==len(train)).all(),'Source/size/seed metadata')
            for name,(model,head,kind) in deployed.items():
                require(kind=='benefit','Actual deployed output')
                selected_model=deployment_fits[name][0]
                for key,value in model.residual.state_dict().items():
                    require(torch.equal(value,selected_model.residual.state_dict()[key]),'Actual selected deployment residual')
                close(model.arrays(price_features(evaluation,FEATURES[dataset]))[1],
                    selected_model.arrays(price_features(evaluation,FEATURES[dataset]))[1],
                    'Actual selected deployment backbone',1e-9)
                head_audit(model,head,outer[name],train,FEATURES[dataset],local,seed)
                pred,x,valid=model.predict(price_features(evaluation,FEATURES[dataset]));scores=scores_independent(head,x,pred,model.space.reported_missing(evaluation),'benefit')
                for budget in local['budgets']:
                    rows=outcomes[(outcomes.method==name)&(outcomes.budget==budget)].reset_index(drop=True)
                    require(rows.listing_id.tolist()==evaluation.listing_id.tolist(),'Same reference validation cohort/order')
                    close(rows.target_log,evaluation.target_log,'Reference source targets')
                    report=summary[(summary.method==name)&(summary.budget==budget)].iloc[0]
                    audit_cell(rows,report,local['maximum_hidden'],local['batch_size'])
                    audit_execution(pred,scores,valid,rows.state.to_numpy(int),rows.final_state.to_numpy(int),rows.action.to_numpy(int),rows.best_response_regret_log.to_numpy(),model.space,local,budget)
                    close(rows.clean_prediction_log,pred[:,0],'Reference honest prices',2e-6)
                    close(rows.attacked_prediction_log,pred[np.arange(len(rows)),rows.final_state.to_numpy(int)],'Reference attacked prices',2e-6)
                    stop=min(len(rows),local['batch_size']);quotes=candidate_quotes(pred[:stop],scores[None,:stop],rows.state.iloc[:stop].to_numpy(int),model.space,int(np.floor(budget*stop)))[...,0]
                    envelope=np.maximum(np.where(valid[:stop],quotes,-np.inf).max(axis=1)-pred[:stop,0],0)
                    close(rows.unilateral_inflation_envelope_log.iloc[:stop],envelope,'Independent first-batch envelope',1e-8)
                    checks.append({'dataset':dataset,'size':size,'seed':seed,'method':name,'budget':budget,'metrics':16,
                        'independent_public_scores':True,'oof_head_refit_verified':True,'exact_first_batch_deviations':True})
            require(sha(folder/'evaluation_completion.json')==case['receipt_sha256'],'Captured case changed')
            for stage,digest in case['stage_completions'].items():require(sha(folder/stage/'completion.json')==digest,'Captured fitting stage changed')
            for name,digest in done['files'].items():require(sha(folder/name)==digest,'Audited case artifact changed')
            require(sha(parent/'evaluation_completion.json')==done['parent_case_receipt_sha256'],'Audited parent case changed')
            for name,digest in old['files'].items():require(sha(parent/name)==digest,'Audited parent artifact changed')
            print(f'AUDITED EQUAL BENEFIT {dataset}/{size}/{seed}',flush=True)
    expected=len(cases)*len(VARIANTS)*len(config['budgets']);require(len(checks)==expected,'All captured reference cells')
    if root_digest is not None:
        require(sha(root)==root_digest,'Completed root unchanged');done=read(root)
        require(done['cells']==expected and sha(run/'all_summary.csv')==done['summary_sha256'],'Complete root cell count/binding')
        pd.testing.assert_frame_equal(pd.concat(summaries,ignore_index=True),pd.read_csv(run/'all_summary.csv'),check_dtype=False,rtol=1e-10,atol=1e-10)
    pd.concat(summaries,ignore_index=True).to_csv(output/'audited_summary.csv',index=False)
    pd.DataFrame(checks).to_csv(output/'cell_checks.csv',index=False);pd.DataFrame(stages).to_csv(output/'stages.csv',index=False)
    require(source_hashes=={p.name:sha(p) for p in sources},'Audit sources changed')
    require(sha(run/'manifest.json')==input_binding['manifest_sha256'],'Extension generation changed')
    write_json(output/'completion.json',{'status':'completed','cells':len(checks),'cases':len(cases),'stages':len(stages),
        'candidate_objectives':3*len(stages),'independently_refitted_deployment_heads':2*len(cases),
        'all_scheduled_cases_complete':len(cases)==len(scheduled),'execution_smoke':manifest['execution_smoke'],
        'source_completion_sha256':root_digest,'input_binding_sha256':sha(output/'input_binding.json'),
        'auditor_source_hashes':source_hashes,'files':{p.name:sha(p) for p in output.iterdir() if p.is_file()},
        'scope':'all captured role/candidate/selection/refit reuse/OOF head/evaluation checks; independent raw head inputs and allocation'})
    print('COMPLETED EQUAL BENEFIT AUDIT',flush=True)

if __name__=='__main__':main()
