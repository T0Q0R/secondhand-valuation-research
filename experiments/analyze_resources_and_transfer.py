"""Independent allocation, resource arithmetic and saved common-report audit.

No production allocator, seller search, public-pipeline function or action-head
score wrapper is called. Pricing models are shared as fixed objects; public
head inputs and sorted allocations are reconstructed independently.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import torch
from threadpoolctl import threadpool_limits
from analyze_nested import read,require,sha,conditional_cluster_interval
from run_all import load_source,write_json
from savval import ACTIONS,FEATURES,price_features

METHODS={'masking_benefit':'masking_suppression','robust_no_feedback':'robust_no_feedback',
         'sav_benefit_head':'sav_benefit_head','sav_val':'sav_val'}

def close(actual,expected,reason,tolerance=1e-8):
    require(np.allclose(actual,expected,atol=tolerance,rtol=1e-8,equal_nan=True),reason)

def scores_independent(head,x,pred,missing,kind):
    n,s,d=x.shape
    inputs=np.column_stack((np.repeat(x.reshape(n*s,d),4,axis=0),
                            np.repeat(pred.reshape(-1),4),np.tile(np.eye(4,dtype=np.float32),(n*s,1))))
    values=head.model.predict(inputs).reshape(n,s,4,3)
    require(kind in {'benefit','suppression'},'Principal method head kind')
    return np.where(missing,values[...,1 if kind=='benefit' else 0],-np.inf)

def allocate_independent(scores,capacity):
    chosen=np.full(len(scores),-1,int)
    candidates=[]
    for i,row in enumerate(scores):
        field=int(np.argmax(row));merit=float(row[field])
        if np.isfinite(merit) and merit>0:candidates.append((-merit,i,field))
    for _,i,field in sorted(candidates)[:capacity]:chosen[i]=field
    return chosen

def public_check(model,head,kind,source,public,budget):
    # Only the report enters valuation and scoring; replay reads source after
    # the complete allocation has been determined.
    prediction,x,_=model.predict(public)
    missing=public.loc[:,list(ACTIONS)].isna().to_numpy()[:,None,:]
    scores=scores_independent(head,x[:,:1],prediction[:,:1],missing,kind)[:,0]
    action=allocate_independent(scores,int(np.floor(budget*len(public))))
    after=public.copy();success=np.zeros(len(public),bool)
    for i in np.flatnonzero(action>=0):
        field=ACTIONS[action[i]]
        require(pd.isna(public.iloc[i][field]),'Query publicly absent field')
        value=source.iloc[i][field]
        if pd.notna(value):after.iloc[i,after.columns.get_loc(field)]=value;success[i]=True
    final=model.predict(after)[0][:,0]
    return final,action,success

def main():
    parser=argparse.ArgumentParser()
    for name in ('parent','resource','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();parent,resource,output=[getattr(args,n).resolve() for n in ('parent','resource','output')]
    pm,pd_done=read(parent/'run_manifest.json'),read(parent/'completion.json')
    rm,rd=read(resource/'manifest.json'),read(resource/'completion.json')
    require(pd_done['status']==rd['status']=='completed' and not rm['execution_smoke'],'Full completed evidence')
    require(pm['binding']==pd_done['binding']==rm['parent_binding']==rd['parent_binding'],'Common parent binding')
    require(rm['parent_completion_sha256']==sha(parent/'completion.json'),'Resource parent receipt')
    require(rm['repetitions']==20 and rm['warmups']==2 and rm['cpu_threads']==4,'Declared timing allowance')
    for name,digest in rd['outputs'].items():require(sha(resource/name)==digest,'Resource output binding')
    for name,digest in rm['source_hashes'].items():require(sha(resource/'source_snapshot'/name)==digest,'Resource source snapshot')
    config=pm['config'];pairs={(d,s) for d in config['datasets'] for s in config['seeds']}
    timings=pd.read_csv(resource/'repetition_timings.csv');equivalence=pd.read_csv(resource/'public_path_equivalence.csv')
    model_bindings=pd.read_csv(resource/'model_bindings.csv');fit=pd.read_csv(resource/'shared_matrix_fit_stages.csv')
    require(len(pairs)==9 and len(model_bindings)==36 and len(fit)==36,'Full fit/model matrix')
    require(len(equivalence)==rd['equivalence_batches']==360 and len(timings)==rd['timing_rows']==7200,'Full timing/equivalence matrix')
    keys=['dataset','seed','method','batch']
    require(not equivalence.duplicated(keys).any() and not timings.duplicated(keys+['repetition']).any(),'Unique resource keys')
    for _,group in timings.groupby(keys):
        require(set(group.repetition)==set(range(20)) and (group.n==100).all(),'All repetitions and batch size')
    components=['pre_quote_seconds','head_seconds','allocation_seconds','software_replay_seconds','post_quote_seconds']
    require((timings[components+['pipeline_seconds']]>=0).all().all(),'Nonnegative clock intervals')
    close(timings[components].sum(axis=1),timings.pipeline_seconds,'Timing component sum',1e-12)
    reported=pd.read_csv(resource/'pipeline_summary.csv').sort_values(['dataset','method']).reset_index(drop=True)
    rebuilt=timings.groupby(['dataset','method']).pipeline_seconds.agg(mean='mean',median='median',
        p90=lambda s:s.quantile(.9),minimum='min',maximum='max',observations='count').reset_index().sort_values(['dataset','method']).reset_index(drop=True)
    pd.testing.assert_frame_equal(reported,rebuilt,check_dtype=False,rtol=1e-10,atol=1e-12)
    require(not output.exists(),'Fresh immutable audit');output.mkdir(parents=True)
    (output/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    checks=[];transfer_rows=[];transfer_summaries=[];bindings={}
    torch.set_num_threads(4)
    with threadpool_limits(limits=4):
        for dataset in config['datasets']:
            _,_,evaluation,_=load_source(dataset,config);source=price_features(evaluation,FEATURES[dataset])
            for seed in config['seeds']:
                folder=parent/dataset/f'seed-{seed}';done=read(folder/'evaluation_completion.json')
                require(done['binding']==pm['binding'] and sha(folder/'per_listing_outcomes.csv.gz')==done['outcomes_sha256'],'Parent listing input')
                transfer_path=folder/'common_attack_transfer.csv';bindings[f'{dataset}/{seed}']=sha(transfer_path)
                transfer=pd.read_csv(transfer_path);outcomes=pd.read_csv(folder/'per_listing_outcomes.csv.gz')
                reference=outcomes[(outcomes.method=='sav_val')&(outcomes.budget==.1)].set_index('listing_id').loc[evaluation.listing_id]
                fixed=reference.state.to_numpy(int)
                for stage in ['outer-0','outer-1','outer-2','deployment_fit']:
                    fp=folder/stage/'fit_completion.json';fr=read(fp)
                    row=fit[(fit.dataset==dataset)&(fit.seed==seed)&(fit.stage==stage)]
                    require(len(row)==1 and row.iloc[0].receipt_sha256==sha(fp),'Fit receipt binding')
                    close(row.iloc[0].seconds_shared_twelve_method_fit,fr['seconds'],'Shared stage timing')
                for method,model_file in METHODS.items():
                    path=folder/'deployment_models'/f'{model_file}.joblib'
                    mb=model_bindings[(model_bindings.dataset==dataset)&(model_bindings.seed==seed)&(model_bindings.method==method)]
                    require(len(mb)==1 and mb.iloc[0].model_sha256==sha(path) and mb.iloc[0].serialized_model_and_head_bytes==path.stat().st_size,'Model byte accounting')
                    model,head,kind=joblib.load(path)
                    if method=='masking_benefit':kind='benefit'
                    expected=outcomes[(outcomes.method==method)&(outcomes.budget==.1)].set_index('listing_id').loc[evaluation.listing_id]
                    for batch,subset in expected.groupby('batch',sort=True):
                        indices=evaluation.set_index('listing_id').index.get_indexer(subset.index)
                        original=source.iloc[indices].reset_index(drop=True);public=original.copy()
                        states=subset.state.to_numpy(int)
                        for a,field in enumerate(ACTIONS):public.loc[model.space.masks[states,a],field]=np.nan
                        quote,action,success=public_check(model,head,kind,original,public,.1)
                        require(np.array_equal(action,subset.action.to_numpy()) and np.array_equal(success,subset.query_succeeded.to_numpy()),'Independent public action/replay')
                        close(quote,subset.attacked_prediction_log,'Independent public final quote',2e-6)
                        er=equivalence[(equivalence.dataset==dataset)&(equivalence.seed==seed)&(equivalence.method==method)&(equivalence.batch==batch)]
                        require(len(er)==1 and er.iloc[0].queries_match and er.iloc[0].successes_match and er.iloc[0].max_abs_quote_difference<=2e-6,'Stored deployment equivalence')
                        checks.append({'dataset':dataset,'seed':seed,'method':method,'batch':batch,'public_allocation_verified':True,'replay_verified':True,'final_quote_verified':True})
                    # Common reports are the full SAV-Val returned primary
                    # reports. There is no reoptimization against other rules.
                    prediction,x,valid=model.predict(source)
                    scores=scores_independent(head,x,prediction,model.space.reported_missing(evaluation),kind)
                    finals=fixed.copy();actions=np.full(len(evaluation),-1,int)
                    for start in range(0,len(evaluation),config['batch_size']):
                        stop=min(start+config['batch_size'],len(evaluation));indices=np.arange(start,stop)
                        chosen=allocate_independent(scores[indices,fixed[indices]],int(np.floor(.1*len(indices))))
                        actions[indices]=chosen
                        for local in np.flatnonzero(chosen>=0):
                            i=indices[local];finals[i]=model.space.query_next[fixed[i],chosen[local]]
                    target=evaluation.target_log.to_numpy();honest=prediction[:,0];attack=prediction[np.arange(len(evaluation)),finals]
                    row=transfer[transfer.method==method];require(len(row)==1,'Unique shared-report method')
                    metrics={'clean_rmsle':float(np.sqrt(np.mean((honest-target)**2))),
                        'attack_rmsle':float(np.sqrt(np.mean((attack-target)**2))),
                        'clean_mae':float(np.abs(np.expm1(honest)-np.expm1(target)).mean()),
                        'attack_mae':float(np.abs(np.expm1(attack)-np.expm1(target)).mean()),
                        'mean_positive_log_inflation':float(np.maximum(attack-honest,0).mean()),
                        'mean_positive_price_inflation':float(np.maximum(np.expm1(attack)-np.expm1(honest),0).mean()),
                        'clean_signed_log_bias':float((honest-target).mean()),'attack_signed_log_bias':float((attack-target).mean()),
                        'clean_underprediction_log':float(np.maximum(target-honest,0).mean()),
                        'actual_audit_fraction':float((actions>=0).mean()),'hiding_fraction':float((fixed!=0).mean()),
                        'failed_query_fraction':float(((actions>=0)&(finals==fixed)).mean())}
                    for metric,value in metrics.items():close(row.iloc[0][metric],value,'Common-report '+metric)
                    require(row.iloc[0].seed==seed and row.iloc[0].budget==.1 and row.iloc[0].n==len(evaluation),'Shared-report metadata')
                    transfer_summaries.append({'dataset':dataset,'seed':seed,'method':method,**metrics})
                    for i in range(len(evaluation)):
                        transfer_rows.append({'dataset':dataset,'seed':seed,'method':method,'listing_id':evaluation.listing_id.iloc[i],
                            'batch':int(reference.batch.iloc[i]),'state':int(fixed[i]),'positive_log_inflation':max(attack[i]-honest[i],0),
                            'attack_absolute_error':abs(np.expm1(attack[i])-np.expm1(target[i]))})
                    require(sha(path)==mb.iloc[0].model_sha256,'Parent model changed')
                require(sha(transfer_path)==bindings[f'{dataset}/{seed}'],'Transfer input changed')
                print(f'AUDITED RESOURCE / SHARED REPORT {dataset}/{seed}',flush=True)
    listing=pd.DataFrame(transfer_rows);contrasts=[]
    for dataset in config['datasets']:
        group=listing[listing.dataset==dataset]
        for metric in ('positive_log_inflation','attack_absolute_error'):
            for method in ('masking_benefit','robust_no_feedback','sav_benefit_head'):
                pivot=group[group.method.isin([method,'sav_val'])].pivot(index=['seed','listing_id','batch'],columns='method',values=metric)
                require(not pivot.isna().any().any(),'Shared-report paired membership')
                paired=(pivot[method]-pivot.sav_val).rename('delta').reset_index()
                require((paired.groupby('listing_id').batch.nunique()==1).all(),'Shared batches across seeds')
                averaged=paired.groupby(['listing_id','batch'],as_index=False).delta.mean()
                interval=conditional_cluster_interval(averaged,config['bootstrap_repetitions'],921006)
                contrasts.append({'dataset':dataset,'reference':method,'metric':metric,**interval,
                    'scope':'all methods on full SAV-Val primary reports; no new response search; seed-averaged conditional shared-batch interval'})
    for name,data in [('public_path_rechecks',checks),('shared_report_summaries',transfer_summaries),('shared_report_contrasts',contrasts)]:
        pd.DataFrame(data).to_csv(output/f'{name}.csv',index=False)
    listing.to_csv(output/'shared_report_listings.csv.gz',index=False)
    rebuilt.to_csv(output/'rechecked_pipeline_summary.csv',index=False)
    write_json(output/'completion.json',{'status':'completed','parent_binding':pm['binding'],
        'resource_completion_sha256':sha(resource/'completion.json'),'public_batches':len(checks),'shared_report_cells':len(transfer_summaries),
        'transfer_input_hashes':bindings,'source_sha256':sha(Path(__file__)),
        'files':{p.name:sha(p) for p in output.iterdir() if p.is_file()},
        'scope':'independent public head inputs/sorted allocations/replay, timing summaries and shared-report metrics; fixed pricing objects; shared CPU hardware'})
    print(f'Completed resource and shared-report audit: {output}',flush=True)

if __name__=='__main__':main()
