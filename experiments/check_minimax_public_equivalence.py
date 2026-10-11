"""Trained-model public adapter check; bounded cohort, not performance evidence."""
import argparse,json,hashlib
from fractions import Fraction as F
from itertools import accumulate
from pathlib import Path
import joblib,numpy as np,torch
from run_all import load_source
from savval import FEATURES,ACTIONS,price_features
from benchmark_public_pipeline import environment_replay
from minimax_public_pipeline import public_pipeline
from minimax_market import MinimaxMarket
from public_minimax_allocation import draw

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(out):
    assert not out.exists();out.mkdir(parents=True)
    root=Path('outputs/nested-development-v2');manifest=json.loads((root/'run_manifest.json').read_text())
    rows=[];bindings={};boundary_disagreements=0;torch.set_num_threads(2)
    for dataset in manifest['config']['datasets']:
        _,_,evaluation,_=load_source(dataset,manifest['config'])
        source=price_features(evaluation.iloc[:100].reset_index(drop=True),FEATURES[dataset])
        path=root/dataset/'seed-13/deployment_models/robust_no_feedback.joblib';bindings[str(path)]=sha(path)
        model,head,_=joblib.load(path);pred,x,valid=model.predict(source)
        rng=np.random.default_rng(20261008)
        profiles=[np.zeros(len(source),int),np.array([rng.choice(np.flatnonzero(v)) for v in valid])]
        for kind in ('suppression','benefit','risk'):
            scores=head.score(x,pred,model.space,kind,reported_missing=model.space.reported_missing(source))
            market=MinimaxMarket(pred,scores,valid,model.space,10)
            for profile,states in enumerate(profiles):
                public=source.copy()
                for a,field in enumerate(ACTIONS):public.loc[model.space.masks[states,a],field]=np.nan
                expected=market.expected_execution(states)
                for u in (.0,.137,.731,np.nextafter(1.,0.)):
                    actual=public_pipeline(model,head,public,.1,u,kind,environment_replay(source))
                    assert np.allclose(actual['pre_quote_log'],expected['pre_quotes'],atol=2e-6,rtol=0)
                    assert np.allclose(actual['probabilities'],expected['probabilities'],atol=1e-7,rtol=0)
                    reference_action=draw(expected,u)
                    action=actual['actions']
                    mismatch=not np.array_equal(action,reference_action)
                    if mismatch:
                        # Tiny inference differences can move an exact draw boundary.
                        # Verify and report this, rather than asserting bitwise identity.
                        left=np.cumsum(expected['probabilities']);right=np.cumsum(actual['probabilities'])
                        exact_left=list(accumulate(F(float(v)) for v in expected['probabilities']))
                        exact_right=list(accumulate(F(float(v)) for v in actual['probabilities']))
                        crossings=[min(a,c)<=F(float(u))+k<=max(a,c) for a,c in zip(exact_left,exact_right) for k in range(10)]
                        if not (any(crossings) and np.max(abs(left-right))<1e-5):
                            detail={'dataset':dataset,'kind':kind,'profile':profile,'u':float(u),'action_differences':np.flatnonzero(action!=reference_action).tolist(),'field_differences':np.flatnonzero(actual['fields']!=expected['fields']).tolist(),'max_cumulative_difference':float(np.max(abs(left-right))),'actual_probabilities':actual['probabilities'].tolist(),'expected_probabilities':expected['probabilities'].tolist()}
                            (out/'failure_diagnostic.json').write_text(json.dumps(detail,indent=2));raise AssertionError('Unexplained allocation difference')
                        boundary_disagreements+=1
                    selected=action>=0;final=states.copy();final[selected]=model.space.query_next[states[selected],action[selected]]
                    assert np.allclose(actual['final_quote_log'],pred[np.arange(len(source)),final],atol=2e-6,rtol=0)
                    success=np.zeros(len(source),bool);success[selected]=model.space.masks[states[selected],action[selected]]
                    assert np.array_equal(success,actual['query_succeeded'])
                    rows.append({'dataset':dataset,'kind':kind,'profile':profile,'uniform':float(u),'queries':int(selected.sum()),'boundary_action_disagreement':mismatch})
        print(dataset,flush=True)
    assert all(sha(Path(p))==v for p,v in bindings.items())
    (out/'cases.json').write_text(json.dumps(rows,indent=2)+'\n')
    sources=[Path(__file__),Path('experiments/minimax_market.py'),Path('experiments/minimax_public_pipeline.py'),Path('experiments/public_minimax_allocation.py')]
    for p in sources:(out/p.name).write_bytes(p.read_bytes())
    receipt={'status':'completed','cases':len(rows),'boundary_action_disagreements':boundary_disagreements,'sources':3,'seed':13,'unique_listings_per_source':100,'model_hashes':bindings,
             'source_hashes':{str(p):sha(p) for p in sources},'scope':'robust saved model; truthful and one random valid profile; three score rules and four draws; marginal equivalence within tolerance, boundary action differences retained; realized public actions replayed independently; no performance/response convergence claim'}
    (out/'completion.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
