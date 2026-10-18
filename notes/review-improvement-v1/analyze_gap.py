"""Aggregate all candidate tradeoffs and paired OOF-selected evaluations.
Partial mode only analyzes complete ten-seed sources and is labeled unfinished.
Selection receipts predate evaluation and are never changed by this analysis.
"""
from pathlib import Path
import argparse,json,hashlib,sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments'))
import run_completion_ablation_v6 as c
import run_review_gap_controls_v2 as runner
OUT=Path(__file__).parent/'gap'
REF=ROOT/'outputs/rpl-ten-seed-v2'
RUN=ROOT/'outputs/review-gap-controls-v2'
SEEDS=runner.SEEDS
METRICS=['mean_positive_log_inflation','clean_mae','attack_mae','failed_query_fraction',
         'max_remaining_response_regret','nonconverged_batch_fraction']

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true');a=parser.parse_args()
    OUT.mkdir(exist_ok=True);manifest=runner.guard()
    completed=[]
    for source in ['synthetic','jucars','mucars']:
        if all((RUN/source/f'seed-{seed}'/'completion.json').exists() for seed in SEEDS):completed.append(source)
    if not a.partial:assert len(completed)==3 and (RUN/'completion.json').exists()
    ref=pd.read_csv(REF/'summary.csv');unique=[];candidates=[];selected=[];bindings=[]
    for source in completed:
        for seed in SEEDS:
            folder=RUN/source/f'seed-{seed}';selection_path=folder/'training-selection.json'
            selection=json.loads(selection_path.read_text());cp=json.loads((folder/'completion.json').read_text())
            assert c.sha(selection_path)==cp['selection_sha256']
            assert c.sha(folder/'summary.csv')==cp['summary_sha256']
            summaries=pd.read_csv(folder/'summary.csv');assert len(summaries)==3
            choices={x['family']:x for x in selection['choices']}
            for family in ['rpl','gap']:
                independent=runner.choose(selection['candidates'],family)
                assert independent==choices[family]
            values={}
            for candidate in selection['candidates']:
                name=candidate['method'];mp=ROOT/candidate['model_path'];assert c.sha(mp)==candidate['model_sha256']
                if candidate['beta']==.5:
                    q=ref[(ref.dataset==source)&(ref.seed==seed)&(ref.method==name)&(ref.budget==.1)]
                    assert len(q)==1;summary=q.iloc[0].to_dict()
                    ev=REF/source/f'seed-{seed}'/name/'evaluation-1000/completion.json'
                    receipt=json.loads(ev.read_text());assert receipt['inputs']['model']==c.sha(mp)
                    for key in METRICS:assert np.isclose(summary[key],receipt['summary'][key],atol=1e-10,rtol=1e-12)
                else:
                    vd=mp.parent;ev=vd/'evaluation-1000/completion.json';receipt=json.loads(ev.read_text())
                    assert receipt['inputs']['model']==c.sha(mp)
                    assert receipt['inputs']['training_selection_sha256']==c.sha(selection_path)
                    assert c.sha(vd/'evaluation-1000/outcomes.csv.gz')==receipt['outcomes_sha256']
                    summary=receipt['summary']
                    # Independently aggregate the three comparison metrics from bound outputs.
                    rows=pd.read_csv(vd/'evaluation-1000/outcomes.csv.gz')
                    for column,key in [('positive_log_inflation','mean_positive_log_inflation'),('clean_absolute_error','clean_mae'),('attack_absolute_error','attack_mae')]:
                        assert np.isclose(rows[column].mean(),summary[key],atol=1e-8,rtol=1e-12)
                    # Every new outer/deployment fit retains exact config, round counts, hashes.
                    for stage in ['outer-0','outer-1','outer-2','deployment']:
                        fit=vd/stage;record=json.loads((fit/'completion.json').read_text())
                        assert c.sha(fit/'model.joblib')==record['model_sha256']
                        assert [v['epochs'] for v in record['rounds']]==[6,6]
                        assert record['inputs']['config']['recovery_path_weight']==0
                        assert record['inputs']['config']['gap_penalty_weight']==candidate['beta']
                row=dict(source=source,seed=seed,method=name,beta=candidate['beta'],path_weight=candidate['path_weight'],**{k:summary[k] for k in METRICS})
                values[name]=row;unique.append(row);candidates.append(candidate)
                bindings.append(dict(source=source,seed=seed,method=name,model_sha256=c.sha(mp),
                   cell_receipt_path=str(ev.relative_to(ROOT)),cell_receipt_sha256=c.sha(ev),
                   training_selection_sha256=c.sha(selection_path)))
            for family,choice in choices.items():
                selected.append(dict(family=family,constraint_met=choice['constraint_met'],
                    oof_max_gain=choice['oof_max_gain'],oof_honest_mae=choice['oof_honest_mae'],
                    **values[choice['selected_method']]))
    u=pd.DataFrame(unique);s=pd.DataFrame(selected)
    if u.empty:print('NO_COMPLETE_SOURCE');return
    assert len(u)==len(completed)*70 and len(s)==len(completed)*20
    u.to_csv(OUT/'all-candidate-cells.csv',index=False);s.to_csv(OUT/'selected-cells.csv',index=False)
    pd.DataFrame(candidates).to_csv(OUT/'training-candidate-scores.csv',index=False)
    aggregation={key:('max' if key=='max_remaining_response_regret' else 'mean') for key in METRICS}
    means=u.groupby(['source','method','beta','path_weight']).agg(aggregation).reset_index()
    means.to_csv(OUT/'all-candidate-means.csv',index=False)
    sm=s.groupby(['source','family']).agg(aggregation).reset_index();sm.to_csv(OUT/'selected-means.csv',index=False)
    frequency=s.groupby(['source','family','method']).size().reset_index(name='seeds');frequency.to_csv(OUT/'selection-frequency.csv',index=False)
    pairs=[];rng=np.random.default_rng(20261019)
    for source in completed:
        r=s[(s.source==source)&(s.family=='rpl')].set_index('seed').reindex(SEEDS)
        g=s[(s.source==source)&(s.family=='gap')].set_index('seed').reindex(SEEDS)
        for key in METRICS:
            diff=(g[key]-r[key]).to_numpy();boot=diff[rng.integers(0,10,(10000,10))].mean(1)
            lo,hi=np.quantile(boot,[.025,.975])
            pairs.append(dict(source=source,metric=key,gap_minus_rpl=float(diff.mean()),low=float(lo),high=float(hi),
              rpl_better_seeds=int((diff>0).sum()),gap_better_seeds=int((diff<0).sum()),
              scope='posthoc marginal fitting-seed bootstrap; fixed evaluation records; selection includes training randomness'))
    pd.DataFrame(pairs).to_csv(OUT/'selected-paired-effects.csv',index=False)
    # Test whether the fixed unit-weight point is dominated within each same-seed candidate grid.
    dominance=[];keys=METRICS[:3]
    for source in completed:
        for seed in SEEDS:
            group=u[(u.source==source)&(u.seed==seed)];target=group[group.method=='path-1-gap-0.5'].iloc[0]
            for _,row in group[(group.path_weight==0)&(group.beta>.5)].iterrows():
                less=(row[keys].astype(float).to_numpy()<=target[keys].astype(float).to_numpy())
                strict=(row[keys].astype(float).to_numpy()<target[keys].astype(float).to_numpy())
                dominance.append(dict(source=source,seed=seed,gap_beta=row.beta,
                    gap_dominates_unit_rpl=bool(less.all() and strict.any()),
                    scope='three-metric within-seed comparison; failures and regret reported separately'))
    pd.DataFrame(dominance).to_csv(OUT/'fixed-unit-dominance.csv',index=False)
    c.write(OUT/'verification.json',dict(status='partial_complete_sources_only' if a.partial else 'all_candidates_and_selection_checked',
       sources=completed,unique_cells=len(u),new_gap_cells=len(completed)*30,reused_rpl_cells=len(completed)*40,
       new_fit_receipts_checked=len(completed)*120,selected_cells=len(s),selection_constraints_failed=int((~s.constraint_met).sum()),
       bindings=bindings,manifest_sha256=c.sha(RUN/'manifest.json'),source_sha256=c.sha(Path(__file__)),
       audit_scope='model/fit/checkpoint/outcome/selection binding and independent metric reaggregation; not new full four-phase audit'))
    print(sm.to_string(index=False));print(frequency.to_string(index=False))

if __name__=='__main__':main()
