"""Local resource guard and terminal report; independent of model/API access.

Uses a best-effort reclaimable-memory headroom threshold, not a hard RAM
reservation. Never alters experiment data, source, numerical settings or budget.
"""
import argparse,datetime,fcntl,hashlib,json,os,re,signal,subprocess,time
from pathlib import Path

def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(p):return json.loads(p.read_text())
def save(p,v):
    tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,p)
def identity(pid):
    p=subprocess.run(['ps','-p',str(pid),'-o','lstart=,command='],capture_output=True,text=True)
    if p.returncode==1:return None
    if p.returncode:raise RuntimeError(p.stderr)
    return p.stdout.strip() or None

def processes():
    p=subprocess.run(['ps','-ax','-o','pid=,ppid=,rss=,nice=,command='],capture_output=True,text=True,check=True)
    rows={}
    for line in p.stdout.splitlines():
        v=line.strip().split(None,4)
        if len(v)==5:rows[int(v[0])]={'parent':int(v[1]),'rss_kib':int(v[2]),'nice':int(v[3]),'command':v[4]}
    return rows

def descendants(rows,roots):
    found={p for p in roots if p in rows}
    while True:
        new={p for p,v in rows.items() if v['parent'] in found}
        if new<=found:return found
        found|=new

def headroom():
    p=subprocess.run(['/usr/bin/memory_pressure','-Q'],capture_output=True,text=True,check=True)
    m=re.search(r'System-wide memory free percentage:\s*(\d+)%',p.stdout)
    if not m:raise RuntimeError('Cannot read macOS reclaimable memory headroom')
    return int(m.group(1))

def transition(was_paused,percent,pause_at,resume_at):
    return percent<resume_at if was_paused else percent<pause_at

def verified_live(roots):return {p for p,i in roots.items() if identity(p)==i}

def terminal_report(a,reason,paused,events,peak):
    run=a.run;pipeline=a.pipeline
    expected=read(run/'manifest.json')['config']
    pairs=[{'dataset':d,'seed':s,'fit_complete':(run/d/f'seed-{s}/fit/completion.json').exists(),
            'evaluation_complete':(run/d/f'seed-{s}/completion.json').exists()}
           for d in expected['datasets'] for s in expected['seeds']]
    report={'time_utc':stamp(),'termination_reason':reason,'guard_does_not_stop_goal':True,
        'peak_research_rss_gib':peak/1048576,'memory_policy':{'pause_below_percent':a.pause_at,
        'resume_at_percent':a.resume_at,'semantics':'best-effort macOS reclaimable headroom; no hard RAM reservation'},
        'fit_pairs_complete':sum(x['fit_complete'] for x in pairs),
        'evaluation_pairs_complete':sum(x['evaluation_complete'] for x in pairs),'configured_pairs':len(pairs),
        'pair_status':pairs,'events':events,'resumed_own_pauses_before_exit':True,
        'remaining':['integrate independently checked full results into the manuscript','render and audit final manuscript','confirm submission declarations and target journal','prepare authorized public evidence release']}
    for key,path in [('training_completion',run/'completion.json'),('pipeline_status',pipeline/'status.json'),('pipeline_completion',pipeline/'completion.json')]:
        if path.exists():report[key]=read(path)
    for stage in ['fit-audit','outcome-audit','analysis','statistics-check']:
        path=pipeline/stage/'completion.json'
        if path.exists():report[stage]=read(path)
    save(a.output/'internal-summary.json',report)
    save(a.output/'status.json',{'status':'stopped','reason':reason,'time_utc':stamp(),'internal_report':'internal-summary.json'})

def main(a):
    a.output.mkdir(parents=True,exist_ok=True)
    lock=(a.output/'execution.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    roots={p:identity(p) for p in [a.training_pid,a.pipeline_pid]+list(a.worker_pid)}
    assert all(roots.values()),'Both requested processes must be verified live at launch'
    assert 'run_matched_factorial.py' in roots[a.training_pid]
    assert 'complete_factorial_pipeline.py' in roots[a.pipeline_pid]
    inputs={'started_utc':stamp(),'roots':roots,'pause_at_percent':a.pause_at,'resume_at_percent':a.resume_at,
        'priority_nice':5,'guard_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'run':str(a.run),'pipeline':str(a.pipeline)}
    assert not (a.output/'inputs.json').exists(),'Use a fresh guard directory'
    save(a.output/'inputs.json',inputs);(a.output/'guard_snapshot.py').write_bytes(Path(__file__).read_bytes())
    events=[];stopped={};peak=0;reason='guard_error';caf=None
    try:
        # Prevent idle system sleep only. Explicit sleep/shutdown remains the user's choice.
        caf=subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(os.getpid())],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        while True:
            live=verified_live(roots);rows=processes();members=descendants(rows,live)
            if not live:reason='all_tracked_processes_terminated';break
            percent=headroom();rss=sum(rows[p]['rss_kib'] for p in members);peak=max(peak,rss)
            pause=transition(bool(stopped),percent,a.pause_at,a.resume_at)
            # Pause the allocating/training/audit workers; the small pipeline waiter stays live.
            workers={p for p in members if p!=a.pipeline_pid}
            for p in workers:
                if rows[p]['nice']<5:subprocess.run(['renice','-n','5','-p',str(p)],capture_output=True)
            if pause:
                for p in workers:
                    if p not in stopped:
                        ident=identity(p)
                        if ident:
                            os.kill(p,signal.SIGSTOP);stopped[p]=ident
                            events.append({'time_utc':stamp(),'action':'pause','pid':p,'headroom_percent':percent})
            else:
                for p,i in list(stopped.items()):
                    if identity(p)==i:
                        os.kill(p,signal.SIGCONT)
                        events.append({'time_utc':stamp(),'action':'resume','pid':p,'headroom_percent':percent})
                    del stopped[p]
            save(a.output/'status.json',{'status':'resource_paused' if stopped else 'monitoring',
                'time_utc':stamp(),'live_roots':sorted(live),'research_rss_gib':rss/1048576,
                'macos_reclaimable_headroom_percent':percent,'paused_pids':sorted(stopped)})
            time.sleep(a.interval)
    except BaseException as e:
        events.append({'time_utc':stamp(),'action':'guard_error','type':type(e).__name__,'message':str(e)})
        reason='guard_error';raise
    finally:
        for p,i in stopped.items():
            if identity(p)==i:
                try:os.kill(p,signal.SIGCONT)
                except ProcessLookupError:pass
        if caf is not None:caf.terminate();caf.wait()
        terminal_report(a,reason,stopped,events,peak)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['run','pipeline','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--training-pid',type=int,required=True);p.add_argument('--pipeline-pid',type=int,required=True)
    p.add_argument('--pause-at',type=int,default=25);p.add_argument('--resume-at',type=int,default=35)
    p.add_argument('--worker-pid',type=int,action='append',default=[])
    p.add_argument('--interval',type=int,default=15)
    a=p.parse_args();assert 0<a.pause_at<a.resume_at<=100
    def stop_guard(signum,frame):raise KeyboardInterrupt('Guard termination requested')
    signal.signal(signal.SIGTERM,stop_guard);signal.signal(signal.SIGINT,stop_guard)
    main(a)
