"""Verification-history pricing; public allocation is inherited unchanged."""
import numpy as np
from cdm_mechanism import Market

class CappedMarket(Market):
    def candidate_quotes(self,item,states):
        recovered=super().candidate_quotes(item,states)
        return np.minimum(recovered,self.pred[item,:,None])

    def execute(self,states):
        recovered,final,action=super().execute(states)
        before=self.pred[np.arange(self.n),np.asarray(states,int)]
        return np.minimum(recovered,before[:,None]),final,action
