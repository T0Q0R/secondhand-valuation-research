"""Full nested factorial training/evaluation; resumable with immutable inputs."""
import argparse,fcntl,json,time
from pathlib import Path
import pandas as pd,torch
from run_all import load_source
from savval import FEATURES,price_features
from matched_factorial_crossfit import fit_nested,sha,write
from matched_factorial_evaluation import evaluate_cell

def main(a):
    config=json.loads(a.config.read_text());out=Path(config['output'])
    if out.exists() and not a.resume:raise FileExistsError(out)
    out.mkdir(parents=True,exist_ok=True);lock=(out/'execution.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    names=['run_matched_factorial.py','matched_factorial_training.py','matched_factorial_crossfit.py','matched_factorial_evaluation.py','matched_feedback_loss.py','minimax_market.py','public_minimax_allocation.py','cdm_mechanism.py','savval.py','run_all.py','run_crossfit.py']
    sources=[Path(__file__).with_name(n) for n in names]
    binding={'config':config,'config_sha256':sha(a.config),'source_hashes':{p.name:sha(p) for p in sources},'scope':'new matched initial-objective/acquisition/feedback/allocation intervention; full-loop cross-fit; not original SAV fits'}
    if (out/'manifest.json').exists():assert json.loads((out/'manifest.json').read_text())==binding
    else:
        write(out/'manifest.json',binding);snap=out/'source_snapshot';snap.mkdir()
        for p in sources:(snap/p.name).write_bytes(p.read_bytes())
    torch.set_num_threads(2);summaries=[];started=time.time()
    budgets=[config['factorial_primary_budget']]+[b for b in config['budgets'] if b!=config['factorial_primary_budget']]
    for dataset in config['datasets']:
        estimator,guidance,evaluation,provenance=load_source(dataset,config);train=pd.concat([estimator,guidance],ignore_index=True)
        for seed in config['seeds']:
            pair=out/dataset/f'seed-{seed}';pair.mkdir(parents=True,exist_ok=True)
            data_binding={'train_sha256':__import__('hashlib').sha256(train.to_csv(index=False).encode()).hexdigest(),'evaluation_sha256':__import__('hashlib').sha256(evaluation.to_csv(index=False).encode()).hexdigest(),'provenance':provenance}
            if (pair/'data_binding.json').exists():assert json.loads((pair/'data_binding.json').read_text())==data_binding
            else:write(pair/'data_binding.json',data_binding)
            print(f'FIT {dataset}/{seed}',flush=True);cells=fit_nested(train,FEATURES[dataset],config,seed,pair/'fit')
            cache={}
            for budget in budgets:
                for (initial,score,feedback,allocation),cell in cells.items():
                    fit_id=cell['fit_id'];model=cell['model'];head=cell['head']
                    if fit_id not in cache:
                        pred,encoded,valid=model.predict(price_features(evaluation,FEATURES[dataset]));cache[fit_id]=(pred,encoded,valid,{})
                    pred,encoded,valid,score_cache=cache[fit_id]
                    if score not in score_cache:score_cache[score]=head.score(encoded,pred,model.space,score,reported_missing=model.space.reported_missing(evaluation))
                    model_path=pair/'fit/deployment_models'/(fit_id+'.joblib');model_hash=sha(model_path)
                    folder=pair/'evaluation'/f'budget-{round(budget*10000):04d}'/initial/score/feedback/allocation
                    result=evaluate_cell(pred,score_cache[score],valid,evaluation,model.space,config,budget,allocation,folder,model_hash)
                    record={'dataset':dataset,'seed':seed,'initial_objective':initial,'score':score,'feedback':feedback,'fit_id':fit_id,**result};summaries.append(record)
                    print(f"EVALUATED {dataset}/{seed} budget={budget} {initial}/{score}/{feedback}/{allocation}",flush=True)
            write(pair/'completion.json',{'status':'completed_pending_independent_audit','method_cells':24*len(budgets),'fit_completion_sha256':sha(pair/'fit/completion.json'),'data_binding_sha256':sha(pair/'data_binding.json')})
            del cache,cells
    assert {p.name:sha(p) for p in sources}==binding['source_hashes']
    pd.DataFrame(summaries).to_csv(out/'summary.csv',index=False)
    write(out/'completion.json',{'status':'completed_pending_independent_audit','method_cells':len(summaries),'source_seed_pairs':len(config['datasets'])*len(config['seeds']),'seconds_this_process':time.time()-started,'summary_sha256':sha(out/'summary.csv')})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--resume',action='store_true');main(p.parse_args())
