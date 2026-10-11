"""Independent full-sort replay; imports no generator or market helpers."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def write(p,x): Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def close(a,b):
    if not np.allclose(a,b,rtol=0,atol=1e-10,equal_nan=True):
        raise AssertionError('Independent numerical reconstruction mismatch')

def main(args):
    run,out=args.run.resolve(),args.output.resolve()
    manifest=read(run/'manifest.json'); done=read(run/'completion.json')
    initial_completion_hash=sha(run/'completion.json')
    assert done['status']=='completed' and done['cases']==18 and done['rows']==360000
    for name,d in done['files'].items(): assert sha(run/name)==d
    for name,d in manifest['input_hashes'].items(): assert sha(name)==d
    if out.exists(): raise FileExistsError(out)
    out.mkdir(parents=True)
    (out/'auditor_snapshot.py').write_bytes(Path(__file__).read_bytes())
    masks=np.array([[a in group for a in range(4)] for size in range(3)
                    for group in itertools.combinations(range(4),size)],bool)
    lookup={tuple(m):i for i,m in enumerate(masks)}
    transition=np.empty((11,4),int)
    for h in range(11):
        for f in range(4):
            m=masks[h].copy();m[f]=False;transition[h,f]=lookup[tuple(m)]
    source=Path(read(Path(manifest['parent'])/'manifest.json')['source_run'])
    rows=0; legal_rule_worlds=0; summary=[]; mutations=set(); receipts=[]
    started=time.time()
    for receipt in done['case_receipts']:
        rel=Path(receipt['path']);folder=run/rel
        assert sha(folder/'completion.json')==receipt['sha256']
        for p,d in read(folder/'completion.json')['files'].items(): assert sha(folder/p)==d
        bound=read(folder/'input_binding.json')
        for p,d in bound.items(): assert sha(p)==d
        parent=Path(manifest['parent'])/rel/'budget-1000'
        with np.load(source/rel/'evaluation_arrays.npz') as f:
            predictions=f['pred'];score=f['scores'];valid=f['valid']
        with np.load(parent/'deviations.npz') as f:
            expected=f['envelopes'][:,[1,2,3,13]]
            winners=f['best_states'][:,[1,2,3,13]]
            weights=f['probabilities'][[1,2,3,13]]
            locator=f['entry_locator']
        with np.load(folder/'decomposition.npz') as f:
            stored=f['values'];close(f['weights'],weights)
            assert np.array_equal(f['winners'],winners) and np.array_equal(f['locator'],locator)
        reconstructed=np.empty_like(stored)
        for profile in read(parent/'profiles.json'):
            start=profile['start'];states=np.array(profile['states']);n=len(states)
            block=score[:,start:start+n]
            # Explicit complete hypothetical reports and stable sorting of
            # every item's merit; no pairwise-ahead shortcut from generator.
            for i in range(n):
                g=start+i; report=np.broadcast_to(states,(11,n)).copy()
                report[:,i]=np.arange(11)
                all_scores=block[:,np.arange(n)[None,:],report,:]
                field=np.argmax(all_scores,axis=-1)
                merit=np.max(all_scores,axis=-1)
                ranking=np.argsort(-merit,axis=-1,kind='stable')
                eligible=np.isfinite(merit)&(merit>0)
                chosen=np.zeros_like(eligible)
                np.put_along_axis(chosen,ranking[:,:,:10],True,axis=-1)
                chosen &= eligible
                assert np.max(chosen.sum(-1))<=10
                legal_rule_worlds+=int(valid[g].sum())*12
                ownfield=field[:,:,i];local_query=eligible[:,:,i]
                actual_query=chosen[:,:,i]
                after=transition[np.arange(11)[None,:],ownfield]
                local=predictions[g,np.where(local_query,after,np.arange(11)[None,:])]
                actual=predictions[g,np.where(actual_query,after,np.arange(11)[None,:])]
                signed=(actual.T-predictions[g,0])@weights.T
                row=(profile['batch']*5+profile['profile'])*n+i
                assert np.array_equal(locator[row],[profile['batch'],profile['profile'],g])
                numerical_best=np.argmax(np.where(valid[g,:,None],signed,-np.inf),axis=0)
                best=winners[row]
                assert valid[g,best].all()
                close(signed[numerical_best,np.arange(4)],signed[best,np.arange(4)])
                close(signed[best,np.arange(4)],expected[row])
                for m,h in enumerate(best):
                    w=weights[m];qh=predictions[g,h];q0=predictions[g,0]
                    ql=local[:,h]@w;qa=actual[:,h]@w
                    success=masks[h,ownfield[:,h]]
                    baseline_field=ownfield[:,0]
                    frozen=np.where(actual_query[:,0],transition[h,baseline_field],h)
                    reconstructed[row,m]=[qh-q0,ql-qh,qa-ql,qa-q0,
                        local_query[:,h]@w,actual_query[:,h]@w,
                        (actual_query[:,h]&success)@w,(actual_query[:,h]&~success)@w,
                        (local_query[:,h]&~actual_query[:,h])@w,
                        (local_query[:,h]&~success)@w,predictions[g,frozen]@w-qh]
        close(stored,reconstructed)
        close(stored[:,:,:3].sum(-1),expected)
        close(stored[:,:,5],stored[:,:,6]+stored[:,:,7])
        close(stored[:,:,4],stored[:,:,5]+stored[:,:,8])
        close(stored[:,:,-1],0)
        if not mutations:
            for name,col in [('estimation',0),('capacity',2),('failed_query',7),('truthful_anchor',10)]:
                corrupted=stored.copy();corrupted[0,0,col]+=.01
                try: close(corrupted,reconstructed)
                except AssertionError: mutations.add(name)
                else: raise AssertionError('Mutation incorrectly accepted')
        dataset,seed,price=rel.parts;seed=int(seed.removeprefix('seed-'))
        for p,profile in enumerate(manifest['profiles']):
            for m,method in enumerate(manifest['methods']):
                v=reconstructed[locator[:,1]==p,m].mean(0)
                r={'dataset':dataset,'seed':seed,'price':price,'profile':profile,'method':method,
                   'n':int((locator[:,1]==p).sum()),**dict(zip(manifest['columns'],v))}
                r['conditional_failed_rate']=v[7]/v[5] if v[5] else np.nan
                summary.append(r)
        assert all(sha(p)==d for p,d in bound.items())
        rows+=len(stored)*4
        receipts.append({'case':str(rel),'sha256':sha(folder/'completion.json')})
        print(f'AUDITED {rel}: all 20000 rows',flush=True)
    keys=['dataset','seed','price','profile','method']
    calculated=pd.DataFrame(summary).sort_values(keys).reset_index(drop=True)
    saved=pd.read_csv(run/'summary.csv').sort_values(keys).reset_index(drop=True)
    assert calculated[keys].equals(saved[keys])
    close(calculated.drop(columns=keys),saved.drop(columns=keys))
    calculated.to_csv(out/'verified_summary.csv',index=False)
    assert sha(run/'completion.json')==initial_completion_hash
    write(out/'completion.json',{'status':'completed','rows':rows,'cases':len(receipts),
        'legal_rule_worlds_full_sorted':legal_rule_worlds,'mutations_rejected':sorted(mutations),
        'parent_completion_sha256':sha(run/'completion.json'),'case_receipts':receipts,
        'seconds':time.time()-started,'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()},
        'scope':'Every decomposition row independently reconstructed by full public batch sorting; fixed models, hypothetical deviations, no causal market attribution'})

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('run','output'): p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
