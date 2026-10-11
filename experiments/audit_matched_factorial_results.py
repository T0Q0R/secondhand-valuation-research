"""Independent final-profile allocation, replay and metric audit for factorial runs."""
from pathlib import Path
import argparse,json,hashlib,fcntl,os
import numpy as np,pandas as pd,joblib,torch
from audit_minimax_response import replay
from run_all import load_source
from savval import FEATURES,price_features

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check_convergence(frame,regrets):
    assert frame.converged.nunique()==1, 'Mixed convergence flags in a batch'
    expected=bool((np.asarray(regrets)<1e-7).all())
    assert bool(frame.converged.iloc[0])==expected, 'Convergence flag disagrees with recomputed regret'

def write_atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(value,indent=2)+'\n');os.replace(tmp,path)

def main(run,out):
    run=run.resolve();out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    lock=(out/'execution.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    torch.set_num_threads(2)
    manifest=json.loads((run/'manifest.json').read_text());config=manifest['config'];parent=json.loads((run/'completion.json').read_text());initial=sha(run/'completion.json')
    summary=pd.read_csv(run/'summary.csv');assert sha(run/'summary.csv')==parent['summary_sha256']
    checker_files=[Path(__file__),Path(__file__).with_name('audit_minimax_response.py')]
    checker_files.extend(Path(__file__).with_name(name) for name in manifest['source_hashes'])
    checker_hashes={str(p.resolve()):sha(p) for p in checker_files}
    audit_inputs={'run':str(run),'parent_completion_sha256':initial,
                  'manifest_sha256':sha(run/'manifest.json'),
                  'summary_sha256':sha(run/'summary.csv'),'checker_hashes':checker_hashes}
    if (out/'inputs.json').exists():assert json.loads((out/'inputs.json').read_text())==audit_inputs,'Audit inputs changed'
    else:write_atomic(out/'inputs.json',audit_inputs)
    inputs_digest=sha(out/'inputs.json')
    rows=deviations=cell_count=0;cache_key=None;source_key=None;cell_bindings={}
    manifest_digest=sha(run/'manifest.json')
    files=sorted(run.glob('*/seed-*/evaluation/budget-*/*/*/*/*/completion.json'))
    expected_cells=len(config['datasets'])*len(config['seeds'])*len(config['budgets'])*24
    assert len(files)==len(summary)==expected_cells==parent['method_cells']
    for cp in files:
        cell_bindings[str(cp.resolve())]=sha(cp)
        cell=cp.parent;dataset,seed_name,_,budget_name,initial_objective,score,feedback,allocation=cell.relative_to(run).parts
        seed=int(seed_name.split('-')[1]);budget=int(budget_name.split('-')[1])/10000
        receipt=json.loads(cp.read_text());assert sha(cell/'summary.json')==receipt['summary_sha256'] and sha(cell/'inputs.json')==receipt['inputs_sha256']
        inputs=json.loads((cell/'inputs.json').read_text());assert inputs['allocation']==allocation and inputs['budget']==budget
        pair=run/dataset/seed_name;mapping=json.loads((pair/'fit/cell_mapping.json').read_text());key=[initial_objective,score,feedback,allocation];fit_id=next(x['fit_id'] for x in mapping if x['cell']==key)
        model_path=pair/'fit/deployment_models'/(fit_id+'.joblib');assert sha(model_path)==inputs['model_sha256']
        if source_key!=dataset:
            _,_,evaluation,_=load_source(dataset,config);source=price_features(evaluation,FEATURES[dataset]);source_key=dataset
        if cache_key!=(dataset,seed,fit_id):
            model,head=joblib.load(model_path);pred,encoded,valid=model.predict(source);score_cache={};cache_key=(dataset,seed,fit_id)
        if score not in score_cache:score_cache[score]=head.score(encoded,pred,model.space,score,reported_missing=model.space.reported_missing(evaluation))
        frames=[]
        for name,h in sorted(receipt['batch_receipts'].items()):
            path=cell/name;assert sha(path)==h;done=json.loads(path.read_text());folder=path.parent
            assert sha(folder/'arrays.npz')==done['arrays_sha256'] and sha(folder/'outcomes.csv.gz')==done['outcomes_sha256']
            z=np.load(folder/'arrays.npz');f=pd.read_csv(folder/'outcomes.csv.gz');batch=int(folder.name.split('-')[1]);start=batch*config['batch_size'];end=start+len(f);n=len(f)
            assert f.listing_id.astype(str).tolist()==evaluation.listing_id.iloc[start:end].astype(str).tolist()
            assert np.allclose(f.target_log,evaluation.target_log.iloc[start:end],atol=1e-12,rtol=0)
            assert np.allclose(z['pred'],pred[start:end],atol=2e-6,rtol=0) and np.array_equal(z['valid'],valid[start:end])
            expected_scores=score_cache[score][start:end];finite=np.isfinite(expected_scores)
            assert np.array_equal(np.isfinite(z['scores']),finite) and np.allclose(z['scores'][finite],expected_scores[finite],atol=1e-7,rtol=1e-8)
            checkpoint=out/'batch_checks'/cell.relative_to(run)/folder.name/'checked.json'
            binding={'inputs_sha256':inputs_digest,'batch_receipt_sha256':h,
                     'arrays_sha256':done['arrays_sha256'],'outcomes_sha256':done['outcomes_sha256'],
                     'model_sha256':inputs['model_sha256'],'cell_completion_sha256':sha(cp)}
            if checkpoint.exists():
                prior=json.loads(checkpoint.read_text())
                assert prior['binding']==binding and prior['status']=='completed','Batch checkpoint mismatch'
                assert prior['outcome_rows']==n
                batch_deviations=int(np.count_nonzero(z['valid']))
                assert prior['legal_unilateral_deviations']==batch_deviations
            else:
                batch_deviations=0
                b=int(np.floor(budget*n));assert b==done['capacity'];states=z['states'];space=model.space
                fields,p,q0,q1,q=replay(z['pred'],z['scores'],states,b,allocation,space)
                assert np.allclose(p,z['probabilities'],atol=1e-10,rtol=0)
                assert np.array_equal(fields[p>0],z['fields'][p>0]);assert p.sum()<=b+1e-10
                clean=z['pred'][:,0];y=f.target_log.to_numpy();yc=np.expm1(y);success=np.zeros(n,bool);selected=fields>=0;success[selected]=space.masks[states[selected],fields[selected]]
                metrics={'query_probability':p,'failed_query_probability':p*(~success),'expected_quote_log':q,'honest_absolute_error':abs(np.expm1(clean)-yc),'expected_attacked_absolute_error':(1-p)*abs(np.expm1(q0)-yc)+p*abs(np.expm1(q1)-yc),'positive_expected_log_inflation':np.maximum(q-clean,0),'expected_realized_positive_log_inflation':(1-p)*np.maximum(q0-clean,0)+p*np.maximum(q1-clean,0),'expected_signed_log_error':q-y,'expected_squared_log_error':(1-p)*(q0-y)**2+p*(q1-y)**2}
                for col,v in metrics.items():assert np.allclose(f[col],v,atol=1e-7,rtol=1e-10),col
                cost=config['concealment_cost_log']*space.masks.sum(axis=1)
                independently_recomputed_regrets=[]
                for i in range(n):
                    vals={}
                    for h in np.flatnonzero(z['valid'][i]):
                        changed=states.copy();changed[i]=h;vals[h]=replay(z['pred'],z['scores'],changed,b,allocation,space)[-1][i]-cost[h];batch_deviations+=1
                    actual_regret=max(0,max(vals.values())-(q[i]-cost[states[i]]))
                    independently_recomputed_regrets.append(actual_regret)
                    assert abs(f.regret.iloc[i]-actual_regret)<1e-8
                    assert abs(f.deviation_envelope.iloc[i]-max(0,max(vals.values())-vals[0]))<1e-8
                check_convergence(f,independently_recomputed_regrets)
                write_atomic(checkpoint,{'status':'completed','binding':binding,
                                        'outcome_rows':n,'legal_unilateral_deviations':batch_deviations})
            deviations+=batch_deviations
            frames.append(f);rows+=n
        data=pd.concat(frames);assert len(data)==len(evaluation)
        saved=json.loads((cell/'summary.json').read_text());match=summary
        for col,value in [('dataset',dataset),('seed',seed),('initial_objective',initial_objective),('score',score),('feedback',feedback),('allocation',allocation),('budget',budget)]:match=match[match[col]==value]
        assert len(match)==1
        for col in ['honest_absolute_error','expected_attacked_absolute_error','positive_expected_log_inflation','failed_query_probability','expected_signed_log_error','deviation_envelope']:
            assert np.isclose(saved[col],data[col].mean(),atol=1e-7,rtol=1e-10)
            assert np.isclose(match.iloc[0][col],saved[col],atol=1e-7,rtol=1e-10)
        assert saved['n']==len(data) and int(match.iloc[0]['n'])==len(data)
        for col,value in [('max_regret',float(data.regret.max())),
                          ('nonconverged_batches',int((~data.groupby('batch').converged.first()).sum()))]:
            assert np.isclose(saved[col],value,atol=1e-10,rtol=0), col
            assert np.isclose(match.iloc[0][col],value,atol=1e-10,rtol=0), col
        cell_count+=1
        print(f'CELL VERIFIED {cell_count}/{expected_cells} {cell.relative_to(run)}',flush=True)
    assert sha(run/'completion.json')==initial and sha(run/'manifest.json')==manifest_digest
    assert all(sha(Path(p))==h for p,h in cell_bindings.items())
    assert sha(out/'inputs.json')==inputs_digest
    assert all(sha(Path(p))==h for p,h in checker_hashes.items())
    result={'status':'completed','execution_smoke':config.get('execution_smoke',False),'method_cells':cell_count,'outcome_rows':rows,'legal_unilateral_deviations':deviations,'parent_completion_sha256':initial,'manifest_sha256':manifest_digest,'cell_completion_hashes':cell_bindings,'audit_inputs_sha256':inputs_digest,'checker_hashes':checker_hashes,'scope':'model/source-bound final-profile allocation, expected errors, all legal unilateral quotes and summary reconstruction; nested fit receipts audited separately'}
    (out/'checker_snapshot.py').write_bytes(Path(__file__).read_bytes());write_atomic(out/'completion.json',result);print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.run,a.output)
