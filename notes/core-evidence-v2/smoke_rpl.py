from pathlib import Path
import sys,copy,json
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'experiments'))
import numpy as np,joblib,torch
from threadpoolctl import threadpool_limits
import run_rpl_ten_seed_v2 as r
from run_all import load_source,rank_subset,evaluate_method
from run_crossfit import inner_split
from savval import FEATURES,price_features

def main():
    m=r.guard();cfg=copy.deepcopy(m['config']);cfg.update(residual_epochs=4,head_trees=12)
    e,g,evaluation,_=load_source('synthetic',cfg)
    train=rank_subset(__import__('pandas').concat([e,g],ignore_index=True),len(e)+len(g),'sav-val-cf-training-order-v2')
    est,guide=inner_split(train,cfg['head_fitting_fraction']);old=r.parent('synthetic',101)/'deployment_fit'
    base=r.c.stage_check(old,est,guide,101);model,_,_=joblib.load(base)
    a=model.predict(price_features(evaluation,FEATURES['synthetic']))[0]
    model.backbone=r.BoundedPredictor(model.backbone)
    assert np.array_equal(a,model.predict(price_features(evaluation,FEATURES['synthetic']))[0])
    checks={}
    for name in ['path-0-gap-0.5','path-0.5-gap-0.5']:
        v=r.variants()[name];cc=dict(cfg,recovery_path_weight=v['path_weight'])
        folder=ROOT/'outputs/core-evidence-smoke-v2'/name
        p=r.fit_stage(est,guide,FEATURES['synthetic'],cc,101,folder,old,v)
        fitted,head,_=joblib.load(p)
        pred,x,valid=fitted.predict(price_features(evaluation,FEATURES['synthetic']))
        error=None
        if v['path_weight']==0:
            reference,_,_=joblib.load(base)
            for i in range(2):reference.train_residual(price_features(est,FEATURES['synthetic']),est.target_log.to_numpy(),cc,101+i,None,gap_weight=.5,epochs=2)
            error=float(abs(pred-reference.predict(price_features(evaluation,FEATURES['synthetic']))[0]).max());assert error<1e-7
        scores=head.score(x,pred,fitted.space,'suppression',reported_missing=fitted.space.reported_missing(evaluation))
        tiny=evaluation.iloc[:100];rows,s=evaluate_method(name,fitted,head,'suppression',tiny,FEATURES['synthetic'],cc,101,.1)
        r.c.matrix_audit(pred[:100],scores[:100],valid[:100],tiny,rows,.1)
        before=r.c.sha(p);r.fit_stage(est,guide,FEATURES['synthetic'],cc,101,folder,old,v);assert before==r.c.sha(p)
        checks[name]=dict(zero_weight_identity_max_error=error,checkpoint_reused_exactly=True,outcome_check=True)
    r.c.write(ROOT/'notes/core-evidence-v2/rpl-smoke.json',dict(status='passed',full_original_training_partitions=True,smoke_epochs=4,formal_epochs=12,base_thread_prediction_identity=True,branches=checks,scope='engineering only; no performance claim'))
    print('PASS',checks)
if __name__=='__main__':
    torch.set_num_threads(2)
    with threadpool_limits(limits=2):main()
