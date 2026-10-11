"""Bind the completed ordinary-benefit reference table to its audit."""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from analyze_nested import read, require, sha
from backfill_development_tables import replace_table
from run_all import write_json

def main():
    parser=argparse.ArgumentParser()
    for name in ('audit','source','receipt'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    require(not args.receipt.exists(),'Fresh manuscript receipt')
    done=read(args.audit/'completion.json')
    require(done['status']=='completed' and done['cells']==54,'All reference cells audited')
    for name,digest in done['files'].items():
        require(sha(args.audit/name)==digest,'Audit output binding')
    summary=pd.read_csv(args.audit/'audited_summary.csv')
    contrasts=pd.read_csv(args.audit/'paired_contrasts.csv')
    rows=[];evidence=[]
    for dataset,label in {'synthetic':'Synthetic','jucars':'JUCars','mucars':'MUCars'}.items():
        cell=summary[(summary.dataset==dataset)&(summary.budget==.1)]
        require(len(cell)==3 and set(cell.seed)=={13,42,2026},'All three reference seeds')
        require((cell.method=='robust_benefit_no_feedback').all(),'Correct head output')
        delta=contrasts[(contrasts.dataset==dataset)&(contrasts.budget==.1)&
            (contrasts.metric=='positive_log_inflation')]
        require(len(delta)==1,'Unique paired primary contrast');d=delta.iloc[0]
        mean=cell.mean_positive_log_inflation.mean();sd=cell.mean_positive_log_inflation.std(ddof=1)
        require(abs(mean-d.reference_mean)<1e-12,'Summary and paired reference agree')
        rows.append(f'{label} & {mean:.5f} ({sd:.5f}) & {cell.clean_mae.mean():.2f} & '
            f'{cell.attack_mae.mean():.2f} & ${d.difference:.5f}\\;[{d.lower:.5f},{d.upper:.5f}]$\\\\')
        evidence.append({'dataset':dataset,'reference_inflation':mean,'seed_sd':sd,
            'honest_mae':cell.clean_mae.mean(),'attack_mae':cell.attack_mae.mean(),**d.to_dict()})
    args.source.write_text(replace_table(args.source.read_text(),'tab:robust_benefit_reference',rows))
    write_json(args.receipt,{'audit_completion_sha256':sha(args.audit/'completion.json'),
        'parent_binding':done['parent_binding'],'evidence':evidence,'script_sha256':sha(Path(__file__)),
        'source_sha256':sha(args.source),'scope':'all three-seed ordinary-benefit reference means at primary capacity'})
    print('Bound three complete ordinary-benefit reference rows.',flush=True)

if __name__=='__main__':main()
