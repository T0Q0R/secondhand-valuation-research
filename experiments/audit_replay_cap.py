"""Reconstruct absolute post-replay quotes independently of cap generator."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
import pandas as pd

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def close(a,b):
    if not np.allclose(a,b,atol=1e-10,rtol=0):raise AssertionError('Absolute-quote replay mismatch')
def write(p,x):Path(p).write_text(json.dumps(x,indent=2)+'\n')

def main(a):
    run,out=a.run.resolve(),a.output.resolve();manifest=read(run/'manifest.json');done=read(run/'completion.json')
    completion_hash=sha(run/'completion.json')
    assert done['status']=='completed' and done['cases']==108
    for p,d in done['files'].items():assert sha(run/p)==d
    for p,d in manifest['input_hashes'].items():assert sha(p)==d
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True);(out/'auditor_snapshot.py').write_bytes(Path(__file__).read_bytes())
    parent=Path(manifest['parent']);source_manifest=read(parent/'manifest.json')
    original=Path(source_manifest['source_run']);which=[source_manifest['methods'].index(m) for m in manifest['methods']]
    count=0;summary=[];mutations=[];started=time.time()
    for receipt in done['case_receipts']:
        rel=Path(receipt['path']);folder=run/rel
        assert sha(folder/'completion.json')==receipt['sha256']
        for p,d in read(folder/'completion.json')['files'].items():assert sha(folder/p)==d
        binding=read(folder/'input_binding.json')
        for p,d in binding.items():assert sha(p)==d
        dataset,seed,price,budget_name=rel.parts
        with np.load(original/rel.parent/'evaluation_arrays.npz') as z:pred=z['pred']
        with np.load(parent/rel/'deviations.npz') as z:
            loc=z['locator'];matrix=z['matrix'];weights=z['probabilities'][which]
            old=z['envelopes'][:,which];entry=z['entry_locator']
        with np.load(folder/'outcomes.npz') as z:
            stored=z['capped'];winners=z['best_states'];close(z['original'],old)
            assert np.array_equal(z['entry_locator'],entry)
        unique,inv=np.unique(loc[:,:3],axis=0,return_inverse=True)
        assert np.array_equal(unique,entry)
        q0=pred[loc[:,2],0];before=pred[loc[:,2],loc[:,3]]
        after=q0[:,None]+matrix
        # Cap absolute prices independently, then take expected price and
        # subtract truth. The generator works directly on signed gains.
        capped_quote=np.minimum(before[:,None],after)
        gain=capped_quote@weights.T-q0[:,None]
        expected=np.full_like(stored,-np.inf)
        np.maximum.at(expected,inv,gain)
        close(expected,stored)
        assert np.max(stored-old)<=1e-10
        close(after[loc[:,3]==0],q0[loc[:,3]==0,None]+np.zeros((1,12)))
        close(gain[loc[:,3]==0],0)
        for method in range(4):
            selected=loc[:,3]==winners[inv,method]
            assert np.array_equal(np.bincount(inv[selected],minlength=5000),np.ones(5000))
            close(gain[selected,method],stored[:,method])
        count+=len(loc)
        if not mutations:
            for name,delta in [('quote_increase',.01),('fabricated_reduction',-.01)]:
                wrong=stored.copy();wrong[0,0]+=delta
                try:close(wrong,expected)
                except AssertionError:mutations.append(name)
                else:raise AssertionError('Mutation accepted')
            # A mixture must cap each realization, not the expected quote.
            per_realization=np.minimum(5.,np.array([0.,10.]))@np.array([.5,.5])
            after_expectation=min(5.,np.array([0.,10.])@np.array([.5,.5]))
            assert per_realization==2.5 and after_expectation==5.
            mutations.append('cap_after_expectation_counterexample')
        for p,profile in enumerate(source_manifest['profile_names']):
            sel=entry[:,1]==p
            for j,method in enumerate(manifest['methods']):
                x=old[sel,j];y=expected[sel,j]
                summary.append({'dataset':dataset,'seed':int(seed.split('-')[1]),'price':price,
                    'budget':int(budget_name.split('-')[1])/10000,'profile':profile,'method':method,
                    'n':len(x),'original_mean':x.mean(),'capped_mean':y.mean(),
                    'mean_reduction':(x-y).mean(),'original_max':x.max(),'capped_max':y.max(),
                    'strictly_improved_fraction':((x-y)>1e-10).mean()})
        assert all(sha(p)==d for p,d in binding.items())
        if budget_name=='budget-3000':print(f'AUDITED CAP {rel.parent}: all six budgets',flush=True)
    keys=['dataset','seed','price','budget','profile','method']
    calculated=pd.DataFrame(summary).sort_values(keys).reset_index(drop=True)
    saved=pd.read_csv(run/'summary.csv').sort_values(keys).reset_index(drop=True)
    assert calculated[keys].equals(saved[keys]);close(calculated.drop(columns=keys),saved.drop(columns=keys))
    calculated.to_csv(out/'verified_summary.csv',index=False)
    assert count==done['legal_rows'] and sha(run/'completion.json')==completion_hash
    write(out/'completion.json',{'status':'completed','cases':108,'legal_rows':count,
          'legal_rule_quote_checks':count*12,'entry_method_comparisons':2160000,
          'truthful_quotes_unchanged':True,'pointwise_unilateral_dominance':True,
          'mutations_rejected':mutations,'parent_completion_sha256':completion_hash,
          'seconds':time.time()-started,'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()},
          'scope':'fixed peers and scores; capped absolute quote reconstruction, not response/equilibrium or attacked MAE guarantee'})

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('run','output'):p.add_argument('--'+n,type=Path,required=True)
    main(p.parse_args())
