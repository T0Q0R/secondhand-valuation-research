"""Verify completed-load and partial-stage resume without optimizer calls."""
import argparse,json,shutil,hashlib
from pathlib import Path
import torch,pandas as pd
from run_all import load_source
from savval import FEATURES
import matched_factorial_training as training
from matched_factorial_crossfit import fit_nested

def fail(*args,**kwargs):raise AssertionError('Resume unexpectedly retrained completed fit')
def main(source,out):
    assert not out.exists();out.mkdir(parents=True);torch.set_num_threads(2)
    cfg=json.loads((source/'fit/inputs.json').read_text())['config']
    estimator,guidance,_,_=load_source('synthetic',cfg);train=pd.concat([estimator,guidance],ignore_index=True)
    training.update=fail;training.fit_heads=fail;training.fit_backbone=fail
    completed=out/'completed-copy';shutil.copytree(source/'fit',completed)
    before={str(p.relative_to(completed)):hashlib.sha256(p.read_bytes()).hexdigest() for p in completed.rglob('*.joblib')}
    cells=fit_nested(train,FEATURES['synthetic'],cfg,13,completed);assert len(cells)==24
    after={str(p.relative_to(completed)):hashlib.sha256(p.read_bytes()).hexdigest() for p in completed.rglob('*.joblib')};assert before==after
    partial=out/'partial-copy';shutil.copytree(source/'fit',partial);(partial/'completion.json').unlink()
    cells=fit_nested(train,FEATURES['synthetic'],cfg,13,partial);assert len(cells)==24
    altered=train.copy();altered.loc[0,'target_log']+=.01
    try:fit_nested(altered,FEATURES['synthetic'],cfg,13,completed)
    except AssertionError:pass
    else:raise AssertionError('Changed training contents accepted')
    corrupt=out/'corrupt-copy';shutil.copytree(source/'fit',corrupt)
    model=next((corrupt/'deployment_models').glob('*.joblib'))
    with model.open('ab') as f:f.write(b'corrupted')
    try:fit_nested(train,FEATURES['synthetic'],cfg,13,corrupt)
    except AssertionError:pass
    else:raise AssertionError('Corrupt saved model accepted')
    result={'status':'completed','completed_load_preserves_model_bytes':True,'partial_resume_with_all_optimizer_calls_forbidden':True,'changed_training_content_rejected':True,'corrupt_model_rejected':True,'scope':'complete per-fit checkpoints; an interrupted uncommitted fit still requires recomputation'}
    (out/'checker_snapshot.py').write_bytes(Path(__file__).read_bytes());(out/'completion.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.source,a.output)
