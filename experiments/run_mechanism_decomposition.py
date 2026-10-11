"""Signed fixed-model decomposition at saved, common-profile maximizing reports."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd
from savval import StateSpace

METHODS = ['suppression', 'benefit', 'risk', 'cdm']
COLUMNS = ['estimation', 'local_replay', 'capacity', 'total', 'local_query',
           'actual_query', 'actual_success', 'actual_failed', 'capacity_exclusion',
           'local_failed', 'truthful_anchor_replay']

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def read(p):
    return json.loads(Path(p).read_text())

def write(p, x):
    Path(p).write_text(json.dumps(x, indent=2, ensure_ascii=False)+'\n')

def generate(args):
    root, audit, out = args.run.resolve(), args.audit.resolve(), args.output.resolve()
    done, checked = [read(p/'completion.json') for p in (root, audit)]
    manifest = read(root/'manifest.json')
    assert done['status'] == checked['status'] == 'completed'
    assert done['cases'] == checked['cases'] == 108 and not done['execution_smoke']
    assert sha(root/'manifest.json') == done['manifest_sha256']
    audited_binding=read(audit/'input_binding.json')
    assert sha(audit/'input_binding.json')==checked['input_binding_sha256']
    assert sha(root/'completion.json')==audited_binding['completion_sha256']
    assert sha(root/'manifest.json')==audited_binding['manifest_sha256']
    assert manifest['cost'] == 0 and manifest['batch_size'] == 100
    if out.exists(): raise FileExistsError(out)
    out.mkdir(parents=True)
    sources = [Path(__file__).resolve(), Path(__file__).with_name('savval.py').resolve(),
               Path('plan/mechanism-decomposition-v1.md').resolve()]
    inputs = {str(p): sha(p) for p in sources + [root/'manifest.json',root/'completion.json',audit/'completion.json']}
    snap=out/'source_snapshot'; snap.mkdir()
    for p in sources: (snap/p.name).write_bytes(p.read_bytes())
    write(out/'manifest.json', {'parent':str(root),'audit':str(audit),'input_hashes':inputs,
          'pairs':manifest['pairs'],'prices':manifest['prices'],'methods':METHODS,
          'columns':COLUMNS,'budget':.1,'profiles':manifest['profile_names'],
          'scope':'fixed-model descriptive diagnostic; no fitting; unlimited capacity reference is infeasible'})
    space = StateSpace.build(manifest['maximum_hidden'])
    which=[manifest['methods'].index(m) for m in METHODS]
    source=Path(manifest['source_run'])
    started=time.time(); receipts=[]; rows=[]; rounded_ties=0; max_gap=0.0
    for dataset,seed in manifest['pairs']:
        for price in manifest['prices']:
            rel=Path(dataset)/f'seed-{seed}'/price
            parent=root/rel/'budget-1000'
            parent_done=read(parent/'completion.json')
            binding=read(parent/'input_binding.json')['files']
            for name,digest in parent_done['files'].items(): assert sha(parent/name)==digest
            for name,digest in binding.items(): assert sha(name)==digest
            arrays=source/rel/'evaluation_arrays.npz'
            assert str(arrays) in binding and sha(arrays)==binding[str(arrays)]
            with np.load(arrays) as f: pred,scores,valid=[f[k] for k in ('pred','scores','valid')]
            with np.load(parent/'deviations.npz') as f:
                winners=f['best_states'][:,which]; expected=f['envelopes'][:,which]
                loc=f['entry_locator']; weights=f['probabilities'][which]
            profiles=read(parent/'profiles.json')
            assert len(pred)==1000 and winners.shape==(5000,4)
            values=np.empty((5000,4,len(COLUMNS)))
            for profile in profiles:
                start=profile['start']; states=np.array(profile['states']); n=len(states)
                block=scores[:,start:start+n]; k=len(block)
                fields=block.argmax(-1); merits=block.max(-1)
                peer_merit=merits[:,np.arange(n),states]
                for i in range(n):
                    global_i=start+i
                    row=(profile['batch']*5+profile['profile'])*n+i
                    assert np.array_equal(loc[row],[profile['batch'],profile['profile'],global_i])
                    own=merits[:,i,:]; own_field=fields[:,i,:]
                    peer_ids=np.delete(np.arange(n),i)
                    ahead=((peer_merit[:,None,peer_ids]>own[:,:,None]) |
                           ((peer_merit[:,None,peer_ids]==own[:,:,None]) & (peer_ids[None,None,:]<i))).sum(-1)
                    eligible=np.isfinite(own)&(own>0)
                    selected=eligible&(ahead<10)
                    cand=np.broadcast_to(np.arange(pred.shape[1]),own.shape)
                    next_state=space.query_next[cand,own_field]
                    local_state=np.where(eligible,next_state,cand)
                    actual_state=np.where(selected,next_state,cand)
                    local=pred[global_i,local_state].T
                    actual=pred[global_i,actual_state].T
                    gains=(actual-pred[global_i,0])@weights.T
                    numerical_best=np.argmax(np.where(valid[global_i,:,None],gains,-np.inf),axis=0)
                    best=winners[row]
                    assert valid[global_i,best].all()
                    gap=float(np.max(gains[numerical_best,np.arange(4)]-gains[best,np.arange(4)]))
                    assert gap<=1e-10
                    rounded_ties+=int(np.count_nonzero(numerical_best!=best));max_gap=max(max_gap,gap)
                    assert np.allclose(gains[best,np.arange(4)],expected[row],atol=1e-10,rtol=0)
                    recover=(next_state!=cand)
                    for m,h in enumerate(best):
                        w=weights[m]; qh=pred[global_i,h]; q0=pred[global_i,0]
                        qlocal=local[h]@w; qactual=actual[h]@w
                        # The truthful-anchor query, if any, cannot reveal a
                        # different field withheld in h. Explicitly verify.
                        base_field=own_field[:,0]; base_selected=selected[:,0]
                        anchor_state=np.where(base_selected,space.query_next[h,base_field],h)
                        anchor=(pred[global_i,anchor_state]@w-qh)
                        v=[qh-q0, qlocal-qh, qactual-qlocal, qactual-q0,
                           eligible[:,h]@w, selected[:,h]@w,
                           (selected[:,h]&recover[:,h])@w,
                           (selected[:,h]&~recover[:,h])@w,
                           (eligible[:,h]&~selected[:,h])@w,
                           (eligible[:,h]&~recover[:,h])@w, anchor]
                        values[row,m]=v
            assert np.allclose(values[:,:,:3].sum(-1),expected,atol=1e-10,rtol=0)
            assert np.max(np.abs(values[:,:,-1]))<1e-10
            folder=out/rel; folder.mkdir(parents=True)
            np.savez_compressed(folder/'decomposition.npz',values=values,winners=winners,locator=loc,weights=weights)
            bound={str(parent/p):sha(parent/p) for p in ('completion.json','input_binding.json','deviations.npz','profiles.json')}
            bound[str(arrays)]=sha(arrays)
            write(folder/'input_binding.json',bound)
            for profile in range(5):
                for m,method in enumerate(METHODS):
                    block=values[loc[:,1]==profile,m]
                    row={'dataset':dataset,'seed':seed,'price':price,'profile':manifest['profile_names'][profile],
                         'method':method,'n':len(block),**dict(zip(COLUMNS,block.mean(0)))}
                    row['conditional_failed_rate']=row['actual_failed']/row['actual_query'] if row['actual_query'] else None
                    rows.append(row)
            assert all(sha(p)==d for p,d in bound.items())
            write(folder/'completion.json',{'status':'completed','rows':20000,
                'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}})
            receipts.append({'path':str(rel),'sha256':sha(folder/'completion.json')})
            print(f'COMPLETED {rel}: 20000 signed decompositions',flush=True)
    pd.DataFrame(rows).to_csv(out/'summary.csv',index=False)
    assert all(sha(p)==d for p,d in inputs.items())
    write(out/'completion.json',{'status':'completed','cases':len(receipts),'rows':len(receipts)*20000,
          'case_receipts':receipts,'seconds':time.time()-started,'independent_audit':'pending',
          'rounding_tie_winners_retained':rounded_ties,'maximum_saved_winner_gap':max_gap,
          'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()}})

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('run','audit','output'): parser.add_argument('--'+name,type=Path,required=True)
    generate(parser.parse_args())
