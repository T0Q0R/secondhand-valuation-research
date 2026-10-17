"""Check the archived failure and the repaired auditor, without changing results."""
import os
for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']:
    os.environ[key] = '1'
from pathlib import Path
import tempfile, time
import joblib, numpy as np, torch
from threadpoolctl import threadpool_limits
import core_evidence_audit_v2 as a
import audit_core_aco_v2 as old
import audit_core_aco_v3 as repaired
from conditional_neighbor_head import ConditionalNeighborHead


def main():
    started = time.time()
    original_out = a.OUT
    manifest = a.read(a.ROOT / 'outputs/aco1-development-v2/manifest.json')
    _, _, ev, _ = a.load_source('synthetic', manifest['parent_config'])
    model, _, _ = joblib.load(a.parent('synthetic', 13) / 'deployment_models/masking_suppression.joblib')
    a.bounded(model)
    pred, x, valid = model.predict(a.price_features(ev, a.FEATURES['synthetic']))
    bankdir = a.ROOT / 'outputs/aco1-development-v2/synthetic/seed-13/bank-masking'
    bank, available, losses, weights = [np.load(bankdir / f'{n}.npy') for n in
        ['bank_encoded', 'bank_available', 'bank_loss_patterns', 'coordinate_weights']]
    groups = a.read(bankdir / 'field_groups.json')
    missing = ev[list(a.ACTIONS)].isna().to_numpy()[:, None, :] | a.BITS[None, :, :]
    checks = []
    for k in [25, 10, 50]:
        head = ConditionalNeighborHead(bank, available, losses, groups, weights, k)
        original = head.score(x, pred, model.space, 'benefit', reported_missing=missing)
        broken = old.scores_direct(bank, available, losses, groups, weights, x, missing, k)
        actual = repaired.scores_direct(bank, available, losses, groups, weights, x, missing, k)
        np.testing.assert_array_equal(actual, original)
        finite = np.isfinite(original)
        checks.append(dict(k=k, exact_repaired_score_match=True,
            old_max_score_difference=float(np.max(abs(broken[finite] - original[finite]))),
            old_different_finite_scores=int(np.count_nonzero(broken[finite] != original[finite]))))
    assert checks[0]['old_different_finite_scores'] > 0
    # Full saved-pair outcome check for both backends and all16 cells.
    with tempfile.TemporaryDirectory(prefix='aco-v3-smoke-') as folder:
        a.OUT = Path(folder)
        (a.OUT / 'fit-audit').mkdir()
        (a.OUT / 'fit-audit/models').symlink_to(original_out / 'fit-audit/models', target_is_directory=True)
        try:
            pair = repaired.audit_pair('synthetic', 13)
            assert pair['cells'] == 16 and pair['status'] == 'completed'
        finally:
            a.OUT = original_out
    report = dict(status='engineering_check_passed_full_matrix_pending', elapsed_seconds=time.time()-started,
        scope='synthetic seed13, all1000 evaluation records, two backends, all16 saved cells',
        old_failure_reproduced=True, strict_score_matches=checks, full_pair=pair,
        production_source_changed=False, original_results_changed=False, tolerance_changed=False,
        old_checker_sha256=a.sha(Path(old.__file__)), repaired_checker_sha256=a.sha(Path(repaired.__file__)))
    a.write(a.ROOT / 'notes/core-evidence-recovery-v3/engineering.json', report)
    print(report, flush=True)


if __name__ == '__main__':
    torch.set_num_threads(1)
    with threadpool_limits(limits=1):
        main()
