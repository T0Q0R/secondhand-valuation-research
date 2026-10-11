"""Check every pure draw against saved private-simulator execution states."""
from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from threadpoolctl import threadpool_limits

from analyze_nested import read,require,sha
from benchmark_public_pipeline import environment_replay
from cdm_mechanism import POLICIES
from cdm_public_pipeline import public_pipeline
from run_all import load_source,write_json
from savval import ACTIONS,FEATURES,price_features


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--partial',action='store_true')
    args=parser.parse_args()
    run,output=args.run.resolve(),args.output.resolve()
    manifest=read(run/'manifest.json')
    full=(run/'completion.json').exists()
    require(full or args.partial,'Completed run or explicit partial required')
    pairs=[pair for pair in manifest['pairs'] if (run/pair[0]/f'seed-{pair[1]}'/'completion.json').exists()]
    require(bool(pairs),'Completed pair required')
    require(not output.exists(),'Fresh equivalence output required')
    output.mkdir(parents=True)
    sources=[Path(__file__),Path(__file__).with_name('cdm_public_pipeline.py'),
             Path(__file__).with_name('benchmark_public_pipeline.py')]
    for source in sources:(output/source.name).write_bytes(source.read_bytes())
    write_json(output/'manifest.json',{'parent_manifest_sha256':sha(run/'manifest.json'),'frozen_pairs':pairs,
               'parent_complete_at_start':full,'scope':'all pure draws for returned uniform/CDM reports at primary budget; public inputs only',
               'source_hashes':{p.name:sha(p) for p in sources}})
    rows=[]
    torch.set_num_threads(4)
    with threadpool_limits(limits=4):
        for dataset in manifest['config']['datasets']:
            seeds=[s for d,s in pairs if d==dataset]
            if not seeds:continue
            _,_,evaluation,_=load_source(dataset,manifest['parent_config'])
            if manifest['execution_smoke']:evaluation=evaluation.iloc[:64].copy()
            source=price_features(evaluation,FEATURES[dataset])
            for seed in seeds:
                for price in manifest['prices']:
                    folder=run/dataset/f'seed-{seed}'/price
                    binding=read(folder/'model_binding.json')
                    require(sha(Path(binding['parent_model_path']))==binding['parent_model_sha256'],'Price binding')
                    require(sha(folder/'head.joblib')==binding['head_sha256'],'Public head binding')
                    model,_,_=joblib.load(binding['parent_model_path'])
                    head=joblib.load(folder/'head.joblib')
                    for method in ('uniform','cdm'):
                        cell=folder/'budget-1000'/method
                        outcome=pd.read_csv(cell/'outcomes.csv.gz')
                        saved=np.load(cell/'execution.npz')
                        require(outcome.listing_id.astype(str).tolist()==evaluation.listing_id.astype(str).tolist(),'Source order')
                        for batch,subset in outcome.groupby('batch',sort=True):
                            idx=subset.index.to_numpy()
                            actual_source=source.iloc[idx].reset_index(drop=True)
                            public=actual_source.copy()
                            states=subset.state.to_numpy(int)
                            for a,field in enumerate(ACTIONS):
                                public.loc[model.space.masks[states,a],field]=np.nan
                            for k in range(len(POLICIES)):
                                # Force every possible pure draw, including zero
                                # probability rules, to test the complete bank.
                                alpha=np.eye(len(POLICIES))[k]
                                result=public_pipeline(model,head,subset.listing_id,public,alpha,.1,.5,
                                                       environment_replay(actual_source))
                                expected_actions=saved['actions'][idx,k]
                                expected_quotes=saved['quotes'][idx,k]
                                require(result['policy_index']==k,'Whole-rule draw')
                                require(np.array_equal(result['actions'],expected_actions),'Public draw/action equivalence')
                                expected_success=np.zeros(len(idx),bool)
                                selected=np.flatnonzero(expected_actions>=0)
                                expected_success[selected]=model.space.masks[states[selected],expected_actions[selected]]
                                require(np.array_equal(result['query_succeeded'],expected_success),'Public replay success')
                                require(np.allclose(result['final_quote_log'],expected_quotes,atol=2e-6,rtol=0),'Public final quotation')
                                rows.append({'dataset':dataset,'seed':seed,'price':price,'method':method,
                                             'batch':int(batch),'policy_index':k,'n':len(idx),
                                             'query_count':int((expected_actions>=0).sum()),
                                             'capacity':result['capacity'],'matches':True})
                print(f'PUBLIC CDM MATCH {dataset}/{seed}',flush=True)
    pd.DataFrame(rows).to_csv(output/'equivalence.csv',index=False)
    write_json(output/'completion.json',{'status':'completed','cases':len(rows),'frozen_pairs':pairs,
               'execution_smoke':manifest['execution_smoke'],'scope':'primary capacity only; all draws on returned mixture reports; no inspection/time guarantee'})
    print(f'COMPLETED PUBLIC CDM CHECK {output}',flush=True)


if __name__=='__main__':main()
