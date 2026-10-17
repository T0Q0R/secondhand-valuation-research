"""Read-only scientific/manuscript checks and same-PDF contact sheets.
Uses existing aggregate evidence. Does not retrain or alter manuscript/figures.
Run from a checkout with pandas, numpy and PyMuPDF; source/log/PDF required.
"""
from pathlib import Path
import hashlib,json,re
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import pymupdf as fitz
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'notes/ten-seed-paper-v1'; QA=OUT/'qa';QA.mkdir(exist_ok=True)
for pat in ('page-*.txt','detail-*.png','contact-*.png'):
    for p in QA.glob(pat): p.unlink()
sourcepath=ROOT/'paper/innovation-addendum-v1.tex';source=sourcepath.read_text()
pdfpath=sourcepath.with_suffix('.pdf');doc=fitz.open(pdfpath)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
labels=re.findall(r'\\label\{([^}]+)\}',source)
refs=re.findall(r'\\(?:ref|eqref|pageref)\{([^}]+)\}',source)
assert len(labels)==len(set(labels));assert set(refs)<=set(labels)
main,appendix=source.split(r'\appendix',1)
assert main.count(r'\begin{figure}')==8
assert appendix.count(r'\begin{figure}')==9
# Figure order is checked against first text citation, excluding display captions.
mainprose=re.sub(r'\\begin\{figure\}.*?\\end\{figure\}','',main,flags=re.S)
figlabels=re.findall(r'\\label\{(fig:[^}]+)\}',main)
firstcites=sorted(figlabels,key=lambda k: mainprose.index(r'\ref{'+k+'}'))
assert figlabels==firstcites
abstract=re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}',source,re.S).group(1)
assert 150<=len(re.findall(r'\b\w+\b',abstract))<=250
# Nine new figure PDFs are the frozen, previously reviewed assets.
fi=json.loads((ROOT/'notes/ten-seed-visual-review-v1/figure-index.json').read_text())
for f in fi['figures']:
    p=ROOT/'paper/figures/ten-seed-v1'/f"{f['name']}.pdf"
    assert sha(p)==f['pdf_sha256']
# Publication checkout stores the audited aggregate; source workspace uses outputs.
evidence=ROOT/'notes/core-evidence-v2/completed-stages/rpl10/audited_cell_summaries.csv'
if not evidence.exists(): evidence=ROOT/'outputs/core-evidence-audit-v2/analysis/rpl10/audited_cell_summaries.csv'
c=pd.read_csv(evidence);assert len(c)==540
expected=pd.read_csv(ROOT/'notes/ten-seed-visual-review-v1/primary_effects.csv')
table=re.search(r'\\label\{tab:rpl_primary\}(.*?)\\end\{table\}',source,re.S).group(1)
checks=[]
for row in expected.to_dict('records'):
    dataset=row['dataset'];d=c[(c.dataset==dataset)&np.isclose(c.budget,.1)]
    b=d[d.method=='path-0-gap-0.5'].set_index('seed');m=d[d.method=='path-1-gap-0.5'].set_index('seed')
    assert len(b)==len(m)==10 and b.index.equals(m.index)
    gain=(1-m.mean_positive_log_inflation.mean()/b.mean_positive_log_inflation.mean())*100
    assert abs(gain-row['inflation_reduction_ratio_of_means_pct'])<1e-10
    assert (m.mean_positive_log_inflation<b.mean_positive_log_inflation).all()
    for weight in ('0','0.5','1'):
        v=d[d.method==f'path-{weight}-gap-0.5'].mean(numeric_only=True)
        line=f"{dataset} / {weight} & {v.mean_positive_log_inflation:.5f} & {v.clean_mae:.2f} & {v.attack_mae:.2f} & {100*v.failed_query_fraction:.2f}"
        assert line in table, line
    checks.append({'dataset':dataset,'endpoint_inflation_improvement_pct':gain,'favorable_seeds':10})
assert int((c.nonconverged_batch_fraction>0).sum())==51
assert round(float(c.nonconverged_batch_fraction.sum())*10)==89
assert abs(float(c.max_remaining_response_regret.max())-.1437206268310547)<1e-12
log=sourcepath.with_suffix('.log').read_text()
assert 'Overfull' not in log
assert 'undefined references' not in log and 'Citation' not in log
pageinfo=[];captions=[];appendixstart=None
for i,page in enumerate(doc):
    t=page.get_text();(QA/f'page-{i+1:02d}.txt').write_text(t)
    if t.startswith('A\nContextual'):appendixstart=i+1
    fig=re.findall(r'Figure (\d+):',t);captions += [int(x) for x in fig]
    pageinfo.append({'page':i+1,'figure_captions':[int(x) for x in fig], 'opening':t[:80]})
assert captions==list(range(1,18)),captions
assert appendixstart
for start in range(0,len(doc),12):
    canvas=fitz.open();cp=canvas.new_page(width=1000,height=1050)
    for k in range(start,min(start+12,len(doc))):
        rect=fitz.Rect((k-start)%4*250,(k-start)//4*350,(k-start)%4*250+250,(k-start)//4*350+330)
        cp.show_pdf_page(rect,doc,k);cp.insert_text((rect.x0+8,rect.y1+12),str(k+1),fontsize=10)
    cp.get_pixmap(matrix=fitz.Matrix(1.25,1.25)).save(QA/f'contact-{start+1:02d}.png')
# Select caption pages, manuscript boundary and author page for full-size QA.
details={1,appendixstart-1,appendixstart}
for p in pageinfo:
    if set(p['figure_captions']) & {1,2,5,11,12}:details.add(p['page'])
for n in sorted(details):doc[n-1].get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(QA/f'detail-{n:02d}.png')
prose=re.sub(r'\\begin\{figure\}.*?\\end\{figure\}','',source,flags=re.S)
(OUT/'prose-for-review.txt').write_text(prose)
report={'status':'computational_checks_passed_visual_review_separate',
 'timestamp':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 'source_sha256':sha(sourcepath),'pdf_sha256':sha(pdfpath),'audited_aggregate_sha256':sha(evidence),
 'pages':len(doc),'main_pages_including_declarations':appendixstart-1,
 'appendix_and_references_pages':len(doc)-appendixstart+1,
 'abstract_words':len(re.findall(r'\b\w+\b',abstract)),
 'figures':17,'main_figures':8,'appendix_figures':9,
 'tables':len(re.findall(r'\\label\{tab:',source)),
 'references':source.count(r'\bibitem'),
 'figure_first_citation_order_passed':True,'figure_caption_order_passed':True,
 'unique_labels':True,'undefined_refs':[],'overfull_boxes':0,
 'underfull_warnings':len(re.findall('Underfull',log)),
 'main_table_nine_rows_verified_against_540_cell_aggregate':True,
 'primary_effects':checks,'nonconverged_cells':51,'nonconverged_batch_replays':89,
 'worst_remaining_regret':float(c.max_remaining_response_regret.max()),
 'figure_asset_bindings_verified':9,'builtin_compilation':'success_2026-10-17_final_source',
 'new_training':False,'formal_submission_ready':False,'page_info':pageinfo}
(QA/'pdf-index.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='page_info'},indent=2))
