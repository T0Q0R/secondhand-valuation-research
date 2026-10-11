"""Bind all comparator, transfer and resource rows to complete audit receipts."""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from analyze_nested import read,require,sha
from backfill_development_tables import replace_table
from run_all import write_json

def checked(folder,receipt_name,files_key):
    done=read(folder/receipt_name);require(done['status']=='completed','Completed audit')
    for name,digest in done[files_key].items():require(sha(folder/name)==digest,'Audit artifact binding')
    return done

def main():
    parser=argparse.ArgumentParser()
    for name in ('aco','grouped','resource','resource-audit','paper','receipt'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();require(not args.receipt.exists(),'Fresh paper receipt')
    ac=checked(args.aco,'analysis_completion.json','outputs');gr=checked(args.grouped,'completion.json','files')
    ra=checked(args.resource_audit,'completion.json','files');checked(args.resource,'completion.json','outputs')
    require(ac['full_parent_matrix'] and ac['audited_cells']==144,'Complete ACO')
    require(gr['cells']==12 and not gr['execution_smoke'],'Complete grouped SMI')
    require(ra['resource_completion_sha256']==sha(args.resource/'completion.json') and ra['public_batches']==360,'Complete resource audit')
    names={'synthetic':'Synthetic','jucars':'JUCars','mucars':'MUCars'};evidence=[]
    grouped=pd.read_csv(args.grouped/'audited_summary.csv');rows=[]
    for dataset,label in names.items():
        methods=[('linear_svr_median_mode','Median/mode SVR'),('grouped_smi_free_with_fallback','SMI / free'),
                 ('grouped_smi_nonnegative_with_fallback','SMI / nonnegative'),('grouped_smi_unit_box_with_fallback','SMI / unit box')]
        for i,(method,title) in enumerate(methods):
            cell=grouped[(grouped.dataset==dataset)&(grouped.method==method)]
            require(len(cell)==1 and cell.iloc[0].n==1000,'Deterministic SMI cell');r=cell.iloc[0]
            rows.append(f'{label if i==0 else ""} & {title} & {int(r.fit_rows)} & {r.honest_mae:.2f} & '
                f'{r.attacked_mae:.2f} & {r.mean_positive_log_inflation:.5f} & '
                f'{100*r.honest_fallback_fraction:.1f} & {100*r.attacked_fallback_fraction:.1f}\\\\')
            evidence.append({'table':'grouped_smi',**r.to_dict()})
        if dataset!='mucars':rows.append('\\midrule')
    target=args.paper/'sections/direct_comparator_results.tex';text=replace_table(target.read_text(),'tab:grouped_smi',rows)
    aco=pd.read_csv(args.aco/'rechecked_summary.csv');rows=[]
    for dataset,label in names.items():
        for i,(price,title) in enumerate([('masking','Mask'),('robust','Robust')]):
            for j,k in enumerate((10,25,50)):
                cell=aco[(aco.dataset==dataset)&(aco.method==f'{price}_aco1_k{k}')&(aco.budget==.1)]
                require(len(cell)==3 and set(cell.seed)=={13,42,2026},'Complete ACO seeds')
                r=cell[['mean_positive_log_inflation','clean_mae','attack_mae']].mean()
                rows.append(f'{label if i==j==0 else ""} & {title if j==0 else ""} & {k} & '
                    f'{r.mean_positive_log_inflation:.5f} & {r.clean_mae:.2f} & {r.attack_mae:.2f}\\\\')
                evidence.append({'table':'aco','dataset':dataset,'price':price,'k':k,**r.to_dict()})
        if dataset!='mucars':rows.append('\\midrule')
    target.write_text(replace_table(text,'tab:aco_primary',rows))
    summary=pd.read_csv(args.resource_audit/'shared_report_summaries.csv')
    pipeline=pd.read_csv(args.resource_audit/'rechecked_pipeline_summary.csv');models=pd.read_csv(args.resource/'model_bindings.csv')
    methods={'masking_benefit':'Mask + benefit','robust_no_feedback':'Robust, no feedback',
             'sav_benefit_head':'SAV + benefit output','sav_val':'SAV-Val'};shared=[];runtime=[]
    for dataset,label in names.items():
        for i,(method,title) in enumerate(methods.items()):
            cell=summary[(summary.dataset==dataset)&(summary.method==method)]
            require(len(cell)==3 and set(cell.seed)=={13,42,2026},'Complete transfer seeds')
            r=cell[['mean_positive_log_inflation','attack_mae']].mean();source=label if i==0 else ''
            shared.append(f'{source} & {title} & {r.mean_positive_log_inflation:.5f} & {r.attack_mae:.2f}\\\\')
            evidence.append({'table':'shared_reports','dataset':dataset,'method':method,**r.to_dict()})
            cell=pipeline[(pipeline.dataset==dataset)&(pipeline.method==method)]
            require(len(cell)==1 and cell.iloc[0].observations==600,'Complete online repetitions');r=cell.iloc[0]
            size=models[(models.dataset==dataset)&(models.method==method)]
            require(len(size)==3 and set(size.seed)=={13,42,2026},'Complete model-size seeds')
            mib=float(size.serialized_model_and_head_bytes.mean()/2**20)
            runtime.append(f'{source} & {title} & {1000*r["median"]:.2f} & {1000*r.p90:.2f} & {mib:.2f}\\\\')
            evidence.append({'table':'online_resources','dataset':dataset,'method':method,
                'median_ms':1000*r['median'],'p90_ms':1000*r.p90,'model_head_mib':mib})
        if dataset!='mucars':shared.append('\\midrule');runtime.append('\\midrule')
    target=args.paper/'sections/resource_transfer_results.tex'
    target.write_text(replace_table(replace_table(target.read_text(),'tab:shared_reports',shared),'tab:online_resources',runtime))
    write_json(args.receipt,{'audit_receipts':{key:sha(path) for key,path in {
        'aco':args.aco/'analysis_completion.json','grouped':args.grouped/'completion.json',
        'resource':args.resource/'completion.json','resource_audit':args.resource_audit/'completion.json'}.items()},
        'evidence':evidence,'source_sha256':sha(Path(__file__)),
        'sections':{name:sha(args.paper/'sections'/name) for name in ['direct_comparator_results.tex','resource_transfer_results.tex']}})
    print('Bound 12 grouped-SMI, 18 ACO, 12 shared-report and 12 resource rows.',flush=True)

if __name__=='__main__':main()
