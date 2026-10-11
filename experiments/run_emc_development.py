"""Independent EMC real-source development gate with immutable case receipts."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

from emc_val import TreeInputs, conformal_quantile, inherited_endpoints, lower_quote, public_allocate
from savval import ACTIONS, FEATURES, StateSpace, price_features, simulate_market, stable_rank

ROOT = Path(__file__).resolve().parents[1]
SPACE = StateSpace.build(4)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def materialize(frame, columns, encoder):
    public, valid = SPACE.materialize(price_features(frame, columns))
    return encoder.prepare(public), valid


def predict(models, public, n):
    predictions = np.stack([m.predict(public, thread_count=1) for m in models], axis=-1).reshape(n, 16, 2)
    return np.minimum(predictions[..., 0], predictions[..., 1]), np.maximum(predictions[..., 0], predictions[..., 1])


def action_inputs(public, raw_l, raw_u, emc_l, emc_u):
    result = public.iloc[np.repeat(np.arange(len(public)), 4)].reset_index(drop=True).copy()
    result['query_field'] = np.tile(np.asarray(ACTIONS), len(public))
    for name, values in [('raw_lower', raw_l), ('raw_upper', raw_u), ('emc_lower', emc_l), ('emc_upper', emc_u)]:
        result[name] = np.repeat(values.reshape(-1), 4)
    return result


def load(name, cap):
    if name == 'synthetic':
        frame = simulate_market(6000, 73101)
        source = {'kind': 'stipulated generator', 'seed': 73101}
    else:
        path = ROOT.parent / 'experiments/data/processed' / f'{name}_bvival_v1/splits/train.csv'
        frame = pd.read_csv(path)
        source = {'path': str(path), 'sha256': sha(path), 'validation_or_test_read': False}
    if frame.listing_id.duplicated().any() or not np.isfinite(frame.target_log).all():
        raise ValueError('Invalid source records')
    order = frame.listing_id.map(lambda x: stable_rank(str(x), 'emc-select-v1')).sort_values(kind='stable').index
    frame = frame.loc[order[:cap]].reset_index(drop=True)
    order = frame.listing_id.map(lambda x: stable_rank(str(x), 'emc-split-v1')).sort_values(kind='stable').index
    return frame.loc[order].reset_index(drop=True), source


def source_case(name, seed, folder, config):
    frame, source = load(name, config['max_records'])
    n = len(frame)
    boundaries = [0, int(.5*n), int(.7*n), int(.85*n), n]
    parts = {key: frame.iloc[boundaries[i]:boundaries[i+1]].reset_index(drop=True)
             for i, key in enumerate(('estimator', 'head', 'calibration', 'evaluation'))}
    if min(map(len, parts.values())) < 20:
        raise ValueError('Insufficient disjoint records')
    columns = FEATURES[name]
    encoder = TreeInputs(price_features(parts['estimator'], columns))
    frame.to_csv(folder/'selected_records.csv', index=False)
    assignments = pd.DataFrame({'listing_id': frame.listing_id, 'split': np.repeat(list(parts), [len(v) for v in parts.values()])})
    assignments.to_csv(folder/'split_assignments.csv', index=False)
    write(folder/'source.json', {'source': source, 'features': columns, 'split_counts': {k:len(v) for k,v in parts.items()}, 'status':'retrospective development'})
    joblib.dump(encoder, folder/'encoder.joblib')
    public, valid = materialize(parts['estimator'], columns, encoder)
    weights = np.broadcast_to(1/valid.sum(axis=1)[:, None], valid.shape)[valid]
    y = np.repeat(parts['estimator'].target_log.to_numpy(), 16)[valid.ravel()]
    models = []
    for quantile in (.1, .9):
        model = CatBoostRegressor(iterations=config['iterations'], depth=6, learning_rate=.05,
            loss_function=f'Quantile:alpha={quantile}', random_seed=seed, thread_count=1,
            verbose=False, allow_writing_files=False)
        model.fit(public.loc[valid.ravel()], y, sample_weight=weights, cat_features=encoder.categorical)
        model.save_model(str(folder/f'quantile-{quantile}.cbm'))
        models.append(model)
    cache = {}
    for key in ('head','calibration','evaluation'):
        public, valid = materialize(parts[key], columns, encoder)
        l,u = predict(models, public, len(parts[key]))
        el,eu = inherited_endpoints(l,u,SPACE.masks)
        cache[key] = (public,valid,l,u,el,eu)
        np.savez_compressed(folder/f'{key}-intervals.npz', raw_lower=l,raw_upper=u,emc_lower=el,emc_upper=eu,
            valid=valid, target=parts[key].target_log.to_numpy())
    public,valid,l,u,el,eu = cache['head']
    missing = SPACE.reported_missing(parts['head'])
    active = valid[:,:,None] & missing
    target = np.stack([(u-l)[:,:,None]-(u-l)[:,SPACE.query_next],
                       (eu-el)[:,:,None]-(eu-el)[:,SPACE.query_next]], axis=-1)
    if (target[...,1][active] < -1e-10).any():
        raise AssertionError('Inherited interval signed span expanded after evidence')
    head_x = action_inputs(public,l,u,el,eu)
    head = CatBoostRegressor(iterations=config['head_iterations'], depth=6, learning_rate=.05,
        loss_function='MultiRMSE', random_seed=seed, thread_count=1, verbose=False, allow_writing_files=False)
    head.fit(head_x.loc[active.ravel()],target.reshape(-1,2)[active.ravel()],cat_features=encoder.categorical+['query_field'])
    head.save_model(str(folder/'query-head.cbm'))
    hp,hv,hl,hu,hel,heu = cache['evaluation']
    gain = head.predict(action_inputs(hp,hl,hu,hel,heu), thread_count=1).reshape(len(hv),16,4,2)
    np.savez_compressed(folder/'public-query-scores.npz', gain=gain)
    for h,mask in enumerate(SPACE.masks):
        weak = np.all(SPACE.masks | ~mask,axis=1)
        if (hel[:,weak] > hel[:,h,None]+1e-10).any() or (heu[:,weak] < heu[:,h,None]-1e-10).any():
            raise AssertionError('Nesting failed')
    cp,cv,cl,cu,_,_ = cache['calibration']
    cy = parts['calibration'].target_log.to_numpy()
    nonconformity = np.maximum.reduce([np.zeros_like(cl),cl-cy[:,None],cy[:,None]-cu])
    ordinary = nonconformity[:,0]
    strategic = np.where(cv,nonconformity,-np.inf).max(axis=1)
    np.savez_compressed(folder/'calibration-scores.npz',ordinary=ordinary,strategic=strategic)
    calibration = {}
    for alpha in config['alphas']:
        oq,rank=conformal_quantile(ordinary,alpha)
        sq,_=conformal_quantile(strategic,alpha)
        if not np.isfinite([oq,sq]).all():
            raise ValueError('This research run needs a finite rank; increase calibration records')
        calibration[str(alpha)]={'ordinary_q':oq,'strategic_q':sq,'rank':rank,'count':len(cy)}
    write(folder/'calibration.json',calibration)
    evaluation = parts['evaluation']
    ids = evaluation.listing_id.astype(str).to_numpy()
    truth = evaluation.target_log.to_numpy()
    feasible = hv & (SPACE.masks.sum(axis=1)<=2)[None,:]
    states = {'honest':np.zeros(len(evaluation),int),
        'shared_raw_lower_max':np.argmax(np.where(feasible,hl,-np.inf),axis=1),
        'shared_hash_hidden':np.array([np.flatnonzero(feasible[i])[int(stable_rank(x,'emc-hidden-v1')[:16],16)%int(feasible[i].sum())]
                                        for i,x in enumerate(ids)])}
    random = np.array([[int(stable_rank(x+'|'+a,'emc-priority-v1')[:16],16)/float(16**16) for a in ACTIONS] for x in ids])
    random = np.broadcast_to(random[:,None,:],(len(evaluation),16,4))
    reported_missing=SPACE.reported_missing(evaluation)
    rows=[]
    for alpha in config['alphas']:
        qs=calibration[str(alpha)]
        variants={'ordinary_cp':(hl-qs['ordinary_q'],hu+qs['ordinary_q'],0),
                  'strategic_cp':(hl-qs['strategic_q'],hu+qs['strategic_q'],0),
                  'emc':(hel-qs['strategic_q'],heu+qs['strategic_q'],1)}
        for method,(all_l,all_u,head_output) in variants.items():
            joint=((all_l<=truth[:,None]) & (truth[:,None]<=all_u)) | ~hv
            joint=joint.all(axis=1)
            for profile,initial in states.items():
                for rho in config['budgets']:
                    for policy in (('none',) if rho==0 else ('random','shrink')):
                        score=random if policy=='random' else np.maximum(gain[...,head_output],0)
                        score=score.copy()
                        score[all_u<np.maximum(0,all_l)]=0
                        final,actions=initial.copy(),np.full(len(initial),-1,int)
                        for start in range(0,len(initial),100):
                            stop=min(start+100,len(initial));cap=int(np.floor(rho*(stop-start)))
                            f,a=public_allocate(score[start:stop],reported_missing[start:stop],initial[start:stop],cap,SPACE.query_next)
                            final[start:stop],actions[start:stop]=f,a
                            assert (a>=0).sum()<=cap
                        idx=np.arange(len(initial));l=all_l[idx,final];u=all_u[idx,final]
                        valid_interval=u>=np.maximum(0,l)
                        quote=lower_quote(l); honest_quote=lower_quote(all_l[:,0])
                        if method=='emc' and (quote>honest_quote+1e-10).any():
                            raise AssertionError('EMC lower quote exceeds full disclosure')
                        success=(actions>=0)&(final!=initial)
                        query_actions=np.maximum(actions,0)
                        should_succeed=(actions>=0)&SPACE.masks[initial,query_actions]
                        assert np.array_equal(success,should_succeed)
                        for i in idx:
                            rows.append({'source':name,'seed':seed,'alpha':alpha,'method':method,'profile':profile,
                                'budget':rho,'policy':policy,'listing_id':ids[i],'batch':int(i//100),
                                'initial_state':int(initial[i]),'final_state':int(final[i]),'action':int(actions[i]),
                                'query_succeeded':bool(success[i]),'target_log':float(truth[i]),
                                'lower_log':float(l[i]),'upper_log':float(u[i]),'valid_interval':bool(valid_interval[i]),
                                'coverage':bool(valid_interval[i] and l[i]<=truth[i]<=u[i]),'joint_state_coverage':bool(joint[i]),
                                'width_log':float(u[i]-max(0,l[i])) if valid_interval[i] else None,
                                'quote_log':float(quote[i]),'honest_quote_log':float(honest_quote[i]),
                                'signed_log_error':float(quote[i]-truth[i]),
                                'quote_absolute_error':float(abs(np.expm1(quote[i])-np.expm1(truth[i]))),
                                'positive_log_inflation':float(max(quote[i]-honest_quote[i],0))})
    outcomes=pd.DataFrame(rows)
    outcomes.to_csv(folder/'outcomes.csv.gz',index=False,compression='gzip')
    keys=['source','seed','alpha','method','profile','budget','policy']
    summary=outcomes.groupby(keys,dropna=False,sort=True).agg(n=('listing_id','size'),coverage=('coverage','mean'),
        joint_state_coverage=('joint_state_coverage','mean'),width_log=('width_log','mean'),valid_interval_rate=('valid_interval','mean'),
        signed_log_bias=('signed_log_error','mean'),quote_mae=('quote_absolute_error','mean'),
        positive_log_inflation=('positive_log_inflation','mean'),query_fraction=('action',lambda x:(x>=0).mean()),
        query_success_fraction=('query_succeeded','mean')).reset_index()
    summary.to_csv(folder/'summary.csv',index=False)
    files={p.name:sha(p) for p in folder.iterdir() if p.is_file()}
    write(folder/'completion.json',{'status':'completed','source':name,'seed':seed,'cells':len(summary),'files':files,
        'config_sha256':sha(folder.parent.parent/'config.json')})
    print(f'COMPLETED {name} seed={seed}: {len(summary)} cells',flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--smoke',action='store_true')
    args=parser.parse_args()
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    config={'status':'retrospective development','smoke':args.smoke,'sources':['synthetic','jucars','mucars'],
            'seeds':[13] if args.smoke else [13,42,2026], 'max_records':200 if args.smoke else 5000,
            'iterations':20 if args.smoke else 250,'head_iterations':20 if args.smoke else 160,
            'alphas':[.05,.10],'budgets':[0,.10,.30]}
    write(output/'config.json',config)
    snapshot=output/'source_snapshot';snapshot.mkdir()
    for path in [Path(__file__),ROOT/'experiments/emc_val.py',ROOT/'experiments/savval.py',ROOT/'plan/emc-development-v1.md']:
        shutil.copyfile(path,snapshot/path.name)
    write(snapshot/'hashes.json',{p.name:sha(p) for p in snapshot.iterdir() if p.is_file()})
    print(f'START {config}',flush=True)
    for name in config['sources']:
        for seed in config['seeds']:
            folder=output/name/f'seed-{seed}';folder.mkdir(parents=True)
            source_case(name,seed,folder,config)
    summaries=[pd.read_csv(p) for p in sorted(output.glob('*/seed-*/summary.csv'))]
    pd.concat(summaries,ignore_index=True).to_csv(output/'summary.csv',index=False)
    write(output/'completion.json',{'status':'completed','smoke':args.smoke,'case_count':len(summaries),
        'cell_count':sum(map(len,summaries)),'summary_sha256':sha(output/'summary.csv'),
        'config_sha256':sha(output/'config.json'),'source_snapshot_sha256':sha(snapshot/'hashes.json')})


if __name__=='__main__':
    main()
