"""Shared-budget factorial fit primitive; outer cross-fitting is a separate layer."""
import copy,hashlib
import numpy as np
import torch
from torch import nn
from savval import StateSpace,fit_backbone,price_features
from run_all import fit_heads
from cdm_mechanism import Market
from minimax_market import MinimaxMarket
from matched_feedback_loss import replay_terms

def update(model,frame,columns,config,seed,epochs,objective,head=None,kind='suppression',allocation='top_b',policy_feedback=False):
    torch.manual_seed(seed)
    x,base,valid=model.arrays(price_features(frame,columns));y=frame.target_log.to_numpy()
    if model.residual is None:
        model.residual=nn.Sequential(nn.Linear(x.shape[-1],model.width),nn.ReLU(),nn.Linear(model.width,model.width),nn.ReLU(),nn.Linear(model.width,1))
        nn.init.zeros_(model.residual[-1].weight);nn.init.zeros_(model.residual[-1].bias)
    optimizer=torch.optim.AdamW(model.residual.parameters(),lr=config['learning_rate'],weight_decay=1e-4)
    xx=torch.from_numpy(x);bb=torch.from_numpy(base);yy=torch.tensor(y,dtype=torch.float32)
    rng=np.random.default_rng(seed);logs=[]
    for epoch in range(epochs):
        scores=None
        if policy_feedback:
            assert head is not None
            scores=head.score(x,model.predict_arrays(x,base),model.space,kind,reported_missing=model.space.reported_missing(frame))
        order=rng.permutation(len(frame));total=0.;steps=0;query_mass=0.
        for start in range(0,len(frame),config['batch_size']):
            idx=order[start:start+config['batch_size']];bx=xx[idx];by=yy[idx];baseline=bb[idx]
            model.residual.train();pred=baseline+model.residual(bx.reshape(-1,bx.shape[-1])).reshape(baseline.shape)
            detached=pred.detach().numpy().astype(float);n=len(idx);capacity=int(np.floor(config.get('training_budget',.1)*n))
            if policy_feedback:
                if allocation=='minimax':
                    response=MinimaxMarket(detached,scores[idx],valid[idx],model.space,capacity,config['concealment_cost_log']).response(sweeps=config['training_attacker_sweeps'],restarts=1)
                    states=response['states'];final=response['final_if_queried'];probability=response['probabilities']
                elif allocation=='top_b':
                    response=Market(detached,scores[idx][None],valid[idx],model.space,capacity,config['concealment_cost_log']).response(np.ones(1),sweeps=config['training_attacker_sweeps'],restarts=1)
                    states=response['states'];final=response['finals'][:,0];probability=(response['actions'][:,0]>=0).astype(float)
                else:raise ValueError('Allocation')
            else:
                utility=detached-config['concealment_cost_log']*model.space.masks.sum(axis=1)
                states=np.argmax(np.where(valid[idx],utility,-np.inf),axis=1);final=states;probability=np.zeros(n)
            row=torch.arange(n);honest=pred[:,0]
            replay=replay_terms(pred[row,states],pred[row,final],by,torch.tensor(probability,dtype=pred.dtype),honest,config['gap_tolerance_log'])
            valid_tensor=torch.tensor(valid[idx]);augmented=(((pred-by[:,None])**2)*valid_tensor).sum(dim=1)/valid_tensor.sum(dim=1)
            loss=(honest-by).square().mean()+.25*augmented.mean()+config['anchor_weight']*(honest-baseline[:,0]).square().mean()
            if objective=='robust':loss=loss+config['attack_loss_weight']*replay['expected_squared_error'].mean()+config['gap_penalty_weight']*replay['expected_gain_penalty'].mean()
            elif objective!='masking':raise ValueError('Objective')
            assert torch.isfinite(loss)
            optimizer.zero_grad();loss.backward();nn.utils.clip_grad_norm_(model.residual.parameters(),5.);optimizer.step()
            total+=float(loss.detach())*n;steps+=1;query_mass+=float(probability.sum())
        logs.append({'epoch':epoch,'updates':steps,'examples':len(frame),'permutation_sha256':hashlib.sha256(order.tobytes()).hexdigest(),'loss':total/len(frame),'query_mass':query_mass,'policy_feedback':policy_feedback,'objective':objective})
    return logs

def fit_factorial(estimator,guidance,columns,config,seed,load_cached=None,save_cached=None):
    if set(estimator.listing_id)&set(guidance.listing_id):raise ValueError('Estimator/guidance overlap')
    if config['feedback_epochs']<config['feedback_rounds']:raise ValueError('Every round needs an update')
    backbone=None
    load_cached=load_cached or (lambda key:None)
    save_cached=save_cached or (lambda key,model,head,receipt:None)
    cells={};receipts={}
    for initial_objective in ('masking','robust'):
        cached=load_cached('initial__'+initial_objective)
        if cached is None:
            if backbone is None:
                backbone=fit_backbone(price_features(estimator,columns),estimator.target_log.to_numpy(),StateSpace.build(config['maximum_hidden']),config,seed,augment=True)
            initial=copy.deepcopy(backbone)
            initial_logs=update(initial,estimator,columns,config,seed,config['initial_epochs'],initial_objective)
            initial_head=fit_heads(initial,guidance,columns,config,seed)
            save_cached('initial__'+initial_objective,initial,initial_head,{'initial_training':initial_logs})
        else:
            initial,initial_head,receipt=cached;initial_logs=receipt['initial_training']
        specifications=[('none','shared','shared')]+[('policy',kind,allocation) for kind in ('suppression','benefit','risk') for allocation in ('top_b','minimax')]
        for feedback,kind,allocation in specifications:
            fit_id=f'{initial_objective}__{feedback}__{kind}__{allocation}'
            cached=load_cached(fit_id)
            if cached is None:
                model=copy.deepcopy(initial);head=copy.deepcopy(initial_head);logs=[]
                for round_id in range(config['feedback_rounds']):
                    epochs=config['feedback_epochs']//config['feedback_rounds']+int(round_id<config['feedback_epochs']%config['feedback_rounds'])
                    trace=update(model,estimator,columns,config,seed+100+round_id,epochs,'robust',head,kind,allocation,feedback=='policy')
                    head=fit_heads(model,guidance,columns,config,seed);logs.append({'round':round_id,'training':trace})
                receipt={'initial_training':initial_logs,'feedback_training':logs,'head_fits':1+config['feedback_rounds'],'estimator_ids':estimator.listing_id.astype(str).tolist(),'guidance_ids':guidance.listing_id.astype(str).tolist()}
                save_cached(fit_id,model,head,receipt)
            else:model,head,receipt=cached
            receipts[fit_id]=receipt
            aliases=[(k,a) for k in ('suppression','benefit','risk') for a in ('top_b','minimax')] if feedback=='none' else [(kind,allocation)]
            for k,a in aliases:cells[(initial_objective,k,feedback,a)]={'model':model,'head':head,'fit_id':fit_id}
    assert len(cells)==24 and len(receipts)==14
    return cells,receipts
