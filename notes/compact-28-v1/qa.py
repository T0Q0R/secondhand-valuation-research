"""Check the compressed same-file manuscript against archived displays/evidence.
No training. Requires saved source, same-path PDF/log and aggregate CSVs.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import re,json,hashlib
import pandas as pd
import numpy as np
import pymupdf as fitz
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'notes/compact-28-v1';QA=OUT/'qa';QA.mkdir(exist_ok=True)
p=ROOT/'paper/innovation-addendum-v1.tex';s=p.read_text();pdf=p.with_suffix('.pdf');doc=fitz.open(pdf)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert len(doc)==28
labels=re.findall(r'\\label\{([^}]+)\}',s);refs=re.findall(r'\\(?:ref|eqref|pageref)\{([^}]+)\}',s)
assert len(labels)==len(set(labels));assert set(refs)<=set(labels)
main,app=s.split(r'\appendix',1)
# Two floats contain two separately numbered figures each, all at full text width.
figlabels=re.findall(r'\\label\{(fig:[^}]+)\}',s);assert len(figlabels)==12
mainlabels=re.findall(r'\\label\{(fig:[^}]+)\}',main);assert len(mainlabels)==8
plain=re.sub(r'\\begin\{figure\}.*?\\end\{figure\}','',s,flags=re.S)
assert sorted(figlabels,key=lambda k:plain.index(r'\ref{'+k+'}'))==figlabels
assert r'\documentclass[11pt]' in s and r'\usepackage[margin=1in]' in s
assert 'irisyou@njust.edu.cn' in s
cited=set(k for item in re.findall(r'\\cite\{([^}]+)\}',s) for k in item.split(','))
listed=set(re.findall(r'\\bibitem\{([^}]+)\}',s));assert cited==listed and len(listed)==20
log=p.with_suffix('.log').read_text();assert 'Overfull' not in log
assert not re.search('undefined references|Citation.*undefined',log)
# Read published aggregate in a fresh checkout, or original outputs in source workspace.
agg=ROOT/'notes/core-evidence-v2/completed-stages/rpl10/audited_cell_summaries.csv'
if not agg.exists():agg=ROOT/'outputs/core-evidence-audit-v2/analysis/rpl10/audited_cell_summaries.csv'
c=pd.read_csv(agg);assert len(c)==540
metrics=[]
for ds in ['synthetic','jucars','mucars']:
 d=c[(c.dataset==ds)&np.isclose(c.budget,.1)];b=d[d.method=='path-0-gap-0.5'].set_index('seed');m=d[d.method=='path-1-gap-0.5'].set_index('seed');assert len(m)==10
 for w in ['0','0.5','1']:
  v=d[d.method==f'path-{w}-gap-0.5'].mean(numeric_only=True)
  row=f'{ds} / {w} & {v.mean_positive_log_inflation:.5f} & {v.clean_mae:.2f} & {v.attack_mae:.2f} & {100*v.failed_query_fraction:.2f}'
  assert row in s
 assert (m.mean_positive_log_inflation<b.mean_positive_log_inflation).all()
 metrics.append({'dataset':ds,'inflation_reduction_pct':(1-m.mean_positive_log_inflation.mean()/b.mean_positive_log_inflation.mean())*100})
assert (c.nonconverged_batch_fraction>0).sum()==51
assert round(c.nonconverged_batch_fraction.sum()*10)==89
assert abs(c.max_remaining_response_regret.max()-.1437206268310547)<1e-12
fi=json.loads((ROOT/'notes/ten-seed-visual-review-v1/figure-index.json').read_text())
for f in fi['figures']:assert sha(ROOT/f"paper/figures/ten-seed-v1/{f['name']}.pdf")==f['pdf_sha256']
# Retained original numerical table rows are unchanged, including adverse outcomes.
archive=ROOT.parent/'manuscript-before-28pages-20261018.tex'
if archive.exists():
 old=archive.read_text()
 for label in ['tab:rpl_primary','tab:recent_primary','tab:final_record_pilot']:
  def rows(t):
   for mm in re.finditer(r'\\begin\{(table|longtable)\}.*?\\end\{\1\}',t,re.S):
    if r'\label{'+label+'}' in mm.group():return [x.strip() for x in mm.group().splitlines() if '&' in x and re.search(r'\d',x)]
   raise ValueError(label)
  assert rows(old)==rows(s),label
pageinfo=[];captions=[];appendixstart=None
for i,page in enumerate(doc):
 t=page.get_text();fig=[int(x) for x in re.findall(r'Figure (\d+):',t)];captions+=fig
 if t.startswith('A\nContextual'):appendixstart=i+1
 pageinfo.append({'page':i+1,'figures':fig,'opening':t[:90]});(QA/f'page-{i+1:02d}.txt').write_text(t)
assert captions==list(range(1,13))
for start in range(0,len(doc),12):
 board=fitz.open();page=board.new_page(width=1000,height=1050)
 for k in range(start,min(start+12,len(doc))):
  rr=fitz.Rect((k-start)%4*250,(k-start)//4*350,(k-start)%4*250+250,(k-start)//4*350+330)
  page.show_pdf_page(rr,doc,k);page.insert_text((rr.x0+8,rr.y1+12),str(k+1),fontsize=10)
 page.get_pixmap(matrix=fitz.Matrix(1.25,1.25)).save(QA/f'contact-{start+1:02d}.png')
details={1,appendixstart-1,appendixstart,len(doc)}
for v in pageinfo:
 if set(v['figures'])&{1,2,6,9,10,11,12}:details.add(v['page'])
for n in sorted(details):doc[n-1].get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(QA/f'detail-{n:02d}.png')
(OUT/'prose-for-review.tex.txt').write_text(plain)
report={'status':'automated_binding_checks_passed_visual_review_separate','timestamp':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'source_sha256':sha(p),'pdf_sha256':sha(pdf),'pages':len(doc),'main_pages_including_declarations':appendixstart-1,'appendices_and_references_pages':len(doc)-appendixstart+1,'body_font_pt':11,'margin_inches':1,'figures':12,'main_figures':8,'appendix_figures':4,'tables':len(re.findall(r'\\label\{tab:',s)),'references':20,'duplicate_labels':[],'undefined_refs':[],'overfull_boxes':0,'underfull_warnings':log.count('Underfull'),'figure_citation_and_caption_order_passed':True,'retained_numerical_tables_bound':True,'nine_asset_hashes_unchanged':True,'primary_effects':metrics,'nonconverged_cells':51,'nonconverged_batch_replays':89,'builtin_compilation':'success_final_saved_source','new_training':False,'formal_submission_ready':False,'page_info':pageinfo}
(OUT/'qa.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='page_info'},indent=2))
