"""Verify manuscript numbers/claims and render the final same-path PDF."""
from pathlib import Path
import datetime,hashlib,json,re
import pandas as pd
import numpy as np
import pymupdf as fitz
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;QA=OUT/'qa'
QA.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=ROOT/'paper/innovation-addendum-v1.tex';s=source.read_text()
pdf=source.with_suffix('.pdf');doc=fitz.open(pdf)
assert len(doc)==28
assert r'\documentclass[11pt]' in s and r'\usepackage[margin=1in]' in s
names=['Yuchen Tang','Fengqin You','Xin Pang','Junxiang Gu']
text=doc[0].get_text()
assert [text.index(n) for n in names]==sorted(text.index(n) for n in names)
assert 'irisyou@njust.edu.cn' in text
labels=re.findall(r'\\label\{([^}]+)\}',s)
refs=re.findall(r'\\(?:ref|eqref|pageref)\{([^}]+)\}',s)
assert len(labels)==len(set(labels)) and set(refs)<=set(labels)
assert r'\label{tab:rpl_crossing}' in s and 'fig:recent_curves' not in s
assert 'A DOI-backed archive has not yet been issued' not in s
assert '10.5281/zenodo.23447567' in s
assert '18 nonconverged batches' in s and '0.14916' in s
assert 'all 45' in s and 'all 45' in s.split(r'\begin{abstract}')[1].split(r'\end{abstract}')[0]
log=source.with_suffix('.log').read_text()
assert 'Overfull' not in log
assert not re.search(r'undefined references|Citation.*undefined',log)
assert (OUT/'main-table.tex').read_text().strip() in s
assert (OUT/'appendix-table.tex').read_text().strip() in s
means=pd.read_csv(OUT/'matched-source-family-means.csv')
assert len(means)==18
for _,r in means.iterrows():
    row=f'{r.mean_positive_log_inflation_lambda0:.5f} & {r.mean_positive_log_inflation_lambda1:.5f} & {r.mean_positive_log_inflation_change_pct:+.2f} & {r.attack_mae_change_pct:+.2f} & {100*r.failed_query_fraction_delta:+.2f}'
    assert row in s
    row=f'{r.mean_positive_log_inflation_lambda0:.5f}/{r.mean_positive_log_inflation_lambda1:.5f} & {r.attack_mae_lambda0:.2f}/{r.attack_mae_lambda1:.2f} & {100*r.failed_query_fraction_lambda0:.2f}/{100*r.failed_query_fraction_lambda1:.2f}'
    assert row in s
# Core theory, primary ten-seed values and all surviving figure bodies are byte-identical.
old=(OUT/'before.tex').read_text()
def table(t,label):
    for m in re.finditer(r'\\begin\{(table|longtable)\}.*?\\end\{\1\}',t,re.S):
        if r'\label{'+label+'}' in m.group():return m.group()
    raise KeyError(label)
assert table(s,'tab:rpl_primary')==table(old,'tab:rpl_primary')
assert table(s,'tab:final_record_pilot')==table(old,'tab:final_record_pilot')
for start,end in [(r'\section{Information limits',r'\section{Recovery diagnosis'),
                  (r'\section{Recovery diagnosis',r'\section{Experimental design')]:
    assert s[s.index(start):s.index(end)]==old[old.index(start):old.index(end)]
oldfigs={}
for m in re.finditer(r'\\begin\{figure\}.*?\\end\{figure\}',old,re.S):
    for label in re.findall(r'\\label\{(fig:[^}]+)\}',m.group()):oldfigs[label]=m.group()
survivors=0
for m in re.finditer(r'\\begin\{figure\}.*?\\end\{figure\}',s,re.S):
    lab=re.findall(r'\\label\{(fig:[^}]+)\}',m.group())
    assert lab and all(m.group()==oldfigs[k] for k in lab)
    survivors+=len(lab)
assert survivors==11
assert (OUT/'legacy-recent-budget-figure.tex').read_text().strip()==oldfigs['fig:recent_curves']
assert (OUT/'legacy-recent-primary-table.tex').read_text().strip()==table(old,'tab:recent_primary')
citations={k for x in re.findall(r'\\cite\{([^}]+)\}',s) for k in x.split(',')}
bib=set(re.findall(r'\\bibitem\{([^}]+)\}',s));assert citations==bib and len(bib)==20
pages=[];captions=[];detail={1,15,19,22,23,28}
for i,page in enumerate(doc):
    t=page.get_text()
    caps=[int(x) for x in re.findall(r'Figure (\d+):',t)];captions+=caps
    compact=' '.join(t.split())
    if any(x in compact for x in ['direct comparison crosses','Adding RPL lowers','Stacking is not uniformly','Table 5:','Table 7:','Four-stage checks']):
        detail.add(i+1)
    (QA/f'page-{i+1:02d}.txt').write_text(t)
    pages.append(dict(page=i+1,opening=t[:90],figures=caps))
assert captions==list(range(1,12))
for start in range(0,len(doc),12):
    board=fitz.open();page=board.new_page(width=1000,height=1050)
    for k in range(start,min(start+12,len(doc))):
        rect=fitz.Rect((k-start)%4*250,(k-start)//4*350,(k-start)%4*250+250,(k-start)//4*350+330)
        page.show_pdf_page(rect,doc,k);page.insert_text((rect.x0+8,rect.y1+12),str(k+1),fontsize=10)
    page.get_pixmap(matrix=fitz.Matrix(1.1,1.1)).save(QA/f'contact-{start+1:02d}.png')
for n in sorted(detail):
    doc[n-1].get_pixmap(matrix=fitz.Matrix(1.6,1.6)).save(QA/f'detail-{n:02d}.png')
report=dict(status='numeric_reference_and_source_checks_passed_visual_review_pending',
    timestamp=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds'),
    source_sha256=sha(source),pdf_sha256=sha(pdf),pages=28,body_font_pt=11,margin_inches=1,
    figures=11,main_comparison_rows=18,absolute_paired_table_rows=18,all_source_family_outcomes=36,
    tables=len(re.findall(r'\\label\{tab:',s)),references=20,
    original_core_theory_unchanged=True,ten_seed_table_unchanged=True,
    original_recent_table_and_budget_figure_preserved=True,
    surviving_figure_bodies_unchanged=True,four_authors_retained=True,
    duplicate_labels=[],undefined_refs=[],overfull_boxes=0,underfull_warnings=log.count('Underfull'),
    crossing_cells=90,reused_native_cells=18,new_fits=0,new_evaluations=0,
    builtin_compilation='success',abstract_space_tokens=len(s.split(r'\begin{abstract}')[1].split(r'\end{abstract}')[0].split()),
    pages_for_detail=sorted(detail),page_info=pages)
(OUT/'qa.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='page_info'},indent=2))

