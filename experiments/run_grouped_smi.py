"""Full-feature, whole-field categorical SMI adaptation with exact no-query attack."""
from __future__ import annotations

import argparse
from collections import Counter
import itertools
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.svm import SVR
from threadpoolctl import threadpool_limits

from analyze_nested import read,require,sha
from grouped_smi import GroupedFamily,solve_grouped_smi
from run_all import load_source,write_json
from run_crossfit import identifiers,inner_split
from savval import ACTIONS,FEATURES,StateSpace,price_features
from support_margin import LinearModel,MarginSolveError


DOMAINS=('free','nonnegative','unit_box')
LOG_FIELDS={'mileage_km','feat_battery_range','feat_battery_capacity'}


def numeric(series,field):
    values=pd.to_numeric(series,errors='coerce').to_numpy(dtype=float,copy=True)
    values[~np.isfinite(values)]=np.nan
    if field in LOG_FIELDS:values=np.log1p(np.maximum(values,0))
    return values


def token(value):
    return 'token:missing' if pd.isna(value) else 'raw:'+str(value)


def make_encoder(train,columns):
    specs=[];cursor=0
    for field in columns:
        categorical=field in ACTIONS[1:] or not pd.api.types.is_numeric_dtype(train[field])
        if categorical:
            values=[token(v) for v in train[field]]
            vocabulary=sorted(set(values)|{'token:unknown'})
            if field not in ACTIONS:vocabulary=sorted(set(vocabulary)|{'token:missing'})
            counts=Counter(values)
            mode=min(counts,key=lambda v:(-counts[v],v))
            width=len(vocabulary)
            spec={'field':field,'kind':'categorical','vocabulary':vocabulary,'mode':mode,
                  'columns':list(range(cursor,cursor+width))}
        else:
            values=numeric(train[field],field)
            observed=values[np.isfinite(values)]
            median=float(np.median(observed)) if len(observed) else 0.
            filled=np.where(np.isfinite(values),values,median)
            minimum=float(filled.min());scale=float(np.ptp(filled)) or 1.
            width=1+int(field not in ACTIONS)
            spec={'field':field,'kind':'numeric','median':median,'minimum':minimum,'scale':scale,
                  'columns':list(range(cursor,cursor+width))}
        specs.append(spec);cursor+=width
    return {'specs':specs,'dimension':cursor,'columns':columns}


def encode(frame,encoder):
    x=np.zeros((len(frame),encoder['dimension']))
    for spec in encoder['specs']:
        field=spec['field'];columns=spec['columns']
        if spec['kind']=='numeric':
            values=numeric(frame[field],field)
            absent=~np.isfinite(values)
            x[:,columns[0]]=(np.where(absent,spec['median'],values)-spec['minimum'])/spec['scale']
            if len(columns)==2:x[:,columns[1]]=absent
            if field in ACTIONS:x[absent,columns[0]]=np.nan
        else:
            lookup={v:i for i,v in enumerate(spec['vocabulary'])}
            for i,value in enumerate(frame[field]):
                if field in ACTIONS and pd.isna(value):x[i,columns]=np.nan
                else:x[i,columns[lookup.get(token(value),lookup['token:unknown'])]]=1.
    return x


def optional_metadata(encoder):
    specs={s['field']:s for s in encoder['specs']}
    groups=tuple(tuple(specs[field]['columns']) for field in ACTIONS)
    categorical=frozenset(g for g,field in enumerate(ACTIONS) if specs[field]['kind']=='categorical')
    fallback=np.zeros(encoder['dimension'])
    for field,group in zip(ACTIONS,groups):
        spec=specs[field]
        if spec['kind']=='numeric':fallback[group[0]]=(spec['median']-spec['minimum'])/spec['scale']
        else:fallback[group[spec['vocabulary'].index(spec['mode'])]]=1.
    return groups,categorical,fallback


def summarize(rows):
    values={name:float(rows[column].mean()) for name,column in {
        'honest_mae':'honest_absolute_error','attacked_mae':'attacked_absolute_error',
        'mean_positive_log_inflation':'positive_log_inflation','honest_signed_log_bias':'honest_signed_log_bias',
        'hiding_fraction':'seller_withholds','honest_fallback_fraction':'honest_fallback',
        'attacked_fallback_fraction':'attacked_fallback','honest_imputation_outside_training_range_fraction':'honest_imputation_outside_training_range',
        'attacked_imputation_outside_training_range_fraction':'attacked_imputation_outside_training_range',
        'mean_hidden_fields':'hidden_fields'}.items()}
    natural=rows.naturally_missing_optional.astype(bool)
    values['naturally_missing_honest_mae']=float(rows.loc[natural,'honest_absolute_error'].mean()) if natural.any() else None
    return values


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--parent',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--execution-smoke',action='store_true')
    args=parser.parse_args()
    parent,output=args.parent.resolve(),args.output.resolve()
    parent_manifest=read(parent/'run_manifest.json')
    for name in ('run_all.py','run_crossfit.py','savval.py'):
        require(sha(Path(__file__).with_name(name))==parent_manifest['source_hashes'][name],'Parent source generation')
    config=dict(parent_manifest['config'])
    if args.execution_smoke:config.update(datasets=['synthetic'],max_train=240,max_evaluation=64)
    sources=[Path(__file__),*[Path(__file__).with_name(name) for name in
             ('grouped_smi.py','support_margin.py','run_all.py','run_crossfit.py','savval.py','analyze_nested.py')],
             Path(__file__).parents[1]/'plan/grouped-smi-comparator-v2.md',
             Path(__file__).parents[1]/'tests/test_grouped_smi.py']
    hashes={p.name:sha(p) for p in sources}
    require(not output.exists(),'Fresh immutable output required')
    output.mkdir(parents=True);snapshot=output/'source_snapshot';snapshot.mkdir()
    for p in sources:(snapshot/p.name).write_bytes(p.read_bytes())
    write_json(output/'manifest.json',{'parent_binding':parent_manifest['binding'],'config':config,
               'source_hashes':hashes,'execution_smoke':args.execution_smoke,'epsilon':.15,'C':1.,
               'domains':list(DOMAINS),'maximum_hidden':config['maximum_hidden'],'svr_max_iter':-1,'svr_tol':1e-5,
               'scope':'full-feature grouped one-hot SMI adaptation; exact no-query reports; retrospective development; not official Weka reproduction'})
    summaries=[];started=time.time()
    with threadpool_limits(limits=1):
        for dataset in config['datasets']:
            first,head,evaluation,provenance=load_source(dataset,config)
            estimator,_=inner_split(pd.concat([first,head],ignore_index=True),config['head_fitting_fraction'])
            eligible=estimator.loc[:,list(ACTIONS)].notna().all(axis=1).to_numpy(copy=True)
            eligible &= np.isfinite(numeric(estimator.mileage_km,'mileage_km'))
            train=estimator.loc[eligible].copy()
            require(len(train)>=30,'Insufficient complete optional-field fitting rows')
            fields=FEATURES[dataset]
            encoder=make_encoder(price_features(train,fields),fields)
            x_train=encode(train,encoder);x_eval=encode(evaluation,encoder)
            require(np.isfinite(x_train).all(),'Nonfinite fitting input')
            groups,categorical,fallback=optional_metadata(encoder)
            y=train.target_log.to_numpy();minimum=float(y.min());scale=float(np.ptp(y))
            require(scale>0,'Constant fitting target')
            normalized=(y-minimum)/scale
            models=[];omitted=[];fitted_bank={};timings=[]
            folder=output/dataset;folder.mkdir()
            print(f'GROUPED SMI {dataset}: {len(train)} complete estimator rows, {len(evaluation)} evaluation, {encoder["dimension"]} coordinates',flush=True)
            for pattern in range(16):
                dropped=frozenset(g for g in range(len(ACTIONS)) if pattern & (1 << g))
                dropped_columns=frozenset(c for g in dropped for c in groups[g])
                kept=[c for c in range(x_train.shape[1]) if c not in dropped_columns]
                fitted=SVR(kernel='linear',C=1.,epsilon=.15,tol=1e-5,max_iter=-1,cache_size=128)
                tick=time.time();fitted.fit(x_train[:,kept],normalized);elapsed=time.time()-tick
                write_json(folder/f'fit-status-{pattern:02d}.json',{'pattern':pattern,'status':int(fitted.fit_status_),
                           'iterations':int(fitted.n_iter_),'seconds':elapsed,'C':1.,'epsilon':.15,'tol':1e-5,'max_iter':-1})
                require(fitted.fit_status_==0,'Linear SVR failed to converge')
                w=np.zeros(x_train.shape[1]);w[kept]=fitted.coef_.ravel();w[np.abs(w)<1e-10]=0.
                models.append(LinearModel(w,float(fitted.intercept_[0]),dropped_columns));omitted.append(dropped)
                fitted_bank[str(pattern)]={'model':fitted,'kept':kept}
                timings.append({'pattern':pattern,'seconds':elapsed,'iterations':int(fitted.n_iter_)})
            family=GroupedFamily(tuple(models),groups,tuple(omitted),categorical)
            joblib.dump(fitted_bank,folder/'svr_models.joblib',compress=3)
            write_json(folder/'fit_audit.json',{'provenance':provenance,'estimator_ids_sha256':identifiers(estimator),
                'fit_ids_sha256':identifiers(train),'evaluation_ids_sha256':identifiers(evaluation),
                'estimator_count':len(estimator),'common_fitting_count':len(train),'encoder':encoder,
                'target_minimum':minimum,'target_scale':scale,'groups':groups,'categorical_groups':sorted(categorical),
                'fallback_values':fallback.tolist(),'timings':timings,'sign_zero_tolerance':1e-10,
                'models':[{'weights':m.weights.tolist(),'intercept':m.intercept,'omitted_columns':sorted(m.omitted),
                           'omitted_groups':sorted(g)} for m,g in zip(models,omitted)]})
            train[['listing_id']].to_csv(folder/'fitting_ids.csv',index=False)
            estimator[['listing_id']].to_csv(folder/'estimator_ids.csv',index=False)
            state_space=StateSpace.build(config['maximum_hidden'])
            _,valid=state_space.materialize(price_features(evaluation,fields))
            n,s=len(evaluation),len(state_space.masks)
            arrays={'encoded_evaluation':x_eval,'valid':valid,'masks':state_space.masks}
            prediction=np.empty((4,n,s));imputation=np.empty((4,n,s,x_eval.shape[1]))
            status=np.empty((4,n,s),dtype='U384');lower=np.full((4,n,s),np.nan)
            second=np.full((4,n,s),np.nan);retained=np.zeros((4,n,s),int)
            for i,record in enumerate(x_eval):
                cache={}
                for state,mask in enumerate(state_space.masks):
                    report=record.copy()
                    for g in np.flatnonzero(mask):report[list(groups[g])]=np.nan
                    missing=np.isnan(report)
                    key=tuple(missing)
                    if key not in cache:
                        filled=np.where(missing,fallback,report)
                        ordinary=float(models[0].weights @ filled+models[0].intercept)
                        choices=[(ordinary,filled,'ordinary_median_mode',np.nan,np.nan,0)]
                        for domain in DOMAINS:
                            try:
                                result=solve_grouped_smi(report,family,.15,domain)
                                choices.append((result.prediction,result.imputed_record,'solved',result.lower_margin_objective,
                                                result.stage_two_objective,result.retained_models))
                            except (MarginSolveError,ValueError) as error:
                                choices.append((ordinary,filled,str(error),np.nan,np.nan,0))
                        cache[key]=choices
                    for m,choice in enumerate(cache[key]):
                        prediction[m,i,state],imputation[m,i,state],status[m,i,state],lower[m,i,state],second[m,i,state],retained[m,i,state]=choice
                if (i+1)%100==0:print(f'  predicted {i+1}/{n}',flush=True)
            arrays.update(prediction_normalized=prediction,imputation=imputation,status=status,
                          lower_objective=lower,second_objective=second,retained_models=retained)
            np.savez_compressed(folder/'state_evidence.npz',**arrays)
            methods=['linear_svr_median_mode',*[f'grouped_smi_{d}_with_fallback' for d in DOMAINS]]
            all_outcomes=[]
            for m,method in enumerate(methods):
                quotes=prediction[m]*scale+minimum
                utility=np.where(valid,quotes-config['concealment_cost_log']*state_space.masks.sum(axis=1)[None],-np.inf)
                chosen=utility.argmax(axis=1);index=np.arange(n)
                honest=quotes[:,0];attacked=quotes[index,chosen]
                require(np.isfinite(np.expm1(quotes)).all(),'Nonfinite native-price transformation')
                fallback_states=status[m]!='solved' if m else np.zeros((n,s),bool)
                mileage=groups[0][0]
                outside=(imputation[m,:,:,mileage]<0)|(imputation[m,:,:,mileage]>1)
                # Only an actually imputed mileage counts as imputation extrapolation.
                mileage_missing=np.isnan(x_eval[:,mileage])[:,None]|state_space.masks[:,0][None]
                outside &= mileage_missing
                target=evaluation.target_log.to_numpy()
                rows=pd.DataFrame({'dataset':dataset,'method':method,'listing_id':evaluation.listing_id,
                    'batch':np.arange(n)//config['batch_size'],'state':chosen,'target_log':target,
                    'honest_log_quote':honest,'attacked_log_quote':attacked,
                    'honest_absolute_error':np.abs(np.expm1(honest)-np.expm1(target)),
                    'attacked_absolute_error':np.abs(np.expm1(attacked)-np.expm1(target)),
                    'positive_log_inflation':np.maximum(attacked-honest,0),'honest_signed_log_bias':honest-target,
                    'seller_withholds':chosen!=0,'hidden_fields':state_space.masks[chosen].sum(axis=1),
                    'honest_fallback':fallback_states[:,0],'attacked_fallback':fallback_states[index,chosen],
                    'honest_solver_status':status[m,:,0],'attacked_solver_status':status[m,index,chosen],
                    'honest_imputation_outside_training_range':outside[:,0],
                    'attacked_imputation_outside_training_range':outside[index,chosen],
                    'naturally_missing_optional':evaluation.loc[:,list(ACTIONS)].isna().any(axis=1)})
                all_outcomes.append(rows)
                summaries.append({'dataset':dataset,'method':method,'budget':0,'queries':0,'n':n,
                    'fit_rows':len(train),'maximum_hidden':config['maximum_hidden'],'deterministic_fit':True,**summarize(rows)})
            pd.concat(all_outcomes,ignore_index=True).to_csv(folder/'outcomes.csv.gz',index=False)
            pd.DataFrame([r for r in summaries if r['dataset']==dataset]).to_csv(folder/'summary.csv',index=False)
            write_json(folder/'completion.json',{'status':'completed','files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}})
            print(f'COMPLETED GROUPED SMI {dataset}',flush=True)
    pd.DataFrame(summaries).to_csv(output/'summary.csv',index=False)
    require({p.name:sha(p) for p in sources}==hashes,'Frozen SMI generation changed')
    write_json(output/'completion.json',{'status':'completed','cells':len(summaries),'execution_smoke':args.execution_smoke,
                'summary_sha256':sha(output/'summary.csv'),'elapsed_seconds':time.time()-started})
    print(f'COMPLETED GROUPED SMI GENERATION {output}',flush=True)


if __name__=='__main__':main()
