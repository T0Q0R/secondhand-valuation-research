"""Finite categorical completion envelope: frozen, three-seed real-cohort pilot.
Mileage must be observed and fixed. No guarantee for mileage suppression.
No targets used for domain selection, no fitting, no seller response updates.
"""
from pathlib import Path
import sys,itertools,json,hashlib,os
os.environ.setdefault('OMP_NUM_THREADS','2');os.environ.setdefault('OPENBLAS_NUM_THREADS','2')
import numpy as np,pandas as pd,torch,joblib
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'experiments'))
from savval import FEATURES,price_features
FIELDS=['transmission','fuel_type','feat_body_condition'];SEEDS=[13,42,2026]
torch.set_num_threads(2);bindings={};rows=[];support=[];domains={};checks=0;max_base_error=0.;max_oracle_error=0.
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def predict(model,frame):
    base=model.backbone.predict(model.encoder.tree_frame(frame),thread_count=2).astype(np.float32)
    if model.residual is None:return base.astype(float)
    model.residual.eval()
    with torch.no_grad():res=model.residual(torch.from_numpy(model.encoder.transform(frame))).reshape(-1).numpy()
    return (base+res).astype(float)
for source in ['jucars','mucars']:
    path=ROOT.parent/'experiments/data/processed'/f'{source}_bvival_v1/splits/validation.csv';bindings[str(path)]=sha(path)
    frame=pd.read_csv(path);rank=frame.listing_id.astype(str).map(lambda s:hashlib.sha256(('sav-val-evaluation-order-v1|'+s).encode()).hexdigest())
    frame=frame.loc[rank.sort_values(kind='stable').index[:1000]].reset_index(drop=True)
    for seed in SEEDS:
        pair=ROOT/'outputs/matched-factorial-ten-seeds-v1'/source/f'seed-{seed}'
        model_path=pair/'fit/deployment_models/robust__none__shared__shared.joblib';bindings[str(model_path.relative_to(ROOT))]=sha(model_path)
        wanted=json.loads((pair/'fit/completion.json').read_text())['deployment_model_hashes']['robust__none__shared__shared'];assert sha(model_path)==wanted
        model,_=joblib.load(model_path);enc=model.encoder
        vocab={f:list(enc.transformer.named_transformers_['categorical'].categories_[enc.categorical.index(f)]) for f in FIELDS}
        assert all('<MISSING>' in v for v in vocab.values());domains[f'{source}/seed-{seed}']=vocab
        eligible=frame.mileage_km.notna().to_numpy().copy()
        for f in FIELDS:eligible &= frame[f].isna().to_numpy()|frame[f].astype(str).isin(vocab[f]).to_numpy()
        x=price_features(frame,FEATURES[source]);base=np.concatenate([predict(model,x.iloc[b:b+128]) for b in range(0,len(x),128)])
        old=[]
        for b in range(10):
            p=pair/f'evaluation/budget-1000/robust/suppression/none/top_b/batch-{b}/arrays.npz';bindings[str(p.relative_to(ROOT))]=sha(p);old.extend(np.load(p)['pred'][:,0])
        error=float(np.max(abs(base-np.array(old))));max_base_error=max(max_base_error,error);assert error<5e-6
        ids=np.flatnonzero(eligible);variants=[];owners=[];sizes=[]
        for i in ids:
            options=[vocab[f] if pd.isna(frame.at[i,f]) else [str(frame.at[i,f])] for f in FIELDS]
            combinations=list(itertools.product(*options));sizes.append(len(combinations))
            for c in combinations:
                row=x.iloc[i].copy()
                for f,v in zip(FIELDS,c):row[f]=np.nan if v=='<MISSING>' else v
                variants.append(row);owners.append(i)
        allx=pd.DataFrame(variants).reset_index(drop=True);values=np.concatenate([predict(model,allx.iloc[b:b+128]) for b in range(0,len(allx),128)])
        envelope=np.full(len(frame),np.inf);np.minimum.at(envelope,np.array(owners),values)
        # Standard all-state production path is an independent batched-inference
        # route to the same frozen quote; compare sampled completions including minima.
        probe=sorted(set(np.linspace(0,len(allx)-1,12,dtype=int).tolist()+[int(np.argmin(values))]))
        oracle=model.predict(allx.iloc[probe])[0][:,0];err=float(np.max(abs(oracle-values[probe])));max_oracle_error=max(max_oracle_error,err);assert err<5e-6;checks+=len(probe)
        # The current record is always in its completion set. Include its saved
        # batch quote explicitly to eliminate floating-batch roundoff artifacts.
        envelope[ids]=np.minimum(envelope[ids],base[ids])
        complete=~frame.loc[ids,FIELDS].isna().any(axis=1).to_numpy()
        envelope[ids[complete]]=base[ids[complete]]
        assert np.all(envelope[ids]<=base[ids]+5e-6)
        target=np.expm1(frame.target_log.to_numpy());qb=np.expm1(base[ids]);qe=np.expm1(envelope[ids])
        missing=frame.loc[ids,FIELDS].isna().any(axis=1).to_numpy()
        for label,mask in [('covered',np.ones(len(ids),bool)),('covered_with_missing_category',missing)]:
            rows.append(dict(dataset=source,seed=seed,subset=label,n=int(mask.sum()),total_records=len(frame),abstentions=int((~eligible).sum()),
                base_honest_mae=float(np.mean(abs(qb[mask]-target[ids][mask]))),envelope_honest_mae=float(np.mean(abs(qe[mask]-target[ids][mask]))),
                base_signed_error=float(np.mean(qb[mask]-target[ids][mask])),envelope_signed_error=float(np.mean(qe[mask]-target[ids][mask])),
                mean_quote_reduction=float(np.mean(qb[mask]-qe[mask])),completion_evaluations=len(values)))
        support.append(dict(dataset=source,seed=seed,records=1000,covered=len(ids),missing_mileage=int(frame.mileage_km.isna().sum()),
            unsupported_observed_category=int((~eligible & frame.mileage_km.notna()).sum()),covered_with_missing_category=int(missing.sum()),completions=len(values),max_completions_per_record=max(sizes)))
        print(source,seed,'covered',len(ids),'completions',len(values),flush=True)
result=pd.DataFrame(rows);result['mae_change']=result.envelope_honest_mae-result.base_honest_mae;result.to_csv(OUT/'final_record_pilot.csv',index=False)
(OUT/'final_record_domains.json').write_text(json.dumps(domains,indent=2)+'\n')
receipt=dict(status='completed_restricted_pilot',seeds=SEEDS,sources=['jucars','mucars'],support=support,training_runs=0,response_updates=0,
 scope='Finite three-categorical-field completions; mileage observed and fixed, all other features fixed. No full four-field mechanism guarantee or new population evaluation. Unsupported records abstain; MAE uses shared covered support.',
 exact_enumeration=True,base_quote_max_abs_log_error=max_base_error,scalar_route_checks=checks,scalar_route_max_abs_log_error=max_oracle_error,
 input_sha256=bindings,script_sha256=sha(Path(__file__)),output_sha256={p.name:sha(p) for p in [OUT/'final_record_pilot.csv',OUT/'final_record_domains.json']})
(OUT/'final_record_completion.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(result.to_string(index=False))
