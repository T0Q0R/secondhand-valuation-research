"""Official ICML2025 SEFA acquisition, four training-only price bins.
One-query, shared batch-budget adaptation with a frozen price estimator.
The official stochastic encoder, NLL/KL loss and acquisition formula are unchanged.
"""
from pathlib import Path
import argparse,copy,fcntl,gc,hashlib,json,sys,time,os,traceback
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np,pandas as pd,torch,joblib
from threadpoolctl import threadpool_limits
import run_completion_ablation_v6 as common
from savval import FEATURES,ACTIONS,price_features,stable_rank
from run_all import load_source,rank_subset,evaluate_method
ROOT=common.ROOT;OFFICIAL=ROOT/'notes/experiment-completion-v6/official-code/a-norcliffe__SEFA';sys.path.insert(0,str(OFFICIAL))
from models.sefa import SEFA,BlockLinear
# PyTorch2.14 returns a noncontiguous einsum result. Official .view fails on CPU;
# reshape preserves exactly the block-linear algebra and autograd graph.
def compatible_block_forward(self,x):
 batchsize=x.shape[0];x=x.reshape(batchsize,-1,self.in_dims)
 return torch.einsum('boi,xbi->xbo',self.weight,x).reshape(batchsize,-1)+self.bias
BlockLinear.forward=compatible_block_forward
sha=common.sha;write=common.write;dump=common.dump

class PublicEncoding:
 def fit(self,frame):
  self.numeric=[c for c in frame if pd.api.types.is_numeric_dtype(frame[c])];self.categorical=[c for c in frame if c not in self.numeric];self.columns=self.numeric+self.categorical;self.means={};self.scales={};self.maps={}
  for c in self.numeric:
   a=self.number(frame[c],c);self.means[c]=float(a.mean()) if a.notna().any() else 0.;self.scales[c]=float(a.std()) if a.notna().sum()>1 and a.std()>1e-8 else 1.
  for c in self.categorical:self.maps[c]={v:i for i,v in enumerate(sorted(frame[c].dropna().astype(str).unique()))}
  return self
 def number(self,s,c):
  a=pd.to_numeric(s,errors='coerce');return np.log1p(a.clip(lower=0)) if c in {'mileage_km','feat_battery_capacity','feat_battery_range'} else a
 def transform(self,frame):
  values=[];masks=[]
  for c in self.columns:
   if c in self.numeric:
    a=self.number(frame[c],c);masks.append(a.notna().to_numpy());values.append(((a-self.means[c])/self.scales[c]).fillna(0).to_numpy())
   else:
    a=frame[c];masks.append(a.notna().to_numpy());values.append(a.astype(str).map(self.maps[c]).fillna(len(self.maps[c])).to_numpy())
  x=np.stack(values,1).astype('float32');m=np.stack(masks,1).astype('float32');return x*m,m
 def settings(self):return dict(num_con_features=len(self.numeric),num_cat_features=len(self.categorical),most_categories=max([len(x)+1 for x in self.maps.values()]+[0]),out_dim=4)

class FrozenPublicScores:
 def __init__(self,scores,pred):self.scores=scores;self.bound=hashlib.sha256(pred.tobytes()).hexdigest()
 def score(self,x,pred,space,kind,*,reported_missing):
  assert self.bound==hashlib.sha256(pred.tobytes()).hexdigest() and self.scores.shape==reported_missing.shape
  return np.where(reported_missing,self.scores,-np.inf)

def legal_masks(x,natural,encoding,rng):
 positions=[encoding.columns.index(c) for c in ACTIONS];observed=natural[:,positions].astype(bool);valid=~(common.BITS[None,:,:]&~observed[:,None,:]).any(2)
 # Uniform over valid reports; no nonquery feature is deliberately hidden.
 choice=np.array([rng.choice(np.flatnonzero(v)) for v in valid]);mask=natural.copy();mask[:,positions]*=~common.BITS[choice];return x*mask,mask

def fit_classifier(frame,validation,cfg,seed,directory,refit_epochs=None):
 directory.mkdir(parents=True,exist_ok=True);cp=directory/'completion.json';path=directory/'model.joblib';inputs=dict(training=common.content(frame),validation=common.content(validation),config=cfg,seed=seed,refit_epochs=refit_epochs)
 if cp.exists():
  r=json.loads(cp.read_text());assert r['inputs']==inputs and sha(path)==r['sha256'];return joblib.load(path),r
 encoder=PublicEncoding().fit(price_features(frame,FEATURES[cfg['source']]));x,m=encoder.transform(frame);vx,vm=encoder.transform(validation);cuts=np.quantile(frame.target_log,[.25,.5,.75]);y=np.searchsorted(cuts,frame.target_log,side='right');vy=np.searchsorted(cuts,validation.target_log,side='right');settings={**cfg['official'],**encoder.settings()};torch.manual_seed(seed);model=SEFA(settings);optimizer=torch.optim.Adam(model.parameters(),lr=settings['lr']);scheduler=torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer,factor=.2,patience=settings['patience']);rng=np.random.default_rng(seed);best=float('inf');bestepoch=0;history=[];stale=0;started=time.time();checkpoint=directory/'training.joblib';checkpoint_receipt=directory/'training.json';start=0
 if checkpoint_receipt.exists():
  cr=json.loads(checkpoint_receipt.read_text());assert cr['inputs']==inputs and cr['sha256']==sha(checkpoint);state=joblib.load(checkpoint);model.load_state_dict(state['model']);optimizer.load_state_dict(state['optimizer']);scheduler.load_state_dict(state['scheduler']);rng.bit_generator.state=state['rng'];torch.set_rng_state(state['torch_rng']);best=state['best'];bestepoch=state['bestepoch'];stale=state['stale'];history=state['history'];start=len(history)
 # Fixed validation reports and common sampling noise across epochs.
 valrng=np.random.default_rng(seed+100003);vxx,vmm=legal_masks(vx,vm,encoder,valrng);vt=torch.from_numpy(vxx);mt=torch.from_numpy(vmm);yt=torch.tensor(vy,dtype=torch.long)
 epochs=refit_epochs or settings['epochs'];batch=settings['batchsize']
 for epoch in range(start,epochs):
  model.train();order=rng.permutation(len(frame));total=0.;examples=0
  for begin in range(0,len(order),batch):
   ix=order[begin:begin+batch]
   if len(ix)==1:ix=np.r_[ix,order[0]]
   bx,bm=legal_masks(x[ix],m[ix],encoder,rng);optimizer.zero_grad();loss=model.loss_func(torch.from_numpy(bx),torch.tensor(y[ix],dtype=torch.long),torch.from_numpy(bm));assert torch.isfinite(loss);loss.backward();optimizer.step();total+=float(loss.detach())*len(ix);examples+=len(ix)
  model.eval()
  with torch.no_grad(),torch.random.fork_rng():
   torch.manual_seed(seed+100019);vl=0.
   for begin in range(0,len(vt),batch):
    end=min(begin+batch,len(vt));ll=model.log_likelihood(vt[begin:end],mt[begin:end],settings['num_samples_predict'])[0];vl+=float(torch.nn.functional.nll_loss(ll,yt[begin:end],reduction='sum'))
   vl/=len(vt)
  history.append(dict(epoch=epoch+1,train_loss=total/examples,validation_nll=vl));scheduler.step(vl)
  if vl<best-1e-6:best=vl;bestepoch=epoch+1;stale=0;dump(directory/'best.joblib',copy.deepcopy(model.state_dict()))
  else:stale+=1
  state=dict(model=model.state_dict(),optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),rng=rng.bit_generator.state,torch_rng=torch.get_rng_state(),best=best,bestepoch=bestepoch,stale=stale,history=history);dump(checkpoint,state);write(checkpoint_receipt,dict(inputs=inputs,sha256=sha(checkpoint),epoch=epoch+1));print('SEFA_EPOCH',cfg['source'],seed,directory.name,epoch+1,vl,flush=True)
  # Preserve all120official trial epochs; retain best validation checkpoint.
 if refit_epochs is None:model.load_state_dict(joblib.load(directory/'best.joblib'))
 model.eval();dump(path,(model,encoder,cuts));r=dict(status='fitted',inputs=inputs,sha256=sha(path),best_validation_nll=best,best_epoch=bestepoch,epochs_run=len(history),history=history,seconds=time.time()-started);write(cp,r);return (model,encoder,cuts),r

def acquisition(model,encoder,frame,space,seed):
 # Common frozen noise for a record across reports: identical public input gives
 # identical scores even if a missing field has a different hidden provenance.
 scores=np.empty((len(frame),11,4));columns=encoder.columns;positions=[columns.index(c) for c in ACTIONS]
 for state,maskbits in enumerate(common.BITS):
  public=frame.loc[:,columns].copy()
  for f,hidden in zip(ACTIONS,maskbits):
   if hidden:public[f]=np.nan
  xx,mm=encoder.transform(public);blocks=[]
  for begin in range(0,len(frame),64):
   with torch.random.fork_rng():
    torch.manual_seed(seed+begin+99173);vals=model.calculate_acquisition_scores(torch.from_numpy(xx[begin:begin+64]),torch.from_numpy(mm[begin:begin+64]));blocks.append(vals[:,positions].numpy())
  scores[:,state]=np.concatenate(blocks)
 return np.where(space.reported_missing(frame),scores,-np.inf)

def pair(task):
 source,seed,cfg,outstr,smoke=task;common.guard();torch.set_num_threads(2);out=Path(outstr)/source/f'seed-{seed}';out.mkdir(parents=True,exist_ok=True);lock=(out/'execution.lock').open('a+');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 with threadpool_limits(limits=2):
  est,guide,evaluation,_=load_source(source,cfg);train=rank_subset(pd.concat([est,guide],ignore_index=True),len(est)+len(guide),'sav-val-cf-training-order-v2');train=rank_subset(train,len(train),'sefa-internal-validation-v6');cut=int(.8*len(train));fit=train.iloc[:cut].copy();validation=train.iloc[cut:].copy();records=[]
  trials=[1,5,9] if not smoke else [1]
  for index in trials:
   config=json.loads((OFFICIAL/f'experiments/hyperparameters/configs/sefa/config{index}.json').read_text())
   if smoke:config.update(epochs=2,num_samples_train=3,num_samples_predict=4,num_samples_acquire=4,hidden_dim_predictor=20,hidden_dim_encoder=8)
   setting=dict(source=source,official=config);_,receipt=fit_classifier(fit,validation,setting,seed,out/f'trial-{index}');records.append(dict(index=index,validation_nll=receipt['best_validation_nll'],best_epoch=receipt['best_epoch'],settings=setting))
  selected=min(records,key=lambda r:(r['validation_nll'],r['index']));write(out/'selection.json',dict(status='selected_training_only',trials=records,selected=selected,held_out_evaluation_labels_used=False,objective='four-bin classification NLL, not evaluation price error or inflation'))
  (model,encoder,cuts),receipt=fit_classifier(train,train,selected['settings'],seed,out/'refit',refit_epochs=selected['best_epoch']);summaries=[]
  for backend in ['masking_suppression','robust_no_feedback']:
   old=common.PARENT/source/f'seed-{seed}';p=old/'deployment_models'/f'{backend}.joblib';price,_,_=joblib.load(p);pred,x,valid=price.predict(price_features(evaluation,FEATURES[source]));table=out/'scores.npz'
   if table.exists():scores=np.load(table)['scores']
   else:
    scores=acquisition(model,encoder,evaluation,price.space,seed);np.savez_compressed(table,scores=scores);write(out/'scores.json',dict(model_sha256=receipt['sha256'],evaluation_features_sha256=common.content(price_features(evaluation,FEATURES[source])),score_sha256=sha(table),label_inputs=False,algorithm='official SEFA class-probability weighted normalized latent-gradient norm'))
   sc=json.loads((out/'scores.json').read_text());assert sc['model_sha256']==receipt['sha256'] and sc['score_sha256']==sha(table) and sc['evaluation_features_sha256']==common.content(price_features(evaluation,FEATURES[source]))
   # Perturb a concealed mileage value: state1 public score must stay unchanged.
   if backend=='masking_suppression':
    tiny=evaluation.iloc[:4].copy();changed=tiny.copy();changed['mileage_km']=123456789.;a=acquisition(model,encoder,tiny,price.space,seed);b=acquisition(model,encoder,changed,price.space,seed);state=common.LOOKUP[1];assert np.allclose(a[:,state],b[:,state],equal_nan=True)
    write(out/'public-input-check.json',dict(status='passed',hidden_value_perturbation='mileage at concealed state',zero_label_inputs=True,finite_scores=int(np.isfinite(scores).sum())))
   head=FrozenPublicScores(scores,pred)
   for budget in cfg['budgets']:
    d=out/backend/f'budget-{round(budget*10000):04d}';d.mkdir(parents=True,exist_ok=True);cp=d/'completion.json';inputs=dict(price_model=sha(p),score_table=sha(table),evaluation=common.content(evaluation),budget=budget)
    if cp.exists():
     r=json.loads(cp.read_text());assert r['inputs']==inputs and sha(d/'outcomes.csv.gz')==r['outcomes_sha256'];summaries.append(r['summary']);continue
    rows,su=evaluate_method('sefa4bin_'+backend,price,head,'sefa',evaluation,FEATURES[source],cfg,seed,budget);audit=common.matrix_audit(pred,scores,valid,evaluation,rows,budget);su.update(dataset=source,price_backend=backend,acquisition='official_SEFA_2025_four_bin_one_query_adaptation');rows.to_csv(d/'outcomes.csv.gz',index=False);write(cp,dict(status='completed_and_corroborated',inputs=inputs,summary=su,audit=audit,outcomes_sha256=sha(d/'outcomes.csv.gz')));summaries.append(su);write(out/'progress.json',dict(completed_cells=len(summaries),expected_cells=2*len(cfg['budgets'])));print('SEFA_CELL',source,seed,backend,budget,flush=True)
  pd.DataFrame(summaries).to_csv(out/'summary.csv',index=False);write(out/'completion.json',dict(status='completed_and_corroborated',cells=len(summaries),summary_sha256=sha(out/'summary.csv')));return summaries

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=2);p.add_argument('--smoke',action='store_true');p.add_argument('--ready-only',action='store_true');a=p.parse_args();common.guard();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);lock=(out/'execution.lock').open('a+');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);cfg=copy.deepcopy(json.loads((common.PARENT/'run_manifest.json').read_text())['config'])
 used=json.loads((OFFICIAL/'USED_SOURCES.json').read_text())
 for row in used['files']:assert sha(OFFICIAL/row['path'])==row['sha256']
 if a.smoke:cfg.update(datasets=['synthetic'],seeds=[13],max_train=300,max_evaluation=100,budgets=[.1])
 tasks=[(d,s,cfg,str(out),a.smoke) for d in cfg['datasets'] for s in cfg['seeds']];manifest=dict(config=cfg,source_sha256=sha(Path(__file__)),official_sources=used,workers=a.workers,smoke_only=a.smoke,pairs=len(tasks),expected_cells=len(tasks)*2*len(cfg['budgets']),selection_trials=[1,5,9],scope='SEFA acquisition on four price bins; fixed separate price models; shared one-query budget adaptation')
 mp=out/'manifest.json'
 if mp.exists():assert json.loads(mp.read_text())==manifest
 else:write(mp,manifest)
 if a.ready_only:return
 rows=[]
 with ProcessPoolExecutor(max_workers=a.workers) as pool:
  fs={pool.submit(pair,t):t[:2] for t in tasks}
  for f in as_completed(fs):
   try:rows.extend(f.result())
   except Exception:write(out/'failure.json',dict(pair=fs[f],traceback=traceback.format_exc()));raise
   pd.DataFrame(rows).to_csv(out/'summary.csv',index=False);write(out/'progress.json',dict(completed_cells=len(rows),expected_cells=manifest['expected_cells']))
 assert len(rows)==manifest['expected_cells'];write(out/'completion.json',dict(status='completed_and_corroborated',cells=len(rows),summary_sha256=sha(out/'summary.csv'),manifest_sha256=sha(mp),smoke_only=a.smoke));common.guard()
if __name__=='__main__':main()
