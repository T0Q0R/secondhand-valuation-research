"""Strict source-complete union without rewriting distinct training bindings."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
import pandas as pd
from analyze_nested import audit_seed,sha,read

SEEDS=[13,42,2026,101,211,307,401,503,601,701]
REFERENCES=['sav_benefit_head','robust_no_feedback','masking_benefit','sav_no_gap','sav_preaudit_attacker']
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')

def main(a):
    original,extra,out=a.original.resolve(),a.extra.resolve(),a.output.resolve()
    roots=[original,extra];manifests=[read(p/'run_manifest.json') for p in roots]
    configs=[m['config'] for m in manifests]
    assert {k:v for k,v in configs[0].items() if k not in ['seeds','output']}=={k:v for k,v in configs[1].items() if k not in ['seeds','output']}
    assert set(configs[0]['seeds']).isdisjoint(configs[1]['seeds'])
    assert set(configs[0]['seeds']+configs[1]['seeds'])==set(SEEDS)
    assert set(a.datasets)<=set(configs[0]['datasets']) and len(set(a.datasets))==len(a.datasets)
    for name in ['run_crossfit.py','run_all.py','savval.py','protocol-v2.md']:
        assert manifests[0]['source_hashes'][name]==manifests[1]['source_hashes'][name]
    inputs={};pairs=[]
    for root,manifest in zip(roots,manifests):
        assert hashlib.sha256(json.dumps(manifest['source_hashes'],sort_keys=True).encode()).hexdigest()==manifest['binding']
        inputs[str(root/'run_manifest.json')]=sha(root/'run_manifest.json')
        for name,digest in manifest['source_hashes'].items():
            assert sha(root/'source_snapshot'/name)==digest
            inputs[str(root/'source_snapshot'/name)]=digest
        if (root/'completion.json').exists():
            done=read(root/'completion.json');assert done['status']=='completed' and done['binding']==manifest['binding']
            assert sha(root/'all_summary.csv')==done['summary_sha256']
            inputs[str(root/'completion.json')]=sha(root/'completion.json')
        for dataset in a.datasets:
            for seed in manifest['config']['seeds']:
                folder=root/dataset/f'seed-{seed}'
                assert (folder/'evaluation_completion.json').exists(),f'Missing completed requested pair: {folder}'
                pairs.append((root,manifest,dataset,seed))
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True);snapshot=out/'source_snapshot';snapshot.mkdir()
    for p in [Path(__file__).resolve(),Path(__file__).with_name('analyze_nested.py').resolve(),Path('plan/ten-seed-union-audit-v1.md').resolve()]:
        (snapshot/p.name).write_bytes(p.read_bytes());inputs[str(p)]=sha(p)
    all_out=[];all_summary=[];checks=[];cohorts={};folds={};pair_receipts=[];started=time.time()
    for root,manifest,dataset,seed in pairs:
        frame,summary,checked=audit_seed(root,dataset,seed,manifest['config'],manifest['binding'])
        folder=root/dataset/f'seed-{seed}'
        cohort=frame[frame.method=='native_no_audit'][['listing_id','batch','target_log']].sort_values('listing_id').reset_index(drop=True)
        assigned=pd.read_csv(folder/'outer_assignments.csv').sort_values('listing_id').reset_index(drop=True)
        if dataset in cohorts:
            assert cohort.equals(cohorts[dataset]) and assigned.equals(folds[dataset])
        else:cohorts[dataset]=cohort;folds[dataset]=assigned
        files=[folder/p for p in ['evaluation_completion.json','summary.csv','per_listing_outcomes.csv.gz',
            'outer_audit.json','outer_assignments.csv','outer_predictions.npz','primary_interval.json','deployment_fit/fit_completion.json']]
        files+=[root/dataset/'data_audit.json']
        files+=list((folder/'deployment_models').glob('*.joblib'))
        for p in files:inputs[str(p)]=sha(p)
        fit=read(folder/'deployment_fit/fit_completion.json')
        for name,digest in fit['files'].items():assert sha(folder/'deployment_fit'/name)==digest
        assert fit['inputs']['binding']==manifest['binding']
        pair_receipts.append({'dataset':dataset,'seed':seed,'root':str(root),'binding':manifest['binding'],
            'evaluation_completion_sha256':sha(folder/'evaluation_completion.json')})
        all_out.append(frame);all_summary.append(summary);checks.extend(checked)
        print(f'AUDITED TEN-SEED UNION INPUT {dataset}/{seed}',flush=True)
    outcomes=pd.concat(all_out,ignore_index=True);summary=pd.concat(all_summary,ignore_index=True)
    assert not summary.duplicated(['dataset','seed','method','budget']).any()
    assert len(checks)==len(a.datasets)*620
    summary.to_csv(out/'all_seed_summary.csv',index=False)
    pd.DataFrame(checks).to_csv(out/'metric_checks.csv',index=False)
    numeric=[c for c in summary.select_dtypes(include='number').columns if c not in ['seed','budget','n','evaluation_seconds']]
    summary.groupby(['dataset','method','budget'])[numeric].agg(['mean','std']).to_csv(out/'method_capacity_mean_sd.csv')
    rng=np.random.default_rng(20261008);batch_draw=rng.integers(0,10,size=(1000,10));seed_draw=rng.integers(0,10,size=(1000,10))
    contrasts=[];matrices={}
    for dataset in a.datasets:
        frame=outcomes[(outcomes.dataset==dataset)&(outcomes.budget==.1)]
        means=summary[(summary.dataset==dataset)&(summary.budget==.1)].groupby('method').mean(numeric_only=True)
        for reference in REFERENCES:
            pair=frame[frame.method.isin(['sav_val',reference])].pivot(index=['seed','batch','listing_id'],columns='method',values='positive_log_inflation')
            assert not pair.isna().any().any()
            delta=(pair[reference]-pair.sav_val).groupby(['seed','batch']).mean().unstack('batch').reindex(sorted(SEEDS))
            assert delta.shape==(10,10) and not delta.isna().any().any()
            matrix=delta.to_numpy();matrices[dataset+'__'+reference]=matrix
            fixed=matrix.mean(0)[batch_draw].mean(1)
            crossed=matrix[seed_draw[:,:,None],batch_draw[:,None,:]].mean((1,2))
            lo,hi=np.quantile(fixed,[.025,.975]);clo,chi=np.quantile(crossed,[.025,.975])
            ours,ref=means.loc['sav_val'],means.loc[reference]
            assert abs(matrix.mean()-(ref.mean_positive_log_inflation-ours.mean_positive_log_inflation))<1e-10
            contrasts.append({'dataset':dataset,'reference':reference,'training_seeds':10,'shared_batches':10,
                'sav_inflation':ours.mean_positive_log_inflation,'reference_inflation':ref.mean_positive_log_inflation,
                'difference':matrix.mean(),'relative_reduction_percent':100*matrix.mean()/ref.mean_positive_log_inflation,
                'conditional_batch_lower':lo,'conditional_batch_upper':hi,'seed_batch_lower':clo,'seed_batch_upper':chi,
                'seed_difference_sd':matrix.mean(1).std(ddof=1),
                'honest_mae_change_percent':100*(ours.clean_mae-ref.clean_mae)/ref.clean_mae,
                'attacked_mae_change_percent':100*(ours.attack_mae-ref.attack_mae)/ref.attack_mae})
    result=pd.DataFrame(contrasts);result.to_csv(out/'primary_contrasts.csv',index=False)
    np.savez_compressed(out/'paired_batch_matrices.npz',**matrices,batch_draws=batch_draw,seed_draws=seed_draw,seeds=np.array(sorted(SEEDS)))
    assert all(sha(Path(p))==d for p,d in inputs.items())
    write(out/'input_binding.json',inputs)
    write(out/'manifest.json',{'sources':a.datasets,'all_planned_sources':configs[0]['datasets'],'seeds':sorted(SEEDS),
        'pair_receipts':pair_receipts,'original_source':str(original),'added_source':str(extra),
        'all_source_coverage':set(a.datasets)==set(configs[0]['datasets']),
        'scope':'strict source-complete original-protocol union; not tuned ordinary-benefit or matched factorial study'})
    text=['# Ten-seed original-protocol union', '', 'Source coverage: '+', '.join(a.datasets)+'.',
        'Every included source has all ten predetermined seeds. Other planned sources remain outside this staged union.',
        '', 'Intervals are exploratory unadjusted95% percentile intervals over1000 resamples.',
        'The crossed seed/batch interval quantifies fitting-seed and shared-evaluation-batch variation on fixed training records, not training-population uncertainty.',
        'sav_benefit_head is the original feedback-trained benefit-head variant, not the separately tuned ordinary-benefit robust comparator.',
        '', '| Source | Reference | SAV inflation | Reference inflation | Relative reduction | Seed+batch interval |',
        '|---|---|---:|---:|---:|---|']
    for _,r in result.iterrows():text.append(f'|{r.dataset}|{r.reference}|{r.sav_inflation:.6f}|{r.reference_inflation:.6f}|{r.relative_reduction_percent:.2f}%|[{r.seed_batch_lower:.6f}, {r.seed_batch_upper:.6f}]|')
    text+=['','Positive differences favor SAV. Negative findings and all method/capacity cells are retained.',
           'The audit checks recorded training/split bindings and metric/replay arithmetic; it does not establish unseen-market guarantees or retrain models independently.']
    (out/'report.md').write_text('\n'.join(text)+'\n')
    write(out/'completion.json',{'status':'selected-source-union-audited','sources':a.datasets,'training_seeds_per_source':10,
        'audited_cells':len(checks),'listing_outcomes':len(outcomes),'seconds':time.time()-started,
        'all_source_coverage':set(a.datasets)==set(configs[0]['datasets']),
        'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()}})
    print(result.to_string(index=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('original','extra','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--datasets',nargs='+',required=True);main(p.parse_args())
