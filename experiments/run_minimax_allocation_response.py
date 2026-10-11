"""Matched top-B versus score-minimax common-response experiment."""
import argparse,fcntl,hashlib,json,time
from pathlib import Path
import joblib,numpy as np,pandas as pd,torch
from run_all import load_source
from savval import FEATURES,price_features
from cdm_mechanism import Market
from minimax_market import MinimaxMarket

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def main(a):
    root=Path('outputs/nested-development-v2');parent=json.loads((root/'run_manifest.json').read_text())
    config=parent['config'];out=a.output.resolve();out.mkdir(parents=True,exist_ok=a.resume)
    lock=(out/'execution.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    sources=[Path(__file__),Path('experiments/minimax_market.py'),Path('experiments/public_minimax_allocation.py'),Path('experiments/cdm_mechanism.py'),Path('plan/minimax-allocation-response-v1.md')]
    binding={'parent_manifest':sha(root/'run_manifest.json'),'smoke':a.smoke,'source_hashes':{str(p):sha(p) for p in sources},'budget':.1,'seeds':[13] if a.smoke else [13,42,2026],'datasets':['synthetic'] if a.smoke else config['datasets'],'prices':{'robust':'robust_no_feedback'} if a.smoke else {'masking':'masking_suppression','robust':'robust_no_feedback'},'sweeps':20,'restarts':4}
    if a.resume:assert json.loads((out/'manifest.json').read_text())==binding
    else:
        write(out/'manifest.json',binding);snap=out/'source_snapshot';snap.mkdir()
        for p in sources:(snap/p.name).write_bytes(p.read_bytes())
    torch.set_num_threads(2);started=time.time();summary=[]
    for dataset in binding['datasets']:
        _,_,evaluation,_=load_source(dataset,config)
        if a.smoke:evaluation=evaluation.iloc[:20].copy()
        source=price_features(evaluation,FEATURES[dataset]);target=evaluation.target_log.to_numpy()
        for seed in binding['seeds']:
            for price,key in binding['prices'].items():
                model_path=root/dataset/f'seed-{seed}'/'deployment_models'/f'{key}.joblib';model_hash=sha(model_path)
                model,head,_=joblib.load(model_path);pred,x,valid=model.predict(source)
                for kind in ('suppression','benefit','risk'):
                    scores=head.score(x,pred,model.space,kind,reported_missing=model.space.reported_missing(source))
                    for allocation in ('top_b','minimax'):
                        cell=out/dataset/f'seed-{seed}'/price/kind/allocation;cell.mkdir(parents=True,exist_ok=True);rows=[]
                        for batch,start in enumerate(range(0,len(source),100)):
                            folder=cell/f'batch-{batch}';stop=min(start+100,len(source));n=stop-start;capacity=int(np.floor(.1*n))
                            if a.resume and (folder/'completion.json').exists():
                                done=json.loads((folder/'completion.json').read_text());assert done['model_sha256']==model_hash
                                assert sha(folder/'outcomes.csv.gz')==done['outcomes_sha256']
                                assert sha(folder/'execution.npz')==done['execution_sha256']
                                rows.append(pd.read_csv(folder/'outcomes.csv.gz'));continue
                            folder.mkdir(exist_ok=True)
                            pp,ss,vv=pred[start:stop],scores[start:stop],valid[start:stop]
                            if allocation=='minimax':
                                market=MinimaxMarket(pp,ss,vv,model.space,capacity,config['concealment_cost_log'])
                                result=market.response(sweeps=20,restarts=4);states=result['states'];p=result['probabilities'];fields=result['fields'];q0=result['pre_quotes'];q1=result['queried_quotes']
                            else:
                                market=Market(pp,ss[None,:,:,:],vv,model.space,capacity,config['concealment_cost_log'])
                                result=market.response(np.ones(1),sweeps=20,restarts=4);states=result['states'];fields=result['actions'][:,0];p=(fields>=0).astype(float);q0=pp[np.arange(n),states];q1=result['quotes'][:,0]
                            q=q0+p*(q1-q0);clean=pp[:,0];y=target[start:stop];yc=np.expm1(y)
                            success=np.zeros(n,bool);hasfield=fields>=0;success[hasfield]=model.space.masks[states[hasfield],fields[hasfield]]
                            frame=pd.DataFrame({'listing_id':evaluation.listing_id.iloc[start:stop].astype(str).to_numpy(),'batch':batch,'state':states,'field':fields,'query_probability':p,'failed_query_probability':p*(~success),'pre_quote_log':q0,'queried_quote_log':q1,'expected_quote_log':q,'target_log':y,'clean_quote_log':clean,'honest_absolute_error':abs(np.expm1(clean)-yc),'expected_attacked_absolute_error':(1-p)*abs(np.expm1(q0)-yc)+p*abs(np.expm1(q1)-yc),'positive_expected_log_inflation':np.maximum(q-clean,0),'expected_realized_positive_log_inflation':(1-p)*np.maximum(q0-clean,0)+p*np.maximum(q1-clean,0),'expected_squared_log_error':(1-p)*(q0-y)**2+p*(q1-y)**2,'expected_signed_log_error':q-y,'regret':result['regret'],'deviation_envelope':result['deviation_envelope'],'converged':result['converged'],'cycle':result['cycle'],'sweeps':result['sweeps']})
                            frame.to_csv(folder/'outcomes.csv.gz',index=False,compression='gzip')
                            np.savez_compressed(folder/'execution.npz',pred=pp,scores=ss,valid=vv,states=states,probabilities=p,fields=fields,pre_quotes=q0,queried_quotes=q1)
                            write(folder/'completion.json',{'status':'completed','capacity':capacity,'n':n,'model_path':str(model_path.resolve()),'model_sha256':model_hash,'outcomes_sha256':sha(folder/'outcomes.csv.gz'),'execution_sha256':sha(folder/'execution.npz')})
                            rows.append(frame)
                        data=pd.concat(rows,ignore_index=True)
                        metrics={c:float(data[c].mean()) for c in ['honest_absolute_error','expected_attacked_absolute_error','positive_expected_log_inflation','expected_realized_positive_log_inflation','failed_query_probability','expected_signed_log_error','deviation_envelope']}
                        record={'dataset':dataset,'seed':seed,'price':price,'score':kind,'allocation':allocation,'n':len(data),**metrics,'max_regret':float(data.regret.max()),'nonconverged_batches':int((~data.groupby('batch').converged.first()).sum())}
                        summary.append(record);write(cell/'summary.json',record);print(json.dumps(record),flush=True)
                assert sha(model_path)==model_hash
    assert binding['source_hashes']=={str(p):sha(p) for p in sources}
    pd.DataFrame(summary).to_csv(out/'summary.csv',index=False)
    write(out/'completion.json',{'status':'completed_pending_independent_audit','smoke':a.smoke,'cells':len(summary),'outcome_rows':sum(row['n'] for row in summary),'seconds_this_process':time.time()-started,'summary_sha256':sha(out/'summary.csv')})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--smoke',action='store_true');p.add_argument('--resume',action='store_true');main(p.parse_args())
