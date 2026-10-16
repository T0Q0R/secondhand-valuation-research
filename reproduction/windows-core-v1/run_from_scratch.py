"""Fresh fitting of the matched RPL lambda0/1 core on another machine.
No original model weights, OOF tensors or production result files are read.
Reference CSV is opened only after fitting and evaluation have completed.
"""
from pathlib import Path
import argparse,copy,hashlib,importlib.metadata,json,os,platform,sys,time
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='2'
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'experiments'))
import joblib,numpy as np,pandas as pd,torch
from threadpoolctl import threadpool_limits
from savval import FEATURES,StateSpace,ActionHeads,fit_backbone,price_features
from run_all import load_source,rank_subset,evaluate_method
from portable_split import fold_assignments,inner_split,verify_split_origin
from recovery_path_training_v1 import train_residual

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def content(f):return hashlib.sha256(f.to_csv(index=False,lineterminator="\n").encode("utf-8")).hexdigest()
def write(p,r):
    p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n');t.replace(p)
def dump(p,r):
    t=p.with_name(p.name+'.tmp');joblib.dump(r,t,compress=3);t.replace(p)
def head(model,frame,columns,cfg,seed,prediction=None):
    pred,x,valid=model.predict(price_features(frame,columns));h=ActionHeads(cfg['head_trees'],seed);h.model.n_jobs=2
    return h.fit(x,pred if prediction is None else prediction,valid,frame.target_log.to_numpy(),model.space,reported_missing=model.space.reported_missing(frame))
def fit(est,guide,columns,cfg,seed,weight,out):
    print('FIT_STAGE',out.parent.name,out.name,flush=True)
    out.mkdir(parents=True,exist_ok=True)
    inputs=dict(estimator=content(est),guidance=content(guide),seed=seed,path_weight=weight,config=cfg)
    cp=out/'completion.json';mp=out/'model.joblib'
    if cp.exists():
        r=json.loads(cp.read_text());assert r['inputs']==inputs and sha(mp)==r['model_sha256'];return joblib.load(mp)
    model=fit_backbone(price_features(est,columns),est.target_log.to_numpy(),StateSpace.build(2),cfg,seed,augment=True)
    current=head(model,guide,columns,cfg,seed);trace=[]
    for i in range(2):
        trace.append(train_residual(model,price_features(est,columns),est.target_log.to_numpy(),
                    dict(cfg,recovery_path_weight=weight),seed+i,None,gap_weight=.5,epochs=6))
        current=head(model,guide,columns,cfg,seed)
    dump(mp,(model,current,'suppression'));write(cp,dict(inputs=inputs,model_sha256=sha(mp),round_traces=trace))
    return model,current,'suppression'
def main():
    p=argparse.ArgumentParser();p.add_argument('--dataset',choices=['synthetic','jucars','mucars','all'],default='synthetic')
    p.add_argument('--seed',type=int,choices=[13],default=13);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--check-only',action='store_true');a=p.parse_args()
    here=Path(__file__).resolve().parent;contract=json.loads((here/'contract.json').read_text(encoding='utf-8'));cfg=contract['config']
    if sys.version_info[:2] != (3,12):raise RuntimeError('Use 64-bit Python 3.12 for this contract')
    if platform.architecture()[0] != '64bit':raise RuntimeError('64-bit Python is required')
    for package,version in contract['required_versions'].items():
        if importlib.metadata.version(package)!=version:raise RuntimeError(f'Dependency mismatch: {package} must be {version}')
    verify_split_origin(ROOT/'experiments/run_crossfit.py')
    for f,h in contract['scientific_source_sha256'].items():assert sha(ROOT/f)==h,f
    # An output folder must never alias original production evidence.
    out=a.output.resolve();assert not out.is_relative_to(ROOT)
    source_names=cfg['datasets'] if a.dataset=='all' else [a.dataset]
    inputs={};datasets={}
    for source in source_names:
        est,guide,ev,provenance=load_source(source,cfg)
        train=rank_subset(pd.concat([est,guide],ignore_index=True),len(est)+len(guide),'sav-val-cf-training-order-v2')
        assert not set(train.listing_id)&set(ev.listing_id)
        inputs[source]=dict(training=content(train),evaluation=content(ev),rows=len(train),evaluation_rows=len(ev))
        assert inputs[source]==contract['population_bindings'][source]
        datasets[source]=(train,ev)
    if a.check_only:print(json.dumps(dict(status='input_checks_passed_no_training',inputs=inputs),indent=2));return
    out.mkdir(parents=True,exist_ok=True);binding=dict(contract_sha256=sha(here/'contract.json'),runner_sha256=sha(Path(__file__)),inputs=inputs,seed=a.seed)
    cp=out/'inputs.json'
    if cp.exists():assert json.loads(cp.read_text())==binding
    else:write(cp,binding)
    write(out/'runtime-environment.json',dict(platform=platform.platform(),machine=platform.machine(),python=sys.version,torch_build=torch.__config__.show(),threads=2,contract_sha256=sha(here/'contract.json'),packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()}))
    started=time.time();all_results=[]
    for source,(train,ev) in datasets.items():
        assigned=fold_assignments(train,3);columns=FEATURES[source]
        for weight in [0.,1.]:
            folder=out/source/f'path-{weight:g}-gap-0.5';oof=np.empty((len(train),11))
            for fold in range(3):
                est,guide=inner_split(train.loc[assigned!=fold],cfg['head_fitting_fraction'])
                model,_,_=fit(est,guide,columns,cfg,a.seed,weight,folder/f'outer-{fold}')
                oof[assigned==fold]=model.predict(price_features(train.loc[assigned==fold],columns))[0]
            est,guide=inner_split(train,cfg['head_fitting_fraction'])
            model,_,kind=fit(est,guide,columns,cfg,a.seed,weight,folder/'deployment')
            hh=head(model,train,columns,cfg,a.seed,prediction=oof)
            for budget in [0.,.1,.3]:
                rows,s=evaluate_method(folder.name,model,hh,kind,ev,columns,cfg,a.seed,budget)
                rows.to_csv(folder/f'outcomes-{round(budget*10000):04d}.csv.gz',index=False)
                s.update(dataset=source);all_results.append(s)
                pd.DataFrame(all_results).to_csv(out/'summary.csv',index=False)
                print('EXTERNAL_CORE_CELL',source,weight,budget,flush=True)
    # Reference cannot influence fitting, selection or stopping.
    assert sha(here/'expected-core-values.csv')==contract['reference_summary_sha256']
    reference=pd.read_csv(here/'expected-core-values.csv');actual=pd.DataFrame(all_results)
    compared=actual.merge(reference,on=['dataset','seed','method','budget'],validate='one_to_one',suffixes=('_new','_reference'))
    assert len(compared)==len(actual);checks=[]
    for metric in contract['comparison_metrics']:
        diff=abs(compared[metric+'_new']-compared[metric+'_reference'])
        limit=contract['metric_atol']+contract['metric_rtol']*abs(compared[metric+'_reference'])
        checks.append(dict(metric=metric,passed=bool((diff<=limit).all()),maximum_absolute_difference=float(diff.max())))
    compared.to_csv(out/'reference-comparison.csv',index=False)
    write(out/'external-training-receipt.json',dict(status='computed_reference_comparison_passed' if all(c['passed'] for c in checks) else 'computed_reference_differences_require_review',
       elapsed_seconds=time.time()-started,platform=platform.platform(),python=sys.version,source_input_bindings=inputs,
       versions={m:importlib.metadata.version(m) for m in ['numpy','pandas','torch','scikit-learn','catboost']},
       contract_sha256=sha(here/'contract.json'),runner_sha256=sha(Path(__file__)),cells=len(actual),
       comparisons=checks,summary_sha256=sha(out/'summary.csv'),
       portability=dict(kind='native Windows CPU adapter; Windows execution not assumed',split_origin='verified identical AST to frozen run_crossfit.py',dataframe_hash='UTF-8 CSV canonical LF',device='CPU',threads=2),
       scope='Fresh fitting and evaluation of lambda0/1 at seed13 on selected fixed cohorts; external-machine execution requires human confirmation. This does not reproduce the full study or certify all audit stages.'))
    print('Saved external-training-receipt.json; retain differences and all nonconverged batches.',flush=True)
if __name__=='__main__':
    torch.set_num_threads(2)
    with threadpool_limits(limits=2):main()
