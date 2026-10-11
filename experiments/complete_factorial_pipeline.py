"""Gate full factorial audits and analysis on producer termination and completion."""
import argparse,fcntl,hashlib,json,os,subprocess,sys,time
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,v):
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(v,indent=2)+'\n');os.replace(tmp,p)
def process_identity(pid):
    p=subprocess.run(['ps','-p',str(pid),'-o','lstart=,command='],text=True,capture_output=True)
    if p.returncode==1:return None
    if p.returncode!=0:raise RuntimeError('Cannot observe producer: '+p.stderr)
    return p.stdout.strip() or None

def main(a):
    run=a.run.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    lock=(out/'execution.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    here=Path(__file__).resolve().parent;manifest=read(run/'manifest.json')
    names=set(manifest['source_hashes'])|{'complete_factorial_pipeline.py','audit_matched_factorial_fits.py',
        'audit_matched_factorial_results.py','audit_minimax_response.py','analyze_matched_factorial.py',
        'check_matched_factorial_statistics.py'}
    for name,h in manifest['source_hashes'].items():assert sha(here/name)==h
    binding={'run':str(run),'manifest_sha256':sha(run/'manifest.json'),
             'code':{str(here/name):sha(here/name) for name in sorted(names)},
             'fit_reuse':str(a.fit_reuse.resolve()) if a.fit_reuse else None}
    if (out/'inputs.json').exists():assert read(out/'inputs.json')==binding,'Pipeline inputs changed'
    else:
        write(out/'inputs.json',binding)
        (out/'pipeline_snapshot.py').write_bytes(Path(__file__).read_bytes())
    def unchanged():
        assert sha(run/'manifest.json')==binding['manifest_sha256']
        assert all(sha(Path(p))==h for p,h in binding['code'].items()),'Pipeline source changed'
    def status(state,**kwargs):write(out/'status.json',{'status':state,'time_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**kwargs})
    try:
        if a.producer_pid:
            identity=process_identity(a.producer_pid)
            assert identity and 'run_matched_factorial.py' in identity,'Producer not verified live'
            status('waiting_for_verified_producer',pid=a.producer_pid,identity=identity)
            print('WAITING '+identity,flush=True)
            while True:
                unchanged();current=process_identity(a.producer_pid)
                if current is None:break
                assert current==identity,'Producer PID identity changed'
                time.sleep(30)
        unchanged();parent=read(run/'completion.json')
        assert parent['status'].startswith('completed')
        assert sha(run/'summary.csv')==parent['summary_sha256']
        cfg=manifest['config'];expected=len(cfg['datasets'])*len(cfg['seeds'])*len(cfg['budgets'])*24
        assert parent['method_cells']==expected
        fit=out/'fit-audit';outcome=out/'outcome-audit';analysis=out/'analysis';check=out/'statistics-check'
        stages=[('fit-audit','audit_matched_factorial_fits.py',['--run',str(run),'--output',str(fit)]+(['--reuse',binding['fit_reuse']] if a.fit_reuse else []),fit),
                ('outcome-audit','audit_matched_factorial_results.py',['--run',str(run),'--output',str(outcome)],outcome),
                ('analysis','analyze_matched_factorial.py',['--run',str(run),'--fit-audit',str(fit),'--outcome-audit',str(outcome),'--output',str(analysis)],analysis),
                ('statistics-check','check_matched_factorial_statistics.py',['--run',str(run),'--analysis',str(analysis),'--output',str(check)],check)]
        receipts={}
        for name,script,args,folder in stages:
            unchanged();status('running_stage',stage=name)
            # Re-run resumable auditors. Nonresumable derived outputs are reused only
            # when recorded complete; the downstream independent checker verifies them.
            if name in ('fit-audit','outcome-audit') or not (folder/'completion.json').exists():
                assert name in ('fit-audit','outcome-audit') or not folder.exists(),'Incomplete derived stage requires inspection'
                with (out/(name+'.log')).open('a') as log:
                    subprocess.run([sys.executable,'-u',str(here/script),*args],stdout=log,stderr=subprocess.STDOUT,check=True)
            done=read(folder/'completion.json');assert done['status']=='completed',name
            receipts[name]=sha(folder/'completion.json');print('COMPLETED '+name,flush=True)
        derived=read(analysis/'completion.json')
        assert all(sha(analysis/name)==h for name,h in derived['files'].items())
        assert all(sha(Path(path))==h for path,h in read(analysis/'input_binding.json').items())
        assert read(check/'completion.json')['analysis_completion_sha256']==sha(analysis/'completion.json')
        unchanged();status('completed')
        write(out/'completion.json',{'status':'completed','parent_completion_sha256':sha(run/'completion.json'),
              'inputs_sha256':sha(out/'inputs.json'),'stage_completion_hashes':receipts,
              'scope':'full configured fit/outcome audits and paired statistical reconstruction; manuscript integration still separate'})
    except BaseException as e:
        status('failed',error=type(e).__name__,message=str(e));raise
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['run','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--fit-reuse',type=Path);p.add_argument('--producer-pid',type=int)
    main(p.parse_args())
