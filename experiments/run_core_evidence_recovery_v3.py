"""Resume ACO and RPL10 audits without changing the frozen v2 source closure.

The original failed queue and its partial ACO receipts remain archived. Six
completed stages retain their original closures. No training or paper writes.
"""
from pathlib import Path
import argparse, fcntl, json, os, shutil, subprocess, sys, time, traceback

for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
    os.environ[key] = '1'
import run_core_evidence_queue_v2 as q
import audit_core_aco_v3 as aco

a = q.a
ORIGINAL_RUNTIME = a.ROOT / 'outputs/core-evidence-runtime-v2'
q.RUNTIME = a.ROOT / 'outputs/core-evidence-recovery-runtime-v3'
original_audit_pair = a.audit_pair


def audit_pair(stage, source, seed, limit=None):
    if stage == 'aco':
        return aco.audit_pair(source, seed, limit)
    return original_audit_pair(stage, source, seed, limit)


# Multiprocessing spawn imports this module, so workers use the same dispatcher.
a.audit_pair = audit_pair


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sync-checkout', type=Path, required=True)
    args = parser.parse_args()
    q.RUNTIME.mkdir(exist_ok=True)
    lock = (q.RUNTIME / 'execution.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    old_lock = (ORIGINAL_RUNTIME / 'execution.lock').open('a+')
    fcntl.flock(old_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    original_manifest = a.read(ORIGINAL_RUNTIME / 'manifest.json')
    q.source_guard(original_manifest)
    completed = ['rpl', 'mechanisms', 'sefa', 'gdfs', 'dime', 'efa']
    inherited = {}
    for stage in completed:
        p = ORIGINAL_RUNTIME / 'stages' / stage / 'completion.json'
        r = a.read(p)
        assert r['source_closure_sha256'] == a.sha(ORIGINAL_RUNTIME / 'manifest.json')
        for phase, h in r['phase_completion_hashes'].items():
            assert a.sha(a.OUT / phase / stage / 'completion.json') == h
        inherited[str(p.relative_to(a.ROOT))] = a.sha(p)
    files = q.FILES + ['experiments/audit_core_aco_v3.py', 'experiments/run_core_evidence_recovery_v3.py']
    manifest = dict(stages=['aco', 'rpl10'], source_hashes={p: a.sha(a.ROOT / p) for p in files},
        producer_manifests=original_manifest['producer_manifests'], inherited_completed_closures=inherited,
        original_manifest_sha256=a.sha(ORIGINAL_RUNTIME / 'manifest.json'),
        original_failure_sha256=a.sha(ORIGINAL_RUNTIME / 'failure.json'),
        change='Audit-only float64 bank/query promotion before independent ACO distances; no tolerance change',
        unique_target_cells=1206, training_complete=True, manuscript_generated=False)
    file = q.RUNTIME / 'manifest.json'
    if file.exists():
        assert a.read(file) == manifest
    else:
        a.write(file, manifest)
    # Keep all old partial evidence, including the zero-budget cell that passed.
    # Fresh v3 ACO receipts must not silently reuse old-checker partial receipts.
    archive = q.RUNTIME / 'superseded-aco-v2'
    if not (q.RUNTIME / 'partial-evidence-archived.json').exists():
        archived = {}
        for phase in ['fit-audit', 'outcome-audit', 'pair-checks']:
            p = a.OUT / phase / 'aco'
            if p.exists():
                destination = archive / phase
                assert not destination.exists()
                archived[phase] = {str(f.relative_to(p)): a.sha(f) for f in p.rglob('*') if f.is_file()}
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), str(destination))
        a.write(q.RUNTIME / 'partial-evidence-archived.json', archived)
    try:
        for stage in ['aco', 'rpl10']:
            q.source_guard(manifest)
            closure = q.RUNTIME / 'stages' / stage / 'completion.json'
            if closure.exists():
                saved = a.read(closure)
                assert saved['source_closure_sha256'] == a.sha(file)
                for phase, h in saved['phase_completion_hashes'].items():
                    assert a.sha(a.OUT / phase / stage / 'completion.json') == h
                completed.append(stage)
                continue
            q.audit_stage(stage, manifest)
            for script in ['analyze_core_evidence_v2.py', 'check_core_statistics_v2.py']:
                a.write(q.RUNTIME / 'status.json', dict(status='analysis_or_statistics', stage=stage,
                    script=script, pid=os.getpid(), last_update=time.time()))
                subprocess.run([sys.executable, str(a.ROOT / 'experiments' / script), '--stage', stage],
                    check=True, cwd=a.ROOT)
            q.source_guard(manifest)
            a.write(closure, dict(status='four_phases_completed_human_scientific_review_pending', stage=stage,
                phase_completion_hashes={phase: a.sha(a.OUT / phase / stage / 'completion.json')
                    for phase in ['fit-audit', 'outcome-audit', 'analysis', 'statistics-check']},
                source_closure_sha256=a.sha(file), completed_at_unix=time.time(), manuscript_generated=False))
            a.write(q.RUNTIME / 'sync' / f'{stage}.json', q.sync_stage(stage, args.sync_checkout))
            completed.append(stage)
        a.write(q.RUNTIME / 'completion.json', dict(status='completed_scientific_review_pending',
            stages=completed, unique_audited_experiment_cells=1206, source_manifest_sha256=a.sha(file),
            original_failure_preserved=True, manuscript_generated=False))
        a.write(q.RUNTIME / 'status.json', dict(status='completed_scientific_review_pending', stages=completed,
            pid=os.getpid(), last_update=time.time()))
    except BaseException:
        for child in q.mp.active_children():
            child.terminate()
            child.join()
        r = dict(status='failed_preserving_all_checkpoints', completed_stages=completed,
            traceback=traceback.format_exc(), last_update=time.time())
        a.write(q.RUNTIME / 'failure.json', r)
        a.write(q.RUNTIME / 'status.json', r)
        raise


if __name__ == '__main__':
    main()
