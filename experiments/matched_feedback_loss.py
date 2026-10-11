"""Differentiable replay expectation with allocation held fixed."""
import torch

def replay_terms(before,queried,target,probability,honest_anchor,tolerance=0.):
    if not (before.shape==queried.shape==target.shape==probability.shape==honest_anchor.shape):
        raise ValueError('Expected matching per-item tensors')
    if probability.requires_grad:
        raise ValueError('Allocation probabilities must be frozen within a step')
    if not torch.isfinite(probability).all() or ((probability<0)|(probability>1)).any():
        raise ValueError('Invalid query probabilities')
    expected=before+probability*(queried-before)
    attacked_squared=(1-probability)*(before-target).square()+probability*(queried-target).square()
    variance=probability*(1-probability)*(queried-before).square()
    gap=torch.relu(expected-honest_anchor.detach()-tolerance)
    return {'expected_quote':expected,'expected_squared_error':attacked_squared,
            'query_variance':variance,'expected_gain_penalty':gap}
