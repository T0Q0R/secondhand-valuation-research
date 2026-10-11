"""Fixed-profile cap experiment, using independently audited legal gain rows."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
import pandas as pd

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def write(p,x): Path(p).write_text(json.dumps(x,indent=2)+'\n')

def main(a):
    root,audit,out=a.run.resolve(),a.audit.resolve(),a.output.resolve()
    manifest=read(root/'manifest.json');done=read(root/'completion.json');checked=read(audit/'completion.json')
    assert done['status']==checked['status']=='completed' and done['cases']==checked['cases']==108
    ab=read(audit/'input_binding.json')
    assert sha(audit/'input_binding.json')==checked['input_binding_sha256']
    assert sha(root/'completion.json')==ab['completion_sha256']
    assert sha(root/'manifest.json')==ab['manifest_sha256']
    assert manifest['cost']==0 and manifest['batch_size']==100
    if out.exists(): raise FileExistsError(out)
    out.mkdir(parents=True)
    (out/'generator_snapshot.py').write_bytes(Path(__file__).read_bytes())
    contract=Path('plan/replay-cap-v1-contract.md')
    (out/'contract.md').write_bytes(contract.read_bytes())
    methods=['suppression','benefit','risk','cdm'];which=[manifest['methods'].index(m) for m in methods]
    inputs={str(p):sha(p) for p in [root/'manifest.json',root/'completion.json',audit/'completion.json',contract.resolve()]}
    write(out/'manifest.json',{'parent':str(root),'audit':str(audit),'methods':methods,
          'input_hashes':inputs,'scope':'exploratory fixed-profile verification-history cap; no fitted or equilibrium claims'})
    rows=[];receipts=[];count=0;started=time.time()
    for dataset,seed in manifest['pairs']:
        for price in manifest['prices']:
            rel=Path(dataset)/f'seed-{seed}'/price
            arrays=Path(manifest['source_run'])/rel/'evaluation_arrays.npz'
            with np.load(arrays) as z: pred=z['pred'];valid=z['valid']
            for budget in manifest['budgets']:
                case=rel/f'budget-{round(budget*10000):04d}'; parent=root/case
                parentdone=read(parent/'completion.json')
                for p,d in parentdone['files'].items(): assert sha(parent/p)==d
                sourcebinding=read(parent/'input_binding.json')['files']
                assert sourcebinding[str(arrays)]==sha(arrays)
                with np.load(parent/'deviations.npz') as z:
                    matrix=z['matrix'];loc=z['locator'];entryloc=z['entry_locator']
                    weights=z['probabilities'][which];original=z['envelopes'][:,which]
                idx=loc[:,0]*500+loc[:,1]*100+loc[:,2]%100
                before=pred[loc[:,2],loc[:,3]]-pred[loc[:,2],0]
                capped=np.minimum(matrix,before[:,None])@weights.T
                assert np.max(capped-matrix@weights.T)<=1e-10
                grid=np.full((5000,pred.shape[1],4),-np.inf)
                grid[idx,loc[:,3]]=capped
                best=np.argmax(grid,axis=1);envelope=grid.max(1)
                assert np.max(envelope-original)<=1e-10
                assert np.max(np.abs(grid[:,0,:]))<=1e-10
                assert (envelope>=-1e-10).all()
                folder=out/case;folder.mkdir(parents=True)
                np.savez_compressed(folder/'outcomes.npz',original=original,capped=envelope,
                                    best_states=best,entry_locator=entryloc)
                binding={str(p):sha(p) for p in [arrays,parent/'completion.json',parent/'deviations.npz',parent/'input_binding.json']}
                write(folder/'input_binding.json',binding)
                for profile,name in enumerate(manifest['profile_names']):
                    sel=entryloc[:,1]==profile
                    for j,method in enumerate(methods):
                        x=original[sel,j];y=envelope[sel,j]
                        rows.append({'dataset':dataset,'seed':seed,'price':price,'budget':budget,
                            'profile':name,'method':method,'n':len(x),'original_mean':x.mean(),
                            'capped_mean':y.mean(),'mean_reduction':(x-y).mean(),
                            'original_max':x.max(),'capped_max':y.max(),
                            'strictly_improved_fraction':((x-y)>1e-10).mean()})
                write(folder/'completion.json',{'status':'completed','legal_rows':len(matrix),
                      'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}})
                receipts.append({'path':str(case),'sha256':sha(folder/'completion.json')});count+=len(matrix)
            print(f'COMPLETED REPLAY CAP {rel}: all six budgets',flush=True)
    pd.DataFrame(rows).to_csv(out/'summary.csv',index=False)
    assert all(sha(p)==d for p,d in inputs.items())
    write(out/'completion.json',{'status':'completed','cases':len(receipts),'legal_rows':count,
        'entry_method_comparisons':len(receipts)*20000,'case_receipts':receipts,
        'seconds':time.time()-started,'independent_audit':'pending',
        'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()}})

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('run','audit','output'):p.add_argument('--'+n,type=Path,required=True)
    main(p.parse_args())
