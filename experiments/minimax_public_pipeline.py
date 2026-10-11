"""Public adapter for the score-surrogate minimax allocation control."""
import numpy as np
from benchmark_public_pipeline import current_quote
from public_minimax_allocation import marginals,draw
from savval import ACTIONS


def select_public(model,head,public,budget,private_uniform,kind):
    if kind not in ('suppression','benefit','risk'):
        raise ValueError('Unsupported public score kind')
    if not np.isfinite(budget) or not 0<=budget<=1:
        raise ValueError('Budget must be in [0,1]')
    quote,encoded=current_quote(model,public)
    missing=public.loc[:,list(ACTIONS)].isna().to_numpy()[:,None,:]
    raw=head.score(encoded[:,None,:],quote[:,None],model.space,kind,reported_missing=missing)[:,0,:]
    # Same positive-score eligibility as deterministic top-B allocation.
    eligible=missing[:,0,:]&np.isfinite(raw)&(raw>0)
    scores=np.where(eligible,raw,0.)
    result=marginals(scores,eligible,int(np.floor(budget*len(public))))
    return {**result,'actions':draw(result,private_uniform),'pre_quote_log':quote,'scores':scores}


def public_pipeline(model,head,public,budget,private_uniform,kind,replay):
    result=select_public(model,head,public,budget,private_uniform,kind)
    after,succeeded=replay(public,result['actions'])
    final,_=current_quote(model,after)
    return {**result,'final_quote_log':final,'query_succeeded':succeeded}
