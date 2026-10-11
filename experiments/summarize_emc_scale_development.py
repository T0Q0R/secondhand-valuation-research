"""Retained normalized EMC contrasts and prespecified practical gate."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analyze_emc_development import read,sha
from summarize_emc_development import paired,wilson


def median_pair(ours,reference,context):
    keys=['seed','listing_id','batch'];metric='quote_label_ratio'
    x=ours[keys+[metric]].merge(reference[keys+[metric]],on=keys,suffixes=('_ours','_reference'),validate='one_to_one')
    assert len(x)==len(ours)==len(reference)
    assert set(x.seed)=={13,42,2026}
    ids=sorted(x.listing_id.unique());seeds=(13,42,2026)
    arrays=[]
    for seed in seeds:
        part=x[x.seed==seed].set_index('listing_id').loc[ids]
        arrays.append(part[[metric+'_ours',metric+'_reference']].to_numpy())
    assert all(np.isfinite(a).all() for a in arrays)
    membership=x[x.seed==13].set_index('listing_id').loc[ids].batch.to_numpy()
    blocks=[np.flatnonzero(membership==b) for b in sorted(set(membership))]
    draws=np.random.default_rng(7906).integers(0,len(blocks),(1000,len(blocks)))
    bootstrap=[]
    for draw in draws:
        index=np.concatenate([blocks[b] for b in draw])
        bootstrap.append(np.mean([np.median(a[index,0])-np.median(a[index,1]) for a in arrays]))
    own=float(np.mean([np.median(a[:,0]) for a in arrays]));ref=float(np.mean([np.median(a[:,1]) for a in arrays]))
    return {**context,'metric':'median_quote_label_ratio','ours_mean_model_median':own,'reference_mean_model_median':ref,
        'ours_minus_reference':own-ref,'lower':float(np.quantile(bootstrap,.025)),'upper':float(np.quantile(bootstrap,.975)),
        'records':len(ids),'fitting_seeds':3,'common_batches':len(blocks),
        'scope':'paired within-model medians, then average three seeds; shared-batch resampling1000; fixed fitted models; unadjusted'}


def main():
    parser=argparse.ArgumentParser()
    for name in ('run','audit','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run=args.run.resolve();audit=args.audit.resolve();output=args.output.resolve()
    done=read(audit/'completion.json');root=read(run/'completion.json');config=read(run/'config.json')
    assert done['status']=='completed' and not done['smoke'] and done['cells']==1080 and done['cases']==9
    assert done['run_completion_sha256']==sha(run/'completion.json') and done['summary_sha256']==sha(audit/'summary.csv')
    assert root['status']=='completed' and root['cell_count']==1080 and root['case_count']==9
    output.mkdir(parents=True,exist_ok=False);source=[];coverage=[];bindings=[]
    for name in config['sources']:
        for seed in config['seeds']:
            case=run/name/f'seed-{seed}';receipt=read(case/'completion.json');assert receipt['cells']==120
            assert sha(case/'outcomes.csv.gz')==receipt['files']['outcomes.csv.gz']
            data=pd.read_csv(case/'outcomes.csv.gz');source.append(data)
            bindings.append({'source':name,'seed':seed,'case_completion_sha256':sha(case/'completion.json')})
            honest=data[(data.profile=='honest')&(data.budget==0)]
            for (alpha,method),cell in honest.groupby(['alpha','method']):
                n=len(cell);k=int(cell.joint_state_coverage.sum());lo,hi=wilson(k,n)
                coverage.append({'source':name,'seed':seed,'alpha':alpha,'method':method,'records':n,'joint_successes':k,
                    'joint_state_coverage':k/n,'wilson_lower':lo,'wilson_upper':hi,'nominal_inside_interval':lo<=1-alpha<=hi,
                    'nominal_point_shortfall':max(1-alpha-k/n,0),
                    'scope':'per-model independent-record descriptive binomial diagnostic; historical vehicle independence and exchangeability unverified; seeds not pooled'})
    outcomes=pd.concat(source,ignore_index=True);keys=['source','alpha','method','profile','budget','policy']
    groups={key:frame for key,frame in outcomes.groupby(keys,sort=True)}
    metrics=['width_log','coverage','valid_interval','quote_absolute_error','signed_log_error','positive_log_inflation','query_succeeded','quote_label_ratio']
    effects=[];medians=[]
    methods=('strategic_unit','strategic_scaled','emc_unit','emc_scaled')
    for name in config['sources']:
        for alpha in config['alphas']:
            for profile in ('honest','shared_raw_lower_max','shared_hash_hidden'):
                for rho in config['budgets']:
                    for policy in (('none',) if rho==0 else ('random','shrink')):
                        for ours,reference,comparison in [('emc_scaled','emc_unit','public_state_scale'),
                                ('strategic_scaled','strategic_unit','public_state_scale'),
                                ('emc_scaled','strategic_scaled','certificate_inheritance'),('emc_unit','strategic_unit','certificate_inheritance')]:
                            own=groups[(name,alpha,ours,profile,rho,policy)];ref=groups[(name,alpha,reference,profile,rho,policy)]
                            context={'source':name,'alpha':alpha,'profile':profile,'budget':rho,
                                'ours':ours+'/'+policy,'reference':reference+'/'+policy,'comparison':comparison}
                            for metric in metrics:effects.append(paired(own,ref,metric,context))
                            if ours=='emc_scaled' and reference=='emc_unit' and profile=='honest' and rho==0:
                                medians.append(median_pair(own,ref,context))
                    if rho>0:
                        for method in methods:
                            own=groups[(name,alpha,method,profile,rho,'shrink')];ref=groups[(name,alpha,method,profile,rho,'random')]
                            context={'source':name,'alpha':alpha,'profile':profile,'budget':rho,
                                'ours':method+'/shrink','reference':method+'/random','comparison':'query_acquisition'}
                            for metric in metrics:effects.append(paired(own,ref,metric,context))
    contrasts=pd.DataFrame(effects)
    # A larger quote/label ratio can reduce underpricing or increase overpricing.
    # Retain the paired numerical contrast without assigning a benefit direction.
    contrasts.loc[contrasts.metric=='quote_label_ratio','favorable_direction']='unspecified'
    assert len(contrasts)==4032
    contrasts.to_csv(output/'paired_contrasts.csv',index=False)
    contrasts[contrasts.alpha==.05].to_csv(output/'primary_contrasts.csv',index=False)
    coverage=pd.DataFrame(coverage);coverage.to_csv(output/'coverage_diagnostics.csv',index=False)
    medians=pd.DataFrame(medians);assert len(medians)==6;medians.to_csv(output/'honest_median_ratio_contrasts.csv',index=False)
    target=medians[(medians.source=='jucars')&(medians.alpha==.05)].iloc[0]
    primary=coverage[(coverage.alpha==.05)&(coverage.method=='emc_scaled')]
    assert len(primary)==9
    structural=outcomes[outcomes.method.str.startswith('emc')].positive_log_inflation.max()<=1e-9
    gate={'status':'evaluated_prespecified_development_gate','JUCars_absolute_median_ratio_gain':float(target.ours_minus_reference),
        'JUCars_gain_threshold':.10,'JUCars_paired_gain_lower':float(target.lower),
        'JUCars_practical_gain_pass':bool(target.ours_minus_reference>=.10 and target.lower>0),
        'all9_primary_scaled_EMC_Wilson_intervals_include95':bool(primary.nominal_inside_interval.all()),
        'zero_observed_EMC_positive_quote_deviations':bool(structural),
        'all_prespecified_checks_pass':bool(target.ours_minus_reference>=.10 and target.lower>0 and primary.nominal_inside_interval.all() and structural),
        'scope':'seen-source development feasibility only, not certified market coverage, novelty or paper readiness'}
    (output/'decision_gate.json').write_text(json.dumps(gate,indent=2)+'\n')
    pd.read_csv(audit/'summary.csv').to_csv(output/'audited_summary.csv',index=False)
    (output/'source_snapshot.py').write_bytes(Path(__file__).read_bytes())
    receipt={'status':'completed','cells':1080,'contrasts':len(contrasts),'median_contrasts':len(medians),'coverage_diagnostics':len(coverage),
        'run_completion_sha256':sha(run/'completion.json'),'audit_completion_sha256':sha(audit/'completion.json'),'case_bindings':bindings,
        'files':{p.name:sha(p) for p in output.iterdir() if p.is_file()},'source_sha256':sha(__file__),
        'paired_source_sha256':sha(Path(__file__).with_name('summarize_emc_development.py'))}
    (output/'completion.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(f'COMPLETED SCALED CONTRASTS {len(contrasts)}; practical gate={gate["all_prespecified_checks_pass"]}',flush=True)


if __name__=='__main__':main()
