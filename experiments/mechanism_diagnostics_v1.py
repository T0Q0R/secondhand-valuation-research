"""Recovery transition counts: all legal hidden-field edges and realized queries.
All-edge rates are model geometry, not population seller behavior probabilities.
"""
import numpy as np

def recovery_diagnostics(pred,valid,space,evaluation,rows):
    after=pred[:,space.query_next]
    edge=valid[:,:,None] & space.masks[None,:,:].astype(bool)
    delta=after-pred[:,:,None]
    values=delta[edge];n=len(pred);ix=np.arange(n)
    states=rows.state.to_numpy(int);final=rows.final_state.to_numpy(int)
    successful=rows.query_succeeded.to_numpy(bool)
    realized=pred[ix,final]-pred[ix,states]
    v=realized[successful]
    return dict(legal_hidden_recovery_edges=int(edge.sum()),
        recovery_raises_quote_edges=int((values>1e-8).sum()),
        recovery_raises_quote_edge_fraction=float((values>1e-8).mean()) if len(values) else 0.,
        max_recovery_log_increase=float(max(0.,values.max())) if len(values) else 0.,
        realized_successful_queries=int(successful.sum()),
        realized_recovery_raises_quote=int((v>1e-8).sum()),
        realized_positive_recovery_log_sum=float(np.maximum(v,0).sum()),
        all_listing_realized_positive_recovery_log_mean=float(np.maximum(realized,0).mean()),
        denominator_note='Edges count only legal hidden fields; realized fractions must use successful queries,not all missing fields.')
