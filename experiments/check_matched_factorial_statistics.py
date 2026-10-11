"""Independent raw-record, semantic contrast and count-weighted interval checks."""
import argparse, hashlib, itertools, json
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def close(a,b):np.testing.assert_allclose(a,b,atol=1e-9,rtol=1e-9)

def check_spec(spec):
    terms=spec['terms'];cells=[tuple(t['cell']) for t in terms];weights=[t['coefficient'] for t in terms]
    assert len(set(cells))==len(cells) and sum(weights)==0
    family=spec['family']
    if family=='feedback_allocation_interaction':
        assert len(cells)==4 and len({(c[0],c[1]) for c in cells})==1
        expected={('none','minimax'):1,('policy','minimax'):-1,('none','top_b'):-1,('policy','top_b'):1}
        assert {(c[2],c[3]):w for c,w in zip(cells,weights)}==expected
    else:
        assert len(cells)==2 and weights==[1,-1]
        a,b=cells
        if family=='joint_policy':
            assert a[:2]==b[:2] and a[2:]==('none','top_b') and b[2:]==('policy','minimax')
        else:
            index={'feedback':2,'allocation':3,'initial_objective':0,'acquisition':1}[family]
            assert all(a[j]==b[j] for j in range(4) if j!=index)
            expected={'feedback':[('none','policy')],'allocation':[('top_b','minimax')],
                      'initial_objective':[('masking','robust')],'acquisition':[('risk','benefit'),('risk','suppression')]}
            assert (a[index],b[index]) in expected[family]

def main(a):
    run=a.run.resolve();analysis=a.analysis.resolve();out=a.output.resolve();assert not out.exists()
    done=read(analysis/'completion.json');cfg=read(run/'manifest.json')['config']
    assert done['status']=='completed'
    for name,h in done['files'].items():assert sha(analysis/name)==h
    bindings=read(analysis/'input_binding.json')
    assert bindings[str(run/'manifest.json')]==sha(run/'manifest.json')
    for path,h in bindings.items():assert sha(Path(path))==h
    info=read(analysis/'contrast_specifications.json');specs=info['contrasts'];metrics=info['metrics'];cells=[tuple(x) for x in info['cells']]
    assert set(cells)==set(itertools.product(['masking','robust'],['suppression','benefit','risk'],['none','policy'],['top_b','minimax'])) and len(cells)==24
    assert Counter(s['family'] for s in specs)=={'feedback':12,'allocation':12,'initial_objective':12,'acquisition':16,'feedback_allocation_interaction':6,'joint_policy':6}
    assert len({s['id'] for s in specs})==64
    vectors=set()
    for spec in specs:
        check_spec(spec)
        vector=tuple(sorted((tuple(t['cell']),t['coefficient']) for t in spec['terms']))
        assert vector not in vectors;vectors.add(vector)
    report=pd.read_csv(analysis/'contrasts.csv');components=pd.read_csv(analysis/'contrast_components.csv')
    means=pd.read_csv(analysis/'cell_means_and_pareto.csv')
    key=['dataset','budget','contrast','metric'];assert not report.duplicated(key).any()
    assert len(report)==len(cfg['datasets'])*len(cfg['budgets'])*64*len(metrics)
    assert len(components)==len(cfg['datasets'])*len(cfg['budgets'])*sum(len(s['terms']) for s in specs)*len(metrics)
    expected_metrics=['positive_expected_log_inflation','honest_absolute_error','expected_attacked_absolute_error',
                      'failed_query_probability','deviation_envelope','expected_realized_positive_log_inflation',
                      'expected_signed_log_error','expected_squared_log_error']
    assert metrics==expected_metrics and info['budgets']==cfg['budgets']
    report=report.set_index(key);components=components.set_index(key+['cell'])
    assert components.index.is_unique
    means=means.set_index(['dataset','budget','initial_objective','score','feedback','allocation']);assert means.index.is_unique
    archive=np.load(analysis/'paired_tensors_and_draws.npz');rng=np.random.default_rng(20261009)
    checked=0;raw_rows=0
    for dataset in cfg['datasets']:
        raw={};diag={}
        for path in sorted(run.glob(dataset+'/seed-*/evaluation/budget-*/*/*/*/*/batch-*/outcomes.csv.gz')):
            assert sha(path)==bindings[str(path)]
            _,seed_name,_,budget_name,i,s,f,allocator,batch_name,_=path.relative_to(run).parts
            seed=int(seed_name.split('-')[1]);budget=int(budget_name.split('-')[1])/10000;batch=int(batch_name.split('-')[1]);cell=(i,s,f,allocator)
            frame=pd.read_csv(path);assert frame.batch.nunique()==1 and frame.batch.iloc[0]==batch
            assert len(frame)==cfg['batch_size'];raw_rows+=len(frame)
            k=(budget,seed,batch,cell);assert k not in raw
            raw[k]=np.array([frame[m].sum()/len(frame) for m in metrics])
            diag[k]=(frame.regret.max(),not bool(frame.converged.iloc[0]))
        seeds=list(archive[dataset+'__seeds']);batches=list(archive[dataset+'__batches']);S,B=len(seeds),len(batches)
        assert seeds==cfg['seeds'] and batches==list(range(B))
        assert len(raw)==len(cfg['budgets'])*S*B*24
        sd=rng.integers(0,S,(1000,S));bd=rng.integers(0,B,(1000,B))
        assert np.array_equal(sd,archive[dataset+'__seed_draws']) and np.array_equal(bd,archive[dataset+'__batch_draws'])
        sc=np.array([np.bincount(row,minlength=S) for row in sd]);bc=np.array([np.bincount(row,minlength=B) for row in bd])
        for budget_index,budget in enumerate(cfg['budgets']):
            cell_matrices={cell:np.array([[raw[(budget,s,b,cell)] for b in batches] for s in seeds]) for cell in cells}
            point={cell:mat.sum(axis=(0,1))/(S*B) for cell,mat in cell_matrices.items()}
            for ci,cell in enumerate(cells):
                close(cell_matrices[cell],archive[dataset+'__tensor'][budget_index,:,:,ci,:])
                row=means.loc[(dataset,budget,*cell)]
                close(row[metrics].to_numpy(dtype=float),point[cell])
                close(row.max_regret,max(diag[(budget,s,b,cell)][0] for s in seeds for b in batches))
                assert row.nonconverged_seed_batches==sum(diag[(budget,s,b,cell)][1] for s in seeds for b in batches)
                assert row.fitting_seeds==S and row.shared_batches==B and row.unique_listings==B*cfg['batch_size']
                for label,ix in [('triple',[0,1,3]),('with_attacked_mae',[0,1,2,3])]:
                    dominators=[other for other in cells if all(point[other][j]<=point[cell][j]+1e-10 for j in ix)
                                and any(point[other][j]<point[cell][j]-1e-10 for j in ix)]
                    assert row['nondominated_'+label]==(len(dominators)==0)
            for spec in specs:
                for mi,metric in enumerate(metrics):
                    matrix=sum(t['coefficient']*cell_matrices[tuple(t['cell'])][:,:,mi] for t in spec['terms'])
                    sampled=((sc@matrix)*bc).sum(axis=1)/(S*B)
                    lo,hi=np.percentile(sampled,[2.5,97.5]);r=report.loc[(dataset,budget,spec['id'],metric)]
                    close([r.difference,r.lower,r.upper],[matrix.sum()/(S*B),lo,hi])
                    assert r.family==spec['family'] and r.primary_capacity==(budget==cfg['factorial_primary_budget'])
                    assert r.smaller_is_preferred==(metric!='expected_signed_log_error')
                    for term in spec['terms']:
                        cell=tuple(term['cell']);component=components.loc[(dataset,budget,spec['id'],metric,'__'.join(cell))]
                        assert component.coefficient==term['coefficient'];close(component['mean'],point[cell][mi])
                    if len(spec['terms'])==2:
                        before,after=[point[tuple(t['cell'])] for t in spec['terms']]
                        relative=100*(before[0]-after[0])/before[0] if before[0]>0 else np.nan
                        honest=100*(after[1]-before[1])/before[1] if before[1]>0 else np.nan
                        close([r.inflation_reduction_percent,r.honest_mae_increase_percent],[relative,honest])
                        if np.isfinite(relative) and np.isfinite(honest):
                            assert r.point_gate==(relative>=10 and honest<=5)
                        else:assert pd.isna(r.point_gate)
                    else:
                        assert all(pd.isna(r[k]) for k in ['point_gate','inflation_reduction_percent','honest_mae_increase_percent'])
                    checked+=1
        print('STATISTICS VERIFIED '+dataset,flush=True)
    assert checked==len(report) and raw_rows==done['raw_outcome_rows']
    # The interaction can be positive while feedback is harmful under both allocators.
    toy={('none','top_b'):10,('policy','top_b'):13,('none','minimax'):8,('policy','minimax'):9}
    interaction=next(s for s in specs if s['family']=='feedback_allocation_interaction')
    value=sum(t['coefficient']*toy[tuple(t['cell'][2:])] for t in interaction['terms'])
    assert value==2 and toy[('none','top_b')]-toy[('policy','top_b')]<0 and toy[('none','minimax')]-toy[('policy','minimax')]<0
    mutated=json.loads(json.dumps(interaction));mutated['terms'][0]['coefficient']=-1;mutated['terms'][1]['coefficient']=1
    mutations=[]
    for name,fn in [('interaction_sign',lambda:check_spec(mutated)),('interval_endpoint',lambda:close(lo+.01,lo))]:
        try:fn()
        except AssertionError:mutations.append(name)
        else:raise AssertionError('Corruption accepted')
    for name,h in done['files'].items():assert sha(analysis/name)==h
    out.mkdir(parents=True);(out/'checker_snapshot.py').write_bytes(Path(__file__).read_bytes())
    result={'status':'completed','execution_smoke':done['execution_smoke'],'metric_contrast_rows':checked,
            'raw_outcome_rows':raw_rows,'contrast_vectors':len(specs),'mutations_rejected':mutations,
            'positive_interaction_with_two_harmful_feedback_effects_checked':True,
            'analysis_completion_sha256':sha(analysis/'completion.json'),
            'scope':'raw-record means, semantically validated contrasts, count-weighted intervals, point gates, components and Pareto flags; not new performance data or training-population uncertainty'}
    (out/'completion.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['run','analysis','output']:p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
