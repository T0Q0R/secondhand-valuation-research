"""Per-cell response evaluation with exact expected itemwise error accounting."""
import hashlib,json
import numpy as np,pandas as pd
from cdm_mechanism import Market
from minimax_market import MinimaxMarket

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')

def evaluate_cell(pred,scores,valid,frame,space,config,budget,allocation,out,model_hash):
    out.mkdir(parents=True,exist_ok=True);rows=[]
    binding={'model_sha256':model_hash,'budget':budget,'allocation':allocation,'evaluation_content':hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest(),'sweeps':config['attacker_sweeps'],'restarts':config['attacker_restarts'],'batch_size':config['batch_size'],'cost':config['concealment_cost_log']}
    if (out/'inputs.json').exists():assert json.loads((out/'inputs.json').read_text())==binding
    else:write(out/'inputs.json',binding)
    for batch,start in enumerate(range(0,len(frame),config['batch_size'])):
        stop=min(start+config['batch_size'],len(frame));n=stop-start;b=int(np.floor(budget*n));folder=out/f'batch-{batch}';folder.mkdir(exist_ok=True)
        if (folder/'completion.json').exists():
            done=json.loads((folder/'completion.json').read_text());assert done['inputs_sha256']==sha(out/'inputs.json')
            assert done['outcomes_sha256']==sha(folder/'outcomes.csv.gz') and done['arrays_sha256']==sha(folder/'arrays.npz')
            rows.append(pd.read_csv(folder/'outcomes.csv.gz'));continue
        pp,ss,vv=pred[start:stop],scores[start:stop],valid[start:stop]
        if allocation=='minimax':
            result=MinimaxMarket(pp,ss,vv,space,b,config['concealment_cost_log']).response(sweeps=config['attacker_sweeps'],restarts=config['attacker_restarts'])
            states=result['states'];p=result['probabilities'];fields=result['fields'];q0=result['pre_quotes'];q1=result['queried_quotes']
        elif allocation=='top_b':
            result=Market(pp,ss[None],vv,space,b,config['concealment_cost_log']).response(np.ones(1),sweeps=config['attacker_sweeps'],restarts=config['attacker_restarts'])
            states=result['states'];fields=result['actions'][:,0];p=(fields>=0).astype(float);q0=pp[np.arange(n),states];q1=result['quotes'][:,0]
        else:raise ValueError('Allocation')
        q=q0+p*(q1-q0);clean=pp[:,0];y=frame.target_log.iloc[start:stop].to_numpy();yc=np.expm1(y)
        success=np.zeros(n,bool);selected=fields>=0;success[selected]=space.masks[states[selected],fields[selected]]
        f=pd.DataFrame({'listing_id':frame.listing_id.iloc[start:stop].astype(str).to_numpy(),'batch':batch,'state':states,'field':fields,'query_probability':p,'failed_query_probability':p*(~success),'pre_quote_log':q0,'queried_quote_log':q1,'expected_quote_log':q,'target_log':y,'clean_quote_log':clean,'honest_absolute_error':abs(np.expm1(clean)-yc),'expected_attacked_absolute_error':(1-p)*abs(np.expm1(q0)-yc)+p*abs(np.expm1(q1)-yc),'positive_expected_log_inflation':np.maximum(q-clean,0),'expected_realized_positive_log_inflation':(1-p)*np.maximum(q0-clean,0)+p*np.maximum(q1-clean,0),'expected_signed_log_error':q-y,'expected_squared_log_error':(1-p)*(q0-y)**2+p*(q1-y)**2,'regret':result['regret'],'deviation_envelope':result['deviation_envelope'],'converged':result['converged'],'cycle':result['cycle'],'sweeps':result['sweeps']})
        f.to_csv(folder/'outcomes.csv.gz',index=False,compression='gzip')
        np.savez_compressed(folder/'arrays.npz',pred=pp,scores=ss,valid=vv,states=states,probabilities=p,fields=fields)
        write(folder/'completion.json',{'status':'completed','inputs_sha256':sha(out/'inputs.json'),'capacity':b,'outcomes_sha256':sha(folder/'outcomes.csv.gz'),'arrays_sha256':sha(folder/'arrays.npz')});rows.append(f)
    data=pd.concat(rows,ignore_index=True)
    summary={'n':len(data),'budget':budget,'allocation':allocation,**{c:float(data[c].mean()) for c in ['honest_absolute_error','expected_attacked_absolute_error','positive_expected_log_inflation','failed_query_probability','expected_signed_log_error','deviation_envelope']},'max_regret':float(data.regret.max()),'nonconverged_batches':int((~data.groupby('batch').converged.first()).sum())}
    write(out/'summary.json',summary)
    write(out/'completion.json',{'status':'completed_pending_independent_audit','summary_sha256':sha(out/'summary.json'),'inputs_sha256':sha(out/'inputs.json'),'batch_receipts':{str(p.relative_to(out)):sha(p) for p in out.glob('batch-*/completion.json')}})
    return summary
