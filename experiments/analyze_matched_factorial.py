"""Complete factorial contrasts, paired crossed intervals and multiobjective cells."""
import argparse, hashlib, itertools, json
from pathlib import Path
import numpy as np
import pandas as pd

FACTORS=(('masking','robust'),('suppression','benefit','risk'),('none','policy'),('top_b','minimax'))
CELLS=list(itertools.product(*FACTORS))
METRICS=['positive_expected_log_inflation','honest_absolute_error',
         'expected_attacked_absolute_error','failed_query_probability','deviation_envelope',
         'expected_realized_positive_log_inflation','expected_signed_log_error','expected_squared_log_error']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')

def specifications():
    out=[]
    def add(family,label,terms):
        assert sum(c for _,c in terms)==0 and len({cell for cell,_ in terms})==len(terms)
        assert all(cell in CELLS for cell,_ in terms)
        out.append({'id':family+'__'+label,'family':family,
                    'terms':[{'cell':list(cell),'coefficient':c} for cell,c in terms]})
    for i,s,a in itertools.product(FACTORS[0],FACTORS[1],FACTORS[3]):
        add('feedback','__'.join([i,s,a]),[((i,s,'none',a),1),((i,s,'policy',a),-1)])
    for i,s,f in itertools.product(FACTORS[0],FACTORS[1],FACTORS[2]):
        add('allocation','__'.join([i,s,f]),[((i,s,f,'top_b'),1),((i,s,f,'minimax'),-1)])
    for s,f,a in itertools.product(FACTORS[1],FACTORS[2],FACTORS[3]):
        add('initial_objective','__'.join([s,f,a]),[(('masking',s,f,a),1),(('robust',s,f,a),-1)])
    for i,f,a,s in itertools.product(FACTORS[0],FACTORS[2],FACTORS[3],['benefit','suppression']):
        add('acquisition','__'.join([i,f,a,'risk_minus_'+s]),[((i,'risk',f,a),1),((i,s,f,a),-1)])
    for i,s in itertools.product(FACTORS[0],FACTORS[1]):
        add('feedback_allocation_interaction','__'.join([i,s]),
            [((i,s,'none','minimax'),1),((i,s,'policy','minimax'),-1),
             ((i,s,'none','top_b'),-1),((i,s,'policy','top_b'),1)])
    assert len(out)==58
    for i,s in itertools.product(FACTORS[0],FACTORS[1]):
        add('joint_policy','__'.join([i,s]),[((i,s,'none','top_b'),1),((i,s,'policy','minimax'),-1)])
    assert len(out)==64 and len({x['id'] for x in out})==64
    return out

def paired_matrix(tensor,spec,metric):
    # tensor has seed, batch, cell, metric axes.
    result=np.zeros(tensor.shape[:2],dtype=float)
    for term in spec['terms']:
        result+=term['coefficient']*tensor[:,:,CELLS.index(tuple(term['cell'])),metric]
    return result

def intervals(matrix,seed_draws,batch_draws):
    values=matrix[seed_draws[:,:,None],batch_draws[:,None,:]].mean(axis=(1,2))
    return np.quantile(values,[.025,.975])

def analyze(a):
    run=a.run.resolve();out=a.output.resolve();assert not out.exists()
    manifest=read(run/'manifest.json');cfg=manifest['config'];parent=read(run/'completion.json')
    checked=read(a.outcome_audit/'completion.json');fit=read(a.fit_audit/'completion.json')
    assert checked['status']==fit['status']=='completed'
    assert checked['parent_completion_sha256']==sha(run/'completion.json')
    assert checked['manifest_sha256']==sha(run/'manifest.json')
    assert fit['coverage']=='all_configured_fits' and fit['inputs']['run_manifest_sha256']==sha(run/'manifest.json')
    expected_pairs={(d,s) for d in cfg['datasets'] for s in cfg['seeds']}
    assert set(map(tuple,fit['inputs']['selected_pairs']))==expected_pairs
    assert fit['source_seed_pairs']==len(expected_pairs)
    assert bool(fit['execution_smoke'])==bool(checked['execution_smoke'])==bool(cfg.get('execution_smoke',False))
    if not cfg.get('execution_smoke',False):
        assert len(expected_pairs)==30 and len(cfg['seeds'])==10 and len(cfg['budgets'])==6
    expected_count=len(expected_pairs)*len(cfg['budgets'])*24
    assert parent['method_cells']==checked['method_cells']==expected_count
    assert sha(run/'summary.csv')==parent['summary_sha256']
    binding={str(run/'manifest.json'):sha(run/'manifest.json'),str(run/'completion.json'):sha(run/'completion.json'),
             str(a.outcome_audit/'completion.json'):sha(a.outcome_audit/'completion.json'),
             str(a.fit_audit/'completion.json'):sha(a.fit_audit/'completion.json')}
    for dataset,seed in sorted(expected_pairs):
        receipt=a.fit_audit/dataset/f'seed-{seed}.json'
        r=read(receipt);assert r['status']=='completed' and (r['dataset'],r['seed'])==(dataset,seed)
        assert r['independently_refitted_heads']==14
        for p,h in r['bound_files'].items(): assert sha(Path(p))==h
        binding[str(receipt.resolve())]=sha(receipt)
    all_paths=sorted(run.glob('*/seed-*/evaluation/budget-*/*/*/*/*/completion.json'))
    assert len(all_paths)==expected_count
    assert set(checked['cell_completion_hashes'])=={str(p) for p in all_paths}
    specs=specifications();rng=np.random.default_rng(20261009)
    contrast_rows=[];components=[];cell_rows=[];matrices={};read_rows=0
    out.mkdir(parents=True)
    for dataset in cfg['datasets']:
        source_paths=[p for p in all_paths if p.relative_to(run).parts[0]==dataset]
        canonical={};raw={};diagnostics={}
        for cp in source_paths:
            assert sha(cp)==checked['cell_completion_hashes'][str(cp)]
            binding[str(cp)]=sha(cp);receipt=read(cp)
            _,seed_name,_,budget_name,i,s,f,alloc=cp.parent.relative_to(run).parts
            seed=int(seed_name.split('-')[1]);budget=int(budget_name.split('-')[1])/10000
            assert seed in cfg['seeds'] and budget in cfg['budgets']
            cell=(i,s,f,alloc);assert cell in CELLS
            for name,h in [('summary.json',receipt['summary_sha256']),('inputs.json',receipt['inputs_sha256'])]:
                assert sha(cp.parent/name)==h
            frames=[]
            for name,h in sorted(receipt['batch_receipts'].items()):
                bp=cp.parent/name;assert sha(bp)==h;batch_done=read(bp)
                path=bp.parent/'outcomes.csv.gz';assert sha(path)==batch_done['outcomes_sha256'];binding[str(path)]=sha(path)
                frame=pd.read_csv(path);batch=int(bp.parent.name.split('-')[1]);assert (frame.batch==batch).all()
                assert len(frame)==cfg['batch_size'] and frame.listing_id.is_unique
                item_data=list(zip(frame.listing_id.astype(str),frame.target_log))
                if batch not in canonical:canonical[batch]=item_data
                assert item_data==canonical[batch]
                assert np.isfinite(frame[METRICS+['regret']].to_numpy()).all()
                assert frame.converged.nunique()==1
                key=(budget,seed,batch,cell);assert key not in raw
                raw[key]=frame[METRICS].mean().to_numpy()
                diagnostics[key]=(float(frame.regret.max()),not bool(frame.converged.iloc[0]))
                read_rows+=len(frame)
            assert len(receipt['batch_receipts'])==len(canonical)
        batches=sorted(canonical);seeds=cfg['seeds'];budgets=cfg['budgets']
        assert batches==list(range(len(batches)))
        if not cfg.get('execution_smoke',False):assert len(batches)==10
        assert len({x[0] for items in canonical.values() for x in items})==len(batches)*cfg['batch_size']
        tensor=np.empty((len(budgets),len(seeds),len(batches),24,len(METRICS)))
        for b,seed,batch,cell in itertools.product(budgets,seeds,batches,CELLS):
            tensor[budgets.index(b),seeds.index(seed),batches.index(batch),CELLS.index(cell)]=raw[(b,seed,batch,cell)]
        assert len(raw)==int(np.prod(tensor.shape[:-1]))
        sd=rng.integers(0,len(seeds),(1000,len(seeds)));bd=rng.integers(0,len(batches),(1000,len(batches)))
        matrices[dataset+'__tensor']=tensor;matrices[dataset+'__seed_draws']=sd;matrices[dataset+'__batch_draws']=bd
        matrices[dataset+'__seeds']=np.asarray(seeds);matrices[dataset+'__batches']=np.asarray(batches)
        for bi,budget in enumerate(budgets):
            means=tensor[bi].mean(axis=(0,1))
            for ci,cell in enumerate(CELLS):
                row={'dataset':dataset,'budget':budget,'initial_objective':cell[0],'score':cell[1],'feedback':cell[2],'allocation':cell[3],
                     'fitting_seeds':len(seeds),'shared_batches':len(batches),'unique_listings':len(batches)*cfg['batch_size']}
                row.update(dict(zip(METRICS,means[ci])))
                row['max_regret']=max(diagnostics[(budget,s,b,cell)][0] for s in seeds for b in batches)
                row['nonconverged_seed_batches']=sum(diagnostics[(budget,s,b,cell)][1] for s in seeds for b in batches)
                for name,ix in [('triple',[0,1,3]),('with_attacked_mae',[0,1,2,3])]:
                    values=means[:,ix];v=values[ci]
                    row['nondominated_'+name]=not any(np.all(other<=v+1e-10) and np.any(other<v-1e-10) for other in values)
                cell_rows.append(row)
            for spec in specs:
                base={'dataset':dataset,'budget':budget,'primary_capacity':budget==cfg['factorial_primary_budget'],
                      'contrast':spec['id'],'family':spec['family']}
                gate=None;relative=None;honest=None
                if len(spec['terms'])==2:
                    reference,candidate=[CELLS.index(tuple(t['cell'])) for t in spec['terms']]
                    before,after=means[reference],means[candidate]
                    relative=100*(before[0]-after[0])/before[0] if before[0]>0 else None
                    honest=100*(after[1]-before[1])/before[1] if before[1]>0 else None
                    if relative is not None and honest is not None:gate=relative>=10 and honest<=5
                for mi,metric in enumerate(METRICS):
                    matrix=paired_matrix(tensor[bi],spec,mi);lo,hi=intervals(matrix,sd,bd)
                    contrast_rows.append({**base,'metric':metric,'difference':float(matrix.mean()),'lower':float(lo),'upper':float(hi),
                        'smaller_is_preferred':metric!='expected_signed_log_error','point_gate':gate,
                        'inflation_reduction_percent':relative,'honest_mae_increase_percent':honest})
                    for term in spec['terms']:
                        ci=CELLS.index(tuple(term['cell']))
                        components.append({**base,'metric':metric,'cell':'__'.join(term['cell']),
                                           'coefficient':term['coefficient'],'mean':float(means[ci,mi])})
        print(f'ANALYZED complete source {dataset}',flush=True)
    assert read_rows==checked['outcome_rows']
    assert all(sha(Path(p))==h for p,h in binding.items())
    pd.DataFrame(contrast_rows).to_csv(out/'contrasts.csv',index=False)
    pd.DataFrame(components).to_csv(out/'contrast_components.csv',index=False)
    pd.DataFrame(cell_rows).to_csv(out/'cell_means_and_pareto.csv',index=False)
    np.savez_compressed(out/'paired_tensors_and_draws.npz',**matrices)
    write(out/'contrast_specifications.json',{'cells':[list(c) for c in CELLS],'metrics':METRICS,'budgets':cfg['budgets'],'contrasts':specs})
    write(out/'input_binding.json',binding)
    (out/'analysis_snapshot.py').write_bytes(Path(__file__).read_bytes())
    write(out/'completion.json',{'status':'completed','execution_smoke':bool(cfg.get('execution_smoke',False)),
        'method_cells':expected_count,'raw_outcome_rows':read_rows,'factor_contrasts_per_source_capacity':58,
        'additional_joint_contrasts':6,'metric_contrast_rows':len(contrast_rows),'resamples':1000,'rng_seed':20261009,
        'source_seed_pairs':len(expected_pairs),'scope':'complete paired factor effects and interaction diagnostics; unadjusted exploratory fixed-training-record intervals; point Pareto dominance only',
        'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()}})

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['run','fit-audit','outcome-audit','output']:p.add_argument('--'+name,type=Path,required=True)
    analyze(p.parse_args())
