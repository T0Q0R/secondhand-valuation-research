"""Versioned ACO audit repair: preserve the production float64 distance contract.
Replaces the earlier first-batch-only unilateral audit with full enumeration.
"""
from pathlib import Path
import gc,itertools
import numpy as np,pandas as pd,joblib
import core_evidence_audit_v2 as a

def scores_direct(bank,available,losses,groups,weights,x,missing,k):
    # ConditionalNeighborHead promotes BOTH bank and public query to float64.
    # Preserve those input values before independent coordinate-wise subtraction.
    # Doing the subtraction in archived float32 can change nearest-neighbor order.
    bank=np.asarray(bank,dtype=np.float64)
    x=np.asarray(x,dtype=np.float64)
    losses=np.asarray(losses,dtype=np.float64)
    weights=np.asarray(weights,dtype=np.float64)
    n,s,d=x.shape;flat=x.reshape(-1,d);patterns=missing.reshape(-1,4).astype(int)@(1<<np.arange(4))
    result=np.full((len(flat),4),-np.inf)
    for pattern in np.unique(patterns):
        hidden=((pattern>>np.arange(4))&1).astype(bool)
        eligible=np.flatnonzero(available[:,~hidden].all(1))
        if not len(eligible):continue
        unseen={a.ACTIONS[f] for f in np.flatnonzero(hidden)}
        coordinates=[j for block in sorted([v for field,v in groups.items() if field not in unseen],key=min) for j in block]
        selected=np.flatnonzero(patterns==pattern)
        for begin in range(0,len(selected),128):
            rows=selected[begin:begin+128];distance=np.zeros((len(rows),len(eligible)))
            for j in coordinates:distance+=weights[j]*(flat[rows,j,None]-bank[None,eligible,j])**2
            neighbors=eligible[np.argsort(distance,axis=1,kind='stable')[:,:min(k,len(eligible))]]
            for field in np.flatnonzero(hidden):
                result[rows,field]=(losses[neighbors,pattern]-losses[neighbors,pattern&~(1<<field)]).mean(1)
    return result.reshape(n,s,4)

def audit_pair(source,seed,limit=None):
    root=a.ROOT/'outputs/aco1-development-v2';manifest=a.read(root/'manifest.json');cfg=manifest['parent_config']
    pair=root/source/f'seed-{seed}';done=a.read(pair/'completion.json')
    assert a.sha(pair/'outcomes.csv.gz')==done['outcomes_sha256'] and a.sha(pair/'summary.csv')==done['summary_sha256']
    e,g,ev,_=a.load_source(source,cfg);train=a.rank(pd.concat([e,g],ignore_index=True),'sav-val-cf-training-order-v2')
    est,guide=a.split(train,cfg['head_fitting_fraction']);outcomes=pd.read_csv(pair/'outcomes.csv.gz');summary=pd.read_csv(pair/'summary.csv')
    assert len(summary)==16;cells=deviations=rows_total=0;fit_bindings={}
    for price,backend in [('masking','masking_suppression'),('robust','robust_no_feedback')]:
        spec=dict(type='original',pair=a.parent(source,seed),key=backend);a.fit_audit(spec,source,seed,cfg,train,ev)
        mp,_,_=a.paths(spec);assert a.sha(mp)==done['source_model_hashes'][backend]
        model,_,_=joblib.load(mp);a.bounded(model);pred,x,valid=model.predict(a.price_features(ev,a.FEATURES[source]))
        bankdir=pair/f'bank-{price}';r=a.read(bankdir/'construction.json')
        assert a.sha(bankdir/'construction.json')==done['bank_construction_hashes'][price]
        assert r['model_sha256']==a.sha(mp) and r['parent_binding']==manifest['parent_binding']
        for f,h in r['files'].items():assert a.sha(bankdir/f)==h;fit_bindings[str(bankdir/f)]=h
        fit_bindings[str(bankdir/'construction.json')]=a.sha(bankdir/'construction.json')
        bank,available,target,predictions,losses,weights=[np.load(bankdir/f'{name}.npy') for name in ['bank_encoded','bank_available','bank_log_targets','bank_predictions','bank_loss_patterns','coordinate_weights']]
        groups=a.read(bankdir/'field_groups.json')
        assert pd.read_csv(bankdir/'bank_ids.csv').listing_id.tolist()==guide.listing_id.tolist()
        assert not set(guide.listing_id)&set(ev.listing_id) and not set(guide.listing_id)&set(est.listing_id)
        np.testing.assert_array_equal(available,guide[list(a.ACTIONS)].notna().to_numpy())
        np.testing.assert_allclose(target,guide.target_log,atol=1e-12,rtol=0)
        np.testing.assert_allclose(bank,model.encoder.transform(a.price_features(guide,a.FEATURES[source])),atol=1e-12,rtol=0)
        np.testing.assert_allclose(losses,(predictions-target[:,None])**2,atol=1e-12,rtol=1e-10)
        assert sorted(j for v in groups.values() for j in v)==list(range(bank.shape[1]))
        for field,ix in groups.items():
            public=a.price_features(guide.iloc[:1],a.FEATURES[source]);other=public.copy()
            other[field]=54321. if field in model.encoder.numeric else '<AUDIT-NEW-CATEGORY>'
            changed=np.flatnonzero((model.encoder.transform(public)!=model.encoder.transform(other)).ravel())
            assert set(changed)<=set(ix)
            if field in model.encoder.categorical:assert (weights[ix]==.5).all()
            else:assert weights[ix[0]]==1 and (weights[ix[1:]]==.5).all()
        # All bank rows and all16 observation patterns, not a prediction sample.
        for pattern in range(16):
            public=a.price_features(guide,a.FEATURES[source]).copy()
            for f,field in enumerate(a.ACTIONS):
                if pattern&(1<<f):public[field]=np.nan
            encoded=model.encoder.transform(public)
            base=model.backbone.predict(model.encoder.tree_frame(public)).astype(np.float32)
            quote=model.predict_arrays(encoded[:,None,:],base[:,None])[:,0]
            np.testing.assert_allclose(quote,predictions[:,pattern],atol=2e-6,rtol=0)
        missing=ev[list(a.ACTIONS)].isna().to_numpy()[:,None,:]|a.BITS[None,:,:]
        for k in [25,10,50]:
            score=scores_direct(bank,available,losses,groups,weights,x,missing,k)
            method=f'{price}_aco1_k{k}'
            group=summary[summary.method==method]
            for _,s in group.iterrows():
                budget=float(s.budget);cp=a.OUT/'outcome-audit/aco'/source/f'seed-{seed}'/method/f'budget-{round(budget*10000):04d}.json'
                bindings={str(pair/'completion.json'):a.sha(pair/'completion.json'),str(pair/'outcomes.csv.gz'):a.sha(pair/'outcomes.csv.gz'),str(mp):a.sha(mp),**fit_bindings}
                if cp.exists():
                    prior=a.read(cp);assert prior['binding']['checker']==a.sha(Path(a.__file__)) and prior['aco_checker_sha256']==a.sha(Path(__file__))
                    assert prior['bindings']==bindings;result=prior
                else:
                    rr=outcomes[(outcomes.method==method)&np.isclose(outcomes.budget,budget)].copy()
                    rr=rr.set_index('listing_id').loc[ev.listing_id].reset_index()
                    rebuilt,batches,dev=a.independent_outcomes(pred,score,valid,ev,rr,budget)
                    for key,value in rebuilt.items():np.testing.assert_allclose(s[key],value,atol=1e-7,rtol=1e-10,err_msg=key)
                    result=dict(status='completed',stage='aco',dataset=source,seed=seed,method=method,budget=budget,
                        binding=dict(checker=a.sha(Path(a.__file__))),aco_checker_sha256=a.sha(Path(__file__)),bindings=bindings,
                        summary=rebuilt,batches=batches,outcome_rows=len(rr),legal_unilateral_deviations=dev)
                    a.write(cp,result);print('ACO_FULL_OUTCOME_AUDITED',source,seed,method,budget,flush=True)
                cells+=1;rows_total+=result['outcome_rows'];deviations+=result['legal_unilateral_deviations']
                if limit:
                    return dict(status='smoke_only',stage='aco',dataset=source,seed=seed,cells=cells,checker_sha256=a.sha(Path(a.__file__)),outcome_rows=rows_total,legal_unilateral_deviations=deviations)
        del model,pred,x,valid,score;gc.collect()
    a.write(a.OUT/'fit-audit/aco'/source/f'seed-{seed}'/'bank.json',dict(status='completed',bindings=fit_bindings,all_bank_patterns_checked=True,all_public_state_scores_reconstructed=True,checker_sha256=a.sha(Path(__file__))))
    result=dict(status='completed',stage='aco',dataset=source,seed=seed,cells=cells,checker_sha256=a.sha(Path(a.__file__)),outcome_rows=rows_total,legal_unilateral_deviations=deviations)
    a.write(a.OUT/'pair-checks/aco'/source/f'seed-{seed}.json',result);return result
