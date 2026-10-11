"""Verify guard transitions with disposable processes, never the live experiment."""
import argparse,json,subprocess,sys,tempfile,time
from pathlib import Path
import research_guard as g

def main(out):
    assert not out.exists();out.mkdir(parents=True)
    checks=[]
    assert g.transition(False,24,25,35)
    assert not g.transition(False,25,25,35)
    assert g.transition(True,34,25,35)
    assert not g.transition(True,35,25,35)
    checks.append('pause_resume_hysteresis_boundary')
    original_identity=g.identity
    try:
        g.identity=lambda pid:'different process'
        assert not g.verified_live({123:'original process'})
    finally:g.identity=original_identity
    checks.append('changed_process_identity_not_followed')
    for fail in [False,True]:
        case=out/('error' if fail else 'normal');case.mkdir()
        run=case/'run';run.mkdir();g.save(run/'manifest.json',{'config':{'datasets':['fixture'],'seeds':[1]}})
        pipeline=case/'pipeline';pipeline.mkdir();g.save(pipeline/'status.json',{'status':'fixture'})
        training=subprocess.Popen([sys.executable,'-c','import time; time.sleep(0.8)','run_matched_factorial.py'])
        waiter=subprocess.Popen([sys.executable,'-c','import time; time.sleep(1.2)','complete_factorial_pipeline.py'])
        original=g.headroom;calls=[0]
        def sample():
            calls[0]+=1
            if fail and calls[0]==2:raise RuntimeError('Injected memory probe error')
            return 20 if calls[0]==1 else 50
        g.headroom=sample
        a=argparse.Namespace(run=run,pipeline=pipeline,output=case/'guard',training_pid=training.pid,
                             pipeline_pid=waiter.pid,worker_pid=[],pause_at=25,resume_at=35,interval=.03)
        try:
            try:g.main(a)
            except RuntimeError as e:
                assert fail and str(e)=='Injected memory probe error'
            else:assert not fail
            training.wait(timeout=3);waiter.wait(timeout=3)
            report=g.read(a.output/'internal-summary.json')
            assert any(e['action']=='pause' for e in report['events'])
            assert report['resumed_own_pauses_before_exit']
            assert report['termination_reason']==('guard_error' if fail else 'all_tracked_processes_terminated')
            if not fail:assert any(e['action']=='resume' for e in report['events'])
            checks.append('probe_error_resumes_paused_worker' if fail else 'real_pause_resume_report_and_exit')
        finally:
            g.headroom=original
            for process in [training,waiter]:
                if process.poll() is None:
                    process.send_signal(g.signal.SIGCONT);process.terminate();process.wait()
    g.save(out/'completion.json',{'status':'completed','checks':checks,'scope':'disposable processes and injected headroom, no live experiment modified'})
    print(json.dumps({'status':'completed','checks':checks}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
