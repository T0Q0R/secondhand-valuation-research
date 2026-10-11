"""Whole-loop outer exclusion and out-of-fold deployment heads for factorial fits."""
import hashlib,json,fcntl
from pathlib import Path
import joblib,numpy as np,pandas as pd
from run_crossfit import fold_assignments,inner_split
from savval import ActionHeads,price_features
from matched_factorial_training import fit_factorial

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def stage_fit(estimator,guidance,columns,config,seed,out):
    out.mkdir(parents=True,exist_ok=True)
    expected={'estimator':hashlib.sha256(estimator.to_csv(index=False).encode()).hexdigest(),'guidance':hashlib.sha256(guidance.to_csv(index=False).encode()).hexdigest(),'config':config,'seed':seed,'columns':columns}
    if (out/'inputs.json').exists():assert json.loads((out/'inputs.json').read_text())==expected
    else:write(out/'inputs.json',expected)
    cache=out/'checkpoints';cache.mkdir(exist_ok=True)
    def load_cached(key):
        receipt=cache/(key+'.json');model_path=cache/(key+'.joblib')
        if not receipt.exists():return None
        meta=json.loads(receipt.read_text());assert sha(model_path)==meta['sha256']
        model,head=joblib.load(model_path);return model,head,meta['training']
    def save_cached(key,model,head,receipt):
        path=cache/(key+'.joblib');temporary=cache/(key+'.joblib.tmp')
        joblib.dump((model,head),temporary,compress=3);temporary.replace(path)
        temp_receipt=cache/(key+'.json.tmp');write(temp_receipt,{'sha256':sha(path),'training':receipt});temp_receipt.replace(cache/(key+'.json'))
        print(f'CHECKPOINT {out.name}/{key}',flush=True)
    cells,receipts=fit_factorial(estimator,guidance,columns,config,seed,load_cached,save_cached)
    saved={}
    for cell in cells.values():
        fit_id=cell['fit_id']
        if fit_id not in saved:
            path=out/(fit_id+'.joblib');joblib.dump((cell['model'],cell['head']),path,compress=3);saved[fit_id]=sha(path)
    write(out/'receipts.json',receipts)
    write(out/'completion.json',{'status':'completed','model_hashes':saved,'receipts_sha256':sha(out/'receipts.json'),'estimator_content_sha256':hashlib.sha256(estimator.to_csv(index=False).encode()).hexdigest(),'guidance_content_sha256':hashlib.sha256(guidance.to_csv(index=False).encode()).hexdigest(),'config':config,'seed':seed})
    return cells

def fit_nested(train,columns,config,seed,out):
    out.mkdir(parents=True,exist_ok=True)
    lock=(out/'execution.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    sources=[Path(__file__),Path(__file__).with_name('matched_factorial_training.py'),Path(__file__).with_name('matched_feedback_loss.py'),Path(__file__).with_name('minimax_market.py'),Path(__file__).with_name('public_minimax_allocation.py'),Path(__file__).with_name('savval.py'),Path(__file__).with_name('run_all.py'),Path(__file__).with_name('run_crossfit.py'),Path(__file__).with_name('cdm_mechanism.py')]
    binding={'train_content':hashlib.sha256(train.to_csv(index=False).encode()).hexdigest(),'columns':columns,'config':config,'seed':seed,'sources':{str(p.resolve()):sha(p) for p in sources}}
    if (out/'inputs.json').exists():assert json.loads((out/'inputs.json').read_text())==binding
    else:
        assert not (out/'completion.json').exists();write(out/'inputs.json',binding)
    if (out/'completion.json').exists():
        done=json.loads((out/'completion.json').read_text())
        assert sha(out/'outer_predictions.npz')==done['outer_predictions_sha256']
        assert sha(out/'outer_assignments.csv')==done['assignment_sha256']
        assert sha(out/'fold_receipts.json')==done['fold_receipts_sha256']
        assert sha(out/'cell_mapping.json')==done['cell_mapping_sha256']
        loaded={}
        for key,h in done['deployment_model_hashes'].items():
            path=out/'deployment_models'/(key+'.joblib');assert sha(path)==h;loaded[key]=joblib.load(path)
        return {tuple(row['cell']):{'model':loaded[row['fit_id']][0],'head':loaded[row['fit_id']][1],'fit_id':row['fit_id']} for row in json.loads((out/'cell_mapping.json').read_text())}
    assigned=fold_assignments(train,config['outer_folds'])
    predictions={};fold_receipts=[]
    for fold in range(config['outer_folds']):
        working=train.loc[assigned!=fold].copy();heldout=train.loc[assigned==fold].copy()
        estimator,guidance=inner_split(working,config['head_fitting_fraction'])
        assert not set(heldout.listing_id)&(set(estimator.listing_id)|set(guidance.listing_id))
        cells=stage_fit(estimator,guidance,columns,config,seed,out/f'outer-{fold}');seen=set()
        for cell in cells.values():
            fit_id=cell['fit_id']
            if fit_id in seen:continue
            seen.add(fit_id);pred,_,_=cell['model'].predict(price_features(heldout,columns))
            if fit_id not in predictions:predictions[fit_id]=np.full((len(train),pred.shape[1]),np.nan)
            predictions[fit_id][assigned==fold]=pred
        fold_receipts.append({'fold':fold,'estimator_ids':estimator.listing_id.astype(str).tolist(),'guidance_ids':guidance.listing_id.astype(str).tolist(),'heldout_ids':heldout.listing_id.astype(str).tolist()})
        print(f'Completed matched outer fold {fold}',flush=True)
    assert all(np.isfinite(p).all() for p in predictions.values())
    estimator,guidance=inner_split(train,config['head_fitting_fraction'])
    cells=stage_fit(estimator,guidance,columns,config,seed,out/'deployment_fit');models={};saved={}
    deploy=out/'deployment_models';deploy.mkdir(exist_ok=True)
    for cell in cells.values():
        fit_id=cell['fit_id']
        if fit_id not in models:
            model=cell['model'];_,encoded,valid=model.predict(price_features(train,columns))
            head=ActionHeads(config['head_trees'],seed).fit(encoded,predictions[fit_id],valid,train.target_log.to_numpy(),model.space,reported_missing=model.space.reported_missing(train))
            path=deploy/(fit_id+'.joblib');joblib.dump((model,head),path,compress=3);saved[fit_id]=sha(path);models[fit_id]=(model,head)
        cell['model'],cell['head']=models[fit_id]
    np.savez_compressed(out/'outer_predictions.npz',**predictions)
    pd.DataFrame({'listing_id':train.listing_id,'outer_fold':assigned}).to_csv(out/'outer_assignments.csv',index=False)
    write(out/'fold_receipts.json',fold_receipts)
    write(out/'cell_mapping.json',[{'cell':list(k),'fit_id':v['fit_id']} for k,v in cells.items()])
    write(out/'completion.json',{'status':'completed_nested_fit','rows':len(train),'outer_folds':config['outer_folds'],'cells':len(cells),'unique_fits_per_stage':len(models),'deployment_model_hashes':saved,'outer_predictions_sha256':sha(out/'outer_predictions.npz'),'assignment_sha256':sha(out/'outer_assignments.csv'),'fold_receipts_sha256':sha(out/'fold_receipts.json'),'cell_mapping_sha256':sha(out/'cell_mapping.json'),'scope':'whole-loop heldout predictions used for deployment head targets; performance evaluation separate'})
    return cells
