"""Independent normalized-interval, fitting-target and hard-cap EMC audit."""
import argparse
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

from analyze_emc_development import MASKS,FIELDS,close,endpoints,public_states,read,sha

METHODS=('strategic_unit','strategic_scaled','emc_unit','emc_scaled')


def scale_frame(public,l,u):
    result=public.copy();result['raw_lower']=l.ravel();result['raw_upper']=u.ravel();return result


def normalized(model,public,l,u):
    x=model.predict(scale_frame(public,l,u),thread_count=1).reshape(l.shape)
    return np.maximum(.05,np.exp(np.clip(x,np.log(.05),np.log(4.))))


def intersect(lo,hi):
    l=np.empty_like(lo);u=np.empty_like(hi)
    for h in range(16):
        weak=[j for j in range(16) if all(not MASKS[h,k] or MASKS[j,k] for k in range(4))]
        l[:,h]=lo[:,weak].max(axis=1);u[:,h]=hi[:,weak].min(axis=1)
    return l,u


def family(lo,hi,scale,uq,sq):
    a=(lo-uq,hi+uq);b=(lo-sq*scale,hi+sq*scale)
    return np.array([a,b,intersect(*a),intersect(*b)])


def action_frame(public,sigma,ends):
    result=public.iloc[np.repeat(np.arange(len(public)),4)].reset_index(drop=True).copy()
    result['query_field']=np.tile(np.asarray(FIELDS),len(public));result['public_sigma']=np.repeat(sigma.ravel(),4)
    for k,name in enumerate(METHODS):
        result[name+'_lower']=np.repeat(ends[k,0].ravel(),4);result[name+'_upper']=np.repeat(ends[k,1].ravel(),4)
    return result


def fitted_model(path,seed,iterations):
    m=CatBoostRegressor();m.load_model(str(path));params=m.get_all_params()
    assert params['random_seed']==seed and params['iterations']==iterations and params['depth']==6
    assert abs(params['learning_rate']-.05)<1e-7
    return m


def audit_case(folder,parent,config):
    done=read(folder/'completion.json');assert done['status']=='completed' and done['cells']==120
    assert done['parent_case_completion_sha256']==sha(parent/'completion.json')
    assert done['config_sha256']==sha(folder.parent.parent/'config.json')
    for name,digest in done['files'].items():assert sha(folder/name)==digest
    binding=read(folder/'parent_binding.json');parent_receipt=read(parent/'completion.json')
    assert binding['parent_files']==parent_receipt['files']
    for name,digest in parent_receipt['files'].items():assert sha(parent/name)==digest
    data=pd.read_csv(parent/'selected_records.csv');assign=pd.read_csv(parent/'split_assignments.csv')
    assert data.listing_id.tolist()==assign.listing_id.tolist()
    parts={key:data[assign.split==key].reset_index(drop=True) for key in ('head','calibration','evaluation')}
    order=sorted(range(len(parts['head'])),key=lambda i:hashlib.sha256(f"emc-scale-split-v1|{parts['head'].listing_id.iloc[i]}".encode()).hexdigest())
    si=np.array(order[:len(order)//2]);qi=np.array(order[len(order)//2:])
    roles=pd.read_csv(folder/'head_roles.csv')
    assert roles.listing_id.tolist()==parts['head'].listing_id.tolist()
    assert roles.role.tolist()==['scale' if i in set(si) else 'query' for i in range(len(order))]
    assert binding['scale_rows']==len(si) and binding['query_rows']==len(qi)
    assert binding['head_roles_sha256']==sha(folder/'head_roles.csv')
    encoder=joblib.load(parent/'encoder.joblib')
    assert not any('price' in c.lower() or c in {'listing_id','target_log','source_row_number','engine_type','mileage_text'} for c in encoder.columns)
    base=[fitted_model(parent/f'quantile-{q}.cbm',done['seed'],250) for q in (.1,.9)]
    scale=fitted_model(folder/'public-scale.cbm',done['seed'],config['iterations'])
    assert list(scale.feature_names_)==encoder.columns+['raw_lower','raw_upper']
    cache={};sigmas={};recorded=np.load(folder/'public-scales.npz')
    for key,part in parts.items():
        public=public_states(part,encoder);lo,hi,_,_=endpoints(base,public,len(part))
        available=part[list(FIELDS)].notna().to_numpy();valid=~(MASKS[None,:,:]&~available[:,None,:]).any(axis=2)
        cache[key]=(public,valid,lo,hi);sigmas[key]=normalized(scale,public,lo,hi)
        close(sigmas[key],recorded[key],'Public sigma prediction')
    hp,hv,hl,hu=cache['head']
    target=np.log(np.maximum(.05,np.abs((hl[si]+hu[si])/2-parts['head'].target_log.to_numpy()[si,None])))
    weights=np.broadcast_to(1/hv[si].sum(axis=1)[:,None],hv[si].shape)[hv[si]]
    fit=np.load(folder/'scale-fitting-targets.npz')
    assert np.array_equal(si,fit['indices']) and np.array_equal(hv[si],fit['valid'])
    close(target,fit['target'],'Scale fitting targets');close(weights,fit['weights'],'Record-balanced scale weights')
    cp,cv,cl,cu=cache['calibration'];cy=parts['calibration'].target_log.to_numpy()
    residual=np.maximum.reduce([np.zeros_like(cl),cl-cy[:,None],cy[:,None]-cu])
    score=np.array([max((residual/sigmas['calibration'])[i][cv[i]]) for i in range(len(cy))])
    close(score,np.load(folder/'scaled-calibration-scores.npz')['score'],'Scaled scores')
    calibration=read(folder/'calibration.json');old_cal=read(parent/'calibration.json')
    lookup={tuple(row):k for k,row in enumerate(MASKS)}
    next_state=np.zeros((16,4),int)
    for h,mask in enumerate(MASKS):
        for j in range(4):
            remaining=mask.copy();remaining[j]=False;next_state[h,j]=lookup[tuple(remaining)]
    outcome=pd.read_csv(folder/'outcomes.csv.gz');summary=pd.read_csv(folder/'summary.csv')
    ep,ev,el,eu=cache['evaluation'];evaluation=parts['evaluation'];ids=evaluation.listing_id.astype(str).to_numpy();y=evaluation.target_log.to_numpy()
    eligible=ev&(MASKS.sum(axis=1)<=2)[None,:]
    profiles={'honest':np.zeros(len(evaluation),int),'shared_raw_lower_max':np.argmax(np.where(eligible,el,-np.inf),axis=1),
        'shared_hash_hidden':np.array([np.flatnonzero(eligible[i])[int(hashlib.sha256(f'emc-hidden-v1|{x}'.encode()).hexdigest()[:16],16)%int(eligible[i].sum())] for i,x in enumerate(ids)])}
    random=np.array([[int(hashlib.sha256(f'emc-priority-v1|{x}|{field}'.encode()).hexdigest()[:16],16)/float(16**16) for field in FIELDS] for x in ids])
    missing=evaluation[list(FIELDS)].isna().to_numpy()[:,None,:]|MASKS[None,:,:]
    head_missing=parts['head'][list(FIELDS)].isna().to_numpy()[:,None,:]|MASKS[None,:,:]
    audited=[];forced=0
    keys=['source','seed','alpha','method','profile','budget','policy']
    for alpha in config['alphas']:
        values=calibration[str(alpha)];rank=int(np.ceil((len(score)+1)*(1-alpha)))
        assert values['rank']==rank and values['count']==len(score)
        close(values['scaled_q'],np.sort(score)[rank-1],'Scaled rank');close(values['unit_q'],old_cal[str(alpha)]['strategic_q'],'Matched unit q')
        uq,sq=values['unit_q'],values['scaled_q']
        head_intervals=family(hl,hu,sigmas['head'],uq,sq);intervals=family(el,eu,sigmas['evaluation'],uq,sq)
        saved=np.load(folder/f'family-{alpha}.npz')
        close(head_intervals,saved['head'],'Head family endpoints');close(intervals,saved['evaluation'],'Evaluation family endpoints')
        spans=head_intervals[:,1]-head_intervals[:,0]
        targets=np.stack([spans[k][:,:,None]-spans[k][:,next_state] for k in range(4)],axis=-1)
        active=(hv[:,:,None]&head_missing)[qi];fit=np.load(folder/f'query-fitting-targets-{alpha}.npz')
        assert np.array_equal(qi,fit['indices']) and np.array_equal(active,fit['active'])
        close(targets[qi],fit['target'],'Matched query fitting targets')
        head=fitted_model(folder/f'query-head-{alpha}.cbm',done['seed'],config['iterations'])
        expected=encoder.columns+['query_field','public_sigma']+[method+'_'+suffix for method in METHODS for suffix in ('lower','upper')]
        assert list(head.feature_names_)==expected
        gain=head.predict(action_frame(ep,sigmas['evaluation'],intervals),thread_count=1).reshape(len(ev),16,4,4)
        close(gain,np.load(folder/f'query-scores-{alpha}.npz')['gain'],'Four matched public scores')
        # Probe identical public reports under changed private hidden values.
        sample=evaluation.iloc[:8].copy();original_public=public_states(sample,encoder);ol,ou,_,_=endpoints(base,original_public,len(sample))
        os=normalized(scale,original_public,ol,ou);oi=family(ol,ou,os,uq,sq)
        og=head.predict(action_frame(original_public,os,oi),thread_count=1).reshape(len(sample),16,4,4)
        for h in range(1,16):
            altered=sample.copy()
            for j,field in enumerate(FIELDS):
                if MASKS[h,j]:altered[field]=987654.0 if j==0 else '<PRIVATE-CHANGED>'
            public=public_states(altered,encoder);l,u,_,_=endpoints(base,public,len(altered));s=normalized(scale,public,l,u);it=family(l,u,s,uq,sq)
            close(os[:,h],s[:,h],'Hidden values affected scale');close(oi[:,:, :,h],it[:,:,:,h],'Hidden values affected certificates')
            changed=head.predict(action_frame(public,s,it),thread_count=1).reshape(len(sample),16,4,4)
            close(og[:,h],changed[:,h],'Hidden values affected queries');forced+=len(sample)
        for k,method in enumerate(METHODS):
            l,u=intervals[k]
            if method.startswith('emc'):
                assert (np.maximum(0,l)<=np.maximum(0,l[:,0,None])+1e-9).all()
                for h in range(16):
                    for weak in range(16):
                        if all(not MASKS[h,j] or MASKS[weak,j] for j in range(4)):
                            assert (l[:,weak]<=l[:,h]+1e-9).all() and (u[:,weak]>=u[:,h]-1e-9).all()
            joint=(((l<=y[:,None])&(y[:,None]<=u))|~ev).all(axis=1)
            cells=outcome[(outcome.alpha==alpha)&(outcome.method==method)]
            for names,cell in cells.groupby(keys,sort=True):
                _,_,_,_,profile,rho,policy=names;cell=cell.reset_index(drop=True)
                assert cell.listing_id.tolist()==ids.tolist();states=profiles[profile]
                assert np.array_equal(states,cell.initial_state)
                scores=np.broadcast_to(random[:,None,:],(*el.shape,4)).copy() if policy=='random' else np.maximum(gain[...,k],0)
                scores[u<np.maximum(0,l)]=0
                final=states.copy();actions=np.full(len(states),-1,int)
                for start in range(0,len(states),100):
                    stop=min(start+100,len(states));candidates=[]
                    for i in range(start,stop):
                        available=[j for j in range(4) if missing[i,states[i],j] and np.isfinite(scores[i,states[i],j]) and scores[i,states[i],j]>0]
                        if available:
                            j=max(available,key=lambda j:(scores[i,states[i],j],-j));candidates.append((float(scores[i,states[i],j]),i,j))
                    candidates.sort(key=lambda x:(-x[0],x[1]))
                    for _,i,j in candidates[:int(np.floor(rho*(stop-start)))]:actions[i]=j;final[i]=next_state[states[i],j]
                    assert sum(actions[start:stop]>=0)<=int(np.floor(rho*(stop-start)))
                assert np.array_equal(actions,cell.action) and np.array_equal(final,cell.final_state)
                idx=np.arange(len(states));lo=l[idx,final];up=u[idx,final];ok=up>=np.maximum(0,lo)
                quote=np.maximum(0,lo);honest=np.maximum(0,l[:,0]);success=(actions>=0)&(final!=states)
                coverage=ok&(lo<=y)&(y<=up);width=np.where(ok,up-np.maximum(0,lo),np.nan)
                close(lo,cell.lower_log,'Final lower');close(up,cell.upper_log,'Final upper');close(width,cell.width_log,'Width')
                assert np.array_equal(ok,cell.valid_interval) and np.array_equal(coverage,cell.coverage) and np.array_equal(joint,cell.joint_state_coverage)
                assert np.array_equal(success,cell.query_succeeded)
                close(y,cell.target_log,'Targets');close(quote,cell.quote_log,'Quote');close(honest,cell.honest_quote_log,'Honest quote')
                ratio=np.expm1(quote)/np.expm1(y);error=np.abs(np.expm1(quote)-np.expm1(y));inflation=np.maximum(quote-honest,0)
                close(ratio,cell.quote_label_ratio,'Price ratio');close(error,cell.quote_absolute_error,'MAE');close(quote-y,cell.signed_log_error,'Signed error');close(inflation,cell.positive_log_inflation,'Inflation')
                audited.append({**dict(zip(keys,names)),'n':len(cell),'coverage':coverage.mean(),'joint_state_coverage':joint.mean(),
                    'width_log':np.nanmean(width),'valid_interval_rate':ok.mean(),'signed_log_bias':(quote-y).mean(),'quote_mae':error.mean(),
                    'median_quote_label_ratio':np.median(ratio),'positive_log_inflation':inflation.mean(),
                    'query_fraction':(actions>=0).mean(),'query_success_fraction':success.mean()})
    result=pd.DataFrame(audited).sort_values(keys).reset_index(drop=True);summary=summary.sort_values(keys).reset_index(drop=True)
    assert len(result)==120
    for col in result:
        if result[col].dtype.kind in 'if':close(result[col],summary[col],'Cell summary '+col)
        else:assert result[col].tolist()==summary[col].tolist()
    return result,forced,len(outcome)


def main():
    parser=argparse.ArgumentParser()
    for name in ('parent','run','output'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();run=a.run.resolve();parent=a.parent.resolve();done=read(run/'completion.json');config=read(run/'config.json')
    assert done['status']=='completed' and done['parent_completion_sha256']==sha(parent/'completion.json')
    assert done['config_sha256']==sha(run/'config.json') and done['summary_sha256']==sha(run/'summary.csv')
    assert done['source_snapshot_sha256']==sha(run/'source_snapshot/hashes.json')
    for name,digest in read(run/'source_snapshot/hashes.json').items():assert sha(run/'source_snapshot'/name)==digest
    a.output.mkdir(parents=True,exist_ok=False);rows=[];forced=count=0
    for source in config['sources']:
        for seed in config['seeds']:
            frame,n,records=audit_case(run/source/f'seed-{seed}',parent/source/f'seed-{seed}',config);rows.append(frame);forced+=n;count+=records
            print(f'AUDITED SCALE {source}/{seed}:120',flush=True)
    combined=pd.concat(rows,ignore_index=True);combined.to_csv(a.output/'summary.csv',index=False)
    assert len(combined)==done['cell_count'] and len(rows)==done['case_count']
    keys=['source','seed','alpha','method','profile','budget','policy'];original=pd.read_csv(run/'summary.csv').sort_values(keys).reset_index(drop=True);sorted_result=combined.sort_values(keys).reset_index(drop=True)
    for col in combined:
        if combined[col].dtype.kind in 'if':close(sorted_result[col],original[col],'Combined summary '+col)
        else:assert sorted_result[col].tolist()==original[col].tolist()
    (a.output/'auditor_snapshot.py').write_bytes(Path(__file__).read_bytes())
    (a.output/'completion.json').write_text(json.dumps({'status':'completed','smoke':config['smoke'],'cells':len(combined),
        'cases':len(rows),'forced_public_equivalence_checks':forced,'record_outcome_checks':count,
        'run_completion_sha256':sha(run/'completion.json'),'parent_completion_sha256':sha(parent/'completion.json'),
        'summary_sha256':sha(a.output/'summary.csv'),'auditor_sha256':sha(__file__)},indent=2)+'\n')


if __name__=='__main__':main()
