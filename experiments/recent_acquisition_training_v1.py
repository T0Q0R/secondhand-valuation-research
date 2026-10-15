"""Task-specific adaptations of GDFS/DIME and explainability-driven AFA.
Official architectures, explicit public-context masks, training-only four-bin targets.
See notes/recent-five-v1/PLAN.zh.md for deviations from original experiments.
"""
from pathlib import Path
import sys,json,copy,time,ast
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from catboost import CatBoostClassifier,Pool
import run_completion_sefa_v6 as shared
from savval import ACTIONS
ROOT=shared.ROOT
REF=ROOT/'notes/recent-five-v1/official-code/sefa-reference'
EFA=ROOT/'notes/recent-five-v1/official-code/explainability-afa/Tabular_Experiments'
from models.gdfs import GDFS
from models.dime import DIME
sys.path.insert(0,str(EFA))
from model_gpt import GPT,GPTConfig
# Load only the upstream MLP class, never execute the training script's CLI/data code.
source=ast.parse((EFA/'first_stage_tabular.py').read_text())
node=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='MLP_tabular')
exec(compile(ast.Module(body=[node],type_ignores=[]),str(EFA/'first_stage_tabular.py'),'exec'))

class ExplainPolicy(nn.Module):
 def __init__(self,d):
  super().__init__();self.net=MLP_tabular(2*d,4,n_hidden=128,n_embd=64)
  self.policy=GPT(GPTConfig(4,4,n_layer=3,n_head=4,n_embd=64,model_type='reward_conditioned',max_timestep=16),4)
 def predict_logits(self,x,m):return self.net(torch.cat([x*m,m],1))
 def step(self,x,m,history=None,last=None):
  n=len(x);logits,emb=self.net(torch.cat([x*m,m],1),fea_return=True)
  reward=logits.softmax(-1).detach();last=torch.zeros(n,dtype=torch.long) if last is None else last
  hist=[] if history is None else list(history);hist.append((emb,reward,last))
  out=self.policy(torch.stack([a[0] for a in hist],1),torch.stack([a[2] for a in hist],1)[:,:,None],targets=torch.zeros(n,len(hist),1,dtype=torch.long),rtgs=torch.stack([a[1] for a in hist],1),timesteps=torch.zeros(n,1,1,dtype=torch.long))
  return logits,out[:,-1],hist

def configs(method,smoke=False):
 if method in ('gdfs','dime'):
  cs=[json.loads((REF/f'experiments/hyperparameters/configs/{method}/config{i}.json').read_text()) for i in [1,5,9]]
 else:cs=[dict(lr=lr,pretrain_lr=lr,batchsize=128,pretrain_epochs=250,epochs=200,second_epochs=16) for lr in [.001,.0005,.0003]]
 if smoke:
  cs=cs[:1]
  for c in cs:c.update(pretrain_epochs=1,epochs=1,second_epochs=1,batchsize=32)
 return cs

def schedule(method,c):
 s=[('pretrain',0)]*c['pretrain_epochs']
 if method=='gdfs':s += [('gdfs',float(t)) for t in c['temp_initial']*np.geomspace(1,.1,5) for _ in range(c['epochs'])]
 elif method=='dime':s += [('dime',float(e)) for e in c['eps_initial']*np.array([1,.25,.05,.005]) for _ in range(c['epochs'])]
 else:s += [('rank',0)]*c['epochs']+[('policy',0)]*c['second_epochs']
 return s

def mask(natural,positions,rng):
 # Uniform over legal reports with <=2 observed query fields hidden.
 valid=~(shared.common.BITS[None,:,:]&~natural[:,positions,None].transpose(0,2,1).astype(bool)).any(2)
 ix=np.array([rng.choice(np.flatnonzero(v)) for v in valid]);m=natural.copy();m[:,positions]*=~shared.common.BITS[ix];return torch.from_numpy(m)

def raw_scores(model,method,x,m,pos):
 if method=='efa':return model.step(x,m)[1].softmax(-1)
 return model.calculate_acquisition_scores(x,m)[:,pos]

def prediction(model,method,x,m):return model.predict_logits(x,m) if method=='efa' else model.predictor(x,m)

def val_loss(model,method,x,natural,y,pos,seed):
 model.eval();rng=np.random.default_rng(seed);total=0.;count=0
 with torch.no_grad():
  for b in range(0,len(x),128):
   xx=x[b:b+128];yy=y[b:b+128];nnat=natural[b:b+128];m=mask(nnat.numpy(),pos,rng)
   before=prediction(model,method,xx,m);loss=F.cross_entropy(before,yy,reduction='none')
   avail=nnat[:,pos]*(1-m[:,pos]);scores=raw_scores(model,method,xx,m,pos).masked_fill(avail==0,-1e6);a=scores.argmax(1);after=m.clone();after[torch.arange(len(xx)),torch.tensor(pos)[a]]=torch.maximum(after[torch.arange(len(xx)),torch.tensor(pos)[a]],avail[torch.arange(len(xx)),a]);loss=(loss+F.cross_entropy(prediction(model,method,xx,after),yy,reduction='none'))/2
   total+=float(loss.sum());count+=len(xx)
 return total/count

def fit(frame,val,method,c,seed,directory,source,smoke=False,refit=False):
 directory.mkdir(parents=True,exist_ok=True);cp=directory/'completion.json';path=directory/'model.joblib'
 inputs=dict(train=shared.common.content(frame),validation=shared.common.content(val),method=method,config=c,seed=seed,source=source,smoke=smoke,refit=refit)
 if cp.exists():
  r=json.loads(cp.read_text());assert r['inputs']==inputs and shared.sha(path)==r['sha256'];return shared.joblib.load(path),r
 enc=shared.PublicEncoding().fit(shared.price_features(frame,shared.FEATURES[source]));xx,nnat=enc.transform(frame);vx,vn=enc.transform(val);pos=[enc.columns.index(a) for a in ACTIONS];cuts=np.quantile(frame.target_log,[.25,.5,.75]);y=torch.tensor(np.searchsorted(cuts,frame.target_log,side='right'));vy=torch.tensor(np.searchsorted(cuts,val.target_log,side='right'));x=torch.from_numpy(xx);natural=torch.from_numpy(nnat)
 torch.manual_seed(seed);rng=np.random.default_rng(seed)
 model=ExplainPolicy(len(enc.columns)) if method=='efa' else {'gdfs':GDFS,'dime':DIME}[method]({**c,**enc.settings()})
 # TreeSHAP rankings are derived only from the fitting partition; no evaluation rows.
 ranking=None
 if method=='efa':
  teacher=CatBoostClassifier(iterations=10 if smoke else 250,depth=6,learning_rate=.05,loss_function='MultiClass',thread_count=torch.get_num_threads(),random_seed=seed,verbose=False,allow_writing_files=False)
  teacher.fit(np.c_[xx,nnat],y.numpy());values=teacher.get_feature_importance(Pool(np.c_[xx,nnat]),type='ShapValues')
  values=values[np.arange(len(xx)),y.numpy(),:-1];ranking=torch.from_numpy(np.abs(values[:,pos])+np.abs(values[:,np.array(pos)+len(enc.columns)]))
  shared.dump(directory/'ranking-teacher.joblib',teacher)
 optimizer=torch.optim.Adam(model.parameters(),lr=c['pretrain_lr']);sched=schedule(method,c);start=0;best=float('inf');best_state=None;history=[];checkpoint=directory/'training.joblib'
 if (directory/'training.json').exists():
  r=json.loads((directory/'training.json').read_text());assert r['inputs']==inputs and r['sha256']==shared.sha(checkpoint)
  old=shared.joblib.load(checkpoint);model.load_state_dict(old['model']);optimizer.load_state_dict(old['optimizer']);rng.bit_generator.state=old['rng'];torch.set_rng_state(old['torch_rng']);start=old['epoch'];best=old['best'];best_state=old['best_state'];history=old['history']
 started=time.time()
 for epoch in range(start,len(sched)):
  phase,param=sched[epoch]
  if epoch==0 or sched[epoch]!=sched[epoch-1]:
   if best_state is not None:model.load_state_dict(best_state)
   optimizer=torch.optim.Adam(model.parameters(),lr=c['pretrain_lr'] if phase=='pretrain' else c['lr']);best=float('inf')
  model.train();total=0.;count=0
  for begin in range(0,len(x),c['batchsize']):
   if begin==0:order=rng.permutation(len(x))
   ix=order[begin:begin+c['batchsize']]
   if len(ix)==1:ix=np.r_[ix,order[0]]
   bx=x[ix];by=y[ix];bn=natural[ix];m=mask(bn.numpy(),pos,rng);optimizer.zero_grad()
   if phase=='pretrain':loss=F.cross_entropy(prediction(model,method,bx,m),by)
   else:
    loss=F.cross_entropy(prediction(model,method,bx,m),by)/3;hist=None;last=None
    for step in range(2):
     avail=bn[:,pos]*(1-m[:,pos]);active=avail.any(1);den=active.sum().clamp_min(1)
     before=prediction(model,method,bx,m)
     if method=='gdfs':
      logits=model.selector(bx,m)[:,pos].masked_fill(avail==0,-1e6);soft=torch.distributions.RelaxedOneHotCategorical(param,logits=logits).rsample()*avail
      sm=m.clone();sm[:,pos]=torch.maximum(sm[:,pos],soft);loss=loss+(F.cross_entropy(model.predictor(bx,sm),by,reduction='none')*active).sum()/den/2
      selected=logits.argmax(1)
     elif method=='dime':
      probs=before.softmax(-1).detach();h=-(probs*probs.clamp_min(1e-8).log()).sum(1,keepdim=True);value=h*model.value(bx,m)[:,pos]
      greedy=value.masked_fill(avail==0,-1e6).argmax(1);random=(torch.rand_like(avail).masked_fill(avail==0,-1)).argmax(1);selected=torch.where(torch.rand(len(bx))<param,random,greedy)
     else:
      before,logits,hist=model.step(bx,m,hist,last);logits=logits.masked_fill(avail==0,-1e6);target=ranking[ix].masked_fill(avail==0,-1).argmax(1)
      loss=loss+(F.cross_entropy(logits,target,reduction='none')*active).sum()/den/2
      selected=target if phase=='rank' else logits.detach().argmax(1);last=selected
     new=m.clone();new[torch.arange(len(bx)),torch.tensor(pos)[selected]]=torch.maximum(new[torch.arange(len(bx)),torch.tensor(pos)[selected]],avail[torch.arange(len(bx)),selected]);after=prediction(model,method,bx,new)
     if method!='gdfs':loss=loss+F.cross_entropy(after,by)/3
     if method=='dime':
      delta=(F.cross_entropy(before,by,reduction='none')-F.cross_entropy(after,by,reduction='none')).detach();estimate=value[torch.arange(len(bx)),selected];loss=loss+(((estimate-delta)**2)*active).sum()/den/2
     m=new
   assert torch.isfinite(loss);loss.backward();optimizer.step();total+=float(loss.detach())*len(ix);count+=len(ix)
  vl=val_loss(model,method,torch.from_numpy(vx),torch.from_numpy(vn),vy,pos,seed+9081)
  if vl<best:best=vl;best_state=copy.deepcopy(model.state_dict())
  history.append(dict(epoch=epoch+1,phase=phase,param=param,train_loss=total/count,validation_nll=vl))
  shared.dump(checkpoint,dict(epoch=epoch+1,model=model.state_dict(),optimizer=optimizer.state_dict(),rng=rng.bit_generator.state,torch_rng=torch.get_rng_state(),best=best,best_state=best_state,history=history));shared.write(directory/'training.json',dict(inputs=inputs,sha256=shared.sha(checkpoint),epoch=epoch+1,total_epochs=len(sched)))
  print('RECENT_EPOCH',method,source,seed,epoch+1,len(sched),vl,flush=True)
 model.load_state_dict(model.state_dict() if refit else best_state);model.eval();shared.dump(path,(model,enc,cuts));r=dict(inputs=inputs,sha256=shared.sha(path),status='fitted',validation_nll=best,epochs=len(sched),history=history,seconds=time.time()-started);shared.write(cp,r);return (model,enc,cuts),r

def acquisition(model,enc,frame,space,seed,method):
 pos=[enc.columns.index(a) for a in ACTIONS];scores=np.empty((len(frame),11,4));model.eval()
 for state,bits in enumerate(shared.common.BITS):
  public=frame.loc[:,enc.columns].copy()
  for field,hidden in zip(ACTIONS,bits):
   if hidden:public[field]=np.nan
  x,m=enc.transform(public);pieces=[]
  with torch.no_grad():
   for b in range(0,len(x),128):pieces.append(raw_scores(model,method,torch.from_numpy(x[b:b+128]),torch.from_numpy(m[b:b+128]),pos).numpy())
  scores[:,state]=np.concatenate(pieces)
 return np.where(space.reported_missing(frame),scores,-np.inf)
