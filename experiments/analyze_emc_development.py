"""Independent arithmetic, allocation and public-path audit of EMC evidence."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

FIELDS=('mileage_km','transmission','fuel_type','feat_body_condition')
MASKS=np.array([[j in group for j in range(4)] for size in range(5) for group in itertools.combinations(range(4),size)])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def close(a,b,why):
    if not np.allclose(a,b,atol=1e-9,rtol=1e-10,equal_nan=True):
        raise AssertionError(why)


def public_states(frame,encoder):
    copies=frame.iloc[np.repeat(np.arange(len(frame)),16)].reset_index(drop=True).copy()
    for j,name in enumerate(FIELDS):
        copies.loc[np.tile(MASKS[:,j],len(frame)),name]=np.nan
    return encoder.prepare(copies)


def endpoints(models,public,n):
    a,b=[m.predict(public,thread_count=1).reshape(n,16) for m in models]
    lo,hi=np.minimum(a,b),np.maximum(a,b)
    lower=np.empty_like(lo);upper=np.empty_like(hi)
    for h in range(16):
        weaker=[j for j in range(16) if all(not MASKS[h,k] or MASKS[j,k] for k in range(4))]
        lower[:,h]=np.max(lo[:,weaker],axis=1)
        upper[:,h]=np.min(hi[:,weaker],axis=1)
    return lo,hi,lower,upper


def action_frame(public,ends):
    result=public.iloc[np.repeat(np.arange(len(public)),4)].reset_index(drop=True).copy()
    result['query_field']=np.tile(np.asarray(FIELDS),len(public))
    for name,values in zip(('raw_lower','raw_upper','emc_lower','emc_upper'),ends):
        result[name]=np.repeat(values.ravel(),4)
    return result


def audit_case(folder,config):
    done=read(folder/'completion.json'); assert done['status']=='completed'
    assert done['config_sha256']==sha(folder.parent.parent/'config.json')
    for name,digest in done['files'].items():
        assert sha(folder/name)==digest,(folder,name,'hash')
    data=pd.read_csv(folder/'selected_records.csv');assign=pd.read_csv(folder/'split_assignments.csv')
    assert data.listing_id.tolist()==assign.listing_id.tolist()
    assert not data.listing_id.duplicated().any()
    ordered=sorted(data.listing_id,key=lambda x:hashlib.sha256(f'emc-split-v1|{x}'.encode()).hexdigest())
    assert ordered==data.listing_id.tolist()
    n=len(data);edges=[0,int(.5*n),int(.7*n),int(.85*n),n]
    roles=('estimator','head','calibration','evaluation')
    assert assign.split.tolist()==[role for i,role in enumerate(roles) for _ in range(edges[i+1]-edges[i])]
    provenance=read(folder/'source.json');features=provenance['features']
    source=provenance['source']
    if 'path' in source:
        assert Path(source['path']).name=='train.csv' and source['validation_or_test_read'] is False
        # The recorded absolute path is provenance only. A copied package must
        # resolve its own inherited input tree rather than read the original.
        project=Path(__file__).resolve().parents[1]
        source_path=project.parent/'experiments/data/processed'/f'{folder.parent.name}_bvival_v1/splits/train.csv'
        assert sha(source_path)==source['sha256']
        original_source=pd.read_csv(source_path)
    else:
        # Independently reconstruct cohort selection; the generator is declared.
        from savval import simulate_market
        assert source['seed']==73101
        original_source=simulate_market(6000,73101)
    selected=sorted(original_source.listing_id,key=lambda x:hashlib.sha256(f'emc-select-v1|{x}'.encode()).hexdigest())[:config['max_records']]
    expected=original_source.set_index('listing_id').loc[data.listing_id].reset_index()
    assert set(selected)==set(data.listing_id)
    # A selected CSV may infer numeric dtype for an originally categorical
    # column containing only numeric strings. Verify the original serialized
    # source bytes instead of treating that harmless parse change as corruption.
    assert hashlib.sha256(expected[data.columns].to_csv(index=False).encode()).hexdigest()==sha(folder/'selected_records.csv')
    assert not any('price' in c.lower() or c in {'target_log','listing_id','source_row_number','mileage_text','engine_type'} for c in features)
    encoder=joblib.load(folder/'encoder.joblib'); assert encoder.columns==features
    models=[]
    for q in (.1,.9):
        m=CatBoostRegressor();m.load_model(str(folder/f'quantile-{q}.cbm')); models.append(m)
        assert list(m.feature_names_)==features
        parameters=m.get_all_params()
        assert parameters['random_seed']==done['seed'] and parameters['iterations']==config['iterations']
        assert parameters['depth']==6 and abs(parameters['learning_rate']-.05)<1e-7
    head=CatBoostRegressor();head.load_model(str(folder/'query-head.cbm'))
    assert list(head.feature_names_)==features+['query_field','raw_lower','raw_upper','emc_lower','emc_upper']
    parameters=head.get_all_params()
    assert parameters['random_seed']==done['seed'] and parameters['iterations']==config['head_iterations']
    assert parameters['depth']==6 and abs(parameters['learning_rate']-.05)<1e-7
    cache={}
    for i,role in enumerate(roles):
        if role=='estimator':continue
        part=data.iloc[edges[i]:edges[i+1]].reset_index(drop=True)
        recorded=np.load(folder/f'{role}-intervals.npz')
        pub=public_states(part,encoder);values=endpoints(models,pub,len(part))
        for key,value in zip(('raw_lower','raw_upper','emc_lower','emc_upper'),values):close(value,recorded[key],key+' saved model prediction')
        available=part[list(FIELDS)].notna().to_numpy()
        valid=~(MASKS[None,:,:] & ~available[:,None,:]).any(axis=2)
        assert np.array_equal(valid,recorded['valid'])
        close(part.target_log,recorded['target'],'target')
        cache[role]=(part,valid,pub,values)
    cal,cvalid,_,(cl,cu,_,_)=cache['calibration']
    residual=np.maximum(np.maximum(cl-cal.target_log.to_numpy()[:,None],cal.target_log.to_numpy()[:,None]-cu),0)
    ordinary=residual[:,0];strategic=np.array([max(residual[i][cvalid[i]]) for i in range(len(cal))])
    saved=np.load(folder/'calibration-scores.npz')
    close(ordinary,saved['ordinary'],'ordinary scores');close(strategic,saved['strategic'],'strategic scores')
    calibration=read(folder/'calibration.json')
    for alpha in config['alphas']:
        k=int(np.ceil((len(cal)+1)*(1-alpha)));receipt=calibration[str(alpha)]
        assert receipt['rank']==k and receipt['count']==len(cal)
        close(np.sort(ordinary)[k-1],receipt['ordinary_q'],'ordinary rank')
        close(np.sort(strategic)[k-1],receipt['strategic_q'],'strategic rank')
    evaluation,valid,public,values=cache['evaluation'];l,u,el,eu=values
    gain=head.predict(action_frame(public,values),thread_count=1).reshape(len(evaluation),16,4,2)
    close(gain,np.load(folder/'public-query-scores.npz')['gain'],'query head')
    # Force identical reported states while changing their private hidden values.
    sample=evaluation.iloc[:min(8,len(evaluation))].copy();forced=0
    original=endpoints(models,public_states(sample,encoder),len(sample))
    original_score=head.predict(action_frame(public_states(sample,encoder),original),thread_count=1).reshape(len(sample),16,4,2)
    for h in range(1,16):
        altered=sample.copy()
        for j,field in enumerate(FIELDS):
            if MASKS[h,j]:
                altered[field]=987654.0 if field=='mileage_km' else '<PRIVATE-CHANGED>'
        changed=endpoints(models,public_states(altered,encoder),len(altered))
        for a,b in zip(original,changed):close(a[:,h],b[:,h],'hidden values affected public endpoints')
        score=head.predict(action_frame(public_states(altered,encoder),changed),thread_count=1).reshape(len(sample),16,4,2)
        close(original_score[:,h],score[:,h],'hidden values affected public query scores');forced+=len(sample)
    for h in range(16):
        for weaker in range(16):
            if all(not MASKS[h,j] or MASKS[weaker,j] for j in range(4)):
                assert (el[:,weaker]<=el[:,h]+1e-9).all() and (eu[:,weaker]>=eu[:,h]-1e-9).all()
    outcome=pd.read_csv(folder/'outcomes.csv.gz');summary=pd.read_csv(folder/'summary.csv')
    keys=['source','seed','alpha','method','profile','budget','policy']
    missing=evaluation[list(FIELDS)].isna().to_numpy()[:,None,:] | MASKS[None,:,:]
    id_order=evaluation.listing_id.astype(str).to_numpy();target=evaluation.target_log.to_numpy()
    eligible=valid & (MASKS.sum(axis=1)<=2)[None,:]
    profiles={'honest':np.zeros(len(evaluation),int),
        'shared_raw_lower_max':np.argmax(np.where(eligible,l,-np.inf),axis=1),
        'shared_hash_hidden':np.array([np.flatnonzero(eligible[i])[int(hashlib.sha256(f'emc-hidden-v1|{x}'.encode()).hexdigest()[:16],16)%int(eligible[i].sum())] for i,x in enumerate(id_order)])}
    random=np.array([[int(hashlib.sha256(f'emc-priority-v1|{x}|{field}'.encode()).hexdigest()[:16],16)/float(16**16) for field in FIELDS] for x in id_order])
    lookup={tuple(row):h for h,row in enumerate(MASKS)}
    audited=[]
    for names,cell in outcome.groupby(keys,sort=True):
        src,seed,alpha,method,profile,rho,policy=names;cell=cell.reset_index(drop=True)
        assert cell.listing_id.tolist()==id_order.tolist()
        states=profiles[profile]; assert np.array_equal(states,cell.initial_state)
        q=calibration[str(alpha)]['ordinary_q' if method=='ordinary_cp' else 'strategic_q']
        bl,bu=(el,eu) if method=='emc' else (l,u)
        before_l,before_u=bl-q,bu+q
        score=np.broadcast_to(random[:,None,:],(*l.shape,4)).copy() if policy=='random' else np.maximum(gain[...,int(method=='emc')],0)
        score[before_u<np.maximum(0,before_l)]=0
        final=states.copy();actions=np.full(len(states),-1,int)
        for start in range(0,len(states),100):
            stop=min(start+100,len(states));candidates=[]
            for i in range(start,stop):
                s=states[i]
                available=[j for j in range(4) if missing[i,s,j] and np.isfinite(score[i,s,j]) and score[i,s,j]>0]
                if available:
                    j=max(available,key=lambda j:(score[i,s,j],-j));candidates.append((float(score[i,s,j]),i,j))
            candidates.sort(key=lambda row:(-row[0],row[1]))
            for _,i,j in candidates[:int(np.floor(rho*(stop-start)))]:
                actions[i]=j;mask=MASKS[states[i]].copy();mask[j]=False;final[i]=lookup[tuple(mask)]
            assert sum(actions[start:stop]>=0)<=int(np.floor(rho*(stop-start)))
        assert np.array_equal(actions,cell.action) and np.array_equal(final,cell.final_state)
        idx=np.arange(len(states));lower=before_l[idx,final];upper=before_u[idx,final];is_valid=upper>=np.maximum(0,lower)
        quote=np.maximum(0,lower);honest=np.maximum(0,before_l[:,0])
        coverage=is_valid & (lower<=target) & (target<=upper)
        joint=(((before_l<=target[:,None]) & (target[:,None]<=before_u)) | ~valid).all(axis=1)
        close(lower,cell.lower_log,'lower');close(upper,cell.upper_log,'upper')
        assert np.array_equal(is_valid,cell.valid_interval) and np.array_equal(coverage,cell.coverage) and np.array_equal(joint,cell.joint_state_coverage)
        width=np.where(is_valid,upper-np.maximum(0,lower),np.nan);close(width,cell.width_log,'width')
        close(quote,cell.quote_log,'quote');close(honest,cell.honest_quote_log,'honest quote')
        close(quote-target,cell.signed_log_error,'signed error')
        ae=np.abs(np.expm1(quote)-np.expm1(target));close(ae,cell.quote_absolute_error,'MAE')
        inflation=np.maximum(quote-honest,0);close(inflation,cell.positive_log_inflation,'inflation')
        assert np.array_equal((actions>=0)&(final!=states),cell.query_succeeded)
        if method=='emc':assert inflation.max()<=1e-9
        stats=dict(zip(keys,names));stats.update(n=len(cell),coverage=coverage.mean(),joint_state_coverage=joint.mean(),
            width_log=np.nanmean(width),valid_interval_rate=is_valid.mean(),signed_log_bias=(quote-target).mean(),
            quote_mae=ae.mean(),positive_log_inflation=inflation.mean(),query_fraction=(actions>=0).mean(),query_success_fraction=((actions>=0)&(final!=states)).mean())
        audited.append(stats)
    independent=pd.DataFrame(audited).sort_values(keys).reset_index(drop=True);summary=summary.sort_values(keys).reset_index(drop=True)
    assert len(independent)==90==done['cells']
    for c in independent:
        if independent[c].dtype.kind in 'if':close(independent[c],summary[c],'summary '+c)
        else:assert independent[c].tolist()==summary[c].tolist()
    return independent,forced,len(outcome)


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    run=a.run.resolve();root=read(run/'completion.json');config=read(run/'config.json')
    assert root['status']=='completed' and root['config_sha256']==sha(run/'config.json') and root['summary_sha256']==sha(run/'summary.csv')
    assert root['source_snapshot_sha256']==sha(run/'source_snapshot/hashes.json')
    for name,digest in read(run/'source_snapshot/hashes.json').items():assert sha(run/'source_snapshot'/name)==digest
    a.output.mkdir(parents=True,exist_ok=False);rows=[];checks=count=0
    for source in config['sources']:
        for seed in config['seeds']:
            frame,forced,n=audit_case(run/source/f'seed-{seed}',config);rows.append(frame);checks+=forced;count+=n
            print(f'AUDITED {source}/{seed}: {len(frame)} cells',flush=True)
    combined=pd.concat(rows,ignore_index=True);combined.to_csv(a.output/'summary.csv',index=False)
    original=pd.read_csv(run/'summary.csv').sort_values(list(combined.columns[:7])).reset_index(drop=True)
    combined=combined.sort_values(list(combined.columns[:7])).reset_index(drop=True)
    for c in combined:
        if combined[c].dtype.kind in 'if':close(combined[c],original[c],'combined '+c)
        else:assert combined[c].tolist()==original[c].tolist()
    assert len(rows)==root['case_count'] and len(combined)==root['cell_count']
    (a.output/'completion.json').write_text(json.dumps({'status':'completed','smoke':config['smoke'],'case_count':len(rows),
        'cell_count':len(combined),'record_outcome_checks':count,'forced_public_equivalence_checks':checks,
        'run_completion_sha256':sha(run/'completion.json'),'summary_sha256':sha(a.output/'summary.csv'),
        'auditor_sha256':sha(__file__)},indent=2)+'\n')


if __name__=='__main__':main()
