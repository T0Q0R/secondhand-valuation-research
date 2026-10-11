"""Independent grouped-SMI audit using scalar interval geometry after LP cross-checks."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from analyze_nested import read,require,sha
from grouped_smi_interval_oracle import enumerate_objectives
from run_all import load_source,write_json
from run_crossfit import identifiers,inner_split
from savval import ACTIONS,FEATURES


def close(actual,expected,reason,tol=2e-6):
    require(np.allclose(actual,expected,atol=tol,rtol=0,equal_nan=True),reason)


def numeric_values(series,field):
    array=np.array(pd.to_numeric(series,errors='coerce'),dtype=float,copy=True)
    array[~np.isfinite(array)]=np.nan
    if field in {'mileage_km','feat_battery_range','feat_battery_capacity'}:
        array=np.log1p(np.maximum(array,0))
    return array


def reconstruct_encoding(fitting,evaluation,encoder):
    result=np.zeros((len(evaluation),encoder['dimension']))
    for spec in encoder['specs']:
        field=spec['field'];columns=spec['columns']
        categorical=field in ACTIONS[1:] or not pd.api.types.is_numeric_dtype(fitting[field])
        require(categorical==(spec['kind']=='categorical'),'Encoder input kind')
        if categorical:
            train_values=['token:missing' if pd.isna(v) else 'raw:'+str(v) for v in fitting[field]]
            vocabulary=set(train_values)|{'token:unknown'}
            if field not in ACTIONS:vocabulary.add('token:missing')
            require(sorted(vocabulary)==spec['vocabulary'],'Training-only category vocabulary')
            counts=Counter(train_values);mode=min(counts,key=lambda v:(-counts[v],v))
            require(mode==spec['mode'],'Training-only categorical mode')
            for i,value in enumerate(evaluation[field]):
                if pd.isna(value) and field in ACTIONS:result[i,columns]=np.nan;continue
                value='token:missing' if pd.isna(value) else 'raw:'+str(value)
                if value not in vocabulary:value='token:unknown'
                result[i,columns[spec['vocabulary'].index(value)]]=1.
        else:
            values=numeric_values(fitting[field],field)
            recorded=values[np.isfinite(values)];median=float(np.median(recorded)) if len(recorded) else 0.
            filled=np.nan_to_num(values,nan=median)
            minimum=float(filled.min());scale=float(np.ptp(filled)) or 1.
            close([spec['median'],spec['minimum'],spec['scale']],[median,minimum,scale],'Training-only numeric scaling')
            incoming=numeric_values(evaluation[field],field);missing=~np.isfinite(incoming)
            result[:,columns[0]]=(np.where(missing,median,incoming)-minimum)/scale
            if len(columns)==2:result[:,columns[1]]=missing
            if field in ACTIONS:result[missing,columns[0]]=np.nan
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run,output=args.run.resolve(),args.output.resolve()
    manifest,complete=read(run/'manifest.json'),read(run/'completion.json')
    require(complete['status']=='completed','Complete grouped-SMI generation required')
    require(sha(run/'summary.csv')==complete['summary_sha256'],'Root summary binding')
    for name,digest in manifest['source_hashes'].items():require(sha(run/'source_snapshot'/name)==digest,'Frozen source snapshot')
    for name in ('run_all.py','run_crossfit.py','savval.py','analyze_nested.py'):
        require(sha(Path(__file__).with_name(name))==manifest['source_hashes'][name],'Imported core generation')
    require(not output.exists(),'Fresh audit output required')
    output.mkdir(parents=True)
    for source in [Path(__file__),Path(__file__).with_name('grouped_smi_interval_oracle.py')]:
        (output/source.name).write_bytes(source.read_bytes())
    config=manifest['config'];audited=[];coverage=[];oracle_checks=0
    root_summary=pd.read_csv(run/'summary.csv')
    with threadpool_limits(limits=1):
        for dataset in config['datasets']:
            folder=run/dataset;done=read(folder/'completion.json')
            require(done['status']=='completed','Dataset completion')
            for name,digest in done['files'].items():require(sha(folder/name)==digest,'Dataset artifact binding')
            first,head,evaluation,provenance=load_source(dataset,config)
            estimator,_=inner_split(pd.concat([first,head],ignore_index=True),config['head_fitting_fraction'])
            eligible=estimator.loc[:,list(ACTIONS)].notna().all(axis=1).to_numpy(copy=True)
            eligible &= np.isfinite(numeric_values(estimator.mileage_km,'mileage_km'))
            fitting=estimator.loc[eligible].copy();receipt=read(folder/'fit_audit.json')
            require(receipt['provenance']==provenance,'Source provenance/content binding')
            for frame,key in [(estimator,'estimator_ids_sha256'),(fitting,'fit_ids_sha256'),(evaluation,'evaluation_ids_sha256')]:
                require(identifiers(frame)==receipt[key],'Fitting/evaluation cohort')
            require(pd.read_csv(folder/'fitting_ids.csv').listing_id.tolist()==fitting.listing_id.tolist(),'Fitting ID file')
            require(pd.read_csv(folder/'estimator_ids.csv').listing_id.tolist()==estimator.listing_id.tolist(),'Estimator ID file')
            require(not set(fitting.listing_id)&set(evaluation.listing_id),'Evaluation label in fitting')
            require(receipt['encoder']['columns']==FEATURES[dataset],'Complete allowed feature set')
            require([s['field'] for s in receipt['encoder']['specs']]==FEATURES[dataset],'Encoder complete ordered specs')
            x_train=reconstruct_encoding(fitting,fitting,receipt['encoder'])
            x_eval=reconstruct_encoding(fitting,evaluation,receipt['encoder'])
            minimum=float(fitting.target_log.min());scale=float(np.ptp(fitting.target_log.to_numpy()))
            close([minimum,scale],[receipt['target_minimum'],receipt['target_scale']],'Training-only target scaling')
            models=receipt['models'];bank=joblib.load(folder/'svr_models.joblib')
            require(set(bank)==set(map(str,range(16))) and len(models)==16,'Complete group-reduced model bank')
            groups=receipt['groups'];specs={s['field']:s for s in receipt['encoder']['specs']}
            require(groups==[specs[field]['columns'] for field in ACTIONS],'Whole optional-field coordinates')
            expected_fallback=np.zeros(x_eval.shape[1])
            for field,group in zip(ACTIONS,groups):
                spec=specs[field]
                if spec['kind']=='numeric':expected_fallback[group[0]]=(spec['median']-spec['minimum'])/spec['scale']
                else:expected_fallback[group[spec['vocabulary'].index(spec['mode'])]]=1.
            close(receipt['fallback_values'],expected_fallback,'Declared training-only fallback')
            categorical=[g for g,field in enumerate(ACTIONS) if specs[field]['kind']=='categorical']
            require(categorical==receipt['categorical_groups'],'Integer categorical groups')
            for pattern,record in enumerate(models):
                omitted=[g for g in range(4) if pattern & (1 << g)]
                omitted_columns=sorted(c for g in omitted for c in groups[g])
                require(record['omitted_groups']==omitted and record['omitted_columns']==omitted_columns,'All field-reduced patterns')
                fitted=bank[str(pattern)]['model'];kept=bank[str(pattern)]['kept']
                require(kept==[c for c in range(x_eval.shape[1]) if c not in omitted_columns],'Complete retained input columns')
                require(fitted.kernel=='linear' and fitted.C==1 and fitted.epsilon==.15 and fitted.fit_status_==0,'Converged declared SVR')
                require(fitted.max_iter==manifest.get('svr_max_iter',200000) and fitted.tol==manifest.get('svr_tol',1e-5),'Declared convergence controls')
                close(fitted.support_vectors_,x_train[fitted.support_][:,kept],'SVR support fitting rows',1e-10)
                weights=np.zeros(x_eval.shape[1]);weights[kept]=fitted.coef_.ravel();weights[np.abs(weights)<1e-10]=0.
                close(record['weights'],weights,'Actual fitted coefficient family',1e-10)
                close(record['intercept'],fitted.intercept_[0],'Actual fitted intercept',1e-10)
            stored=np.load(folder/'state_evidence.npz')
            close(stored['encoded_evaluation'],x_eval,'Independent public input encoding',1e-10)
            masks=np.array([[g in combination for g in range(4)] for size in range(config['maximum_hidden']+1)
                            for combination in __import__('itertools').combinations(range(4),size)])
            require(np.array_equal(stored['masks'],masks),'Complete report enumeration')
            available=evaluation.loc[:,list(ACTIONS)].notna().to_numpy()
            valid=~(masks[None] & ~available[:,None]).any(axis=2)
            require(np.array_equal(valid,stored['valid']),'Original-recorded-value concealment feasibility')
            for i,record in enumerate(x_eval):
                cache={}
                for state,mask in enumerate(masks):
                    report=record.copy()
                    for g in np.flatnonzero(mask):report[groups[g]]=np.nan
                    missing=np.isnan(report);filled=np.where(missing,expected_fallback,report)
                    ordinary=float(np.array(models[0]['weights']) @ filled+models[0]['intercept'])
                    close(stored['prediction_normalized'][0,i,state],ordinary,'Ordinary imputation quote')
                    close(stored['imputation'][0,i,state],filled,'Ordinary imputation record')
                    for m,domain in enumerate(manifest['domains'],1):
                        key=(domain,tuple(missing))
                        if key not in cache:
                            cache[key]=enumerate_objectives(report,models,groups,categorical,.15,domain);oracle_checks+=1
                        oracle=cache[key];status=str(stored['status'][m,i,state])
                        if oracle['status']!='solved':
                            require(status!='solved','Production solver accepted independently failing report')
                            if oracle['status']=='inconsistent_family':require('sign consistent' in status,'Declared inconsistency fallback')
                            else:require('Grouped equation' in status,'Declared optimization fallback')
                            close(stored['prediction_normalized'][m,i,state],ordinary,'Identical median/mode fallback')
                            close(stored['imputation'][m,i,state],filled,'Identical fallback record')
                            continue
                        require(status=='solved','Production solver rejected independently solvable report')
                        close(stored['lower_objective'][m,i,state],oracle['lower'],'Enumerated stage-one optimum')
                        close(stored['second_objective'][m,i,state],oracle['second'],'Enumerated stage-two optimum')
                        require(stored['retained_models'][m,i,state]==oracle['retained'],'Exact sign-consistent model family')
                        imputed=stored['imputation'][m,i,state]
                        close(imputed[~missing],report[~missing],'Observed values preserved',1e-10)
                        for g in categorical:
                            values=imputed[groups[g]]
                            require(np.allclose(values,np.rint(values),atol=1e-9) and np.all(values>=0) and np.all(values<=1) and np.isclose(values.sum(),1),'Integer one-hot completion')
                        if missing[groups[0][0]] and domain!='free':
                            require(imputed[groups[0][0]]>=-2e-6,'Nonnegative mileage domain')
                            if domain=='unit_box':require(imputed[groups[0][0]]<=1+2e-6,'Unit-box mileage domain')
                        if missing.any():
                            family=[r for r in models if set(r['omitted_groups'])<={g for g,cols in enumerate(groups) if missing[cols].all()} and
                                    np.array_equal(np.sign(np.array(r['weights'])[[c for c in range(len(imputed)) if c not in r['omitted_columns']]]),
                                                   np.sign(np.array(models[0]['weights'])[[c for c in range(len(imputed)) if c not in r['omitted_columns']]]))]
                            centers=np.array([np.array(r['weights']) @ imputed+r['intercept'] for r in family])
                            require(centers.min()>=oracle['lower']-2e-6 and centers.max()<=oracle['lower']+.15+2e-6,'All final margin constraints')
                            close(np.sign(np.array(models[0]['weights'])[missing]) @ imputed[missing],oracle['second'],'Final signed-imputation objective')
                        quote=float(np.array(models[0]['weights']) @ imputed+models[0]['intercept'])
                        close(stored['prediction_normalized'][m,i,state],quote,'Final full-model quote, not lower bound')
                if (i+1)%100==0:print(f'AUDIT GROUPED {dataset} {i+1}/{len(x_eval)}',flush=True)
            outcomes=pd.read_csv(folder/'outcomes.csv.gz');summary=pd.read_csv(folder/'summary.csv')
            names=['linear_svr_median_mode',*[f'grouped_smi_{d}_with_fallback' for d in manifest['domains']]]
            require(len(summary)==4 and set(summary.method)==set(names),'Complete method/domain matrix')
            for m,name in enumerate(names):
                rows=outcomes[outcomes.method==name].reset_index(drop=True)
                require(rows.listing_id.tolist()==evaluation.listing_id.tolist(),'Complete evaluation membership/order')
                quotes=stored['prediction_normalized'][m]*scale+minimum
                utility=np.where(valid,quotes-config['concealment_cost_log']*masks.sum(axis=1)[None],-np.inf)
                selected=utility.argmax(axis=1);index=np.arange(len(rows))
                require(np.array_equal(rows.state,selected),'Exact legal best response with honest tie')
                close(rows.target_log,evaluation.target_log,'Evaluation targets')
                close(rows.honest_log_quote,quotes[:,0],'Honest quotation')
                close(rows.attacked_log_quote,quotes[index,selected],'Attacked quotation')
                target=evaluation.target_log.to_numpy();honest=quotes[:,0];attack=quotes[index,selected]
                calculated={'honest_absolute_error':abs(np.expm1(honest)-np.expm1(target)),
                    'attacked_absolute_error':abs(np.expm1(attack)-np.expm1(target)),
                    'positive_log_inflation':np.maximum(attack-honest,0),'honest_signed_log_bias':honest-target,
                    'seller_withholds':selected!=0,'hidden_fields':masks[selected].sum(axis=1)}
                failed=stored['status'][m]!='solved' if m else np.zeros(valid.shape,bool)
                calculated.update(honest_fallback=failed[:,0],attacked_fallback=failed[index,selected])
                mileage=groups[0][0];imputed=stored['imputation'][m,:,:,mileage]
                outside=((imputed<0)|(imputed>1))&(np.isnan(x_eval[:,mileage])[:,None]|masks[:,0][None])
                calculated.update(honest_imputation_outside_training_range=outside[:,0],attacked_imputation_outside_training_range=outside[index,selected])
                for column,values in calculated.items():close(rows[column],values,'Per-listing '+column)
                report=summary[summary.method==name].iloc[0]
                metrics={'honest_mae':'honest_absolute_error','attacked_mae':'attacked_absolute_error',
                    'mean_positive_log_inflation':'positive_log_inflation','honest_signed_log_bias':'honest_signed_log_bias',
                    'hiding_fraction':'seller_withholds','mean_hidden_fields':'hidden_fields',
                    'honest_fallback_fraction':'honest_fallback','attacked_fallback_fraction':'attacked_fallback',
                    'honest_imputation_outside_training_range_fraction':'honest_imputation_outside_training_range',
                    'attacked_imputation_outside_training_range_fraction':'attacked_imputation_outside_training_range'}
                for metric,column in metrics.items():close(report[metric],np.mean(calculated[column]),'Summary '+metric)
                natural=evaluation.loc[:,list(ACTIONS)].isna().any(axis=1).to_numpy()
                close(rows.naturally_missing_optional,natural,'Natural missingness cohort')
                expected=float(np.mean(calculated['honest_absolute_error'][natural])) if natural.any() else np.nan
                close(report.naturally_missing_honest_mae,expected,'Naturally missing honest MAE')
                require(report.budget==0 and report.queries==0 and report.n==len(evaluation) and report.fit_rows==len(fitting),'No-query/count scope')
                for status,count in Counter(stored['status'][m][valid]).items():
                    coverage.append({'dataset':dataset,'method':name,'status':status,'legal_states':count})
                audited.append(report.to_dict())
            for name,digest in done['files'].items():require(sha(folder/name)==digest,'Dataset changed during audit')
    pd.testing.assert_frame_equal(pd.DataFrame(audited).reset_index(drop=True),root_summary,check_dtype=False,rtol=1e-8,atol=1e-8)
    pd.DataFrame(audited).to_csv(output/'audited_summary.csv',index=False)
    pd.DataFrame(coverage).to_csv(output/'solver_coverage.csv',index=False)
    require(len(audited)==complete['cells'],'Complete audited generation')
    write_json(output/'completion.json',{'status':'completed','cells':len(audited),'oracle_checks':oracle_checks,
               'execution_smoke':manifest['execution_smoke'],'source_completion_sha256':sha(run/'completion.json'),
               'source_manifest_sha256':sha(run/'manifest.json'),'auditor_sha256':sha(Path(__file__)),
               'oracle_sha256':sha(Path(__file__).with_name('grouped_smi_interval_oracle.py')),
               'files':{p.name:sha(p) for p in output.iterdir() if p.is_file()},
               'scope':'all public state predictions; independent categorical enumeration/scalar interval optima; fitting cohorts and exact no-query attacks; separate LP cross-check tests'})
    print(f'AUDITED GROUPED SMI GENERATION {output}',flush=True)


if __name__=='__main__':main()
