"""Independent complete robust/benefit reference and paired-contrast audit."""
from __future__ import annotations
import argparse
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import torch
from threadpoolctl import threadpool_limits
from analyze_nested import read,require,sha,conditional_cluster_interval
from analyze_saved_diagnostics import audit_cell
from analyze_resources_and_transfer import scores_independent,allocate_independent
from analyze_cdm_development import candidate_quotes
from run_all import load_source,write_json
from savval import FEATURES,price_features

def main():
    parser=argparse.ArgumentParser()
    for name in ('run','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run,output=args.run.resolve(),args.output.resolve()
    manifest,done=read(run/'manifest.json'),read(run/'completion.json');config=manifest['config']
    require(done['status']=='completed' and done['cells']==54,'Complete ordinary-benefit reference')
    require(sha(run/'summary.csv')==done['summary_sha256'],'Root summary binding')
    require(manifest['saved_parent_kind']=='suppression' and manifest['evaluated_kind']=='benefit','Explicit head outputs')
    parent=Path(manifest['parent_path']);pm=read(parent/'run_manifest.json')
    require(pm['binding']==manifest['parent_binding']==done['parent_binding'],'Common parent')
    require(sha(parent/'completion.json')==manifest['parent_completion_sha256'],'Parent complete binding')
    scheduled={(d,s) for d in config['datasets'] for s in config['seeds']}
    require(set(map(tuple,done['pairs']))==scheduled and len(scheduled)==9,'All original pairs')
    for name,digest in manifest['source_hashes'].items():require(sha(run/'source_snapshot'/name)==digest,'Runner source snapshot')
    require(not output.exists(),'Fresh immutable reference audit');output.mkdir(parents=True)
    sources=[Path(__file__),*[Path(__file__).with_name(n) for n in ('analyze_nested.py','analyze_saved_diagnostics.py',
        'analyze_resources_and_transfer.py','analyze_cdm_development.py','run_all.py','savval.py')]]
    snapshot=output/'source_snapshot';snapshot.mkdir()
    for path in sources:(snapshot/path.name).write_bytes(path.read_bytes())
    hashes={p.name:sha(p) for p in sources};rows=[];all_outcomes=[];parent_outcomes=[];checks=[]
    aggregate=pd.read_csv(run/'summary.csv');torch.set_num_threads(4)
    with threadpool_limits(limits=4):
        for dataset in config['datasets']:
            _,_,evaluation,provenance=load_source(dataset,config)
            for seed in config['seeds']:
                folder=run/dataset/f'seed-{seed}';r=read(folder/'completion.json')
                require(r['status']=='completed' and r['source_provenance']==provenance,'Source cohort/provenance')
                for field,name in [('outcomes_sha256','outcomes.csv.gz'),('summary_sha256','summary.csv')]:
                    require(sha(folder/name)==r[field],'Reference pair artifact')
                model_path=Path(r['model_path']);require(sha(model_path)==r['model_sha256'],'Parent model bytes')
                model,head,kind=joblib.load(model_path);require(kind=='suppression','Actual saved parent kind')
                pred,x,valid=model.predict(price_features(evaluation,FEATURES[dataset]))
                scores=scores_independent(head,x,pred,model.space.reported_missing(evaluation),'benefit')
                listing=pd.read_csv(folder/'outcomes.csv.gz');summary=pd.read_csv(folder/'summary.csv')
                old_folder=parent/dataset/f'seed-{seed}';old_done=read(old_folder/'evaluation_completion.json')
                require(sha(old_folder/'per_listing_outcomes.csv.gz')==old_done['outcomes_sha256'],'Parent listing binding')
                old=pd.read_csv(old_folder/'per_listing_outcomes.csv.gz')
                for budget in config['budgets']:
                    selected=listing[listing.budget==budget].reset_index(drop=True)
                    report=summary[summary.budget==budget];require(len(report)==1,'Unique reference budget')
                    report=report.iloc[0]
                    require(selected.listing_id.tolist()==evaluation.listing_id.tolist(),'Exact reference evaluation order')
                    require((selected.method=='robust_benefit_no_feedback').all() and (selected.seed==seed).all(),'Method/seed metadata')
                    require(valid[np.arange(len(selected)),selected.state.to_numpy(int)].all(),'Originally feasible withholding')
                    require(np.allclose(selected.target_log,evaluation.target_log,atol=1e-10,rtol=0),'Source target binding')
                    ordinary=old[(old.method=='robust_no_feedback')&(old.budget==budget)].set_index('listing_id').loc[evaluation.listing_id]
                    require(np.allclose(selected.clean_prediction_log,ordinary.clean_prediction_log,atol=2e-6,rtol=0),'Same frozen honest predictor')
                    metrics=audit_cell(selected,report,config['maximum_hidden'],config['batch_size'])
                    for batch,start in enumerate(range(0,len(selected),config['batch_size'])):
                        stop=min(start+config['batch_size'],len(selected));indices=np.arange(start,stop)
                        states=selected.state.iloc[start:stop].to_numpy(int);cap=int(np.floor(budget*len(indices)))
                        actions=allocate_independent(scores[indices,states],cap)
                        finals=states.copy()
                        for i in np.flatnonzero(actions>=0):finals[i]=model.space.query_next[states[i],actions[i]]
                        require(np.array_equal(actions,selected.action.iloc[start:stop]) and np.array_equal(finals,selected.final_state.iloc[start:stop]),'Independent reference allocation')
                        quote=pred[indices,finals]
                        require(np.allclose(quote,selected.attacked_prediction_log.iloc[start:stop],atol=2e-6,rtol=0),'Reference final quotes')
                        if batch==0:
                            candidates=candidate_quotes(pred[start:stop],scores[None,start:stop],states,model.space,cap)[...,0]
                            utility=np.where(valid[start:stop],candidates-config['concealment_cost_log']*model.space.masks.sum(axis=1)[None],-np.inf)
                            current=quote-config['concealment_cost_log']*model.space.masks[states].sum(axis=1)
                            regret=np.maximum(utility.max(axis=1)-current,0)
                            # Only legal alternatives enter the quote envelope.
                            envelope=np.maximum(np.where(valid[start:stop],candidates,-np.inf).max(axis=1)-pred[start:stop,0],0)
                            require(np.allclose(regret,selected.best_response_regret_log.iloc[start:stop],atol=1e-8,rtol=0),'Exact reference first-batch regret')
                            require(np.allclose(envelope,selected.unilateral_inflation_envelope_log.iloc[start:stop],atol=1e-8,rtol=0),'Exact reference first-batch envelope')
                    rows.append(report.to_dict());checks.append({'dataset':dataset,'seed':seed,'budget':budget,
                        'independent_allocation':True,'recomputed_metrics':metrics,'exact_first_batch_deviations':True})
                all_outcomes.append(listing.assign(dataset=dataset));parent_outcomes.append(old[old.method=='sav_val'].assign(dataset=dataset))
                require(sha(model_path)==r['model_sha256'],'Frozen model changed')
                print(f'AUDITED ROBUST BENEFIT {dataset}/{seed}',flush=True)
    columns=['dataset','seed','method','budget']
    pd.testing.assert_frame_equal(pd.DataFrame(rows).sort_values(columns).reset_index(drop=True),
        aggregate.sort_values(columns).reset_index(drop=True),check_dtype=False,rtol=1e-10,atol=1e-10)
    outcomes=pd.concat(all_outcomes+parent_outcomes,ignore_index=True);contrasts=[]
    for dataset in config['datasets']:
        for budget in config['budgets']:
            group=outcomes[(outcomes.dataset==dataset)&(outcomes.budget==budget)]
            for metric in ('positive_log_inflation','clean_absolute_error','attack_absolute_error'):
                pivot=group.pivot(index=['seed','listing_id','batch'],columns='method',values=metric)
                require(not pivot.isna().any().any(),'Paired reference membership')
                difference=(pivot.robust_benefit_no_feedback-pivot.sav_val).rename('delta').reset_index()
                require((difference.groupby('listing_id').batch.nunique()==1).all(),'Shared batches across seeds')
                paired=difference.groupby(['listing_id','batch'],as_index=False).delta.mean()
                interval=conditional_cluster_interval(paired,config['bootstrap_repetitions'],941006)
                own=pivot.sav_val.mean();reference=pivot.robust_benefit_no_feedback.mean()
                contrasts.append({'dataset':dataset,'budget':budget,'metric':metric,'sav_mean':own,'reference_mean':reference,
                    'relative_reduction_percent':100*(reference-own)/reference if reference>0 else np.nan,**interval,
                    'scope':'original-contract ordinary-benefit reference; fixed parent estimator/head; seed-averaged conditional shared-batch interval'})
    pd.DataFrame(rows).to_csv(output/'audited_summary.csv',index=False)
    pd.DataFrame(checks).to_csv(output/'cell_checks.csv',index=False)
    pd.DataFrame(contrasts).to_csv(output/'paired_contrasts.csv',index=False)
    require(hashes=={p.name:sha(p) for p in sources},'Audit sources changed')
    write_json(output/'completion.json',{'status':'completed','cells':len(rows),'parent_binding':manifest['parent_binding'],
        'source_completion_sha256':sha(run/'completion.json'),'source_hashes':hashes,
        'files':{p.name:sha(p) for p in output.iterdir() if p.is_file()},
        'scope':'all 54 reference cells, same honest prices, independent public scores/allocations/metrics; exact first-batch deviations'})
    print('Completed ordinary-benefit reference audit.',flush=True)

if __name__=='__main__':main()
