"""Independent two-outcome value/gradient reconstruction; no training claim."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np,torch
from matched_feedback_loss import replay_terms

def main(out):
    assert not out.exists();out.mkdir(parents=True)
    rng=np.random.default_rng(20261008);count=0;max_error=0.
    for mode in ('fractional','none','certain','failed'):
        for _ in range(50):
            q0=torch.tensor(rng.normal(10,2,7),requires_grad=True,dtype=torch.float64)
            q1=torch.tensor(rng.normal(10,2,7) if mode!='failed' else q0.detach().numpy(),requires_grad=True,dtype=torch.float64)
            target=torch.tensor(rng.normal(10,2,7),dtype=torch.float64)
            p=torch.tensor(rng.random(7) if mode in ('fractional','failed') else np.full(7,mode=='certain'),dtype=torch.float64)
            anchor=torch.tensor(rng.normal(10,2,7),requires_grad=True,dtype=torch.float64)
            result=replay_terms(q0,q1,target,p,anchor,.1)
            objective=(result['expected_squared_error']+.3*result['expected_gain_penalty']).sum()
            gradients=torch.autograd.grad(objective,(q0,q1),retain_graph=True)
            r0=q0.detach().clone().requires_grad_();r1=q1.detach().clone().requires_grad_();terms=[]
            for i in range(7):
                expected=sum([w*q for w,q in [(1-p[i],r0[i]),(p[i],r1[i])]])
                loss=sum([w*(q-target[i])**2 for w,q in [(1-p[i],r0[i]),(p[i],r1[i])]])
                terms.append(loss+.3*torch.maximum(expected-anchor[i].detach()-.1,torch.tensor(0.)))
            direct=torch.stack(terms).sum();reference=torch.autograd.grad(direct,(r0,r1))
            assert abs(float(objective.detach()-direct.detach()))<1e-10
            assert all(torch.allclose(a,b,atol=1e-12,rtol=1e-12) for a,b in zip(gradients,reference))
            identity=(result['expected_quote']-target).square()+result['query_variance']
            error=float((identity-result['expected_squared_error']).abs().max().detach());max_error=max(max_error,error)
            assert error<1e-10;count+=1
    example=replay_terms(torch.tensor([8.]),torch.tensor([12.]),torch.tensor([10.]),torch.tensor([.5]),torch.tensor([10.]))
    assert example['expected_squared_error'].item()==4 and example['expected_gain_penalty'].item()==0
    assert (example['expected_quote']-10).square().item()==0
    try:replay_terms(torch.zeros(1),torch.zeros(1),torch.zeros(1),torch.ones(1,requires_grad=True),torch.zeros(1))
    except ValueError:pass
    else:raise AssertionError('Unfrozen allocation accepted')
    files=[Path(__file__),Path('experiments/matched_feedback_loss.py'),Path('plan/matched-feedback-loss-v1.md')]
    for p in files:(out/p.name).write_bytes(p.read_bytes())
    result={'status':'completed','value_gradient_cases':count,'items_per_case':7,'max_identity_error':max_error,'counterexample_expected_loss':4,'counterexample_loss_of_expectation':0,'input_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'scope':'loss primitive only; no model fitted or incentive improvement established'}
    (out/'completion.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
