"""Exercise real interruption, cache reuse, mutation rejection and audit locking."""
import argparse,contextlib,fcntl,hashlib,json,shutil
from pathlib import Path
import audit_matched_factorial_results as audit

def main(a):
    assert not a.output.exists();a.output.mkdir(parents=True)
    original=audit.replay;checks=[]
    expected=json.loads((a.completed_audit/'completion.json').read_text())
    assert expected['execution_smoke'], 'Use an execution fixture, not the live experiment'
    partial=a.output/'interrupted-audit'
    def interrupt_after_checkpoint(*args,**kwargs):
        if list(partial.glob('batch_checks/**/checked.json')):
            raise InterruptedError('Injected interruption after a durable batch checkpoint')
        return original(*args,**kwargs)
    audit.replay=interrupt_after_checkpoint
    try:
        audit.main(a.run,partial)
    except InterruptedError:
        assert len(list(partial.glob('batch_checks/**/checked.json')))==1
        assert not (partial/'completion.json').exists()
        checks.append('interruption_preserves_one_completed_batch')
    else:raise AssertionError('Interruption did not occur')
    finally:audit.replay=original
    audit.main(a.run,partial)
    got=json.loads((partial/'completion.json').read_text())
    for key in ['method_cells','outcome_rows','legal_unilateral_deviations','cell_completion_hashes']:
        assert got[key]==expected[key],key
    checks.append('partial_resume_matches_uninterrupted_coverage')
    def forbidden(*args,**kwargs):raise RuntimeError('Completed checkpoint unexpectedly replayed')
    audit.replay=forbidden
    try:audit.main(a.run,partial)
    finally:audit.replay=original
    checks.append('completed_resume_uses_all_bound_checkpoints')
    checkpoint=next(partial.glob('batch_checks/**/checked.json'));old=checkpoint.read_bytes()
    bad=json.loads(old);bad['binding']['arrays_sha256']='corrupted';checkpoint.write_text(json.dumps(bad))
    try:
        try:audit.main(a.run,partial)
        except AssertionError as e:assert 'checkpoint mismatch' in str(e)
        else:raise AssertionError('Corrupt binding accepted')
    finally:checkpoint.write_bytes(old)
    checks.append('changed_checkpoint_binding_rejected')
    inputs=partial/'inputs.json';old=inputs.read_bytes();bad=json.loads(old);bad['summary_sha256']='corrupted';inputs.write_text(json.dumps(bad))
    try:
        try:audit.main(a.run,partial)
        except AssertionError as e:assert 'inputs changed' in str(e)
        else:raise AssertionError('Changed audit input accepted')
    finally:inputs.write_bytes(old)
    checks.append('changed_audit_inputs_rejected')
    with (partial/'execution.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:audit.main(a.run,partial)
        except BlockingIOError:pass
        else:raise AssertionError('Concurrent writer accepted')
    checks.append('concurrent_writer_rejected')
    result={'status':'completed','checks':checks,'method_cells':got['method_cells'],
            'outcome_rows':got['outcome_rows'],'legal_unilateral_deviations':got['legal_unilateral_deviations'],
            'checker_sha256':hashlib.sha256(Path(audit.__file__).read_bytes()).hexdigest(),
            'scope':'resumability and input binding on the small execution fixture; not full experimental results'}
    (a.output/'test_snapshot.py').write_bytes(Path(__file__).read_bytes())
    (a.output/'completion.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['run','completed-audit','output']:p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
