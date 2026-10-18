"""Recompute ten-seed geometry, quote shifts and fixed-report decompositions.
No fitting, no search reruns, no publication of listing-level outputs.
"""
from pathlib import Path
import hashlib,json,sys,gc
import numpy as np
import pandas as pd
import torch,joblib
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments'))
import run_rpl_ten_seed_v2  # Required for saved BoundedPredictor objects.
import run_completion_ablation_v6 as c
from run_all import load_source
from savval import FEATURES,price_features,allocate,ACTIONS
OUT=Path(__file__).parent/'mechanisms'
REF=ROOT/'outputs/rpl-ten-seed-v2'
SEEDS=[13,42,2026,101,211,307,401,503,601,701]

class OneThread:
    def __init__(self,base):self.base=base
    def predict(self,*a,**kw):kw['thread_count']=1;return self.base.predict(*a,**kw)

def rows(source,seed,weight,budget):
    cell=REF/source/f'seed-{seed}'/f'path-{weight:g}-gap-0.5'/f'evaluation-{round(budget*10000):04d}'
    receipt=json.loads((cell/'completion.json').read_text())
    if 'reused' in receipt:
        origin=receipt['reused'];assert origin['type']=='ablation'
        cell=ROOT/origin['root']/'evaluation'/origin['method']/f'budget-{round(budget*10000):04d}'
        original=json.loads((cell/'completion.json').read_text())
    else:original=receipt
    file=cell/'outcomes.csv.gz';assert c.sha(file)==original['outcomes_sha256']
    return pd.read_csv(file),receipt,dict(path=str(file.relative_to(ROOT)),sha256=c.sha(file))

def model_path(source,seed,w):
    if w==0 and seed in [13,42,2026]:
        return ROOT/'outputs/completion-ablation-v6'/source/f'seed-{seed}'/'deployment_models/off_gap.joblib'
    return REF/source/f'seed-{seed}'/f'path-{w:g}-gap-0.5'/'deployment_model.joblib'

def geometry(pred,valid,space):
    mask=valid[:,:,None]&space.masks[None,:,:]
    gain=np.maximum(pred-pred[:,[0]],0)
    delta=pred[:,space.query_next]-pred[:,:,None]
    inc=gain[:,space.query_next]-gain[:,:,None]
    values=inc[mask];positive=np.maximum(values,0)
    terminal=mask&(space.query_next[None,:,:]==0)
    assert not (inc[terminal]>0).any()
    out=dict(edges=int(mask.sum()),raw_quote_raising_rate=float((delta[mask]>1e-8).mean()),
       gain_violating_rate=float((values>1e-8).mean()),positive_increment_mean=float(positive.mean()),
       positive_increment_max=float(positive.max()),terminal_edges=int(terminal.sum()),terminal_violations=0)
    for q in [.5,.9,.95,.99]:out[f'increment_q{round(100*q)}']=float(np.quantile(positive,q))
    return out

def decomposition(pred,scores,states,space,mode):
    n=len(states);ix=np.arange(n);q0=pred[ix,states];honest=pred[:,0]
    chosen=scores[ix,states].argmax(1);merit=scores[ix,states,chosen]
    next_state=space.query_next[states,chosen]
    qrelaxed=np.where(np.isfinite(merit)&(merit>0),pred[ix,next_state],q0)
    qa=np.empty(n)
    for start in range(0,n,100):
        end=min(start+100,n);ss=states[start:end]
        final,_,_=allocate(scores[start:end],ss,space,int(.1*(end-start)))
        qa[start:end]=pred[np.arange(start,end),final]
    E=q0-honest;R=qrelaxed-q0;C=qa-qrelaxed;G=qa-honest
    assert np.allclose(E+R+C,G,atol=1e-12,rtol=0)
    return dict(report_mode=mode,E=float(E.mean()),R=float(R.mean()),C=float(C.mean()),
                G=float(G.mean()),positive_G=float(np.maximum(G,0).mean()))

def main():
    OUT.mkdir(exist_ok=True);torch.set_num_threads(1)
    cfg=json.loads((REF/'manifest.json').read_text())['config']
    edges=[];decomp=[];batches=[];bindings=[]
    with threadpool_limits(limits=1):
        for source in ['synthetic','jucars','mucars']:
            _,_,evaluation,_=load_source(source,cfg)
            for seed in SEEDS:
                baseline,_,_=rows(source,seed,0,.1)
                for w in [0.,1.]:
                    mp=model_path(source,seed,w);model,head,_=joblib.load(mp)
                    original=model.backbone
                    if isinstance(original,run_rpl_ten_seed_v2.BoundedPredictor):original=original.model
                    model.backbone=OneThread(original);head.model.n_jobs=1
                    raw,x,valid=model.predict(price_features(evaluation,FEATURES[source]));pred=raw.astype(float)
                    edge=geometry(pred,valid,model.space)
                    edges.append(dict(source=source,seed=seed,path_weight=w,**edge))
                    scores=head.score(x,raw,model.space,'suppression',reported_missing=model.space.reported_missing(evaluation))
                    mainrows,receipt,_=rows(source,seed,w,.1)
                    assert receipt['inputs']['model']==c.sha(mp)
                    assert receipt['inputs']['evaluation']==c.content(evaluation)
                    assert mainrows.listing_id.tolist()==evaluation.listing_id.tolist()
                    assert np.allclose(pred[:,0],mainrows.clean_prediction_log,atol=1e-12,rtol=0)
                    assert np.allclose(pred[np.arange(len(pred)),mainrows.final_state],mainrows.attacked_prediction_log,atol=1e-12,rtol=0)
                    for mode,states in [('own_response',mainrows.state.to_numpy(int)),('fixed_lambda0_response',baseline.state.to_numpy(int))]:
                        decomp.append(dict(source=source,seed=seed,path_weight=w,
                            **decomposition(pred,scores,states,model.space,mode)))
                    for budget in [0.,.1,.3]:
                        frame,receipt,binding=rows(source,seed,w,budget)
                        assert frame.listing_id.tolist()==evaluation.listing_id.tolist()
                        bindings.append(dict(source=source,seed=seed,path_weight=w,budget=budget,
                           model_path=str(mp.relative_to(ROOT)),model_sha256=c.sha(mp),**binding))
                        for batch,g in frame.groupby('batch',sort=True):
                            attempted=(g.action>=0);failed=attempted&~g.query_succeeded
                            batches.append(dict(source=source,seed=seed,path_weight=w,budget=budget,batch=batch,
                              inflation=float(g.positive_log_inflation.mean()),
                              envelope=float(g.unilateral_inflation_envelope_log.mean()),
                              honest_quote=float(g.clean_prediction_log.mean()),attacked_quote=float(g.attacked_prediction_log.mean()),
                              honest_bias=float(g.clean_signed_log_error.mean()),attacked_bias=float(g.attack_signed_log_error.mean()),
                              honest_mae=float(g.clean_absolute_error.mean()),attacked_mae=float(g.attack_absolute_error.mean()),
                              actual_query_rate=float(attempted.mean()),failed_per_listing=float(failed.mean()),
                              failed_per_attempt=float(failed.sum()/attempted.sum()) if attempted.any() else 0.,
                              nonconverged=bool((~g.batch_converged).any()),regret_max=float(g.best_response_regret_log.max())))
                    del model,head,pred,raw,x,valid,scores;gc.collect()
                pd.DataFrame(edges).to_csv(OUT/'edge-60-models.csv',index=False)
                print('MECHANISM',source,seed,len(edges),flush=True)
    pd.DataFrame(decomp).to_csv(OUT/'fixed-report-and-own-decomposition.csv',index=False)
    b=pd.DataFrame(batches);b.to_csv(OUT/'batch-1800-aggregates.csv',index=False)
    e=pd.DataFrame(edges);e.groupby(['source','path_weight']).mean(numeric_only=True).drop(columns='seed').to_csv(OUT/'edge-source-means.csv')
    pd.DataFrame(decomp).groupby(['source','path_weight','report_mode']).mean(numeric_only=True).drop(columns='seed').to_csv(OUT/'decomposition-source-means.csv')
    b.groupby(['source','path_weight','budget']).mean(numeric_only=True).drop(columns=['seed','batch']).to_csv(OUT/'quote-and-query-source-means.csv')
    rng=np.random.default_rng(20261018);contrasts=[]
    for source in ['synthetic','jucars','mucars']:
        def matrix(w,budget,key):
            q=b[(b.source==source)&(b.path_weight==w)&(b.budget==budget)]
            return q.pivot(index='seed',columns='batch',values=key).reindex(SEEDS).to_numpy()
        # Crossed resampling preserves lambda/budget pairing and common batches.
        seed_indices=rng.integers(0,10,(5000,10));batch_indices=rng.integers(0,10,(5000,10))
        d0=matrix(0,0,'inflation')-matrix(1,0,'inflation')
        d1=matrix(0,.1,'inflation')-matrix(1,.1,'inflation')
        for name,values in [('zero_query_improvement',d0),('capacity_10_improvement',d1),('budget_interaction',d1-d0),
          ('honest_bias_change',matrix(1,.1,'honest_bias')-matrix(0,.1,'honest_bias')),
          ('attacked_bias_change',matrix(1,.1,'attacked_bias')-matrix(0,.1,'attacked_bias')),
          ('envelope_improvement',matrix(0,.1,'envelope')-matrix(1,.1,'envelope'))]:
            bootstrap=values[seed_indices[:,:,None],batch_indices[:,None,:]].mean((1,2))
            lo,hi=np.quantile(bootstrap,[.025,.975])
            contrasts.append(dict(source=source,contrast=name,mean=float(values.mean()),low=float(lo),high=float(hi),
                 scope='posthoc marginal percentile crossed-bootstrap; fixed population; no simultaneous coverage'))
    pd.DataFrame(contrasts).to_csv(OUT/'paired-contrasts.csv',index=False)
    c.write(OUT/'verification.json',dict(status='completed_model_and_outcome_bound',models=60,outcome_cells=180,batch_rows=1800,
      model_geometry_rows=len(edges),terminal_edge_violations=0,source_sha256=c.sha(Path(__file__)),
      binding=bindings,source_summary_sha256=c.sha(REF/'summary.csv'),
      scope='new descriptive diagnostics and fixed-report algebra, no new fit or best-response search; conditional retrospective intervals'))

if __name__=='__main__':main()
