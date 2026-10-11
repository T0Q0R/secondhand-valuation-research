"""Post-hoc sufficient stability conditions on every saved allocation profile."""
import argparse,hashlib,itertools,json
from pathlib import Path
import numpy as np
import pandas as pd

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(a):
    run=a.run;out=a.output;assert not out.exists()
    audit=json.loads((a.audit/'completion.json').read_text())
    assert audit['status']=='completed' and audit['summaries_recomputed']==108 and audit['outcome_rows']==108000
    assert audit['parent_completion_sha256']==sha(run/'completion.json')
    masks=[tuple(j in group for j in range(4)) for k in range(3) for group in itertools.combinations(range(4),k)]
    lookup={v:i for i,v in enumerate(masks)}
    records=[];binding={str(run/'completion.json'):sha(run/'completion.json'),str(a.audit/'completion.json'):sha(a.audit/'completion.json')}
    paths=sorted(run.glob('*/seed-*/*/*/*/batch-*/completion.json'));assert len(paths)==1080
    for cp in paths:
        assert sha(cp)==audit['batch_completion_hashes'][str(cp)]
        done=json.loads(cp.read_text());path=cp.parent/'execution.npz'
        assert sha(path)==done['execution_sha256'];binding[str(cp)]=sha(cp);binding[str(path)]=sha(path)
        dataset,seed,price,score,allocator,batch=cp.parent.relative_to(run).parts
        z=np.load(path);states=z['states'];pred=z['pred'];n=len(states)
        scores=z['scores'][np.arange(n),states];best=scores.max(axis=1)
        finite=np.isfinite(best);positive=finite&(best>0);g=best[positive]
        fields=np.argmax(scores,axis=1);second=np.sort(scores,axis=1)[:,-2]
        gaps=np.full(n,np.inf);two_finite=positive&np.isfinite(second)
        gaps[two_finite]=best[two_finite]-second[two_finite]
        before=pred[np.arange(n),states];after=before.copy()
        for i in np.flatnonzero(positive):
            recovered=list(masks[states[i]]);recovered[fields[i]]=False
            after[i]=pred[i,lookup[tuple(recovered)]]
        R=float(np.max(np.abs(after-before)))
        for alpha in [.001,.01,.05,.1]:
            row={'dataset':dataset,'seed':int(seed.split('-')[1]),'price':price,'score':score,
                 'generating_allocator':allocator,'batch':int(batch.split('-')[1]),'relative_radius':alpha,
                 'positive_items':int(positive.sum()),'recovery_span':R,'radius_defined':len(g)>0,
                 'zero_recovery_span':R==0}
            if len(g)==0:
                row.update(delta=None,minimum_score_floor=None,support_condition=False,field_condition=False,
                           minimax_certificate=False,nontrivial_probability_bound=False,probability_bound=None,
                           expected_quote_bound=None,top_b_constancy_certificate=False)
            else:
                delta=float(alpha*np.median(g));m=float(g.min()-delta)
                support=bool((g>delta).all() and (best[finite&~positive]<-delta).all())
                fields_ok=bool((gaps[positive]>2*delta).all())
                certified=support and fields_ok
                probability=min(1.,2*delta/m) if certified else None
                ranked=np.sort(g)[::-1];b=done['capacity']
                rank_ok=b==0 or b>=len(g) or ranked[b-1]-ranked[b]>2*delta
                row.update(delta=delta,minimum_score_floor=m,support_condition=support,field_condition=fields_ok,
                           minimax_certificate=certified,nontrivial_probability_bound=certified and probability<1,
                           probability_bound=probability,expected_quote_bound=R*probability if certified else None,
                           top_b_constancy_certificate=bool(certified and rank_ok))
            records.append(row)
    data=pd.DataFrame(records);assert len(data)==4320
    keys=['dataset','price','score','generating_allocator','relative_radius']
    cols=['radius_defined','support_condition','field_condition','minimax_certificate',
          'nontrivial_probability_bound','top_b_constancy_certificate','zero_recovery_span']
    summary=data.groupby(keys)[cols].sum().reset_index();summary['batches_per_group']=30
    assert len(summary)==144 and (data.groupby(keys).size()==30).all()
    assert all(sha(Path(p))==h for p,h in binding.items())
    out.mkdir(parents=True);data.to_csv(out/'batch_certificates.csv',index=False);summary.to_csv(out/'coverage.csv',index=False)
    (out/'input_binding.json').write_text(json.dumps(binding,indent=2)+'\n')
    (out/'analysis_snapshot.py').write_bytes(Path(__file__).read_bytes())
    result={'status':'completed_pending_independent_check','saved_batches':1080,'batch_radius_rows':4320,
            'scope':'post-hoc sufficient conditions at fixed saved reports; perturbation radius is hypothetical, no score-error calibration or causal/performance guarantee',
            'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()}}
    (out/'completion.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['run','audit','output']:p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
