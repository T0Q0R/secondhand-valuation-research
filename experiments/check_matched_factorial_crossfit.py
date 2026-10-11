"""End-to-end small nested training execution and heldout exclusion audit."""
from pathlib import Path
import argparse,json,hashlib
import joblib,numpy as np,pandas as pd,torch
from run_all import load_source
from savval import FEATURES,price_features
from matched_factorial_crossfit import fit_nested

def main(out):
    assert not out.exists();out.mkdir(parents=True);torch.set_num_threads(2)
    cfg=json.loads(Path('outputs/matched-factorial-training-smoke-v1/config.json').read_text());cfg['outer_folds']=2
    estimator,guidance,evaluation,_=load_source('synthetic',cfg);train=pd.concat([estimator,guidance],ignore_index=True)
    cells=fit_nested(train,FEATURES['synthetic'],cfg,13,out/'fit')
    assignment=pd.read_csv(out/'fit/outer_assignments.csv');pred=np.load(out/'fit/outer_predictions.npz');receipts=json.loads((out/'fit/fold_receipts.json').read_text());checked=0
    for receipt in receipts:
        held=set(receipt['heldout_ids']);assert not held&(set(receipt['estimator_ids'])|set(receipt['guidance_ids']))
        assert set(receipt['estimator_ids']).isdisjoint(receipt['guidance_ids'])
        indices=np.flatnonzero(assignment.outer_fold.to_numpy()==receipt['fold']);heldout=train.iloc[indices]
        assert set(heldout.listing_id)==held
        stage=out/'fit'/f"outer-{receipt['fold']}";logs=json.loads((stage/'receipts.json').read_text())
        for fit_id in pred.files:
            assert set(logs[fit_id]['estimator_ids'])==set(receipt['estimator_ids'])
            assert set(logs[fit_id]['guidance_ids'])==set(receipt['guidance_ids'])
            model,_=joblib.load(stage/(fit_id+'.joblib'));actual,_,_=model.predict(price_features(heldout,FEATURES['synthetic']))
            assert np.allclose(actual,pred[fit_id][indices],atol=2e-6,rtol=0);checked+=len(indices)
    for cell in cells.values():
        actual,_,_=cell['model'].predict(price_features(evaluation,FEATURES['synthetic']));assert np.isfinite(actual).all()
    files=[Path(__file__),Path('experiments/matched_factorial_crossfit.py'),Path('experiments/matched_factorial_training.py')]
    for p in files:(out/p.name).write_bytes(p.read_bytes())
    result={'status':'completed_nested_execution_smoke','cells':24,'unique_fits_per_stage':14,'outer_folds':2,'training_rows':len(train),'heldout_prediction_rows_reconstructed':checked,'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'scope':'small synthetic execution and heldout exclusion; not10seed full experiment'}
    (out/'completion.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
