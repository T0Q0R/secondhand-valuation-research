"""Complete frozen-model capped common-response study; no fitting."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
import pandas as pd
from replay_cap_market import CappedMarket
from savval import StateSpace

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,indent=2)+'\n')

def summarize(frame):
    return {'honest_mae':float(frame.clean_absolute_error.mean()),
        'attacked_mae':float(frame.expected_attack_absolute_error.mean()),
        'inflation':float(frame.positive_expected_log_inflation.mean()),
        'realized_positive_inflation':float(frame.expected_realized_positive_log_inflation.mean()),
        'signed_log_bias':float(frame.expected_signed_log_error.mean()),
        'query':float(frame.expected_query_probability.mean()),
        'failed':float(frame.expected_failed_query_probability.mean()),
        'mean_regret':float(frame.best_response_regret_log.mean()),
        'max_regret':float(frame.best_response_regret_log.max()),
        'deviation':float(frame.unilateral_deviation_envelope_log.mean()),
        'nonconverged_batch_fraction':float(1-frame.groupby('batch').batch_converged.first().mean())}

def main(a):
    root,audit,out=a.run.resolve(),a.audit.resolve(),a.output.resolve()
    manifest=read(root/'manifest.json');done=read(root/'completion.json');checked=read(audit/'completion.json')
    assert done['status']==checked['status']=='completed'
    assert checked['cells']==1512
    if 'parent_completion_sha256' in checked:assert sha(root/'completion.json')==checked['parent_completion_sha256']
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True);snapshot=out/'source_snapshot';snapshot.mkdir()
    files=[Path(__file__).resolve(),Path(__file__).with_name('replay_cap_market.py').resolve(),
           Path(__file__).with_name('cdm_mechanism.py').resolve(),Path(__file__).with_name('savval.py').resolve(),
           Path('plan/replay-cap-response-v1.md').resolve()]
    for p in files:(snapshot/p.name).write_bytes(p.read_bytes())
    inputs={str(p):sha(p) for p in files+[root/'manifest.json',root/'completion.json',audit/'completion.json']}
    config=manifest['config'];assert config['concealment_cost_log']==0 and config['batch_size']==100
    methods=['suppression','benefit','risk','cdm'];space=StateSpace.build(2)
    write(out/'manifest.json',{'source':str(root),'source_audit':str(audit),'input_hashes':inputs,
          'pairs':manifest['pairs'],'prices':list(manifest['prices']),'budgets':config['budgets'],
          'methods':methods,'config':config,'scope':'new capped common responses; frozen models and original weights'})
    receipts=[];summaries=[];start_time=time.time()
    for dataset,seed in manifest['pairs']:
        for price in manifest['prices']:
            rel=Path(dataset)/f'seed-{seed}'/price
            arrays=root/rel/'evaluation_arrays.npz'
            with np.load(arrays) as z:pred,scores,valid=[z[k] for k in ('pred','scores','valid')]
            assert len(pred)==1000
            for budget in config['budgets']:
                budget_rel=rel/f'budget-{round(budget*10000):04d}';parent=root/budget_rel
                parent_done=read(parent/'completion.json')
                for method in methods:
                    tick=time.time();old_dir=parent/method
                    for name in ('outcomes.csv.gz','execution.npz','summary.json'):
                        assert sha(old_dir/name)==parent_done['files'][method+'/'+name]
                    old=pd.read_csv(old_dir/'outcomes.csv.gz')
                    assert np.allclose(old.clean_prediction_log,pred[:,0],atol=1e-10,rtol=0)
                    with np.load(old_dir/'execution.npz') as z:full_weights=z['probabilities']
                    assert (full_weights>=0).all() and abs(full_weights.sum()-1)<1e-9
                    active=np.flatnonzero(full_weights>0);weights=full_weights[active]
                    result=old.copy();allquotes=[];allfinal=[];allactions=[]
                    for batch,begin in enumerate(range(0,1000,100)):
                        end=begin+100;market=CappedMarket(pred[begin:end],scores[active,begin:end],
                            valid[begin:end],space,int(np.floor(budget*100)),0.)
                        response=market.response(weights,sweeps=config['attacker_sweeps'],restarts=config['attacker_restarts'])
                        quote=response['quotes'];action=response['actions'];state=response['states']
                        currency=np.expm1(quote);target=old.target_log.to_numpy()[begin:end]
                        clean=pred[begin:end,0];success=np.zeros_like(action,bool)
                        queried=action>=0
                        rr,cc=np.nonzero(queried);success[rr,cc]=space.masks[state[rr],action[rr,cc]]
                        assert (queried.sum(0)<=market.capacity).all()
                        expected=quote@weights
                        columns={'state':state,'hidden_count':space.masks[state].sum(1),
                            'expected_prediction_log':expected,'expected_prediction_currency':currency@weights,
                            'expected_attack_absolute_error':np.abs(currency-np.expm1(target)[:,None])@weights,
                            'expected_attack_squared_log_error':((quote-target[:,None])**2)@weights,
                            'positive_expected_log_inflation':np.maximum(expected-clean,0),
                            'expected_realized_positive_log_inflation':np.maximum(quote-clean[:,None],0)@weights,
                            'expected_query_probability':queried@weights,
                            'expected_failed_query_probability':(queried&~success)@weights,
                            'expected_signed_log_error':(quote-target[:,None])@weights,
                            'best_response_regret_log':response['regret'],
                            'unilateral_deviation_envelope_log':response['deviation_envelope'],
                            'batch_converged':response['converged'],'batch_cycle':response['cycle'],
                            'batch_sweeps':response['sweeps']}
                        for name,value in columns.items():result.loc[begin:end-1,name]=value
                        allquotes.append(quote);allfinal.append(response['finals']);allactions.append(action)
                    folder=out/budget_rel/method;folder.mkdir(parents=True)
                    result.to_csv(folder/'outcomes.csv.gz',index=False)
                    np.savez_compressed(folder/'execution.npz',quotes=np.concatenate(allquotes),
                        finals=np.concatenate(allfinal),actions=np.concatenate(allactions),
                        policy_indices=active,probabilities=weights)
                    binding={str(p):sha(p) for p in [arrays,parent/'completion.json',old_dir/'outcomes.csv.gz',old_dir/'execution.npz',old_dir/'summary.json']}
                    write(folder/'input_binding.json',binding)
                    for variant,f in [('original',old),('capped',result)]:
                        summaries.append({'dataset':dataset,'seed':seed,'price':price,'budget':budget,
                            'method':method,'variant':variant,**summarize(f)})
                    assert all(sha(p)==d for p,d in binding.items())
                    write(folder/'completion.json',{'status':'completed','seconds':time.time()-tick,
                        'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}})
                    receipts.append({'path':str(budget_rel/method),'sha256':sha(folder/'completion.json')})
                print(f'COMPLETED CAPPED RESPONSE {budget_rel}: four methods',flush=True)
                pd.DataFrame(summaries).to_csv(out/'summary.csv',index=False)
    assert len(receipts)==432 and all(sha(p)==d for p,d in inputs.items())
    write(out/'completion.json',{'status':'completed','cells':len(receipts),'listing_outcomes':432000,
        'seconds':time.time()-start_time,'case_receipts':receipts,'independent_audit':'pending',
        'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()}})

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('run','audit','output'):p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
