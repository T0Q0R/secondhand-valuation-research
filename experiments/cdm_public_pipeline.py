"""CDM deployment path: public reports, frozen weights, one private batch draw.

No original concealment state, source availability, label or truthful anchor is
an input. The replay callback reads only selected fields after allocation.
"""
from __future__ import annotations

import numpy as np

from benchmark_public_pipeline import current_quote
from cdm_mechanism import POLICIES, policy_scores
from savval import ACTIONS


def select_public(model, head, ids, public, probabilities, budget, private_uniform):
    alpha=np.asarray(probabilities,dtype=float)
    if len(alpha)!=len(POLICIES) or (alpha<0).any() or abs(alpha.sum()-1)>1e-9:
        raise ValueError('Invalid frozen mixture probabilities')
    if not 0<=private_uniform<1 or not 0<=budget<=1 or len(ids)!=len(public):
        raise ValueError('Invalid public batch/draw')
    quote,encoded=current_quote(model,public)
    missing=public.loc[:,list(ACTIONS)].isna().to_numpy()[:,None,:]
    scores=policy_scores(ids,encoded[:,None,:],quote[:,None],missing,model.space,head)[:, :, 0, :]
    policy=min(int(np.searchsorted(np.cumsum(alpha),private_uniform,side='right')),len(alpha)-1)
    rule=scores[policy]
    fields=np.argmax(rule,axis=1)
    merit=rule[np.arange(len(public)),fields]
    ranking=np.lexsort((np.arange(len(public)),-merit))
    eligible=np.isfinite(merit)&(merit>0)
    capacity=int(np.floor(budget*len(public)))
    selected=ranking[eligible[ranking]][:capacity]
    actions=np.full(len(public),-1,int)
    actions[selected]=fields[selected]
    if (actions>=0).sum()>capacity:
        raise AssertionError('Actual batch capacity')
    return {'policy_index':policy,'pre_quote_log':quote,'actions':actions,'scores':scores,
            'capacity':capacity}


def public_pipeline(model,head,ids,public,probabilities,budget,private_uniform,replay):
    result=select_public(model,head,ids,public,probabilities,budget,private_uniform)
    after,succeeded=replay(public,result['actions'])
    final,_=current_quote(model,after)
    return {**result,'final_quote_log':final,'query_succeeded':succeeded}
