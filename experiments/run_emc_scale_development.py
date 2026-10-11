"""Matched public-state normalized EMC development; preserves its parent."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

from emc_val import conformal_quantile,inherited_endpoints,lower_quote,public_allocate
from run_emc_development import SPACE,materialize,sha,write
from savval import ACTIONS,stable_rank

ROOT=Path(__file__).resolve().parents[1]
METHODS=('strategic_unit','strategic_scaled','emc_unit','emc_scaled')


def scale_inputs(public,l,u):
    result=public.copy();result['raw_lower']=l.ravel();result['raw_upper']=u.ravel()
    return result


def scale_prediction(model,public,l,u):
    value=model.predict(scale_inputs(public,l,u),thread_count=1).reshape(l.shape)
    return np.maximum(.05,np.exp(np.clip(value,np.log(.05),np.log(4.))))


def families(l,u,sigma,unit_q,scaled_q):
    raw_unit=(l-unit_q,u+unit_q);raw_scaled=(l-scaled_q*sigma,u+scaled_q*sigma)
    inherited_unit=inherited_endpoints(*raw_unit,SPACE.masks)
    inherited_scaled=inherited_endpoints(*raw_scaled,SPACE.masks)
    return np.stack([raw_unit,inherited_unit,raw_scaled,inherited_scaled])[np.array([0,2,1,3])]


def query_inputs(public,sigma,intervals):
    result=public.iloc[np.repeat(np.arange(len(public)),4)].reset_index(drop=True).copy()
    result['query_field']=np.tile(np.asarray(ACTIONS),len(public))
    result['public_sigma']=np.repeat(sigma.ravel(),4)
    for k,method in enumerate(METHODS):
        for j,suffix in enumerate(('lower','upper')):
            result[method+'_'+suffix]=np.repeat(intervals[k,j].ravel(),4)
    return result


def case(parent,folder,name,seed,config):
    receipt=json.loads((parent/'completion.json').read_text());assert receipt['status']=='completed' and receipt['cells']==90
    for filename,digest in receipt['files'].items():assert sha(parent/filename)==digest
    data=pd.read_csv(parent/'selected_records.csv');assignment=pd.read_csv(parent/'split_assignments.csv')
    assert data.listing_id.tolist()==assignment.listing_id.tolist()
    encoder=joblib.load(parent/'encoder.joblib');columns=encoder.columns
    parts={key:data[assignment.split==key].reset_index(drop=True) for key in ('head','calibration','evaluation')}
    order=parts['head'].listing_id.map(lambda x:stable_rank(str(x),'emc-scale-split-v1')).sort_values(kind='stable').index.to_numpy()
    scale_indices=order[:len(order)//2];query_indices=order[len(order)//2:]
    pd.DataFrame({'listing_id':parts['head'].listing_id,'role':np.where(np.isin(np.arange(len(order)),scale_indices),'scale','query')}).to_csv(folder/'head_roles.csv',index=False)
    assert not set(parts['head'].listing_id.iloc[scale_indices])&set(parts['head'].listing_id.iloc[query_indices])
    write(folder/'parent_binding.json',{'source':name,'seed':seed,'parent_case_completion_sha256':sha(parent/'completion.json'),
        'parent_config_sha256':receipt['config_sha256'],'parent_files':receipt['files'],'scale_rows':len(scale_indices),'query_rows':len(query_indices),
        'head_roles_sha256':sha(folder/'head_roles.csv')})
    cache={}
    for key,frame in parts.items():
        old=np.load(parent/f'{key}-intervals.npz')
        public,valid=materialize(frame,columns,encoder)
        assert np.array_equal(valid,old['valid'])
        cache[key]=(public,valid,old['raw_lower'],old['raw_upper'])
    public,valid,l,u=cache['head']
    inputs=scale_inputs(public,l,u).iloc[np.repeat(scale_indices*16,16)+np.tile(np.arange(16),len(scale_indices))]
    ok=valid[scale_indices]
    center=(l[scale_indices]+u[scale_indices])/2
    targets=np.log(np.maximum(.05,np.abs(center-parts['head'].target_log.to_numpy()[scale_indices,None])))
    weights=np.broadcast_to(1/ok.sum(axis=1)[:,None],ok.shape)[ok]
    np.savez_compressed(folder/'scale-fitting-targets.npz',indices=scale_indices,target=targets,weights=weights,valid=ok)
    scale=CatBoostRegressor(iterations=config['iterations'],depth=6,learning_rate=.05,loss_function='RMSE',
        random_seed=seed,thread_count=1,verbose=False,allow_writing_files=False)
    scale.fit(inputs.loc[ok.ravel()],targets[ok],sample_weight=weights,cat_features=encoder.categorical)
    scale.save_model(str(folder/'public-scale.cbm'))
    sigmas={key:scale_prediction(scale,values[0],values[2],values[3]) for key,values in cache.items()}
    np.savez_compressed(folder/'public-scales.npz',**sigmas)
    cal=np.load(parent/'calibration-scores.npz');old_cal=json.loads((parent/'calibration.json').read_text())
    _,valid,cl,cu=cache['calibration'];cy=parts['calibration'].target_log.to_numpy()
    raw=np.maximum.reduce([np.zeros_like(cl),cl-cy[:,None],cy[:,None]-cu])
    score=np.where(valid,raw/sigmas['calibration'],-np.inf).max(axis=1)
    np.savez_compressed(folder/'scaled-calibration-scores.npz',score=score)
    calibration={};outputs=[];all_summary=[]
    evaluation=parts['evaluation'];ids=evaluation.listing_id.astype(str).to_numpy();target=evaluation.target_log.to_numpy()
    ep,ev,el,eu=cache['evaluation']
    feasible=ev & (SPACE.masks.sum(axis=1)<=2)[None,:]
    profiles={'honest':np.zeros(len(evaluation),int),
        'shared_raw_lower_max':np.argmax(np.where(feasible,el,-np.inf),axis=1),
        'shared_hash_hidden':np.array([np.flatnonzero(feasible[i])[int(stable_rank(x,'emc-hidden-v1')[:16],16)%int(feasible[i].sum())] for i,x in enumerate(ids)])}
    random=np.array([[int(stable_rank(x+'|'+a,'emc-priority-v1')[:16],16)/float(16**16) for a in ACTIONS] for x in ids])
    random=np.broadcast_to(random[:,None,:],(len(evaluation),16,4));missing=SPACE.reported_missing(evaluation)
    parent_rows=pd.read_csv(parent/'outcomes.csv.gz')
    for alpha in config['alphas']:
        sq,rank=conformal_quantile(score,alpha);uq=old_cal[str(alpha)]['strategic_q']
        assert np.isfinite(sq)
        calibration[str(alpha)]={'scaled_q':sq,'unit_q':uq,'rank':rank,'count':len(score)}
        hp,hv,hl,hu=cache['head'];hi=families(hl,hu,sigmas['head'],uq,sq)
        ei=families(el,eu,sigmas['evaluation'],uq,sq)
        np.savez_compressed(folder/f'family-{alpha}.npz',head=hi,evaluation=ei)
        query_x=query_inputs(hp,sigmas['head'],hi)
        choose=np.repeat(query_indices*64,64)+np.tile(np.arange(64),len(query_indices))
        active=(hv[:,:,None]&SPACE.reported_missing(parts['head']))[query_indices]
        spans=hi[:,1]-hi[:,0]
        gain_targets=np.stack([spans[k][:,:,None]-spans[k][:,SPACE.query_next] for k in range(4)],axis=-1)
        assert not (gain_targets[query_indices][active][:,2:] < -1e-9).any()
        np.savez_compressed(folder/f'query-fitting-targets-{alpha}.npz',indices=query_indices,
            target=gain_targets[query_indices],active=active)
        learner=CatBoostRegressor(iterations=config['iterations'],depth=6,learning_rate=.05,loss_function='MultiRMSE',
            random_seed=seed,thread_count=1,verbose=False,allow_writing_files=False)
        learner.fit(query_x.iloc[choose].loc[active.ravel()],gain_targets[query_indices].reshape(-1,4)[active.ravel()],
            cat_features=encoder.categorical+['query_field'])
        learner.save_model(str(folder/f'query-head-{alpha}.cbm'))
        gain=learner.predict(query_inputs(ep,sigmas['evaluation'],ei),thread_count=1).reshape(len(ev),16,4,4)
        np.savez_compressed(folder/f'query-scores-{alpha}.npz',gain=gain)
        for k,method in enumerate(METHODS):
            lower,upper=ei[k]
            joint=(((lower<=target[:,None])&(target[:,None]<=upper))|~ev).all(axis=1)
            if method.startswith('emc'):
                assert (np.maximum(0,lower)<=np.maximum(0,lower[:,0,None])+1e-9).all()
                for h,mask in enumerate(SPACE.masks):
                    weak=np.all(SPACE.masks|~mask,axis=1)
                    assert (lower[:,weak]<=lower[:,h,None]+1e-9).all() and (upper[:,weak]>=upper[:,h,None]-1e-9).all()
            for profile,initial in profiles.items():
                for rho in config['budgets']:
                    for policy in (('none',) if rho==0 else ('random','shrink')):
                        score_table=random.copy() if policy=='random' else np.maximum(gain[...,k],0)
                        score_table[upper<np.maximum(0,lower)]=0
                        final=initial.copy();action=np.full(len(initial),-1,int)
                        for start in range(0,len(initial),100):
                            stop=min(start+100,len(initial));cap=int(np.floor(rho*(stop-start)))
                            f,a=public_allocate(score_table[start:stop],missing[start:stop],initial[start:stop],cap,SPACE.query_next)
                            final[start:stop],action[start:stop]=f,a
                        idx=np.arange(len(initial));lo=lower[idx,final];up=upper[idx,final]
                        interval_ok=up>=np.maximum(0,lo);quote=lower_quote(lo);honest=lower_quote(lower[:,0])
                        succeeded=(action>=0)&(final!=initial)
                        if method.endswith('unit') and policy in ('none','random'):
                            original_method='emc' if method=='emc_unit' else 'strategic_cp'
                            old=parent_rows[(parent_rows.alpha==alpha)&(parent_rows.method==original_method)&(parent_rows.profile==profile)&(parent_rows.budget==rho)&(parent_rows.policy==policy)]
                            assert len(old)==len(evaluation) and np.array_equal(action,old.action) and np.array_equal(final,old.final_state)
                            assert np.allclose(lo,old.lower_log,atol=1e-9,rtol=1e-10) and np.allclose(up,old.upper_log,atol=1e-9,rtol=1e-10)
                        if method.startswith('emc'):assert not (quote>honest+1e-9).any()
                        for i in idx:
                            outputs.append({'source':name,'seed':seed,'alpha':alpha,'method':method,'profile':profile,'budget':rho,'policy':policy,
                                'listing_id':ids[i],'batch':int(i//100),'initial_state':int(initial[i]),'final_state':int(final[i]),'action':int(action[i]),
                                'query_succeeded':bool(succeeded[i]),'target_log':float(target[i]),'lower_log':float(lo[i]),'upper_log':float(up[i]),
                                'valid_interval':bool(interval_ok[i]),'coverage':bool(interval_ok[i] and lo[i]<=target[i]<=up[i]),
                                'joint_state_coverage':bool(joint[i]),'width_log':float(up[i]-max(0,lo[i])) if interval_ok[i] else None,
                                'quote_log':float(quote[i]),'honest_quote_log':float(honest[i]),'signed_log_error':float(quote[i]-target[i]),
                                'quote_absolute_error':float(abs(np.expm1(quote[i])-np.expm1(target[i]))),
                                'quote_label_ratio':float(np.expm1(quote[i])/np.expm1(target[i])),
                                'positive_log_inflation':float(max(quote[i]-honest[i],0))})
    write(folder/'calibration.json',calibration)
    outcomes=pd.DataFrame(outputs);outcomes.to_csv(folder/'outcomes.csv.gz',index=False,compression='gzip')
    keys=['source','seed','alpha','method','profile','budget','policy']
    summary=outcomes.groupby(keys,sort=True).agg(n=('listing_id','size'),coverage=('coverage','mean'),joint_state_coverage=('joint_state_coverage','mean'),
        width_log=('width_log','mean'),valid_interval_rate=('valid_interval','mean'),signed_log_bias=('signed_log_error','mean'),
        quote_mae=('quote_absolute_error','mean'),median_quote_label_ratio=('quote_label_ratio','median'),
        positive_log_inflation=('positive_log_inflation','mean'),query_fraction=('action',lambda v:(v>=0).mean()),query_success_fraction=('query_succeeded','mean')).reset_index()
    summary.to_csv(folder/'summary.csv',index=False)
    write(folder/'completion.json',{'status':'completed','source':name,'seed':seed,'cells':len(summary),
        'parent_case_completion_sha256':sha(parent/'completion.json'),'config_sha256':sha(folder.parent.parent/'config.json'),
        'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}})
    print(f'COMPLETED SCALE {name}/{seed}: {len(summary)} cells',flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--parent',type=Path,default=Path('outputs/emc-development-v1'));p.add_argument('--output',type=Path,required=True)
    p.add_argument('--smoke',action='store_true');args=p.parse_args();parent=args.parent.resolve();done=json.loads((parent/'completion.json').read_text())
    assert done['status']=='completed' and not done['smoke'] and done['cell_count']==810
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    config={'status':'post-v1 retrospective development refinement','smoke':args.smoke,'sources':['synthetic','jucars','mucars'],
        'seeds':[13] if args.smoke else [13,42,2026],'iterations':20 if args.smoke else 160,'alphas':[.05,.1],'budgets':[0,.1,.3],
        'parent_completion_sha256':sha(parent/'completion.json'),'parent_relative_path':'outputs/emc-development-v1'}
    write(output/'config.json',config);snapshot=output/'source_snapshot';snapshot.mkdir()
    for path in [Path(__file__),ROOT/'experiments/emc_val.py',ROOT/'experiments/run_emc_development.py',ROOT/'experiments/savval.py',ROOT/'plan/emc-state-scale-development-v1.md']:
        shutil.copyfile(path,snapshot/path.name)
    write(snapshot/'hashes.json',{p.name:sha(p) for p in snapshot.iterdir() if p.is_file()})
    print(f'START SCALE {config}',flush=True)
    for source in config['sources']:
        for seed in config['seeds']:
            folder=output/source/f'seed-{seed}';folder.mkdir(parents=True);case(parent/source/f'seed-{seed}',folder,source,seed,config)
    summaries=[pd.read_csv(p) for p in sorted(output.glob('*/seed-*/summary.csv'))]
    pd.concat(summaries,ignore_index=True).to_csv(output/'summary.csv',index=False)
    write(output/'completion.json',{'status':'completed','smoke':args.smoke,'case_count':len(summaries),'cell_count':sum(map(len,summaries)),
        'config_sha256':sha(output/'config.json'),'summary_sha256':sha(output/'summary.csv'),'parent_completion_sha256':sha(parent/'completion.json'),
        'source_snapshot_sha256':sha(snapshot/'hashes.json')})


if __name__=='__main__':main()
