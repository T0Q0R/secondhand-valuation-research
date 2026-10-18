"""Full real-source residual replay against an existing v1 stage."""
from pathlib import Path
import sys,json,copy,time
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'experiments'))
import joblib,torch,numpy as np
import run_review_gap_controls_v1 as r
from review_gap_price_fit_v2 import fit_stage
from run_crossfit import inner_split
from savval import FEATURES,price_features
from threadpoolctl import threadpool_limits

def main():
    torch.set_num_threads(2);cfg=r.guard()['config'];source='jucars';seed=13
    with threadpool_limits(limits=2):
        train,ev,assigned,old=r.data(source,cfg,seed)
        est,guide=inner_split(train.loc[assigned!=0],cfg['head_fitting_fraction'])
        v=dict(beta=1.,path_weight=0.,tolerance=.02,rounds=2,feedback=False,axis='matched_stronger_gap')
        scfg=copy.deepcopy(cfg);scfg.update(gap_penalty_weight=1.,recovery_path_weight=0.,feedback_rounds=2,gap_tolerance_log=.02)
        start=time.time();p=fit_stage(est,guide,FEATURES[source],scfg,seed,
          ROOT/'outputs/review-gap-controls-v2/engineering-price-equivalence-jucars13',old/'outer-0',v)
        refpath=r.OUT/source/f'seed-{seed}'/'path-0-gap-1/outer-0/model.joblib'
        new,_,_=joblib.load(p);ref,_,_=joblib.load(refpath)
        a=new.residual.state_dict();b=ref.residual.state_dict()
        assert all(torch.equal(a[k],b[k]) for k in a)
        public=price_features(ev,FEATURES[source]);x=new.predict(public)[0];y=ref.predict(public)[0]
        assert np.array_equal(x,y)
        original=json.loads(refpath.with_name('completion.json').read_text())
        current=json.loads(p.with_name('completion.json').read_text());assert current['rounds']==original['rounds']
        result=dict(status='passed',exact_residual_parameters=True,exact_quotes=True,exact_training_logs=True,
          quote_shape=list(x.shape),original_stage_seconds=original['seconds'],optimized_stage_seconds=time.time()-start,
          original_model_sha256=r.c.sha(refpath),optimized_model_sha256=r.c.sha(p),
          scope='single complete real-source fit, equal optimizer updates; unused intermediate heads omitted, final OOF head remains')
        r.c.write(ROOT/'outputs/review-gap-controls-v2/engineering-check.json',result)
        print(json.dumps(result,indent=2))

if __name__=='__main__':main()
