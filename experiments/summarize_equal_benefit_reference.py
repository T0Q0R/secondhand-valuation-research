"""Paired all-budget benefit-reference contrasts from independently audited cases."""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from analyze_nested import read,require,sha
from summarize_tuning_size import METRICS,paired_row
from run_all import write_json

REFERENCE='robust_benefit_no_feedback'
PAIRS=[(f'{role}__sav_val',f'{role}__{REFERENCE}') for role in ('fixed','tuned')]
PAIRS.extend((f'{role}__{REFERENCE}',f'{role}__robust_no_feedback') for role in ('fixed','tuned'))
PAIRS.append((f'tuned__{REFERENCE}',f'fixed__{REFERENCE}'))

def main():
    parser=argparse.ArgumentParser()
    for name in ('run','audit','tuning-audit','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run,audit,tuning_audit,output=[getattr(args,n).resolve() for n in ('run','audit','tuning_audit','output')]
    done=read(audit/'completion.json');inputs=read(audit/'input_binding.json');manifest=read(run/'manifest.json')
    require(done['status']=='completed','Complete extension audit')
    for name,digest in done['files'].items():require(sha(audit/name)==digest,'Audited extension output binding')
    require(sha(run/'manifest.json')==inputs['manifest_sha256'],'Extension generation binding')
    parent_done=read(tuning_audit/'completion.json');parent_inputs=read(tuning_audit/'input_binding.json')
    require(parent_done['status']=='completed' and sha(tuning_audit/'input_binding.json')==parent_done['input_binding_sha256'],
            'Completed strong-control tuning audit')
    require(parent_inputs['binding']==manifest['tuning_binding'],'Same independently audited tuning parent')
    parent_cases={(c['dataset'],c['size'],c['seed']):c for c in parent_inputs['cases']}
    require(not output.exists(),'Fresh contrast output');output.mkdir(parents=True)
    (output/'source_snapshot.py').write_bytes(Path(__file__).read_bytes())
    tuning=Path(manifest['tuning_path']);groups={};summaries=[];bindings=[]
    for case in inputs['cases']:
        dataset,size,seed=case['dataset'],case['size'],case['seed'];key=(dataset,size,seed)
        require(key in parent_cases,'Every receiving comparator independently audited')
        folder=run/dataset/f'size-{size}'/f'seed-{seed}';parent=tuning/dataset/f'size-{size}'/f'seed-{seed}'
        require(sha(folder/'evaluation_completion.json')==case['receipt_sha256'],'Audited reference case unchanged')
        require(sha(parent/'evaluation_completion.json')==parent_cases[key]['receipt_sha256'],'Audited comparator case unchanged')
        reference_done,parent_case_done=read(folder/'evaluation_completion.json'),read(parent/'evaluation_completion.json')
        for directory,record in [(folder,reference_done),(parent,parent_case_done)]:
            for name in ('outcomes.csv.gz','summary.csv'):
                require(sha(directory/name)==record['files'][name],'Audited outcome/summary binding')
        data=pd.concat([pd.read_csv(parent/'outcomes.csv.gz'),pd.read_csv(folder/'outcomes.csv.gz')],ignore_index=True)
        require(not data.duplicated(['method','budget','listing_id']).any(),'Disjoint method identities')
        for _,cell in data.groupby(['method','budget']):
            require(cell.listing_id.tolist()==data[(data.method==f'fixed__{REFERENCE}')&(data.budget==manifest['config']['budgets'][0])].listing_id.tolist(),
                    'Every policy uses the same ordered validation cohort')
        groups.setdefault((dataset,size),[]).append(data)
        summaries.extend([pd.read_csv(parent/'summary.csv'),pd.read_csv(folder/'summary.csv')])
        bindings.append({'dataset':dataset,'size':size,'seed':seed,'reference_receipt_sha256':case['receipt_sha256'],
            'comparator_receipt_sha256':parent_cases[key]['receipt_sha256']})
    comparisons=[];config=manifest['config']
    for (dataset,size),frames in sorted(groups.items()):
        data=pd.concat(frames,ignore_index=True);seeds=set(data.seed)
        context={'dataset':dataset,'train_cap':size,'all_scheduled_seeds_complete':seeds==set(config['seeds'])}
        for ours,reference in PAIRS:
            for budget in config['budgets']:
                for metric in METRICS:
                    comparisons.append(paired_row(data,ours,reference,metric,budget,config['bootstrap_repetitions'],context))
    pd.concat(summaries,ignore_index=True).to_csv(output/'audited_joint_summary.csv',index=False)
    pd.DataFrame(comparisons).to_csv(output/'paired_contrasts.csv',index=False)
    pd.DataFrame(comparisons).query('budget == .1').to_csv(output/'primary_contrasts.csv',index=False)
    write_json(output/'completion.json',{'status':'completed','execution_smoke':manifest['execution_smoke'],
        'cases':len(bindings),'reference_cells':done['cells'],'contrasts':len(comparisons),
        'all_scheduled_cases_complete':done['all_scheduled_cases_complete'],'case_bindings':bindings,
        'reference_audit_sha256':sha(audit/'completion.json'),'tuning_audit_sha256':sha(tuning_audit/'completion.json'),
        'source_sha256':sha(Path(__file__)),'paired_statistics_sha256':sha(Path(__file__).with_name('summarize_tuning_size.py')),
        'files':{p.name:sha(p) for p in output.iterdir() if p.is_file()},
        'scope':'all captured matching fixed/tuned references at all capacities; shared-batch intervals conditional on fitted models'})
    print('COMPLETED EQUAL BENEFIT CONTRASTS',flush=True)

if __name__=='__main__':main()
