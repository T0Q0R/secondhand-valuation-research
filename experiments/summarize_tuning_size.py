"""All-budget fixed/tuned contrasts from a captured independent source audit."""
from __future__ import annotations

import argparse
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from analyze_nested import conditional_cluster_interval,contrast,read,require,sha
from run_all import write_json


METHODS=('robust_no_feedback','sav_val','sav_benefit_head')
PAIRS=[(f'{kind}__sav_val',f'{kind}__{ref}') for kind in ('fixed','tuned')
       for ref in ('robust_no_feedback','sav_benefit_head')]
PAIRS += [(f'tuned__{method}',f'fixed__{method}') for method in METHODS]
METRICS=('positive_log_inflation','clean_absolute_error','attack_absolute_error')


def paired_row(data,ours,reference,metric,budget,repetitions,context):
    paired=contrast(data,reference,ours=ours,metric=metric,budget=budget)
    seeds=sorted(data.seed.unique())
    require((paired.groupby('listing_id').seed.nunique()==len(seeds)).all(),'Common evaluated cohort across seeds')
    require((paired.groupby('listing_id').batch.nunique()==1).all(),'Shared batch identity')
    average=paired.groupby(['listing_id','batch'],as_index=False).delta.mean()
    interval=conditional_cluster_interval(average,repetitions,906061)
    selected=data[data.budget==budget]
    own_mean=float(selected[selected.method==ours][metric].mean())
    ref_mean=float(selected[selected.method==reference][metric].mean())
    return {**context,'ours':ours,'reference':reference,'metric':metric,'budget':budget,
            'ours_mean':own_mean,'reference_mean':ref_mean,
            'relative_reduction_percent':100*(ref_mean-own_mean)/ref_mean if ref_mean>0 else None,
            'completed_training_seeds':len(seeds),**interval,
            'interval_scope':'shared-batch sampling conditional on fitted models; seed-averaged paired contrast; unadjusted exploratory'}


def main():
    parser=argparse.ArgumentParser()
    for name in ('run','audit','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run,audit,output=args.run.resolve(),args.audit.resolve(),args.output.resolve()
    done=read(audit/'completion.json');binding=read(audit/'input_binding.json');manifest=read(run/'manifest.json')
    require(done['status']=='completed' and sha(audit/'input_binding.json')==done['input_binding_sha256'],'Completed independent audit')
    require(sha(run/'manifest.json')==binding['manifest_sha256'],'Audited source manifest')
    require(not output.exists(),'Fresh statistical generation required')
    output.mkdir(parents=True);(output/'source_snapshot.py').write_bytes(Path(__file__).read_bytes())
    outcomes={};summaries=[];membership={};seeds={}
    for case in binding['cases']:
        dataset,size,seed=case['dataset'],case['size'],case['seed']
        folder=run/dataset/f'size-{size}'/f'seed-{seed}'
        require(sha(folder/'evaluation_completion.json')==case['receipt_sha256'],'Captured case unchanged')
        receipt=read(folder/'evaluation_completion.json')
        for name in ('outcomes.csv.gz','summary.csv','outer_assignments.csv'):
            require(sha(folder/name)==receipt['files'][name],'Audited artifact unchanged')
        outcomes[(dataset,size,seed)]=pd.read_csv(folder/'outcomes.csv.gz')
        summaries.append(pd.read_csv(folder/'summary.csv'))
        membership[(dataset,size,seed)]=set(pd.read_csv(folder/'outer_assignments.csv').listing_id)
        seeds.setdefault((dataset,size),[]).append(seed)
    summary=pd.concat(summaries,ignore_index=True)
    require(len(summary)==done['cells'],'Audited cell count')
    summary.to_csv(output/'audited_summary.csv',index=False)
    comparisons=[];size_effects=[]
    config=manifest['config'];repetitions=config['bootstrap_repetitions']
    for (dataset,size),available in sorted(seeds.items()):
        data=pd.concat([outcomes[(dataset,size,seed)] for seed in available],ignore_index=True)
        context={'dataset':dataset,'train_cap':size,'all_scheduled_seeds_complete':set(available)==set(config['seeds'])}
        for ours,reference in PAIRS:
            for budget in config['budgets']:
                for metric in METRICS:comparisons.append(paired_row(data,ours,reference,metric,budget,repetitions,context))
    for dataset in config['datasets']:
        caps=sorted(size for d,size in seeds if d==dataset)
        for small,large in combinations(caps,2):
            shared=sorted(set(seeds[(dataset,small)])&set(seeds[(dataset,large)]))
            if not shared:continue
            for seed in shared:
                require(membership[(dataset,small,seed)]<membership[(dataset,large,seed)],'Nested capped training membership')
            for method in sorted(summary.method.unique()):
                frames=[]
                for size,tag in [(small,'smaller'),(large,'larger')]:
                    for seed in shared:
                        frame=outcomes[(dataset,size,seed)]
                        frame=frame[frame.method==method].copy();frame['method']=tag;frames.append(frame)
                data=pd.concat(frames,ignore_index=True)
                for budget in config['budgets']:
                    for metric in METRICS:
                        context={'dataset':dataset,'method':method,'smaller_cap':small,'larger_cap':large,
                                 'all_scheduled_seeds_complete':set(shared)==set(config['seeds'])}
                        size_effects.append(paired_row(data,'larger','smaller',metric,budget,repetitions,context))
    pd.DataFrame(comparisons).to_csv(output/'method_contrasts.csv',index=False)
    pd.DataFrame(size_effects).to_csv(output/'size_contrasts.csv',index=False)
    pd.DataFrame(comparisons).query('budget == .1').to_csv(output/'primary_method_contrasts.csv',index=False)
    write_json(output/'completion.json',{'status':'completed','cells':len(summary),'method_contrasts':len(comparisons),
        'size_contrasts':len(size_effects),'all_scheduled_cases_completed':done['all_scheduled_cases_completed'],
        'execution_smoke':manifest['execution_smoke'],'audit_completion_sha256':sha(audit/'completion.json'),
        'input_binding_sha256':sha(audit/'input_binding.json'),'source_sha256':sha(Path(__file__)),
        'files':{p.name:sha(p) for p in output.iterdir() if p.is_file()},
        'scope':'all fixed/tuned references and retained sizes/budgets; no evaluation-best selection; conditional exploratory intervals'})
    print(f'COMPLETED TUNING-SIZE CONTRASTS {output}',flush=True)


if __name__=='__main__':main()
