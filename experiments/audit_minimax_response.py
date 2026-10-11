"""Read-only independent full-sort/rational replay and outcome arithmetic."""
import argparse,json,hashlib
from fractions import Fraction as F
from pathlib import Path
import numpy as np,pandas as pd
import joblib,torch
from run_all import load_source
from savval import FEATURES,price_features
from savval import StateSpace

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def allocation(scores,states,b,kind):
    n=len(states);fields=[];g=[]
    for i,s in enumerate(states):
        opts=[(float(v),a) for a,v in enumerate(scores[i,s]) if np.isfinite(v) and v>0]
        value=max([0.]+[v for v,a in opts]);field=min([a for v,a in opts if v==value],default=-1)
        fields.append(field);g.append(F(value))
    if kind=='top_b':
        chosen=sorted([i for i in range(n) if g[i]>0],key=lambda i:(-g[i],i))[:b]
        p=[F(int(i in chosen)) for i in range(n)]
    else:
        pos=sorted([v for v in g if v],reverse=True)
        if b==0:p=[F(0)]*n
        elif len(pos)<=b:p=[F(int(v>0)) for v in g]
        else:
            for k in range(b+1,len(pos)+1):
                t=F(k-b)/sum((1/v for v in pos[:k]),F(0))
                if (pos[k] if k<len(pos) else 0)<=t<=pos[k-1]:break
            else:raise AssertionError('Threshold missing')
            p=[max(F(0),1-t/v) if v else F(0) for v in g]
    return np.array(fields),np.array([float(v) for v in p])

def replay(pred,scores,states,b,kind,space):
    fields,p=allocation(scores,states,b,kind);final=states.copy();selected=fields>=0
    final[selected]=space.query_next[states[selected],fields[selected]]
    before=pred[np.arange(len(states)),states];after=pred[np.arange(len(states)),final]
    return fields,p,before,after,before+p*(after-before)

def main(run,out):
    assert not out.exists();out.mkdir(parents=True)
    parent=json.loads((run/'completion.json').read_text());space=StateSpace.build(2)
    manifest=json.loads((run/'manifest.json').read_text());config=json.loads(Path('outputs/nested-development-v2/run_manifest.json').read_text())['config'];cost=config['concealment_cost_log']*space.masks.sum(axis=1)
    parent_root=Path('outputs/nested-development-v2')
    assert sha(parent_root/'run_manifest.json')==manifest['parent_manifest']
    for name,expected_hash in manifest['source_hashes'].items():
        assert sha(run/'source_snapshot'/Path(name).name)==expected_hash
    expected_cells={(dataset,seed,price,score,kind) for dataset in manifest['datasets'] for seed in manifest['seeds'] for price in manifest['prices'] for score in ('suppression','benefit','risk') for kind in ('top_b','minimax')}
    recorded={};model_cache=None;dataset_cache=None;model_bindings={};torch.set_num_threads(2)
    cells=rows=deviations=0;bindings={} 
    for cp in sorted(run.glob('*/seed-*/*/*/*/batch-*/completion.json')):
        d=cp.parent;done=json.loads(cp.read_text());kind=d.parent.name;z=np.load(d/'execution.npz');frame=pd.read_csv(d/'outcomes.csv.gz');n=len(frame)
        assert sha(d/'outcomes.csv.gz')==done['outcomes_sha256'] and sha(d/'execution.npz')==done['execution_sha256']
        dataset,seed_name,price,score,alloc,batch_name=d.relative_to(run).parts
        seed=int(seed_name.split('-')[1]);batch=int(batch_name.split('-')[1]);key=(dataset,seed,price,score,alloc)
        assert key in expected_cells
        if dataset_cache!=dataset:
            _,_,evaluation,_=load_source(dataset,config)
            if manifest['smoke']:evaluation=evaluation.iloc[:20].copy()
            public_source=price_features(evaluation,FEATURES[dataset]);dataset_cache=dataset
        expected_path=parent_root/dataset/seed_name/'deployment_models'/(manifest['prices'][price]+'.joblib')
        assert Path(done['model_path']).resolve()==expected_path.resolve()
        if model_cache!=(dataset,seed,price):
            model_bindings[str(expected_path)]=sha(expected_path)
            model,head,_=joblib.load(expected_path)
            full_pred,full_x,full_valid=model.predict(public_source)
            score_cache={};model_cache=(dataset,seed,price)
        assert model_bindings[str(expected_path)]==done['model_sha256']
        if score not in score_cache:
            score_cache[score]=head.score(full_x,full_pred,model.space,score,reported_missing=model.space.reported_missing(public_source))
        start=batch*100;stop=min(start+100,len(evaluation));expected=evaluation.iloc[start:stop]
        assert n==len(expected) and n>0 and done['capacity']==int(np.floor(.1*n))
        assert frame.listing_id.astype(str).tolist()==expected.listing_id.astype(str).tolist()
        assert np.allclose(frame.target_log,expected.target_log,atol=1e-12,rtol=0)
        assert np.array_equal(z['valid'],full_valid[start:stop])
        assert np.allclose(z['pred'],full_pred[start:stop],atol=2e-6,rtol=0)
        assert np.array_equal(np.isfinite(z['scores']),np.isfinite(score_cache[score][start:stop]))
        finite=np.isfinite(z['scores'])
        assert np.allclose(z['scores'][finite],score_cache[score][start:stop][finite],atol=1e-7,rtol=1e-8)
        recorded.setdefault(key,[]).append(frame)

        bindings[str(cp)]=sha(cp);states=z['states'];pred=z['pred'];scores=z['scores'];b=done['capacity']
        fields,p,q0,q1,q=replay(pred,scores,states,b,kind,space)
        assert np.allclose(z['probabilities'],p,atol=1e-10,rtol=0)
        has=p>0;assert np.array_equal(z['fields'][has],fields[has])
        assert np.allclose(q,frame.expected_quote_log,atol=1e-9,rtol=0)
        y=frame.target_log.to_numpy();clean=pred[:,0];yc=np.expm1(y)
        success=np.zeros(n,bool);eligible=fields>=0;success[eligible]=space.masks[states[eligible],fields[eligible]]
        expected={'query_probability':p,'failed_query_probability':p*(~success),'honest_absolute_error':abs(np.expm1(clean)-yc),'expected_attacked_absolute_error':(1-p)*abs(np.expm1(q0)-yc)+p*abs(np.expm1(q1)-yc),'positive_expected_log_inflation':np.maximum(q-clean,0),'expected_realized_positive_log_inflation':(1-p)*np.maximum(q0-clean,0)+p*np.maximum(q1-clean,0),'expected_squared_log_error':(1-p)*(q0-y)**2+p*(q1-y)**2,'expected_signed_log_error':q-y}
        for col,value in expected.items():assert np.allclose(frame[col],value,atol=1e-7,rtol=1e-10),col
        for i in range(n):
            vals={}
            for h in np.flatnonzero(z['valid'][i]):
                profile=states.copy();profile[i]=h
                vals[h]=replay(pred,scores,profile,b,kind,space)[-1][i]-cost[h];deviations+=1
            regret=max(0,max(vals.values())-(q[i]-cost[states[i]]));dev=max(0,max(vals.values())-vals[0])
            assert abs(frame.regret.iloc[i]-regret)<1e-8 and abs(frame.deviation_envelope.iloc[i]-dev)<1e-8
        assert p.sum()<=b+1e-10;cells+=1;rows+=n
    assert rows==parent['outcome_rows'] and all(sha(Path(p))==v for p,v in bindings.items())
    assert set(recorded)==expected_cells
    summary=pd.read_csv(run/'summary.csv');assert sha(run/'summary.csv')==parent['summary_sha256']
    assert len(summary)==len(expected_cells)==parent['cells']
    metric_cols=['honest_absolute_error','expected_attacked_absolute_error','positive_expected_log_inflation','expected_realized_positive_log_inflation','failed_query_probability','expected_signed_log_error','deviation_envelope']
    for key,frames in recorded.items():
        data=pd.concat(frames);assert len(data)==(20 if manifest['smoke'] else 1000)
        match=summary
        for name,value in zip(('dataset','seed','price','score','allocation'),key):match=match[match[name]==value]
        assert len(match)==1
        for col in metric_cols:assert np.isclose(match.iloc[0][col],data[col].mean(),atol=1e-7,rtol=1e-10)
        assert np.isclose(match.iloc[0].max_regret,data.regret.max(),atol=1e-9,rtol=0)
        assert int(match.iloc[0].nonconverged_batches)==int((~data.groupby('batch').converged.first()).sum())
    assert all(sha(Path(p))==v for p,v in model_bindings.items())

    (out/'checker_snapshot.py').write_bytes(Path(__file__).read_bytes())
    result={'status':'completed','smoke':parent['smoke'],'batch_cells':cells,'outcome_rows':rows,'legal_unilateral_deviations':deviations,'parent_completion_sha256':sha(run/'completion.json'),'batch_completion_hashes':bindings,'verified_model_hashes':model_bindings,'summaries_recomputed':len(expected_cells),'scope':'independent rational score allocation/full-sort top-B, all final unilateral deviations, replay and expected-error arithmetic; no global response optimality'}
    (out/'completion.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='batch_completion_hashes'}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.run,a.output)
