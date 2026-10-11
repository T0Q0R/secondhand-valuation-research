"""Training-internal equal-budget tuning for three matched price methods."""
from __future__ import annotations

import copy
import time

import numpy as np

from run_all import fit_heads, rank_subset
from savval import StateSpace, fit_backbone, price_features, strategic_response


METHODS=('robust_no_feedback','sav_val','sav_benefit_head')
GRID=(.25,.5,1.0)


def tuning_split(frame):
    ordered=rank_subset(frame,len(frame),'sav-equal-tune-validation-v1')
    count=int(np.floor(.2*len(frame)))
    if count<2 or len(frame)-count<8:
        raise ValueError('Insufficient tuning rows')
    return ordered.iloc[count:].copy(),ordered.iloc[:count].copy()


def fit_group(estimator,guidance,columns,config,seed,weights):
    """Same backbone and exact residual budgets; unused variants are omitted."""
    public=price_features(estimator,columns)
    y=estimator.target_log.to_numpy()
    started=time.time()
    base=fit_backbone(public,y,StateSpace.build(config['maximum_hidden']),config,seed,augment=True)
    initial_head=fit_heads(base,guidance,columns,config,seed)
    backbone_seconds=time.time()-started
    models,logs,times={},{},{}
    for tag,beta in weights.items():
        method=tag.rsplit('__',1)[-1]
        if method not in METHODS:
            raise ValueError('Unknown fitted method')
        print(f'    FIT {tag} gap={beta}',flush=True)
        tick=time.time()
        model=copy.deepcopy(base)
        local=dict(config,gap_penalty_weight=beta)
        if method=='robust_no_feedback':
            trace=model.train_residual(public,y,local,seed,policy=None)
            head=fit_heads(model,guidance,columns,local,seed)
            kind='suppression'
        else:
            kind='benefit' if method=='sav_benefit_head' else 'suppression'
            head=initial_head
            trace=[]
            rounds=local['feedback_rounds']
            for iteration in range(rounds):
                epochs=local['residual_epochs']//rounds+int(iteration<local['residual_epochs']%rounds)
                trained=model.train_residual(public,y,local,seed+iteration,head,
                                              gap_weight=beta,policy_kind=kind,policy_aware=True,epochs=epochs)
                head=fit_heads(model,guidance,columns,local,seed)
                trace.append({'round':iteration+1,'training':trained,'head_targets':head.target_summary})
        models[tag]=(model,head,kind)
        logs[tag]={'gap_weight':beta,'training':trace}
        times[tag]=time.time()-tick
    return models,{'shared_backbone_and_initial_head_seconds':backbone_seconds,
                   'method_residual_and_final_heads_seconds':times,'logs':logs}


def validation_score(fitted,frame,columns,config,*,return_evidence=False):
    model,head,kind=fitted
    pred,x,valid=model.predict(price_features(frame,columns))
    scores=head.score(x,pred,model.space,kind,reported_missing=model.space.reported_missing(frame))
    target=frame.target_log.to_numpy()
    attack_loss=[]
    responses=[]
    for start in range(0,len(frame),config['batch_size']):
        stop=min(start+config['batch_size'],len(frame))
        response=strategic_response(pred[start:stop],scores[start:stop],valid[start:stop],model.space,
                                     budget=.1,sweeps=config['attacker_sweeps'],restarts=config['attacker_restarts'],
                                     cost=config['concealment_cost_log'])
        quote=pred[np.arange(start,stop),response['final_state']]
        attack_loss.extend((quote-target[start:stop])**2)
        responses.append({'states':response['states'],'final_state':response['final_state'],
                          'action':response['action'],'regret':response['regret']})
    honest=float(np.mean((pred[:,0]-target)**2))
    attacked=float(np.mean(attack_loss))
    result={'objective':honest+attacked,'honest_squared_log_loss':honest,'attack_squared_log_loss':attacked}
    if return_evidence:
        evidence={'pred':pred,'scores':scores,'valid':valid,'target':target}
        evidence.update({name:np.concatenate([r[name] for r in responses])
                         for name in ('states','final_state','action','regret')})
        return result,evidence
    return result


def choose_weights(trials):
    chosen={}
    for method in METHODS:
        candidates=[row for row in trials if row['method']==method]
        if {row['gap_weight'] for row in candidates}!=set(GRID) or len(candidates)!=len(GRID):
            raise ValueError('Unequal or incomplete tuning allowance')
        best=min(candidates,key=lambda row:(row['objective'],GRID.index(row['gap_weight'])))
        chosen[method]=best['gap_weight']
    return chosen
