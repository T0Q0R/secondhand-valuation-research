"""Complete the robust ordinary-benefit reference without changing parent fits."""
from __future__ import annotations
import argparse
from pathlib import Path
import time
import joblib
import pandas as pd
import torch
from threadpoolctl import threadpool_limits
from analyze_nested import read,require,sha
from run_all import load_source,evaluate_method,write_json
from savval import FEATURES

def main():
    parser=argparse.ArgumentParser()
    for name in ('parent','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();parent,output=args.parent.resolve(),args.output.resolve()
    manifest,done=read(parent/'run_manifest.json'),read(parent/'completion.json');config=manifest['config']
    require(done['status']=='completed' and done['binding']==manifest['binding'],'Full parent complete')
    require(sha(parent/'all_summary.csv')==done['summary_sha256'],'Parent summary binding')
    for name in ('run_all.py','run_crossfit.py','savval.py'):
        require(sha(Path(__file__).with_name(name))==manifest['source_hashes'][name],'Frozen parent core')
    require(not output.exists(),'Fresh immutable reference generation');output.mkdir(parents=True)
    sources=[Path(__file__),*[Path(__file__).with_name(n) for n in ('run_all.py','run_crossfit.py','savval.py','analyze_nested.py')],
             Path(__file__).parents[1]/'plan/robust-benefit-reference-v1.md']
    snapshot=output/'source_snapshot';snapshot.mkdir()
    for source in sources:(snapshot/source.name).write_bytes(source.read_bytes())
    hashes={p.name:sha(p) for p in sources};start=time.time()
    write_json(output/'manifest.json',{'parent_path':str(parent),'parent_binding':manifest['binding'],'config':config,
        'source_hashes':hashes,'method':'robust_benefit_no_feedback','saved_parent_kind':'suppression','evaluated_kind':'benefit',
        'parent_completion_sha256':sha(parent/'completion.json'),'scope':'all nine pairs and six budgets; fixed robust prices and shared OOF multi-output head; no fitting'})
    rows=[];pairs=[];torch.set_num_threads(4)
    with threadpool_limits(limits=4):
        for dataset in config['datasets']:
            _,_,evaluation,provenance=load_source(dataset,config)
            for seed in config['seeds']:
                model_path=parent/dataset/f'seed-{seed}'/'deployment_models/robust_no_feedback.joblib'
                digest=sha(model_path);model,head,kind=joblib.load(model_path)
                require(kind=='suppression','Explicit original reference output')
                folder=output/dataset/f'seed-{seed}';folder.mkdir(parents=True)
                own=[];listing=[]
                for budget in config['budgets']:
                    result,summary=evaluate_method('robust_benefit_no_feedback',model,head,'benefit',evaluation,
                        FEATURES[dataset],config,seed,budget)
                    listing.append(result);own.append({'dataset':dataset,**summary})
                pd.concat(listing,ignore_index=True).to_csv(folder/'outcomes.csv.gz',index=False)
                pd.DataFrame(own).to_csv(folder/'summary.csv',index=False)
                write_json(folder/'completion.json',{'status':'completed','dataset':dataset,'seed':seed,'cells':len(own),
                    'parent_binding':manifest['binding'],'model_path':str(model_path),'model_sha256':digest,
                    'source_provenance':provenance,'outcomes_sha256':sha(folder/'outcomes.csv.gz'),
                    'summary_sha256':sha(folder/'summary.csv'),'saved_kind':kind,'evaluated_kind':'benefit'})
                require(sha(model_path)==digest,'Model changed');rows.extend(own);pairs.append([dataset,seed])
                print(f'COMPLETED ROBUST BENEFIT {dataset}/{seed}: {len(own)} cells',flush=True)
    require(hashes=={p.name:sha(p) for p in sources},'Reference source bytes changed')
    pd.DataFrame(rows).to_csv(output/'summary.csv',index=False)
    write_json(output/'completion.json',{'status':'completed','cells':len(rows),'pairs':pairs,
        'parent_binding':manifest['binding'],'elapsed_seconds':time.time()-start,
        'summary_sha256':sha(output/'summary.csv'),'scope':'54 original-contract ordinary-benefit reference cells; retrospective'})
    print('Completed robust ordinary-benefit reference.',flush=True)

if __name__=='__main__':main()
