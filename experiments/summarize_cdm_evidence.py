"""Seed-averaged paired batch intervals for independently audited CDM cells.

All fixed-rule contrasts and budgets are retained; no evaluation-best rule is
selected. Bootstrap units are the shared evaluation batches, not model seeds.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from analyze_nested import read,require,sha
from run_all import write_json


METRICS=['positive_expected_log_inflation','expected_realized_positive_log_inflation',
         'expected_attack_absolute_error','best_response_regret_log']


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--audit',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run,audit,output=args.run.resolve(),args.audit.resolve(),args.output.resolve()
    done,binding=read(audit/'completion.json'),read(audit/'audit_binding.json')
    require(done['status']=='completed','Independent audit required')
    require(binding['run_manifest_sha256']==sha(run/'manifest.json'),'Audited run binding')
    manifest=read(run/'manifest.json')
    require(not output.exists(),'Fresh statistical output required')
    output.mkdir(parents=True)
    (output/'source_snapshot.py').write_bytes(Path(__file__).read_bytes())
    outcomes={}
    seeds_by_source={}
    for dataset,seed in binding['frozen_completed_pairs']:
        require(sha(run/dataset/f'seed-{seed}'/'completion.json')==binding['pair_receipt_hashes'][f'{dataset}/seed-{seed}'],'Pair receipt changed')
        seeds_by_source.setdefault(dataset,[]).append(seed)
        for price in manifest['prices']:
            for budget in manifest['config']['budgets']:
                folder=run/dataset/f'seed-{seed}'/price/f'budget-{int(round(budget*10000)):04d}'
                receipt=read(folder/'completion.json')
                for method in [*manifest['policies'],'uniform','cdm']:
                    path=folder/method/'outcomes.csv.gz'
                    require(sha(path)==receipt['files'][str(path.relative_to(folder))],'Outcome binding')
                    outcomes[(dataset,seed,price,budget,method)]=pd.read_csv(path)
                solution=read(folder/'fit/solution.json')
                selected=solution['best_training_pure_policy']
                outcomes[(dataset,seed,price,budget,'training_selected_pure')]=outcomes[(dataset,seed,price,budget,selected)]
    rows=[]
    references=[*manifest['policies'],'uniform','training_selected_pure']
    rng=np.random.default_rng(904061)
    repetitions=manifest['config']['bootstrap_repetitions']
    for dataset,seeds in seeds_by_source.items():
        for price in manifest['prices']:
            for budget in manifest['config']['budgets']:
                for reference in references:
                    paired=[]
                    for seed in seeds:
                        cdm=outcomes[(dataset,seed,price,budget,'cdm')]
                        ref=outcomes[(dataset,seed,price,budget,reference)]
                        require(cdm.listing_id.tolist()==ref.listing_id.tolist(),'Paired cohort')
                        require(cdm.batch.tolist()==ref.batch.tolist(),'Shared batch membership')
                        delta=ref[METRICS].to_numpy()-cdm[METRICS].to_numpy()
                        frame=pd.DataFrame(delta,columns=METRICS)
                        frame['listing_id']=cdm.listing_id
                        frame['batch']=cdm.batch
                        paired.append(frame)
                    aligned=paired[0][['listing_id','batch']].copy()
                    require(all(p.listing_id.tolist()==aligned.listing_id.tolist() for p in paired),'Same evaluation cohort across seeds')
                    for metric in METRICS:
                        aligned[metric]=np.mean([p[metric].to_numpy() for p in paired],axis=0)
                    groups=[g for _,g in aligned.groupby('batch',sort=True)]
                    sampled=rng.integers(0,len(groups),size=(repetitions,len(groups)))
                    sizes=np.array([len(g) for g in groups])
                    for metric in METRICS:
                        sums=np.array([g[metric].sum() for g in groups])
                        estimates=sums[sampled].sum(axis=1)/sizes[sampled].sum(axis=1)
                        low,high=np.quantile(estimates,[.025,.975])
                        cdm_mean=np.mean([outcomes[(dataset,s,price,budget,'cdm')][metric].mean() for s in seeds])
                        ref_mean=np.mean([outcomes[(dataset,s,price,budget,reference)][metric].mean() for s in seeds])
                        rows.append({'dataset':dataset,'price':price,'budget':budget,'reference':reference,'metric':metric,
                                     'cdm_mean':float(cdm_mean),'reference_mean':float(ref_mean),
                                     'paired_improvement':float(aligned[metric].mean()),'lower':float(low),'upper':float(high),
                                     'relative_reduction_percent':float(100*(ref_mean-cdm_mean)/ref_mean) if ref_mean>0 else None,
                                     'completed_training_seeds':len(seeds),'clusters':len(groups),
                                     'all_scheduled_source_seeds_complete':set(seeds)==set(manifest['parent_config']['seeds']),
                                     'interval_scope':'shared evaluation batches conditional on fitted models; seed-averaged paired contrast; unadjusted exploratory'})
    results=pd.DataFrame(rows)
    results.to_csv(output/'paired_contrasts.csv',index=False)
    primary=results[(results.budget==.1)&(results.metric=='positive_expected_log_inflation')]
    primary.to_csv(output/'primary_contrasts.csv',index=False)
    (output/'report.md').write_text('CDM conditional development contrasts\n\nAll fixed rules, training-selected pure rules, uniform mixing and all declared capacities are retained. Positive differences favor CDM. Intervals resample shared batches once after averaging paired listing differences over the available fitted seeds. Seeds are not independent sampling units; partial sources are explicitly marked. The utility is transformed log quotation, not expected currency. These are unadjusted exploratory intervals and do not establish universal incentive compatibility or completed-paper novelty.\n\n'+primary.to_string(index=False)+'\n')
    write_json(output/'completion.json',{'status':'completed','contrast_rows':len(rows),
               'audit_completion_sha256':sha(audit/'completion.json'),'audit_binding_sha256':sha(audit/'audit_binding.json'),
               'source_sha256':sha(Path(__file__)),'execution_smoke':manifest['execution_smoke'],
               'files':{p.name:sha(p) for p in output.iterdir() if p.is_file()},
               'all_scheduled_pairs_completed':done['all_scheduled_pairs_completed'],
               'scope':'all retained fixed references/budgets; conditional shared-batch intervals; no tuned evaluation-best control'})
    print(f'COMPLETED CDM CONTRASTS {output}',flush=True)


if __name__=='__main__':main()
