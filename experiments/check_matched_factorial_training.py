"""Small execution and matched-budget check; no scientific performance claim."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np,torch
from run_all import load_source
from savval import FEATURES,price_features
from matched_factorial_training import fit_factorial

def digest(model):
    return hashlib.sha256(b''.join(v.detach().numpy().tobytes() for v in model.residual.state_dict().values())).hexdigest()
def main(out):
    assert not out.exists();out.mkdir(parents=True);torch.set_num_threads(2)
    config=json.loads(Path('outputs/nested-development-v2/run_manifest.json').read_text())['config']
    config.update({'synthetic_train':80,'synthetic_evaluation':20,'max_train':60,'max_evaluation':20,'head_fitting_fraction':.3,'catboost_iterations':8,'head_trees':4,'residual_hidden_width':8,'initial_epochs':1,'feedback_epochs':2,'feedback_rounds':2,'batch_size':20,'training_attacker_sweeps':1})
    estimator,guidance,evaluation,_=load_source('synthetic',config)
    cells,receipts=fit_factorial(estimator,guidance,FEATURES['synthetic'],config,13)
    signatures=[];predictions=[];mapping=[]
    for fit_id,r in receipts.items():
        logs=r['initial_training']+[entry for round in r['feedback_training'] for entry in round['training']]
        assert len(logs)==3 and sum(x['updates'] for x in logs)==9 and r['head_fits']==3
        assert not set(r['estimator_ids'])&set(r['guidance_ids'])
        signatures.append([(x['examples'],x['permutation_sha256']) for x in logs])
    assert all(x==signatures[0] for x in signatures)
    for key,cell in cells.items():
        prediction,_,_=cell['model'].predict(price_features(evaluation,FEATURES['synthetic']))
        assert np.isfinite(prediction).all();predictions.append(prediction)
        mapping.append({'cell':list(key),'fit_id':cell['fit_id'],'residual_sha256':digest(cell['model'])})
    for initial in ('masking','robust'):
        shared=[x for x in mapping if x['cell'][0]==initial and x['cell'][2]=='none']
        assert len({x['residual_sha256'] for x in shared})==1
    np.savez_compressed(out/'predictions.npz',predictions=np.asarray(predictions));(out/'cell_mapping.json').write_text(json.dumps(mapping,indent=2)+'\n');(out/'training_receipts.json').write_text(json.dumps(receipts,indent=2)+'\n');(out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    sources=[Path(__file__),Path('experiments/matched_factorial_training.py'),Path('experiments/matched_feedback_loss.py')]
    for p in sources:(out/p.name).write_bytes(p.read_bytes())
    result={'status':'completed_execution_smoke','cells':24,'unique_fits':14,'gradient_updates_per_fit':9,'head_fits_per_fit':3,'estimator_records':len(estimator),'guidance_records':len(guidance),'evaluation_records':len(evaluation),'matched_record_orders':True,'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},'scope':'small synthetic fit primitive; no nested cross-fitting or full performance experiment'}
    (out/'completion.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
