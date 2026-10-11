"""All matched allocation contrasts; no filtering by direction/convergence."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np,pandas as pd

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(run,audit,out):
    assert not out.exists();out.mkdir(parents=True)
    done=json.loads((run/'completion.json').read_text());checked=json.loads((audit/'completion.json').read_text())
    assert done['status']=='completed_pending_independent_audit' and checked['status']=='completed'
    assert not done['smoke'] and checked['parent_completion_sha256']==sha(run/'completion.json')
    for name,h in checked['batch_completion_hashes'].items():assert sha(Path(name))==h
    assert checked['summaries_recomputed']==108 and checked['outcome_rows']==108000
    manifest=json.loads((run/'manifest.json').read_text());frames=[]
    for cp in sorted(run.glob('*/seed-*/*/*/*/batch-*/completion.json')):
        dataset,seed,price,score,alloc,batch=cp.parent.relative_to(run).parts
        receipt=json.loads(cp.read_text());path=cp.parent/'outcomes.csv.gz';assert sha(path)==receipt['outcomes_sha256']
        f=pd.read_csv(path);f['dataset']=dataset;f['seed']=int(seed.split('-')[1]);f['price']=price;f['score']=score;f['allocation']=alloc;frames.append(f)
    data=pd.concat(frames,ignore_index=True);metric=['positive_expected_log_inflation','honest_absolute_error','expected_attacked_absolute_error','failed_query_probability','deviation_envelope']
    rng=np.random.default_rng(20261008);records=[];matrices={}
    for (dataset,price,score),f in data.groupby(['dataset','price','score'],sort=True):
        keys=['seed','batch','listing_id'];left=f[f.allocation=='top_b'].set_index(keys);right=f[f.allocation=='minimax'].set_index(keys)
        assert not left.index.duplicated().any() and not right.index.duplicated().any() and set(left.index)==set(right.index)
        right=right.loc[left.index];assert np.allclose(left.target_log,right.target_log,atol=0,rtol=0)
        seed_ids=sorted(f.seed.unique());batch_ids=sorted(f.batch.unique());assert len(seed_ids)==3 and len(batch_ids)==10
        si=rng.integers(0,3,(1000,3));bi=rng.integers(0,10,(1000,10))
        prefix=dataset+'__'+price+'__'+score
        matrices[prefix+'__seed_draws']=si;matrices[prefix+'__batch_draws']=bi
        matrices[prefix+'__seed_ids']=np.asarray(seed_ids);matrices[prefix+'__batch_ids']=np.asarray(batch_ids)
        row={'dataset':dataset,'price':price,'score':score,'fitting_seeds':3,'shared_batches':10,'unique_listings':len(f.listing_id.unique())}
        for m in metric:
            difference=(left[m]-right[m]).groupby(['seed','batch']).mean().unstack('batch').loc[seed_ids,batch_ids].to_numpy()
            values=difference[si[:,:,None],bi[:,None,:]].mean(axis=(1,2));lo,hi=np.quantile(values,[.025,.975])
            row.update({m+'_top_b':float(left[m].mean()),m+'_minimax':float(right[m].mean()),m+'_reduction':float(difference.mean()),m+'_lower':float(lo),m+'_upper':float(hi)})
            matrices[dataset+'__'+price+'__'+score+'__'+m]=difference
        infl=row[metric[0]+'_top_b'];hon=row[metric[1]+'_top_b']
        row['inflation_reduction_percent']=100*row[metric[0]+'_reduction']/infl if infl>0 else None
        row['honest_mae_increase_percent']=-100*row[metric[1]+'_reduction']/hon if hon>0 else None
        row['point_gate']=bool(infl>0 and hon>0 and row['inflation_reduction_percent']>=10 and row['honest_mae_increase_percent']<=5)
        row['positive_inflation_interval']=row[metric[0]+'_lower']>0
        for label,ms in [('triple',[metric[0],metric[1],metric[3]]),('including_attacked_mae',metric[:4])]:
            d=[row[m+'_reduction'] for m in ms]
            row['minimax_dominates_'+label]=bool(all(v>=-1e-10 for v in d) and any(v>1e-10 for v in d))
            row['top_b_dominates_'+label]=bool(all(v<=1e-10 for v in d) and any(v< -1e-10 for v in d))
        for name,part in [('top_b',left),('minimax',right)]:
            row[name+'_max_regret']=float(part.regret.max());row[name+'_nonconverged_batches']=int((~part.groupby(['seed','batch']).converged.first()).sum());row[name+'_signed_bias']=float(part.expected_signed_log_error.mean())
        records.append(row)
    assert len(records)==18
    pd.DataFrame(records).to_csv(out/'contrasts.csv',index=False);np.savez_compressed(out/'paired_seed_batch_matrices.npz',**matrices)
    (out/'analysis_snapshot.py').write_bytes(Path(__file__).read_bytes())
    receipt={'status':'completed','contrasts':len(records),'resamples':1000,'seed':20261008,'run_completion_sha256':sha(run/'completion.json'),'audit_completion_sha256':sha(audit/'completion.json'),'scope':'exploratory unadjusted paired seed/shared-batch intervals on fixed training records; no training-population or equilibrium guarantee'}
    (out/'completion.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('run','audit','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();main(a.run,a.audit,a.output)
