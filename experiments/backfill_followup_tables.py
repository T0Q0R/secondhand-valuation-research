"""Mechanically bind bounded CDM and tuning/size manuscript tables to receipts."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from analyze_nested import read,require,sha
from backfill_development_tables import replace_table
from run_all import write_json


def checked(path,name):
    done=read(path/'completion.json')
    require(done['status']=='completed' and not done['execution_smoke'],'Complete source statistics required')
    require(sha(path/name)==done['files'][name],'Statistical artifact binding')
    return pd.read_csv(path/name),done


def main():
    parser=argparse.ArgumentParser()
    for name in ('cdm','tuning','paper','receipt'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--caps',nargs='+',type=int,choices=(1000,2500,5000),default=[1000,2500])
    parser.add_argument('--tuning-sources',nargs='+',choices=('synthetic','jucars','mucars'),default=['synthetic'])
    parser.add_argument('--cdm-sources',nargs='+',choices=('synthetic','jucars','mucars'),default=['synthetic','jucars'])
    args=parser.parse_args()
    require(not args.receipt.exists(),'Fresh mapping receipt required')
    require(len(set(args.caps))==len(args.caps),'Unique training caps')
    cdm,cdm_done=checked(args.cdm,'primary_contrasts.csv')
    tuning,tuning_done=checked(args.tuning,'audited_summary.csv')
    contrasts,_=checked(args.tuning,'primary_method_contrasts.csv')
    source_names={'synthetic':'Synthetic','jucars':'JUCars','mucars':'MUCars'}
    names={dataset:source_names[dataset] for dataset in args.cdm_sources}
    cdm_rows=[];evidence=[]
    for dataset,label in names.items():
        for j,price in enumerate(('masking','robust')):
            group=cdm[(cdm.dataset==dataset)&(cdm.price==price)]
            require((group.completed_training_seeds==3).all() and group.all_scheduled_source_seeds_complete.all(),'Complete CDM source seeds')
            require((group.budget==.1).all() and (group.metric=='positive_expected_log_inflation').all(),'CDM primary metric/capacity')
            values={reference:group[group.reference==reference].iloc[0] for reference in ('risk','benefit','uniform')}
            require(all(len(group[group.reference==reference])==1 for reference in values),'Unique CDM table reference')
            own=values['risk'].cdm_mean
            require(all(abs(row.cdm_mean-own)<1e-12 for row in values.values()),'Consistent CDM mean')
            row=values['risk'];source=label if j==0 else ''
            estimator='Mask-aware' if price=='masking' else 'Robust'
            cdm_rows.append(f'{source} & {estimator} & {own:.5f} & {row.reference_mean:.5f} & {values["benefit"].reference_mean:.5f} & {values["uniform"].reference_mean:.5f} & $[{row.lower:.5f},{row.upper:.5f}]$\\\\')
            evidence.append({'table':'cdm','dataset':dataset,'price':price,'cdm_mean':own,
                             'risk_mean':row.reference_mean,'benefit_mean':values['benefit'].reference_mean,
                             'uniform_mean':values['uniform'].reference_mean,'lower':row.lower,'upper':row.upper})
        if dataset!=args.cdm_sources[-1]:cdm_rows.append('\\midrule')
    target=args.paper/'sections/cdm_development_results.tex'
    target.write_text(replace_table(target.read_text(),'tab:cdm_development',cdm_rows))
    labels={'robust_no_feedback':'Robust, no feedback','sav_benefit_head':'SAV + benefit output','sav_val':'SAV-Val'}
    tuning_rows=[]
    completed=[];unfinished=[]
    for dataset in args.tuning_sources:
        for size in args.caps:
            own=tuning[(tuning.dataset==dataset)&(tuning.train_cap==size)]
            if set(own.seed)!={13,42,2026}:
                unfinished.append([dataset,size]);continue
            require(len(own)==108,'All six variants, six budgets, three seeds')
            if completed:tuning_rows.append('\\midrule')
            completed.append([dataset,size])
            for j,(method,label) in enumerate(labels.items()):
                cells=own[(own.method==f'tuned__{method}')&(own.budget==.1)]
                require(set(cells.seed)=={13,42,2026} and len(cells)==3,'Complete tuning source/size seeds')
                values=cells[['mean_positive_log_inflation','clean_mae','attack_mae']].mean()
                source_label=source_names[dataset] if j==0 else '';size_label=str(size) if j==0 else ''
                tuning_rows.append(f'{source_label} & {size_label} & {label} & {values.mean_positive_log_inflation:.5f} & {values.clean_mae:.2f} & {values.attack_mae:.2f}\\\\')
                evidence.append({'table':'tuning','dataset':dataset,'size':size,'method':method,**values.to_dict()})
    target=args.paper/'sections/equal_tuning_development_results.tex'
    text=replace_table(target.read_text(),'tab:equal_tuning_development',tuning_rows)
    retained_cells=sum(len(tuning[(tuning.dataset==dataset)&(tuning.train_cap==size)])
                       for dataset,size in completed)
    full_scope=(tuning_done['all_scheduled_cases_completed'] and
                retained_cells==972 and len(completed)==9 and not unfinished)
    heading=(r'\subsection{Equal-allowance tuning and size retraining}' if full_scope
             else r'\subsection{Equal-allowance tuning and partial size retraining}')
    scope_text=('All nine scheduled source/cap cohorts and all 972 evaluation cells '
                'are independently audited. ' if full_scope else
                'Every captured complete cohort appears below; unfinished cohorts are excluded explicitly. '
                'These counts do not establish completion of the 972-cell study. ')
    if full_scope:
        text=text.replace('The remaining public-source size cases remain under execution.',
                          'All nine scheduled source/cap cohorts are complete and independently audited.')
    table_start=text.index('\\begin{table*}')
    table_end=text.index('\\end{table*}')+len('\\end{table*}')
    intro=(heading+'\n'
           f'The independently audited follow-up retains {len(completed)} complete three-seed '
           f'source/cap cohorts and {retained_cells} final evaluation cells. '
           +scope_text+
           r'Table~\ref{tab:equal_tuning_development} retains the three tuned methods at the '
           'primary capacity. Fixed-weight versions and every preset capacity remain in the '
           'associated audit and contrast outputs.\n\n')
    narrative=[];paired_evidence=[]
    for dataset,size in completed:
        sentences=[]
        for reference,label in [('robust_no_feedback','static suppression-output control'),
                                ('sav_benefit_head','feedback benefit-output variant')]:
            pair=contrasts[(contrasts.dataset==dataset)&(contrasts.train_cap==size)&
                           (contrasts.ours=='tuned__sav_val')&
                           (contrasts.reference==f'tuned__{reference}')]
            metrics=('positive_log_inflation','clean_absolute_error','attack_absolute_error')
            require(len(pair)==3 and set(pair.metric)==set(metrics) and
                    pair.all_scheduled_seeds_complete.all() and
                    (pair.completed_training_seeds==3).all(),'Complete paired tuning metrics')
            values={metric:pair[pair.metric==metric].iloc[0] for metric in metrics}
            inflation=values['positive_log_inflation'];gain=inflation.relative_reduction_percent
            honest=-values['clean_absolute_error'].relative_reduction_percent
            attack=-values['attack_absolute_error'].relative_reduction_percent
            direction='lower' if gain>=0 else 'higher'
            intervals='exclude zero' if all(values[m].lower>0 or values[m].upper<0
                                            for m in metrics[1:]) else 'include zero in at least one metric'
            sentences.append(
                f'Against the tuned {label}, inflation is {abs(gain):.2f}\\% {direction}, '
                f'with reference-minus-SAV interval $[{inflation.lower:.5f},{inflation.upper:.5f}]$. '
                f'Honest and attacked MAE changes are {honest:+.2f}\\% and {attack:+.2f}\\%; '
                f'their paired error intervals {intervals}.')
            for metric,value in values.items():
                paired_evidence.append({'dataset':dataset,'size':size,'reference':reference,
                    'metric':metric,**{key:float(value[key]) for key in
                    ('ours_mean','reference_mean','relative_reduction_percent','difference','lower','upper')}})
        narrative.append(f'The complete {source_names[dataset]} cohort uses configured cap {size:,}. '+
                         ' '.join(sentences))
    final_scope=('Every scheduled source/cap cohort, negative finding and honest-error '
                 'tradeoff is retained.\n' if full_scope else
                 'Final scope requires every scheduled source/cap cohort, negative '
                 'findings and honest-error tradeoffs.\n')
    conclusion=('Equal allowances do not establish a consistent full-method advantage. '
        'Tuning minimizes honest plus attacked squared log loss; a chosen setting can improve '
        'accuracy while increasing inflation. No objective, trial grid, primary capacity or '
        'reference identity was changed after observing outcomes. These conditional, unadjusted '
        'intervals concern fitted models and historical validation batches. '+final_scope)
    target.write_text(intro+text[table_start:table_end]+'\n\n'+'\n\n'.join(narrative)+'\n\n'+conclusion)
    write_json(args.receipt,{'cdm_completion_sha256':sha(args.cdm/'completion.json'),
        'tuning_completion_sha256':sha(args.tuning/'completion.json'),'evidence':evidence,
        'completed_tuning_source_caps':completed,'unfinished_tuning_source_caps':unfinished,
        'all_scheduled_tuning_cases_in_manuscript':full_scope,
        'retained_tuning_cells':retained_cells,
        'primary_tuning_contrasts':paired_evidence,
        'source_sha256':sha(Path(__file__)),'sections':{name:sha(args.paper/'sections'/name) for name in
        ('cdm_development_results.tex','equal_tuning_development_results.tex')},
        'scope':f'{2 * len(names)} three-seed CDM rows and {3 * len(completed)} three-seed tuning rows; all completed source/cap cohorts, incomplete cohorts explicitly excluded'})
    print(f'Backfilled {2 * len(names)} CDM rows and {3 * len(completed)} tuning/size rows from hash-bound source statistics.',flush=True)


if __name__=='__main__':main()
