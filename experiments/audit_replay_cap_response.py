"""Independent stable-sort audit of every capped final profile and deviation."""
import argparse,hashlib,itertools,json,time
from pathlib import Path
import numpy as np
import pandas as pd

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,indent=2)+'\n')
def close(a,b):
    if not np.allclose(a,b,atol=1e-8,rtol=1e-10,equal_nan=True):
        raise AssertionError('Independent response reconstruction mismatch')

def main(a):
    run,out=a.run.resolve(),a.output.resolve();done=read(run/'completion.json');manifest=read(run/'manifest.json')
    done_hash=sha(run/'completion.json')
    assert done['status']=='completed' and done['cells']==432
    for p,d in done['files'].items():assert sha(run/p)==d
    for p,d in manifest['input_hashes'].items():assert sha(p)==d
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True);(out/'auditor_snapshot.py').write_bytes(Path(__file__).read_bytes())
    masks=np.array([[a in group for a in range(4)] for size in range(3)
                    for group in itertools.combinations(range(4),size)],bool)
    lookup={tuple(m):i for i,m in enumerate(masks)};transition=np.empty((11,4),int)
    for h in range(11):
        for f in range(4):
            m=masks[h].copy();m[f]=False;transition[h,f]=lookup[tuple(m)]
    source=Path(manifest['source']);summaries=[];count=0;allocations=0;deviations=0;mutations=[];started=time.time()
    for receipt in done['case_receipts']:
        rel=Path(receipt['path']);folder=run/rel
        assert sha(folder/'completion.json')==receipt['sha256']
        for p,d in read(folder/'completion.json')['files'].items():assert sha(folder/p)==d
        binding=read(folder/'input_binding.json')
        for p,d in binding.items():assert sha(p)==d
        dataset,seed,price,budget_name,method=rel.parts;budget=int(budget_name.split('-')[1])/10000;B=int(np.floor(budget*100))
        with np.load(source/Path(*rel.parts[:3])/'evaluation_arrays.npz') as z:pred,scores,valid=[z[k] for k in ('pred','scores','valid')]
        saved=pd.read_csv(folder/'outcomes.csv.gz');old=pd.read_csv(source/rel/'outcomes.csv.gz')
        with np.load(folder/'execution.npz') as z:quotes=z['quotes'];finals=z['finals'];actions=z['actions'];indices=z['policy_indices'];weights=z['probabilities']
        with np.load(source/rel/'execution.npz') as z:original_weights=z['probabilities']
        assert np.array_equal(indices,np.flatnonzero(original_weights>0));close(weights,original_weights[indices])
        for col in ['listing_id','batch','method','seed','budget','target_log','clean_prediction_log','clean_absolute_error']:
            if not pd.api.types.is_numeric_dtype(old[col]):assert saved[col].equals(old[col])
            else:close(saved[col],old[col])
        assert len(saved)==1000 and np.array_equal(saved.batch,np.repeat(np.arange(10),100))
        target=saved.target_log.to_numpy();close(saved.clean_prediction_log,pred[:,0])
        close(saved.clean_absolute_error,np.abs(np.expm1(pred[:,0])-np.expm1(target)))
        reconstructed=saved.copy()
        for batch,start in enumerate(range(0,1000,100)):
            stop=start+100;state=saved.state.to_numpy(int)[start:stop];n=100
            assert valid[np.arange(start,stop),state].all()
            block=scores[indices,start:stop];k=len(indices)
            actual_scores=block[:,np.arange(n),state,:]
            field=actual_scores.argmax(-1);merit=actual_scores.max(-1)
            ranking=np.argsort(-merit,axis=-1,kind='stable')
            chosen=np.zeros_like(merit,dtype=bool)
            np.put_along_axis(chosen,ranking[:,:B],True,axis=-1)
            chosen &= np.isfinite(merit)&(merit>0)
            assert (chosen.sum(-1)<=B).all();allocations+=k
            action=np.where(chosen,field,-1).T
            final=np.where(chosen,transition[state[None,:],field],state[None,:]).T
            raw=pred[np.arange(start,stop)[:,None],final]
            quote=np.minimum(raw,pred[np.arange(start,stop),state,None])
            assert np.array_equal(action,actions[start:stop]) and np.array_equal(final,finals[start:stop]);close(quote,quotes[start:stop])
            all_candidates=[]
            for i in range(n):
                reports=np.broadcast_to(state,(11,n)).copy();reports[:,i]=np.arange(11)
                public_scores=block[:,np.arange(n)[None,:],reports,:]
                fields=public_scores.argmax(-1);merits=public_scores.max(-1)
                order=np.argsort(-merits,axis=-1,kind='stable')
                selected=np.zeros_like(merits,dtype=bool)
                np.put_along_axis(selected,order[:,:,:B],True,axis=-1)
                selected &= np.isfinite(merits)&(merits>0)
                assert (selected.sum(-1)<=B).all()
                own_final=np.where(selected[:,:,i],transition[np.arange(11)[None,:],fields[:,:,i]],np.arange(11)[None,:])
                q=np.minimum(pred[start+i,own_final],pred[start+i,np.arange(11)[None,:]])
                values=q.T@weights
                all_candidates.append(np.where(valid[start+i],values,-np.inf))
                deviations+=int(valid[start+i].sum())*k
            candidates=np.array(all_candidates);current=quote@weights
            regret=np.maximum(candidates.max(1)-current,0)
            envelope=np.maximum(candidates.max(1)-candidates[:,0],0)
            close(candidates[:,0],pred[start:stop,0])
            close(candidates[np.arange(n),state],current)
            assert np.all(saved.batch_converged.iloc[start:stop].to_numpy()==bool((regret<1e-7).all()))
            assert saved.batch_sweeps.iloc[start:stop].nunique()==1
            assert 1<=int(saved.batch_sweeps.iloc[start])<=20
            success=np.zeros_like(action,bool);rr,cc=np.nonzero(action>=0);success[rr,cc]=masks[state[rr],action[rr,cc]]
            currency=np.expm1(quote);y=target[start:stop];clean=pred[start:stop,0]
            columns={'hidden_count':masks[state].sum(1),'expected_prediction_log':current,
                'expected_prediction_currency':currency@weights,
                'expected_attack_absolute_error':np.abs(currency-np.expm1(y)[:,None])@weights,
                'expected_attack_squared_log_error':((quote-y[:,None])**2)@weights,
                'positive_expected_log_inflation':np.maximum(current-clean,0),
                'expected_realized_positive_log_inflation':np.maximum(quote-clean[:,None],0)@weights,
                'expected_query_probability':(action>=0)@weights,
                'expected_failed_query_probability':((action>=0)&~success)@weights,
                'expected_signed_log_error':(quote-y[:,None])@weights,
                'best_response_regret_log':regret,'unilateral_deviation_envelope_log':envelope}
            for col,value in columns.items():
                close(saved[col].iloc[start:stop],value);reconstructed.loc[start:stop-1,col]=value
            if not mutations:
                for name,values in [('quote',quote),('regret',regret),('failed_query',columns['expected_failed_query_probability'])]:
                    corrupted=np.array(values,copy=True);corrupted.flat[0]+=.1
                    try:close(corrupted,values)
                    except AssertionError:mutations.append(name)
                    else:raise AssertionError('Mutation accepted')
        for variant,f in [('original',old),('capped',reconstructed)]:
            mapping={'honest_mae':'clean_absolute_error','attacked_mae':'expected_attack_absolute_error',
                'inflation':'positive_expected_log_inflation','realized_positive_inflation':'expected_realized_positive_log_inflation',
                'signed_log_bias':'expected_signed_log_error','query':'expected_query_probability',
                'failed':'expected_failed_query_probability','mean_regret':'best_response_regret_log',
                'deviation':'unilateral_deviation_envelope_log'}
            summaries.append({'dataset':dataset,'seed':int(seed.split('-')[1]),'price':price,'budget':budget,
                'method':method,'variant':variant,**{k:float(f[v].mean()) for k,v in mapping.items()},
                'max_regret':float(f.best_response_regret_log.max()),
                'nonconverged_batch_fraction':float(1-f.groupby('batch').batch_converged.first().mean())})
        assert all(sha(p)==d for p,d in binding.items());count+=1
        if method=='cdm':print(f'AUDITED CAPPED RESPONSES {rel.parent}',flush=True)
    calculated=pd.DataFrame(summaries);keys=['dataset','seed','price','budget','method','variant']
    left=calculated.sort_values(keys).reset_index(drop=True);right=pd.read_csv(run/'summary.csv').sort_values(keys).reset_index(drop=True)
    assert left[keys].equals(right[keys]);close(left.drop(columns=keys),right[left.columns].drop(columns=keys))
    calculated.to_csv(out/'verified_summary.csv',index=False)
    assert sha(run/'completion.json')==done_hash
    write(out/'completion.json',{'status':'completed','cells':count,'listing_outcomes':count*1000,
        'actual_supported_rule_batches':allocations,'legal_rule_deviations_sorted':deviations,
        'mutations_rejected':mutations,'parent_completion_sha256':done_hash,'seconds':time.time()-started,
        'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()},
        'scope':'all final allocations, capped quotes, errors and full legal unilateral regret; not globally optimal joint responses or replay of every search step'})

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('run','output'):p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
