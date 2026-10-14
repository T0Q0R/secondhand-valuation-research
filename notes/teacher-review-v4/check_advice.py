"""Check teacher's wording suggestions on fixed artifacts and frozen inference.
No fitting, response updates, model selection or added training seeds.
"""
from pathlib import Path
import hashlib,itertools,json,os,sys
os.environ.setdefault('OMP_NUM_THREADS','2');os.environ.setdefault('OPENBLAS_NUM_THREADS','2')
import numpy as np,pandas as pd,torch,joblib
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;OLD=ROOT/'notes/revision-mechanisms-v3'
sys.path.insert(0,str(ROOT/'experiments'))
from savval import FEATURES,price_features
torch.set_num_threads(2);bindings={}
def bind(p):
    bindings[str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def predict(model,x):
    base=model.backbone.predict(model.encoder.tree_frame(x),thread_count=2).astype(np.float32)
    model.residual.eval()
    with torch.no_grad():res=model.residual(torch.from_numpy(model.encoder.transform(x))).reshape(-1).numpy()
    return (base+res).astype(float)
v=pd.read_csv(bind(OLD/'variance_components.csv'));z=np.load(bind(OLD/'paired_differences.npz'));variance=[]
for alloc in ['top_b','minimax']:
    a=v.query("dataset=='mucars' and initial_objective=='masking' and score=='suppression' and allocation==@alloc").set_index('coverage')
    y=z[f'mucars__masking__suppression__{alloc}__uncapped'];equal=np.var(y.mean(1),ddof=0)/len(y)
    variance.append(dict(allocation=alloc,batch_count_factor=107/10,listing_count_factor=10672/1000,
        batch_variance_reduction_factor=float(a.loc['capped','batch_variance']/a.loc['uncapped','batch_variance']),
        seed_variance_change_fraction=float(a.loc['uncapped','seed_variance']/a.loc['capped','seed_variance']-1),
        full_equal_batch_seed_variance=equal,full_record_weighted_seed_variance=float(a.loc['uncapped','seed_variance']),
        tail_weight_only_seed_variance_change_fraction=float(a.loc['uncapped','seed_variance']/equal-1)))
domains=json.loads(bind(OLD/'final_record_domains.json').read_text());prior=pd.read_csv(bind(OLD/'final_record_pilot.csv'));rows=[]
for source in ['jucars','mucars']:
    path=bind(ROOT.parent/'experiments/data/processed'/f'{source}_bvival_v1/splits/validation.csv')
    f=pd.read_csv(path);rank=f.listing_id.astype(str).map(lambda s:hashlib.sha256(('sav-val-evaluation-order-v1|'+s).encode()).hexdigest());f=f.loc[rank.sort_values(kind='stable').index[:1000]].reset_index(drop=True)
    for seed in [13,42,2026]:
        vocab=domains[f'{source}/seed-{seed}'];eligible=f.mileage_km.notna().to_numpy().copy()
        for c in vocab:eligible &= (f[c].isna()|f[c].astype(str).isin(vocab[c])).to_numpy()
        ids=np.flatnonzero(eligible);missing=f.loc[ids,list(vocab)].isna().any(axis=1).to_numpy();target=np.expm1(f.loc[ids,'target_log'].to_numpy())
        saved=prior.query('dataset==@source and seed==@seed and subset=="covered_with_missing_category"').iloc[0]
        row=dict(dataset=source,seed=seed,covered=len(ids),singletons=int((~missing).sum()),natural_missing=int(missing.sum()),mean_advertised_price_missing=float(target[missing].mean()),
            mean_quote_reduction_over_mean_advertised_price=float(saved.mean_quote_reduction/target[missing].mean()),mean_mae_increase_over_mean_advertised_price=float(saved.mae_change/target[missing].mean()))
        if source=='mucars':
            p=bind(ROOT/f'outputs/matched-factorial-ten-seeds-v1/{source}/seed-{seed}/fit/deployment_models/robust__none__shared__shared.joblib');model,_=joblib.load(p)
            expected=json.loads((p.parent.parent/'completion.json').read_text())['deployment_model_hashes']['robust__none__shared__shared'];assert hashlib.sha256(p.read_bytes()).hexdigest()==expected
            x=price_features(f,FEATURES[source]);base=np.concatenate([predict(model,x.iloc[b:b+128]) for b in range(0,len(x),128)])
            variants=[];owners=[]
            for i in ids:
                options=[vocab[c] if pd.isna(f.at[i,c]) else [str(f.at[i,c])] for c in vocab]
                for values in itertools.product(*options):
                    item=x.iloc[i].copy()
                    for c,value in zip(vocab,values):item[c]=np.nan if value=='<MISSING>' else value
                    variants.append(item);owners.append(i)
            xx=pd.DataFrame(variants).reset_index(drop=True);qq=np.concatenate([predict(model,xx.iloc[b:b+128]) for b in range(0,len(xx),128)])
            env=np.full(len(f),np.inf);np.minimum.at(env,owners,qq);env[ids]=np.minimum(env[ids],base[ids]);env[ids[~missing]]=base[ids[~missing]]
            qb=np.expm1(base[ids]);qe=np.expm1(env[ids]);reduction=qb-qe
            assert np.isclose(reduction[missing].mean(),saved.mean_quote_reduction,atol=1e-8,rtol=0)
            assert np.isclose((abs(qe-target)-abs(qb-target))[missing].mean(),saved.mae_change,atol=1e-8,rtol=0)
            assert np.all(reduction[~missing]==0)
            pct=reduction[missing]/qb[missing];advertised=reduction[missing]/target[missing]
            row.update(mean_individual_quote_reduction_fraction=float(pct.mean()),max_individual_quote_reduction_fraction=float(pct.max()),
                max_individual_reduction_over_advertised_price=float(advertised.max()),completion_evaluations=len(qq),
                singleton_quote_change_max=float(abs(reduction[~missing]).max()))
        rows.append(row)
pd.DataFrame(rows).to_csv(HERE/'price_and_singleton_diagnostics.csv',index=False)
pd.DataFrame(variance).to_csv(HERE/'coverage_weight_diagnostics.csv',index=False)
# Small independent accounting checks for the requested prose denominators.
frozen=pd.read_csv(bind(ROOT/'notes/revision-review-v2/statistics/frozen_allocation_threshold_sensitivity.csv'))
subset=frozen[frozen.honest_mae_increase_threshold_percent==5].groupby('inflation_reduction_threshold_percent')[['passing_points','comparisons']].sum()
assert subset.passing_points.tolist()==[8,4,2,0,0] and (subset.comparisons==18).all()
joint=pd.read_csv(bind(ROOT/'notes/revision-review-v2/statistics/threshold_sensitivity.csv'))
joint=joint[(joint.honest_mae_increase_threshold_percent==5)&(joint.family=='joint_policy')].groupby('inflation_reduction_threshold_percent')[['passing_points','comparisons']].sum()
assert joint.passing_points.tolist()==[3,0,0,0,0] and (joint.comparisons==18).all()
fixture=json.loads(bind(ROOT/'oqbo-val/outputs/finite-demo-01/case-10.json').read_text())
assert len(fixture['rules'])==8 and set(fixture['rules'])=={'priority-'+''.join(map(str,p)) for p in itertools.permutations(range(3))}|{'risk','none'}
cost=pd.read_csv(bind(OLD/'cost_mechanism_means.csv'));benefits=[]
for scenario in ['uniform020','heterogeneous020']:
    c=cost.query('dataset=="synthetic" and allocation=="top_b" and scenario==@scenario').set_index('feedback')
    difference={k:float(c.loc['none',k]-c.loc['policy',k]) for k in ['inflation','honest_mae','attacked_mae','failed_query']}
    assert min(difference.values())>0
    benefits.append(dict(scenario=scenario,improvements=difference))
comparison=dict(frozen_threshold_counts=subset.reset_index().to_dict('records'),joint_threshold_counts=joint.reset_index().to_dict('records'),eight_fixture_rules=fixture['rules'],synthetic_higher_cost_mean_benefits=benefits)
(HERE/'accounting-checks.json').write_text(json.dumps(comparison,indent=2)+'\n')
summary=dict(status='completed_frozen_artifact_and_inference_checks',training_runs=0,response_updates=0,
 scope='Existing conditional variance components; six categorical-domain support summaries; three MUCars frozen models re-evaluated solely to distinguish individual quote reduction from advertised-price-normalized mean losses.',
 input_sha256=bindings,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 output_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in list(HERE.glob('*.csv'))+[HERE/'accounting-checks.json']})
(HERE/'diagnostic-completion.json').write_text(json.dumps(summary,indent=2)+'\n');print(pd.DataFrame(rows).to_string(index=False));print(pd.DataFrame(variance).to_string(index=False))
