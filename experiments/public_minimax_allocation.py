"""Public-score minimax baseline, not an incentive-optimality claim.

This module deliberately accepts only public scores and eligibility. It never
sees targets, source availability, seller truth or replay transitions.
"""
from __future__ import annotations
import numpy as np
from fractions import Fraction as F


def marginals(scores, eligible, capacity):
    scores=np.asarray(scores,dtype=float); eligible=np.asarray(eligible,dtype=bool)
    if scores.ndim!=2 or scores.shape!=eligible.shape or scores.shape[1]==0:
        raise ValueError('Expected matching item-by-field arrays')
    n=len(scores)
    if isinstance(capacity,(bool,np.bool_)) or not isinstance(capacity,(int,np.integer)) or not 0<=capacity<=n:
        raise ValueError('Integer capacity must lie between zero and batch size')
    if not np.isfinite(scores[eligible]).all() or (scores[eligible]<0).any():
        raise ValueError('Eligible vulnerability scores must be finite and nonnegative')
    masked=np.where(eligible,scores,-np.inf)
    fields=np.argmax(masked,axis=1)
    gain=masked[np.arange(n),fields]
    gain=np.where(np.isfinite(gain)&(gain>0),gain,0.)
    fields=np.where(gain>0,fields,-1)
    positive=gain>0; probabilities=np.zeros(n)
    if capacity>=positive.sum(): probabilities[positive]=1.
    elif capacity>0:
        lo,hi=0.,float(gain.max())
        for _ in range(80):
            t=lo+(hi-lo)/2
            needed=np.maximum(1-t/gain[positive],0.).sum()
            if needed>capacity: lo=t
            else: hi=t
        probabilities[positive]=np.maximum(1-hi/gain[positive],0.)
        total=probabilities.sum()
        if total>capacity: probabilities*=capacity/total
    # Roundoff in summation must not create a lottery above the hard capacity.
    exact_total=sum((F(float(v)) for v in probabilities),F(0))
    if exact_total>capacity:
        i=int(np.argmax(probabilities))
        probabilities[i]=max(0.,np.nextafter(float(F(float(probabilities[i]))-(exact_total-capacity)),0.))
    objective=float(np.max(gain*(1-probabilities),initial=0.))
    return {'fields':fields,'probabilities':probabilities,'gains':gain,
            'surrogate_bound':objective,'capacity':int(capacity)}


def draw(result,private_uniform):
    if not np.isfinite(private_uniform) or not 0<=private_uniform<1:
        raise ValueError('Private uniform must be in [0,1)')
    p=np.asarray(result['probabilities']);fields=np.asarray(result['fields'])
    b=result['capacity'];total=sum((F(float(v)) for v in p),F(0))
    if (p<0).any() or (p>1).any() or total>b:
        raise ValueError('Invalid probabilities')
    # Exact represented-float interval arithmetic avoids boundary duplicates.
    ends=[];running=F(0)
    for v in p:
        running+=F(float(v));ends.append(running)
    actions=np.full(len(p),-1,int)
    from bisect import bisect_right
    for k in range(b):
        point=F(float(private_uniform))+k
        if point>=total: break
        i=bisect_right(ends,point)
        if i>=len(p) or fields[i]<0 or actions[i]>=0:
            raise AssertionError('Invalid systematic interval realization')
        actions[i]=fields[i]
    assert (actions>=0).sum()<=b
    return actions
