"""Verify the completed crossing, join reused native-head controls, write tables.
No training, model inference, response search or evaluation-based tuning.
"""
from pathlib import Path
import gzip, hashlib, json, sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'experiments'))
import core_evidence_audit_v2 as audit
sha=audit.sha
read=audit.read
METRICS=['mean_positive_log_inflation','clean_mae','attack_mae','failed_query_fraction',
         'max_remaining_response_regret','nonconverged_batch_fraction']
FAMILIES=['native','aco','sefa','gdfs','dime','efa']
LABELS=dict(native='Native head',aco='ACO',sefa='SEFA',gdfs='GDFS',dime='DIME',efa='Expl.-AFA')
SOURCES=['synthetic','jucars','mucars']

def main():
    run=ROOT/'outputs/rpl-five-factorial-v3'
    complete=read(run/'completion.json');assert complete['cells']==90
    assert sha(run/'summary.csv')==complete['summary_sha256']
    cross=pd.read_csv(run/'summary.csv');assert len(cross)==90
    archived=json.loads(gzip.decompress((ROOT/'notes/rpl-five-factorial-v1/cell-receipts.json.gz').read_bytes()))
    bindings={};native=[]
    for _,r in cross.iterrows():
        p=run/r.dataset/f'seed-{r.seed}'/f'rpl-{r.rpl_weight}'/r.family/'completion.json'
        cp=read(p);assert archived[str(p.relative_to(ROOT))]==cp
        for name,h in cp['inputs']['source_bindings'].items():assert sha(ROOT/name)==h
        assert sha(ROOT/cp['inputs']['price_model'])==cp['inputs']['price_sha256']
        assert sha(p.parent/'outcomes.csv.gz')==cp['outcomes_sha256']
        bindings[str(p.relative_to(ROOT))]=sha(p)
    audited=ROOT/'notes/core-evidence-v2/completed-stages/rpl10/audited_cell_summaries.csv'
    if not audited.exists():audited=ROOT/'outputs/core-evidence-audit-v2/analysis/rpl10/audited_cell_summaries.csv'
    old=pd.read_csv(audited)
    for source in SOURCES:
        for seed in [13,42,2026]:
            for weight in [0,1]:
                p=ROOT/'outputs/recovery-path-learning-v1'/source/f'seed-{seed}'/f'path-{weight}-gap-0.5/evaluation-1000/completion.json'
                cp=read(p);summary=cp['summary'];rr,raw=audit.row_file(p)
                peer=read(run/source/f'seed-{seed}'/f'rpl-{weight}'/'sefa/completion.json')
                assert cp['inputs']['model']==peer['inputs']['price_sha256']
                assert cp['inputs']['evaluation']==peer['inputs']['evaluation']
                cr=pd.read_csv(run/source/f'seed-{seed}'/f'rpl-{weight}'/'sefa/outcomes.csv.gz')
                assert rr.listing_id.tolist()==cr.listing_id.tolist()
                ref=old[(old.dataset==source)&(old.seed==seed)&np.isclose(old.budget,.1)&(old.method==f'path-{weight}-gap-0.5')]
                assert len(ref)==1
                for m in METRICS:np.testing.assert_allclose(summary[m],ref.iloc[0][m],atol=1e-10,rtol=1e-10)
                native.append(dict(summary,dataset=source,family='native',rpl_weight=weight,seed=seed,gap_weight=.5))
                bindings[str(p.relative_to(ROOT))]=sha(p);bindings[str(raw.relative_to(ROOT))]=sha(raw)
    combined=pd.concat([pd.DataFrame(native),cross],ignore_index=True)
    assert len(combined)==108 and not combined.duplicated(['dataset','seed','rpl_weight','family']).any()
    combined.to_csv(OUT/'all-108-cells.csv',index=False)
    paired=[];means=[];choices=[]
    for source in SOURCES:
        for fam in FAMILIES:
            g=combined[(combined.dataset==source)&(combined.family==fam)]
            off=g[g.rpl_weight==0].set_index('seed');on=g[g.rpl_weight==1].set_index('seed')
            row=dict(dataset=source,family=fam,n_fitting_seeds=3,inflation_decreasing_seeds=int((on.mean_positive_log_inflation<off.mean_positive_log_inflation).sum()))
            for m in METRICS:
                for w,v in [(0,off),(1,on)]:
                    row[m+f'_lambda{w}']=v[m].mean()
                    row[m+f'_lambda{w}_min']=v[m].min();row[m+f'_lambda{w}_max']=v[m].max()
                a=off[m].mean();b=on[m].mean();row[m+'_delta']=b-a
                row[m+'_change_pct']=100*(b/a-1) if a else np.nan
            means.append(row)
            for seed in off.index:
                q=dict(dataset=source,family=fam,seed=int(seed))
                for m in METRICS:q[m+'_lambda0']=off.loc[seed,m];q[m+'_lambda1']=on.loc[seed,m];q[m+'_delta']=on.loc[seed,m]-off.loc[seed,m]
                paired.append(q)
    means=pd.DataFrame(means);pairs=pd.DataFrame(paired)
    means.to_csv(OUT/'matched-source-family-means.csv',index=False)
    pairs.to_csv(OUT/'all-54-paired-effects.csv',index=False)
    for source in SOURCES:
        native=means[(means.dataset==source)&(means.family=='native')].iloc[0]
        g=means[(means.dataset==source)&(means.family!='native')]
        assert g.mean_positive_log_inflation_lambda1.max()<g.mean_positive_log_inflation_lambda0.min()
        best=g.loc[g.mean_positive_log_inflation_lambda1.idxmin()]
        choices.append(dict(dataset=source,descriptive_best_stacked_family=best.family,
            inflation_stacked=float(best.mean_positive_log_inflation_lambda1),
            inflation_native_rpl=float(native.mean_positive_log_inflation_lambda1),
            change_vs_native_rpl_pct=100*(best.mean_positive_log_inflation_lambda1/native.mean_positive_log_inflation_lambda1-1),
            highest_stacked_inflation=float(g.mean_positive_log_inflation_lambda1.max()),
            lowest_unregularized_family_inflation=float(g.mean_positive_log_inflation_lambda0.min()),
            honest_mae_rpl_change_pct=float(native.clean_mae_change_pct)))
    pd.DataFrame(choices).to_csv(OUT/'descriptive-choice-summary.csv',index=False)
    main=[r'\begin{table}[tbp]\centering\small',
          r'\caption{Matched RPL--acquisition comparison at 10\% capacity and $\beta=.5$. Each entry averages the same three fitting seeds. $I$ is positive log inflation; $\Delta A$ is the attacked-MAE change (percent), and $\Delta F$ the failed-query change (percentage points per listing), from $\lambda=0$ to 1. Native head rows reuse 18 existing cells; the other rows are the new 90-cell $2\times5$ crossing. Negative changes favor the indicated metric.}',
          r'\label{tab:rpl_crossing}',r'\setlength{\tabcolsep}{4pt}',
          r'\begin{tabular}{llrrrrr}\toprule',
          r'Source & Acquisition & $I_0\downarrow$ & $I_1\downarrow$ & $\Delta I$ (\%) & $\Delta A$ (\%) & $\Delta F$ (pp)\\\midrule']
    for source in SOURCES:
        for j,fam in enumerate(FAMILIES):
            r=means[(means.dataset==source)&(means.family==fam)].iloc[0]
            name={'synthetic':'Synthetic','jucars':'JUCars','mucars':'MUCars'}[source] if j==0 else ''
            main.append(f'{name} & {LABELS[fam]} & {r.mean_positive_log_inflation_lambda0:.5f} & {r.mean_positive_log_inflation_lambda1:.5f} & {r.mean_positive_log_inflation_change_pct:+.2f} & {r.attack_mae_change_pct:+.2f} & {100*r.failed_query_fraction_delta:+.2f}'+r'\\')
        if source!=SOURCES[-1]:main.append(r'\midrule')
    main += [r'\bottomrule\end{tabular}',r'\end{table}']
    (OUT/'main-table.tex').write_text('\n'.join(main)+'\n')
    appendix=[r'\begin{longtable}{lrlrrrr}',
              r'\caption{Absolute matched RPL--acquisition outcomes at 10\% capacity and $\beta=.5$, using the same three fitting seeds. MAE is in each source currency; failed queries are percent of all listings. Native head denotes the original suppression head, not zero acquisition. All nonconverged profiles remain included. Full per-seed ranges and convergence values are in the linked source CSVs.}\label{tab:recent_primary}\\',
              r'\toprule Source & $\lambda$ & Acquisition & Inflation & Honest MAE & Attacked MAE & Failed (\%)\\\midrule\endfirsthead',
              r'\toprule Source & $\lambda$ & Acquisition & Inflation & Honest MAE & Attacked MAE & Failed (\%)\\\midrule\endhead']
    for source in SOURCES:
        for weight in [0,1]:
            for fam in FAMILIES:
                r=means[(means.dataset==source)&(means.family==fam)].iloc[0]
                appendix.append(f'{source} & {weight} & {LABELS[fam]} & {r[f"mean_positive_log_inflation_lambda{weight}"]:.5f} & {r[f"clean_mae_lambda{weight}"]:.2f} & {r[f"attack_mae_lambda{weight}"]:.2f} & {100*r[f"failed_query_fraction_lambda{weight}"]:.2f}'+r'\\')
            appendix.append(r'\midrule')
    appendix[-1]=r'\bottomrule\end{longtable}'
    (OUT/'appendix-table.tex').write_text('\n'.join(appendix)+'\n')
    # Compact source/family seed ranges support the descriptive, n=3 presentation.
    report=dict(status='verified_90_new_crossing_plus_18_reused_native_cells',new_fits=0,new_evaluations=0,
        crossing_cells=90,reused_native_cells=18,paired_crossing_effects=45,
        all_crossing_pairs_inflation_decreasing=bool((pairs[pairs.family!='native'].mean_positive_log_inflation_delta<0).all()),
        crossing_nonconverged_cells=int((cross.nonconverged_batch_fraction>1e-10).sum()),
        crossing_nonconverged_batches=int(round(cross.nonconverged_batch_fraction.sum()*10)),
        crossing_maximum_regret=float(cross.max_remaining_response_regret.max()),descriptive_choices=choices,
        bindings=bindings,script_sha256=sha(Path(__file__)),scope='Fixed source cohorts; three fitting seeds, not confidence intervals or evaluation-selected deployment defaults')
    (OUT/'evidence-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='bindings'},indent=2))

if __name__=='__main__':main()
