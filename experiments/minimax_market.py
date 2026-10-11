"""Expected item-local replay under publicly scored minimax marginals.

Private valid states and replay transitions are environment inputs, never
allocation inputs. Every unilateral report recomputes the public allocation.
"""
import numpy as np
from public_minimax_allocation import marginals

class MinimaxMarket:
    def __init__(self,pred,scores,valid,space,capacity,cost=0.):
        self.pred=np.asarray(pred,float);self.scores=np.asarray(scores,float)
        self.valid=np.asarray(valid,bool);self.space=space;self.capacity=capacity;self.cost=cost
        self.n,self.s=self.pred.shape
        if self.scores.shape[:2]!=(self.n,self.s) or self.valid.shape!=self.pred.shape:
            raise ValueError('State dimensions')
        if not np.isfinite(self.pred).all() or not self.valid[:,0].all() or cost<0:
            raise ValueError('Invalid environment')

    def expected_execution(self,states):
        states=np.asarray(states,int)
        if states.shape!=(self.n,) or not self.valid[np.arange(self.n),states].all():
            raise ValueError('Invalid report profile')
        raw=self.scores[np.arange(self.n),states]
        eligible=np.isfinite(raw)&(raw>0)
        allocation=marginals(np.where(eligible,raw,0.),eligible,self.capacity)
        fields=allocation['fields'];p=allocation['probabilities']
        final=states.copy();chosen=fields>=0
        final[chosen]=self.space.query_next[states[chosen],fields[chosen]]
        before=self.pred[np.arange(self.n),states];after=self.pred[np.arange(self.n),final]
        return {**allocation,'states':states.copy(),'final_if_queried':final,
                'pre_quotes':before,'queried_quotes':after,'expected_quotes':before+p*(after-before)}

    def candidate_quotes(self,item,states):
        result=np.full(self.s,-np.inf)
        for candidate in np.flatnonzero(self.valid[item]):
            changed=np.array(states,copy=True);changed[item]=candidate
            result[candidate]=self.expected_execution(changed)['expected_quotes'][item]
        return result

    def response(self,sweeps=20,restarts=4):
        costs=self.cost*self.space.masks.sum(axis=1)
        starts=[np.zeros(self.n,int)]
        if restarts>1:starts.append(np.argmax(np.where(self.valid,self.pred-costs,-np.inf),axis=1))
        for restart in range(2,restarts):
            rng=np.random.default_rng(1931+restart)
            starts.append(np.array([rng.choice(np.flatnonzero(v)) for v in self.valid]))
        runs=[]
        for initial in starts:
            states=initial.copy();visited={tuple(states)};cycle=False;count=0
            for sweep in range(sweeps):
                changed=False
                for i in range(self.n):
                    values=self.candidate_quotes(i,states)-costs;best=int(np.argmax(values))
                    if values[best]>values[states[i]]+1e-8:states[i]=best;changed=True
                count=sweep+1
                if not changed:break
                if tuple(states) in visited:cycle=True;break
                visited.add(tuple(states))
            execution=self.expected_execution(states)
            utility=execution['expected_quotes']-costs[states]
            candidates=np.array([self.candidate_quotes(i,states)-costs for i in range(self.n)])
            regret=np.maximum(candidates.max(axis=1)-utility,0)
            runs.append({**execution,'utility':utility,'regret':regret,
                         'deviation_envelope':np.maximum(candidates.max(axis=1)-candidates[:,0],0),
                         'sweeps':count,'cycle':cycle,'converged':bool((regret<1e-7).all())})
        return max(runs,key=lambda x:float(x['utility'].sum()))
