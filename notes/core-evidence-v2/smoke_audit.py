from pathlib import Path
import sys,json,subprocess,copy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'experiments'))
import numpy as np,pandas as pd,joblib,torch
from threadpoolctl import threadpool_limits
import core_evidence_audit_v2 as a
import analyze_core_evidence_v2 as analysis

def main():
    reports=[]
    for stage in ['rpl','mechanisms','sefa','gdfs','dime','efa','aco']:
        reports.append(a.audit_pair(stage,'synthetic',13,1))
    cfg=a.read(ROOT/'outputs/recovery-path-learning-v1/manifest.json')['config']
    e,g,ev,_=a.load_source('synthetic',cfg);train=a.rank(pd.concat([e,g],ignore_index=True),'sav-val-cf-training-order-v2')
    spec=a.resolve_model('rpl','synthetic',13,'path-1-gap-0.5')
    a.fit_audit(spec,'synthetic',13,cfg,train,ev)
    mp,_,_=a.paths(spec);model,head,_=joblib.load(mp);a.bounded(model)
    pred,x,valid=model.predict(a.price_features(ev,a.FEATURES['synthetic']))
    scores=a.independent_scores(head,x,pred,ev)
    cp=ROOT/'outputs/recovery-path-learning-v1/synthetic/seed-13/path-1-gap-0.5/evaluation-1000/completion.json'
    rows,_=a.row_file(cp);a.independent_outcomes(pred,scores,valid,ev,rows,.1)
    rejected=[]
    for field in ['attacked_prediction_log','best_response_regret_log','query_succeeded','final_state']:
        wrong=rows.copy()
        if field=='query_succeeded':wrong.loc[wrong.index[0],field]=not bool(wrong.iloc[0][field])
        else:wrong.loc[wrong.index[0],field]+=1
        try:a.independent_outcomes(pred,scores,valid,ev,wrong,.1)
        except AssertionError:rejected.append(field)
        else:raise RuntimeError('Accepted corrupted '+field)
    # Non-degenerate paired fixture exercises every bootstrap replicate and band.
    rng=np.random.default_rng(773);x=rng.normal(size=(4,3,10,6));si=rng.integers(3,size=(4000,3));bi=rng.integers(10,size=(4000,10))
    rep=analysis.bootstrap(x,si,bi);point,lo,hi,sd,q=analysis.intervals(x,rep)
    out=a.OUT/'analysis/smoke';out.mkdir(parents=True,exist_ok=True)
    keys=[dict(dataset='fixture',budget=.1,reference='ref',candidate=str(i)) for i in range(4)]
    table=[]
    for c,k in enumerate(keys):
        for j,m in enumerate(a.METRICS):table.append(dict(**k,metric=m,reference_minus_candidate=point[c,j],lower=lo[c,j],upper=hi[c,j],bootstrap_sd=sd[c,j],simultaneous_lower=point[c,j]-q*sd[c,j],simultaneous_upper=point[c,j]+q*sd[c,j]))
    # Strings with a prefix avoid CSV numeric type inference in key matching.
    for k in keys:k['candidate']='candidate-'+k['candidate']
    for row in table:row['candidate']='candidate-'+row['candidate']
    pd.DataFrame(table).to_csv(out/'paired_contrasts.csv',index=False)
    np.savez_compressed(out/'paired_tensors_and_draws.npz',differences=x,seed_draws=si,batch_draws=bi,bootstrap_replicates=rep)
    a.write(out/'contrast_keys.json',dict(keys=keys,metrics=a.METRICS,seed_ids=[13,42,2026]))
    a.write(out/'completion.json',dict(fitting_seeds=3,studentized_max_deviation_quantile=q,artifacts={p.name:a.sha(p) for p in out.iterdir() if p.is_file() and p.name!='completion.json'}))
    subprocess.run([sys.executable,str(ROOT/'experiments/check_core_statistics_v2.py'),'--stage','smoke'],check=True)
    a.write(ROOT/'notes/core-evidence-v2/audit-smoke.json',dict(status='passed',producer_families=reports,
        positive_RPL_head_refit=True,corrupted_columns_rejected=rejected,bootstrap_fixture_replicates=4000,
        statistics_check=a.read(a.OUT/'statistics-check/smoke/completion.json'),scope='engineering acceptance checks, not whole-study audit completion'))
    print('ALL_CORE_AUDIT_SMOKES_PASS',flush=True)

if __name__=='__main__':
    torch.set_num_threads(1)
    with threadpool_limits(limits=1):main()
