"""Independent CDM audit: sorted-rank replay, full LP and expectation arithmetic."""
from __future__ import annotations

import argparse
import bisect
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from scipy.optimize import linprog
from threadpoolctl import threadpool_limits

from analyze_nested import read, require, sha
from run_all import load_source, rank_subset, write_json
from run_crossfit import identifiers, inner_split
from savval import ACTIONS, FEATURES, StateSpace, price_features, stable_rank


def close(left, right, message, tolerance=1e-8):
    require(np.allclose(left, right, rtol=0, atol=tolerance, equal_nan=False), message)


def candidate_quotes(pred, scores, states, space, capacity):
    """Independent sorted-peer/bisect oracle; no CDM Market or allocator calls."""
    n, s = pred.shape
    result = np.empty((n, s, len(scores)))
    for k, rule in enumerate(scores):
        current = rule[np.arange(n), states]
        current_merit = current.max(axis=1)
        for i in range(n):
            peers = sorted((-float(m), j) for j, m in enumerate(current_merit)
                           if j != i and np.isfinite(m) and m > 0)
            for state in range(s):
                field = int(np.argmax(rule[i, state]))
                merit = float(rule[i, state, field])
                selected = (np.isfinite(merit) and merit > 0 and
                            bisect.bisect_left(peers, (-merit, i)) < capacity)
                after = int(space.query_next[state, field]) if selected else state
                result[i, state, k] = pred[i, after]
    return result


def allocate_independent(scores, states, space, capacity):
    action = np.full(len(states), -1, int)
    final = np.asarray(states).copy()
    choices = []
    for i, state in enumerate(states):
        field = int(np.argmax(scores[i, state]))
        merit = float(scores[i, state, field])
        if np.isfinite(merit) and merit > 0:
            choices.append((-merit, i, field))
    for _, i, field in sorted(choices)[:capacity]:
        action[i] = field
        final[i] = space.query_next[states[i], field]
    return final, action


def scores_independent(ids, x, pred, missing, space, head):
    n, s = pred.shape
    # Rebuild the input layout and output transformation directly.
    blocks = np.repeat(x.reshape(n*s, -1), 4, axis=0)
    inputs = np.column_stack((blocks, np.repeat(pred.reshape(-1), 4),
                              np.tile(np.eye(4), (n*s, 1))))
    raw = head.model.predict(inputs).reshape(n, s, 4, 3)
    scores = [np.full(missing.shape, -np.inf), np.where(missing, raw[..., 0], -np.inf),
              np.where(missing, raw[..., 1], -np.inf),
              np.where(missing & (np.arange(4)[None, None, :] == head.fixed_benefit_field),
                       raw[..., 2], -np.inf)]
    for a in range(4):
        scores.append(np.where(missing & (np.arange(4)[None, None, :] == a), 1., -np.inf))
    for k in range(4):
        priority = np.array([[int(stable_rank(str(i), f"cdm-public-hash-{k}-field-{a}")[:13], 16)
                              / float(16**13) + 1e-12 for a in range(4)] for i in ids])
        scores.append(np.where(missing, priority[:, None, :], -np.inf))
    return np.asarray(scores)


def audit_fit(folder, pred, scores, valid, frame, space, config, budget):
    arrays = np.load(folder / "matrix.npz")
    matrix, locator = arrays['matrix'], arrays['locator']
    profiles = read(folder / "profiles.json")
    solution = read(folder / "solution.json")
    alpha = np.asarray(solution['probabilities'])
    rebuilt, locators = [], []
    for profile in profiles:
        start = profile['start']
        stop = min(start + config['batch_size'], len(frame))
        states = np.asarray(profile['states'], int)
        require(valid[np.arange(start, stop), states].all(), "Impossible calibration profile")
        quotes = candidate_quotes(pred[start:stop], scores[:, start:stop], states,
                                  space, int(np.floor(budget * (stop-start))))
        signed = quotes - quotes[:, 0:1]
        signed -= config['concealment_cost_log'] * space.masks.sum(axis=1)[None, :, None]
        legal = valid[start:stop]
        rebuilt.append(signed[legal])
        where = np.argwhere(legal)
        locators.append(np.c_[np.full(len(where), profile['batch']),
                              np.full(len(where), profile['scenario']), where[:, 0]+start, where[:, 1]])
    close(np.concatenate(rebuilt), matrix, "Signed payoff matrix disagreement", 1e-10)
    require(np.array_equal(np.concatenate(locators), locator), "Payoff row locator disagreement")
    require(matrix.shape[1] == len(solution['policies']), "Rule bank width")
    error = float(np.mean(np.abs(np.expm1(pred[:, 0]) - np.expm1(frame.target_log))))
    close(solution['normal_errors'], np.full(len(alpha), error), "Honest errors", 1e-6)
    close(solution['allowance'], error*1.01, "Honest error cap", 1e-6)
    require(not solution['normal_error_constraint_has_rule_variation'], "Inactive honest constraint flag")
    constraint = np.vstack((np.c_[matrix, -np.ones(len(matrix))],
                            np.r_[np.full(len(alpha), error), 0.0]))
    full = linprog(np.r_[np.zeros(len(alpha)), 1.0], A_ub=constraint,
                   b_ub=np.r_[np.zeros(len(matrix)), error*1.01],
                   A_eq=np.r_[np.ones(len(alpha)), 0.0][None], b_eq=[1.0],
                   bounds=[(0.0, None)]*(len(alpha)+1), method='highs')
    require(full.success, "Independent full LP failed")
    close(full.x[-1], solution['bound'], "Restricted versus full LP optimum", 1e-7)
    require(np.max(matrix@alpha) <= solution['bound']+1e-8, "Full finite deviation feasibility")
    close(solution['pure_worst_gains'], np.maximum(matrix.max(axis=0), 0), "Pure reference bounds")
    require(abs(alpha.sum()-1)<1e-9 and (alpha >= -1e-12).all(), "Fit probabilities")
    return {'payoff_rows': len(matrix), 'bound': solution['bound'],
            'full_lp_difference': float(abs(full.x[-1]-solution['bound']))}


def audit_cell(folder, pred, scores, valid, frame, space, config, budget):
    outcome = pd.read_csv(folder/'outcomes.csv.gz')
    execution = np.load(folder/'execution.npz')
    summary = read(folder/'summary.json')
    draws = pd.read_csv(folder/'draws.csv')
    alpha = execution['probabilities']
    states = outcome.state.to_numpy(int)
    require(outcome.listing_id.astype(str).tolist() == frame.listing_id.astype(str).tolist(), "Outcome order/cohort")
    require(valid[np.arange(len(frame)), states].all(), "Impossible evaluation concealment")
    require(np.array_equal(outcome.hidden_count, space.masks[states].sum(axis=1)), "Hidden counts")
    quote, final, action = execution['quotes'], execution['finals'], execution['actions']
    succeeded = np.zeros_like(action, bool)
    for batch, start in enumerate(range(0,len(frame), config['batch_size'])):
        stop=min(start+config['batch_size'],len(frame))
        cap=int(np.floor(budget*(stop-start)))
        for k in range(len(alpha)):
            expected_final, expected_action = allocate_independent(scores[k,start:stop],states[start:stop],space,cap)
            require(np.array_equal(final[start:stop,k],expected_final),"Independent final-state allocation")
            require(np.array_equal(action[start:stop,k],expected_action),"Independent query allocation")
            require((expected_action>=0).sum()<=cap,"Actual hard capacity")
            close(quote[start:stop,k],pred[np.arange(start,stop),expected_final],"Executed quote",1e-10)
            selected=np.flatnonzero(expected_action>=0)
            succeeded[start+selected,k]=space.masks[states[start+selected],expected_action[selected]]
        if batch==0:
            all_quotes=candidate_quotes(pred[start:stop],scores[:,start:stop],states[start:stop],space,cap)
            net=all_quotes@alpha-config['concealment_cost_log']*space.masks.sum(axis=1)[None]
            net=np.where(valid[start:stop],net,-np.inf)
            realized=quote[start:stop]@alpha-config['concealment_cost_log']*space.masks[states[start:stop]].sum(axis=1)
            regret=np.maximum(net.max(axis=1)-realized,0)
            envelope=np.maximum(net.max(axis=1)-net[:,0],0)
            close(regret,outcome.best_response_regret_log.iloc[start:stop],"Exact mixture unilateral regret",1e-9)
            close(envelope,outcome.unilateral_deviation_envelope_log.iloc[start:stop],"Truthful counterfactual envelope",1e-9)
        expected_draw=np.searchsorted(np.cumsum(alpha),np.random.default_rng(7214000+summary['seed']*101+batch).random(config['private_draw_repetitions']),side='right')
        expected_draw=np.minimum(expected_draw,len(alpha)-1)
        require(np.array_equal(execution['draw_indices'][batch],expected_draw),"Private draw indices")
        batch_draws=draws[draws.batch==batch].sort_values('repetition')
        require(batch_draws.policy_index.tolist()==expected_draw.tolist(),"Draw table binding")
        for _, draw in batch_draws.iterrows():
            k=int(draw.policy_index)
            selected=action[start:stop,k]>=0
            require(draw.queries==selected.sum() and draw.capacity==cap and draw.queries<=cap,"Draw capacity")
            require(draw.failed_queries==(selected&~succeeded[start:stop,k]).sum(),"Failed query charging")
            close(draw.mae,np.abs(np.expm1(quote[start:stop,k])-np.expm1(frame.target_log.iloc[start:stop])).mean(),"Realized draw MAE",1e-6)
            close(draw.mean_positive_log_inflation,np.maximum(quote[start:stop,k]-pred[start:stop,0],0).mean(),"Realized draw inflation")
    target=frame.target_log.to_numpy()
    clean=pred[:,0]
    expected=quote@alpha
    currency=np.expm1(quote)
    mappings={'target_log':target,'clean_prediction_log':clean,'expected_prediction_log':expected,
              'expected_prediction_currency':currency@alpha,
              'clean_absolute_error':np.abs(np.expm1(clean)-np.expm1(target)),
              'expected_attack_absolute_error':np.abs(currency-np.expm1(target)[:,None])@alpha,
              'expected_attack_squared_log_error':((quote-target[:,None])**2)@alpha,
              'positive_expected_log_inflation':np.maximum(expected-clean,0),
              'expected_realized_positive_log_inflation':np.maximum(quote-clean[:,None],0)@alpha,
              'expected_query_probability':(action>=0)@alpha,
              'expected_failed_query_probability':((action>=0)&~succeeded)@alpha,
              'expected_signed_log_error':(quote-target[:,None])@alpha}
    for name,value in mappings.items():
        close(outcome[name],value,f"Expected arithmetic: {name}",1e-6 if 'currency' in name or 'absolute' in name else 1e-8)
    checks={'honest_mae':mappings['clean_absolute_error'].mean(),
            'expected_attack_mae':mappings['expected_attack_absolute_error'].mean(),
            'expected_attack_rmsle':np.sqrt(mappings['expected_attack_squared_log_error'].mean()),
            'mean_positive_expected_log_inflation':mappings['positive_expected_log_inflation'].mean(),
            'mean_expected_realized_positive_log_inflation':mappings['expected_realized_positive_log_inflation'].mean(),
            'expected_query_fraction':mappings['expected_query_probability'].mean(),
            'expected_failed_query_fraction':mappings['expected_failed_query_probability'].mean(),
            'hiding_fraction':(outcome.hidden_count>0).mean(),
            'expected_signed_log_bias':mappings['expected_signed_log_error'].mean(),
            'max_remaining_regret':outcome.best_response_regret_log.max(),
            'mean_remaining_regret':outcome.best_response_regret_log.mean(),
            'mean_unilateral_deviation_envelope':outcome.unilateral_deviation_envelope_log.mean(),
            'nonconverged_batch_fraction':1-outcome.groupby('batch').batch_converged.first().mean()}
    for name,value in checks.items():
        close(summary[name],value,f"Cell summary {name}",1e-6)
    return summary


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--partial',action='store_true')
    args=parser.parse_args()
    run, output=args.run.resolve(),args.output.resolve()
    manifest=read(run/'manifest.json')
    global_complete=(run/'completion.json').exists()
    require(global_complete or args.partial,'Completed generation or explicit partial required')
    root_receipt_hash=sha(run/'completion.json') if global_complete else None
    if global_complete:
        completion=read(run/'completion.json')
        require(completion['status']=='completed','Completed generation required')
        require(sha(run/'all_summary.csv')==completion['summary_sha256'],'Global summary hash')
        require(completion['pairs']==manifest['pairs'],'Frozen pair completion')
        pairs=manifest['pairs']
    else:
        pairs=[pair for pair in manifest['pairs'] if
               (run/pair[0]/f'seed-{pair[1]}'/'completion.json').exists()]
        require(bool(pairs),'No completed pairs for partial audit')
        completion={'cells':len(pairs)*len(manifest['prices'])*len(manifest['config']['budgets'])*(len(manifest['policies'])+2),
                    'all_scheduled_pairs_completed':False}
    config=manifest['config']
    for name,digest in manifest['source_hashes'].items():
        require(sha(run/'source_snapshot'/name)==digest,'Source snapshot binding')
    require(not output.exists(),'Fresh audit output required')
    output.mkdir(parents=True)
    (output/'auditor_snapshot.py').write_bytes(Path(__file__).read_bytes())
    pair_hashes={f'{d}/seed-{s}':sha(run/d/f'seed-{s}'/'completion.json') for d,s in pairs}
    write_json(output/'audit_binding.json',{'run_manifest_sha256':sha(run/'manifest.json'),
               'frozen_completed_pairs':pairs,'pair_receipt_hashes':pair_hashes,
               'run_complete_at_start':global_complete,'partial_requested':args.partial,
               'root_completion_sha256':root_receipt_hash})
    torch.set_num_threads(4)
    rows,fit_rows=[],[]
    space=StateSpace.build(config['maximum_hidden'])
    with threadpool_limits(limits=4):
        for dataset in manifest['parent_config']['datasets']:
            seeds=[s for d,s in pairs if d==dataset]
            if not seeds: continue
            first,old_head,evaluation,_=load_source(dataset,manifest['parent_config'])
            estimator,guidance=inner_split(pd.concat([first,old_head],ignore_index=True),config['head_fitting_fraction'])
            guide_order=rank_subset(guidance,len(guidance),'cdm-head-calibration-v1')
            cut=len(guide_order)//2
            head_frame,calibration=guide_order.iloc[:cut].copy(),guide_order.iloc[cut:].copy()
            if manifest['execution_smoke']:
                head_frame,calibration,evaluation=head_frame.iloc[:64].copy(),calibration.iloc[:64].copy(),evaluation.iloc[:64].copy()
            for seed in seeds:
                own=run/dataset/f'seed-{seed}'
                binding=read(own/'data_audit.json')
                for name,frame in [('head',head_frame),('calibration',calibration),('evaluation',evaluation)]:
                    require(pd.read_csv(own/f'{name}_ids.csv').listing_id.astype(str).tolist()==frame.listing_id.astype(str).tolist(),'Cohort IDs')
                    require(binding[f'{name}_ids_sha256']==identifiers(frame),'Cohort hash')
                require(binding['estimator_ids_sha256']==identifiers(estimator),'Estimator split')
                for price in manifest['prices']:
                    folder=own/price
                    model_binding=read(folder/'model_binding.json')
                    require(sha(Path(model_binding['parent_model_path']))==model_binding['parent_model_sha256'],'Immutable model binding')
                    require(sha(folder/'head.joblib')==model_binding['head_sha256'],'Head binding')
                    model,_,_=joblib.load(model_binding['parent_model_path'])
                    head=joblib.load(folder/'head.joblib')
                    arrays=[]
                    for name,frame in [('calibration',calibration),('evaluation',evaluation)]:
                        a=np.load(folder/f'{name}_arrays.npz')
                        actual,x,valid=model.predict(price_features(frame,FEATURES[dataset]))
                        close(a['pred'],actual,'Price prediction reconstruction',2e-6)
                        require(np.array_equal(a['valid'],valid),'Original hiding eligibility')
                        close(a['target_log'],frame.target_log.to_numpy(),'Outcome binding')
                        rebuilt=scores_independent(frame.listing_id,x,actual,space.reported_missing(frame),space,head)
                        require(np.array_equal(np.isfinite(a['scores']),np.isfinite(rebuilt)),'Public field score availability')
                        close(a['scores'][np.isfinite(rebuilt)],rebuilt[np.isfinite(rebuilt)],'Public score reconstruction',1e-10)
                        arrays.append((a['pred'],a['scores'],a['valid']))
                    for budget in config['budgets']:
                        budget_folder=folder/f'budget-{int(round(budget*10000)):04d}'
                        done=read(budget_folder/'completion.json')
                        for name,digest in done['files'].items():
                            require(sha(budget_folder/name)==digest,'Budget artifact hash')
                        fit=audit_fit(budget_folder/'fit',*arrays[0],calibration,space,config,budget)
                        fit_rows.append({'dataset':dataset,'seed':seed,'price':price,'budget':budget,**fit})
                        solution=read(budget_folder/'fit/solution.json')
                        for name in [*manifest['policies'],'uniform','cdm']:
                            cell=budget_folder/name
                            result=audit_cell(cell,*arrays[1],evaluation,space,config,budget)
                            alpha=np.load(cell/'execution.npz')['probabilities']
                            expected=(solution['probabilities'] if name=='cdm' else
                                      np.full(len(alpha),1/len(alpha)) if name=='uniform' else
                                      np.eye(len(alpha))[manifest['policies'].index(name)])
                            close(alpha,expected,'Method probability binding',1e-12)
                            rows.append({'dataset':dataset,'price':price,**result})
                        print(f'AUDITED CDM {dataset}/{seed}/{price}/{budget}',flush=True)
    require(len(rows)==completion['cells'],'Full cell count')
    pd.DataFrame(rows).to_csv(output/'audited_summary.csv',index=False)
    pd.DataFrame(fit_rows).to_csv(output/'audited_fits.csv',index=False)
    write_json(output/'completion.json',{'status':'completed','cells':len(rows),'fits':len(fit_rows),
               'parent_completion_sha256':root_receipt_hash,'auditor_sha256':sha(Path(__file__)),
               'partial':not global_complete,'frozen_completed_pairs':pairs,
               'all_scheduled_pairs_completed':completion['all_scheduled_pairs_completed'],
               'execution_smoke':manifest['execution_smoke'],
               'files':{p.name:sha(p) for p in output.iterdir() if p.is_file()},
               'scope':'all stored finite calibration rows, full LP optimum, all execution/draw expectations; exact first-batch deviations; no unseen-type or whole-game guarantee'})
    print(f'AUDITED CDM GENERATION {output}',flush=True)


if __name__=='__main__':
    main()
