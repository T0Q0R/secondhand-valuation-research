"""Read-only synthetic model fingerprints; no training or tolerance changes.
Produces a small return ZIP from the eight already-fitted price models.
"""
from pathlib import Path
import argparse,hashlib,io,json,platform,sys,zipfile,importlib.metadata
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'experiments'))
import numpy as np,pandas as pd,torch,joblib
from threadpoolctl import threadpool_limits
from run_all import load_source
from savval import FEATURES,price_features

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def array_sha(x):return hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest()
class OneThread:
    def __init__(self,model):self.model=model
    def predict(self,*args,**kwargs):return self.model.predict(*args,**dict(kwargs,thread_count=1))
def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    run=a.run.resolve();out=a.output.resolve();assert run.is_dir() and not out.exists()
    contract_path=Path(__file__).with_name('contract.json');contract=json.loads(contract_path.read_text())
    input_receipt=json.loads((run/'inputs.json').read_text())
    assert input_receipt['contract_sha256']==sha(contract_path)
    for f,h in contract['scientific_source_sha256'].items():assert sha(ROOT/f)==h,f
    _,_,evaluation,_=load_source('synthetic',contract['config'])
    assert hashlib.sha256(evaluation.to_csv(index=False).encode()).hexdigest()==contract['population_bindings']['synthetic']['evaluation']
    models=[];arrays={}
    for method in ['path-0-gap-0.5','path-1-gap-0.5']:
        for stage in ['outer-0','outer-1','outer-2','deployment']:
            folder=run/'synthetic'/method/stage;mp=folder/'model.joblib'
            receipt=json.loads((folder/'completion.json').read_text());assert receipt['model_sha256']==sha(mp)
            model,_,_=joblib.load(mp);original=model.backbone
            leaves=np.asarray(original.get_leaf_values());leaf_counts=np.asarray(original.get_tree_leaf_counts())
            borders={str(k):list(map(float,v)) for k,v in original.get_borders().items()}
            model.backbone=OneThread(original)
            x,base,valid=model.arrays(price_features(evaluation,FEATURES['synthetic']))
            predicted=model.predict_arrays(x,base)
            prefix=method+'__'+stage
            arrays[prefix+'__base']=base;arrays[prefix+'__predicted']=predicted
            arrays[prefix+'__encoded_sample']=x[:16];arrays[prefix+'__tree_leaves']=leaves
            params={k:v.detach().cpu().numpy() for k,v in model.residual.state_dict().items()}
            for key,v in params.items():arrays[prefix+'__residual__'+key]=v
            models.append(dict(method=method,stage=stage,training_inputs=receipt['inputs'],model_file_sha256=sha(mp),
                encoding_shape=list(x.shape),encoding_sha256=array_sha(x),valid_sha256=array_sha(valid),
                base_sha256=array_sha(base),prediction_sha256=array_sha(predicted),
                tree_leaf_counts=leaf_counts.tolist(),tree_borders=borders,tree_leaf_sha256=array_sha(leaves),
                residual_parameter_sha256={k:array_sha(v) for k,v in params.items()}))
            print('FINGERPRINTED',method,stage,flush=True)
    buffer=io.BytesIO();np.savez_compressed(buffer,**arrays);payload=buffer.getvalue()
    metadata=dict(scope='read-only fingerprints of8 saved synthetic price models; no fitting/evaluation response search',
        platform=platform.platform(),python=sys.version,torch_build_config=torch.__config__.show(),
        versions={m:importlib.metadata.version(m) for m in ['numpy','pandas','torch','scikit-learn','catboost']},
        contract_sha256=sha(contract_path),source_runner_sha256=sha(Path(__file__)),input_receipt=input_receipt,
        models=models,arrays_sha256=hashlib.sha256(payload).hexdigest())
    out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('diagnostic.json',json.dumps(metadata,indent=2)+'\n');z.writestr('arrays.npz',payload)
    print('SAVED',out,'bytes',out.stat().st_size,flush=True)
if __name__=='__main__':
    torch.set_num_threads(1)
    with threadpool_limits(limits=1):main()
