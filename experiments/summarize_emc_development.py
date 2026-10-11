"""All-source EMC diagnostics; conditional paired common-batch intervals."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())


def wilson(k,n):
    z=1.959963984540054;p=k/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den;half=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return center-half,center+half


def paired(ours,reference,metric,context):
    keys=['seed','listing_id','batch']
    x=ours[keys+[metric]].merge(reference[keys+[metric]],on=keys,suffixes=('_ours','_reference'),validate='one_to_one')
    assert len(x)==len(ours)==len(reference)
    # A width contrast includes only records valid for both methods in all
    # fitting seeds. Invalidity and coverage contrasts retain every record.
    finite=np.isfinite(x[metric+'_ours']) & np.isfinite(x[metric+'_reference'])
    eligible=x.assign(finite=finite).groupby('listing_id').finite.all()
    x=x[x.listing_id.isin(eligible[eligible].index)].copy()
    assert set(x.seed)=={13,42,2026}
    byrecord=x.groupby(['listing_id','batch'])[[metric+'_ours',metric+'_reference']].mean().reset_index()
    assert (x.groupby('listing_id').seed.nunique()==3).all()
    byrecord['delta']=byrecord[metric+'_reference']-byrecord[metric+'_ours']
    blocks=byrecord.groupby('batch').delta.agg(['sum','count'])
    draws=np.random.default_rng(7906).integers(0,len(blocks),(1000,len(blocks)))
    bootstrap=blocks['sum'].to_numpy()[draws].sum(axis=1)/blocks['count'].to_numpy()[draws].sum(axis=1)
    own=byrecord[metric+'_ours'].mean();ref=byrecord[metric+'_reference'].mean()
    return {**context,'metric':metric,'ours_mean':float(own),'reference_mean':float(ref),
        'reference_minus_ours':float(ref-own),'relative_reduction_percent':float(100*(ref-own)/ref) if abs(ref)>1e-12 else None,
        'lower':float(np.quantile(bootstrap,.025)),'upper':float(np.quantile(bootstrap,.975)),
        'fitting_seeds':3,'paired_records':len(byrecord),'retained_record_seed_rows':len(x),
        'excluded_invalid_record_ids':len(eligible)-len(byrecord),'common_batches':len(blocks),
        'favorable_direction':'negative' if metric in ('coverage','valid_interval','query_succeeded') else 'unspecified' if metric=='signed_log_error' else 'positive',
        'interval_scope':'1000 shared-batch bootstrap replicates after averaging paired fitting seeds; conditional on fitted models; unadjusted; width conditioned on common valid records'}


def main():
    parser=argparse.ArgumentParser()
    for name in ('run','audit','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run=args.run.resolve();audit=args.audit.resolve();output=args.output.resolve()
    done=read(audit/'completion.json');root=read(run/'completion.json');config=read(run/'config.json')
    assert done['status']=='completed' and not done['smoke'] and done['cell_count']==810
    assert done['run_completion_sha256']==sha(run/'completion.json') and done['summary_sha256']==sha(audit/'summary.csv')
    assert root['case_count']==9 and root['cell_count']==810
    output.mkdir(parents=True,exist_ok=False)
    source=[];coverage=[]
    for name in config['sources']:
        for seed in config['seeds']:
            case=run/name/f'seed-{seed}';receipt=read(case/'completion.json')
            assert sha(case/'outcomes.csv.gz')==receipt['files']['outcomes.csv.gz']
            data=pd.read_csv(case/'outcomes.csv.gz');source.append(data)
            canonical=data[(data.profile=='honest')&(data.budget==0)]
            for (alpha,method),cell in canonical.groupby(['alpha','method']):
                n=len(cell);k=int(cell.joint_state_coverage.sum());lower,upper=wilson(k,n)
                coverage.append({'source':name,'seed':seed,'alpha':alpha,'method':method,'records':n,
                    'joint_state_successes':k,'joint_state_coverage':k/n,'wilson_lower':lower,'wilson_upper':upper,
                    'nominal_inside_interval':lower<=1-alpha<=upper,
                    'scope':'per fitted model, single independent-record binomial diagnostic if exchangeability holds; seeds not pooled; actual vehicle independence unverified'})
    outcomes=pd.concat(source,ignore_index=True)
    keys=['source','alpha','method','profile','budget','policy']
    groups={key:frame for key,frame in outcomes.groupby(keys,sort=True)}
    metrics=['width_log','coverage','valid_interval','quote_absolute_error','signed_log_error','positive_log_inflation','query_succeeded']
    effects=[]
    for name in config['sources']:
        for alpha in config['alphas']:
            for profile in ('honest','shared_raw_lower_max','shared_hash_hidden'):
                for rho in config['budgets']:
                    policies=('none',) if rho==0 else ('random','shrink')
                    for policy in policies:
                        own=groups[(name,alpha,'emc',profile,rho,policy)]
                        reference=groups[(name,alpha,'strategic_cp',profile,rho,policy)]
                        context={'source':name,'alpha':alpha,'profile':profile,'budget':rho,
                            'ours':'emc/'+policy,'reference':'strategic_cp/'+policy,'comparison':'certificate_inheritance'}
                        for metric in metrics:effects.append(paired(own,reference,metric,context))
                    if rho>0:
                        for method in ('ordinary_cp','strategic_cp','emc'):
                            own=groups[(name,alpha,method,profile,rho,'shrink')]
                            reference=groups[(name,alpha,method,profile,rho,'random')]
                            context={'source':name,'alpha':alpha,'profile':profile,'budget':rho,
                                'ours':method+'/shrink','reference':method+'/random','comparison':'query_acquisition'}
                            for metric in metrics:effects.append(paired(own,reference,metric,context))
    contrasts=pd.DataFrame(effects);contrasts.to_csv(output/'paired_contrasts.csv',index=False)
    contrasts[contrasts.alpha==.05].to_csv(output/'primary_contrasts.csv',index=False)
    pd.DataFrame(coverage).to_csv(output/'coverage_diagnostics.csv',index=False)
    pd.read_csv(audit/'summary.csv').to_csv(output/'audited_summary.csv',index=False)
    (output/'source_snapshot.py').write_bytes(Path(__file__).read_bytes())
    receipt={'status':'completed','cells':810,'contrasts':len(contrasts),'coverage_diagnostics':len(coverage),
        'run_completion_sha256':sha(run/'completion.json'),'audit_completion_sha256':sha(audit/'completion.json'),
        'files':{p.name:sha(p) for p in output.iterdir() if p.is_file()},'source_sha256':sha(__file__),
        'scope':'development evidence; shared reports; no new-market confirmation or novelty proof; conservative quote versus point prediction are distinct tasks'}
    (output/'completion.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(f'COMPLETED EMC CONTRASTS {len(contrasts)}',flush=True)


if __name__=='__main__':main()
