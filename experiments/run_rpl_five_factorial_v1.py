"""Matched 2x5 crossing, 3 sources x 3 seeds, 10% capacity; no model fitting.

Preserves all historical runners, guards, tolerances and checkpoints. ACO bank
losses are rebuilt under each price model; the four neural score tables are
price-independent frozen acquisitions, not refitted or selected on outcomes.
"""
from pathlib import Path
import argparse, copy, fcntl, gc, hashlib, json, os, time, traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
import joblib
import numpy as np
import pandas as pd
import torch
from threadpoolctl import threadpool_limits
import core_evidence_audit_v2 as audit
from audit_core_aco_v3 import scores_direct
import run_completion_ablation_v6 as common
from run_completion_sefa_v6 import FrozenPublicScores
from run_aco_comparator import prepare_bank
from conditional_neighbor_head import ConditionalNeighborHead
from run_all import load_source, rank_subset, evaluate_method
from run_crossfit import inner_split
from savval import ACTIONS, FEATURES, price_features

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/rpl-five-factorial-v1'
FAMILIES = dict(aco=None, sefa='completion-sefa-v6-official',
                gdfs='recent-gdfs-v1', dime='recent-dime-v1', efa='recent-efa-v1')
SOURCES = ['synthetic', 'jucars', 'mucars']
SEEDS = [13, 42, 2026]
sha, read, write = audit.sha, audit.read, audit.write
DEPS = ['run_rpl_five_factorial_v1.py', 'core_evidence_audit_v2.py',
        'audit_core_aco_v3.py', 'run_completion_ablation_v6.py',
        'run_completion_sefa_v6.py', 'run_aco_comparator.py',
        'conditional_neighbor_head.py', 'benchmark_public_pipeline.py',
        'run_all.py', 'run_crossfit.py', 'savval.py']


class OneThreadBackbone:
    def __init__(self, model):
        self.model = getattr(model, 'model', model)

    def predict(self, *args, **kwargs):
        return self.model.predict(*args, **dict(kwargs, thread_count=1))


def guard():
    m = read(OUT / 'manifest.json')
    for p, h in m['dependencies'].items():
        assert sha(ROOT / p) == h, p
    assert sha(ROOT / 'paper/innovation-addendum-v1.tex') == m['manuscript_sha256']
    return m


def model_path(source, seed, weight):
    if weight == 0:
        p = ROOT / 'outputs/completion-ablation-v6' / source / f'seed-{seed}' / 'deployment_models/off_gap.joblib'
        assert sha(p) == read(p.with_suffix('.json'))['model_sha256']
    else:
        p = ROOT / 'outputs/recovery-path-learning-v1' / source / f'seed-{seed}' / 'path-1-gap-0.5/deployment_model.joblib'
        assert sha(p) == read(p.with_suffix('.json'))['sha256']
    return p


def prepare(workers):
    assert 1 <= workers <= 5
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = copy.deepcopy(read(common.PARENT / 'run_manifest.json')['config'])
    cfg.update(datasets=SOURCES, seeds=SEEDS, budgets=[.1])
    assert cfg['concealment_cost_log'] == 0 and cfg['batch_size'] == 100
    m = dict(config=cfg, expected_cells=90, expected_pairs=9, rpl_weights=[0, 1],
             gap_weight=.5, families=list(FAMILIES), budget=.1, new_fits=0,
             workers=workers, compute_threads_per_worker=1, total_compute_limit=6,
             nice=10, dependencies={f'experiments/{n}':sha(ROOT/'experiments'/n) for n in DEPS},
             manuscript_sha256=sha(ROOT/'paper/innovation-addendum-v1.tex'),
             parent_manifest_sha256=sha(common.PARENT/'run_manifest.json'),
             scope='Retrospective matched price-by-acquisition crossing; three fitting seeds on fixed cohorts; full seed ranges, no confirmatory inference. ACO bank losses recomputed for each price. Neural acquisition unchanged. No training, tuning, new seeds or external-machine runs.')
    p = OUT / 'manifest.json'
    if p.exists():
        assert read(p) == m
    else:
        write(p, m)
    return m


def neural_scores(family, source, seed, evaluation):
    p = ROOT / 'outputs' / FAMILIES[family] / source / f'seed-{seed}'
    receipt = read(p/'scores.json')
    assert receipt['label_inputs'] is False
    assert receipt['evaluation_features_sha256'] == common.content(price_features(evaluation, FEATURES[source]))
    assert sha(p/'scores.npz') == receipt['score_sha256']
    assert sha(p/'refit/model.joblib') == receipt['model_sha256']
    assert (p/'completion.json').exists()
    files = ['scores.json', 'scores.npz', 'refit/model.joblib', 'selection.json', 'public-input-check.json']
    return np.load(p/'scores.npz')['scores'], {str((p/f).relative_to(ROOT)):sha(p/f) for f in files}


def pair(task):
    source, seed = task
    m = guard(); cfg = m['config']; torch.set_num_threads(1)
    own = OUT/source/f'seed-{seed}'; own.mkdir(parents=True, exist_ok=True)
    lock = (own/'execution.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    rows_out = []
    with threadpool_limits(limits=1):
        e, g, ev, _ = load_source(source, cfg)
        train = rank_subset(pd.concat([e,g], ignore_index=True), len(e)+len(g), 'sav-val-cf-training-order-v2')
        est, guidance = inner_split(train, cfg['head_fitting_fraction'])
        assert not set(train.listing_id) & set(ev.listing_id)
        assert len(train) == 5000 and len(ev) == 1000
        write(own/'data-binding.json', dict(training=common.content(train), evaluation=common.content(ev),
              training_ids=audit.ids(train), evaluation_ids=audit.ids(ev), guidance_ids=audit.ids(guidance)))
        tables = {f:neural_scores(f, source, seed, ev) for f in FAMILIES if f != 'aco'}
        for weight in [0,1]:
            mp = model_path(source, seed, weight); mh = sha(mp)
            model, _, _ = joblib.load(mp)
            model.backbone = OneThreadBackbone(model.backbone)
            pred, x, valid = model.predict(price_features(ev, FEATURES[source]))
            # Model-only equivalence against the frozen RPL reference, no search.
            ref = read(ROOT/'outputs/recovery-path-learning-v1'/source/f'seed-{seed}'/f'path-{weight}-gap-0.5/evaluation-1000/completion.json')['summary']
            honest_mae = float(abs(np.expm1(pred[:,0])-np.expm1(ev.target_log.to_numpy())).mean())
            np.testing.assert_allclose(honest_mae, ref['clean_mae'], atol=1e-7, rtol=1e-10)
            bankdir = own/f'bank-rpl-{weight}'
            if bankdir.exists():
                r = read(bankdir/'receipt.json')
                assert r['price_sha256'] == mh and r['guidance'] == common.content(guidance)
                for f,h in r['files'].items(): assert sha(bankdir/f) == h
                arrays = [np.load(bankdir/f'{n}.npy') for n in ['bank_encoded','bank_available','bank_loss_patterns']]
                arrays += [read(bankdir/'field_groups.json'), np.load(bankdir/'coordinate_weights.npy')]
            else:
                arrays = prepare_bank(model, guidance, FEATURES[source], bankdir)
                write(bankdir/'receipt.json', dict(price_sha256=mh, guidance=common.content(guidance),
                      files={p.name:sha(p) for p in bankdir.iterdir() if p.is_file()}))
            aco = ConditionalNeighborHead(*arrays, k=25)
            missing = model.space.reported_missing(ev)
            ac_scores = aco.score(x, pred, model.space, 'benefit', reported_missing=missing)
            independent = scores_direct(*arrays[:3], arrays[3], arrays[4], x, missing, 25)
            np.testing.assert_allclose(ac_scores, independent, atol=1e-12, rtol=1e-10)
            # Reuse the existing public-input invariance contract at concealed state 1.
            tiny = ev.iloc[:4].copy(); other = tiny.copy(); other['mileage_km'] = 123456789.
            pp, xx, _ = model.predict(price_features(tiny, FEATURES[source]))
            qq, yy, _ = model.predict(price_features(other, FEATURES[source]))
            s1 = aco.score(xx,pp,model.space,'benefit',reported_missing=model.space.reported_missing(tiny))
            s2 = aco.score(yy,qq,model.space,'benefit',reported_missing=model.space.reported_missing(other))
            np.testing.assert_allclose(s1[:,1],s2[:,1],atol=1e-12,rtol=0)
            for family in FAMILIES:
                folder = own/f'rpl-{weight}'/family; folder.mkdir(parents=True, exist_ok=True)
                if family == 'aco':
                    scores = ac_scores
                    bindings = {str((bankdir/'receipt.json').relative_to(ROOT)):sha(bankdir/'receipt.json')}
                else:
                    scores, bindings = tables[family]
                assert scores.shape == (len(ev),11,4) and not np.isnan(scores).any()
                assert np.isneginf(scores[~missing]).all()
                sp = folder/'scores.npz'
                if not sp.exists():np.savez_compressed(sp,scores=scores)
                np.testing.assert_array_equal(np.load(sp)['scores'],scores)
                inputs = dict(price_model=str(mp.relative_to(ROOT)), price_sha256=mh,
                              source_bindings=bindings, evaluation=common.content(ev),
                              score_sha256=sha(sp), manifest_sha256=sha(OUT/'manifest.json'),
                              rpl_weight=weight, gap_weight=.5, budget=.1, family=family)
                cp = folder/'completion.json'
                if cp.exists():
                    r = read(cp); assert r['inputs'] == inputs
                    assert sha(folder/'outcomes.csv.gz') == r['outcomes_sha256']
                    rows_out.append(r['summary']);continue
                head = FrozenPublicScores(scores,pred)
                outcomes, s = evaluate_method(f'rpl{weight}_{family}',model,head,'sefa',ev,FEATURES[source],cfg,seed,.1)
                assert outcomes.listing_id.tolist() == ev.listing_id.tolist()
                integer = common.matrix_audit(pred,scores,valid,ev,outcomes,.1)
                rebuilt,batches,deviations = audit.independent_outcomes(pred,scores,valid,ev,outcomes,.1)
                for k,v in rebuilt.items():np.testing.assert_allclose(s[k],v,atol=1e-7,rtol=1e-10,err_msg=k)
                s.update(dataset=source, family=family, rpl_weight=weight, gap_weight=.5)
                outcomes.to_csv(folder/'outcomes.csv.gz',index=False)
                write(cp,dict(status='computed_and_independently_outcome_corroborated', inputs=inputs,
                      summary=s, outcomes_sha256=sha(folder/'outcomes.csv.gz'), integer_audit=integer,
                      batches=batches, legal_unilateral_deviations=deviations,
                      acquisition_check='ACO full coordinate-wise score reconstruction; neural source table and public-input receipt bound',
                      scope='Independent outcome algebra; shares frozen predictors, loader and acquisition source. Not a new four-stage fit/statistical audit.'))
                rows_out.append(s)
                write(own/'progress.json',dict(completed_cells=len(rows_out),expected_cells=10))
                print('FACTORIAL_CELL',source,seed,weight,family,flush=True)
            assert sha(mp) == mh
            del model,pred,x,valid,aco,arrays,independent;gc.collect()
        assert len(rows_out) == 10
        pd.DataFrame(rows_out).to_csv(own/'summary.csv',index=False)
        write(own/'completion.json',dict(status='completed',cells=10,summary_sha256=sha(own/'summary.csv')))
    guard()
    return rows_out


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--first-pair',action='store_true')
    args=parser.parse_args()
    if os.getpriority(os.PRIO_PROCESS,0)<10:os.nice(10-os.getpriority(os.PRIO_PROCESS,0))
    m=prepare(args.workers)
    if args.prepare_only:return
    lock=(OUT/'execution.lock').open('a+')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    tasks=[(d,s) for d in SOURCES for s in SEEDS]
    if args.first_pair:tasks=tasks[:1]
    summaries=[];started=time.time()
    try:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            fs={pool.submit(pair,t):t for t in tasks}
            for future in as_completed(fs):
                summaries.extend(future.result())
                pd.DataFrame(summaries).to_csv(OUT/'summary.csv',index=False)
                write(OUT/'status.json',dict(status='running',completed_cells=len(summaries),expected_cells=90,
                      workers=args.workers,threads_per_worker=1,nice=os.getpriority(os.PRIO_PROCESS,0)))
        if not args.first_pair:assert len(summaries)==90
        write(OUT/('first-pair.json' if args.first_pair else 'completion.json'),dict(
              status='first_pair_engineering_check' if args.first_pair else 'computed_and_independently_outcome_corroborated',
              cells=len(summaries),new_fits=0,seconds=time.time()-started,
              manifest_sha256=sha(OUT/'manifest.json'),summary_sha256=sha(OUT/'summary.csv')))
        write(OUT/'status.json',dict(status='first_pair_complete' if args.first_pair else 'completed',
              completed_cells=len(summaries),expected_cells=90,seconds=time.time()-started))
    except BaseException:
        write(OUT/f'failure-{time.time_ns()}.json',dict(status='failed_preserving_checkpoints',traceback=traceback.format_exc()))
        raise


if __name__=='__main__':main()
