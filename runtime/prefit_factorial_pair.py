"""One independent future fit using the unchanged production fitting code.

The supervisor yields before the sequential producer reaches the final pair;
only committed nested-fit checkpoints are reused after an interruption.
"""
import argparse,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def latest_pair(log):
    # Read the tail without repeatedly loading the complete experiment log.
    with log.open('rb') as f:
        f.seek(0,2);f.seek(max(0,f.tell()-1024*1024));lines=f.read().decode(errors='replace').splitlines()
    return next((line[4:] for line in reversed(lines) if line.startswith('FIT ')),None)

def compute(a):
    import pandas as pd,torch
    from run_all import load_source
    from savval import FEATURES
    from matched_factorial_crossfit import fit_nested
    manifest=read(a.run/'manifest.json');cfg=manifest['config']
    assert sha(a.config)==manifest['config_sha256'] and read(a.config)==cfg
    for name,h in manifest['source_hashes'].items():assert sha(ROOT/'experiments'/name)==h
    torch.set_num_threads(2)
    estimator,guidance,evaluation,provenance=load_source(a.dataset,cfg)
    train=pd.concat([estimator,guidance],ignore_index=True)
    pair=a.run/a.dataset/f'seed-{a.seed}';pair.mkdir(parents=True,exist_ok=True)
    binding={'train_sha256':hashlib.sha256(train.to_csv(index=False).encode()).hexdigest(),
             'evaluation_sha256':hashlib.sha256(evaluation.to_csv(index=False).encode()).hexdigest(),'provenance':provenance}
    if (pair/'data_binding.json').exists():assert read(pair/'data_binding.json')==binding
    else:(pair/'data_binding.json').write_text(json.dumps(binding,indent=2)+'\n')
    fit_nested(train,FEATURES[a.dataset],cfg,a.seed,pair/'fit')
    for name,h in manifest['source_hashes'].items():assert sha(ROOT/'experiments'/name)==h

def main(a):
    if a.child:compute(a);return
    a.output.mkdir(parents=True,exist_ok=False)
    cfg=read(a.run/'manifest.json')['config']
    assert a.dataset==cfg['datasets'][-1] and a.seed in cfg['seeds']
    position=cfg['seeds'].index(a.seed)
    yield_pair=f"{a.dataset}/{cfg['seeds'][position-1]}"
    current=latest_pair(a.run.with_suffix('.log'))
    assert current is not None, 'Sequential producer stage unknown'
    current_dataset,current_seed=current.split('/')
    current_position=(cfg['datasets'].index(current_dataset),cfg['seeds'].index(int(current_seed)))
    yield_position=(cfg['datasets'].index(a.dataset),position-1)
    assert position>0 and current_position<yield_position,'Sequential producer already too close'
    args=[sys.executable,'-u',str(Path(__file__).resolve()),'--child','--run',str(a.run),
          '--config',str(a.config),'--dataset',a.dataset,'--seed',str(a.seed),'--output',str(a.output)]
    process=None;status='failed';reason=None
    try:
        with (a.output/'worker.log').open('w') as log:
            process=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT)
            while process.poll() is None:
                if latest_pair(a.run.with_suffix('.log')) in [yield_pair,f'{a.dataset}/{a.seed}']:
                    reason='Yield before sequential producer reaches pair';process.terminate();process.wait();status='yielded';break
                time.sleep(10)
            if status!='yielded':
                assert process.returncode==0,f'Prefit exit {process.returncode}'
                assert (a.run/a.dataset/f'seed-{a.seed}/fit/completion.json').exists()
                status='completed'
    finally:
        if process is not None and process.poll() is None:process.terminate();process.wait()
        (a.output/'completion.json').write_text(json.dumps({'status':status,'reason':reason,'dataset':a.dataset,
            'seed':a.seed,'scope':'unchanged nested-fit precomputation; evaluation and independent audits remain in main pipeline'},indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['run','config','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--dataset',required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--child',action='store_true')
    a=p.parse_args()
    def stop(signum,frame):raise KeyboardInterrupt('Prefit termination')
    signal.signal(signal.SIGTERM,stop)
    main(a)
