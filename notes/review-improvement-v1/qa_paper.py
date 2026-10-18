"""Check evidence bindings, preserved scientific blocks, typography and PDF pages.
Visual review is a separate explicit step after contact/detail rendering.
"""
from pathlib import Path
import argparse,hashlib,json,re,datetime
import pandas as pd
import pymupdf as fitz
ROOT=Path(__file__).resolve().parents[2];N=Path(__file__).parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    a=argparse.ArgumentParser();a.add_argument('--interim',action='store_true');args=a.parse_args()
    source=ROOT/'paper/innovation-addendum-v1.tex';s=source.read_text()
    old=(N/'before-prose-revision.tex').read_text()
    # The method explanation is revised; formal theorem statements and proofs stay intact.
    for kind in ['proposition','proof']:
        pattern=r'\\begin\{'+kind+r'\}.*?\\end\{'+kind+r'\}'
        assert re.findall(pattern,s,re.S)==re.findall(pattern,old,re.S)
    oldfigures=re.findall(r'\\begin\{figure\}.*?\\end\{figure\}',old,re.S)
    newfigures=re.findall(r'\\begin\{figure\}.*?\\end\{figure\}',s,re.S)
    supplement=(ROOT/'paper/review-supplement-v1/main.tex').read_text()
    migrated=re.findall(r'\\begin\{figure\}.*?\\end\{figure\}',(N/'legacy-extended-appendix.tex').read_text(),re.S)
    assert oldfigures==newfigures+migrated and len(oldfigures)==9
    assert sum(len(re.findall(r'\\label\{fig:',v)) for v in newfigures+migrated)==11
    assert (N/'legacy-extended-appendix.tex').read_text() in supplement
    for label in ['tab:rpl_primary','tab:rpl_crossing','tab:recent_primary','tab:final_record_pilot']:
        def get(text):
            return next(v.group() for v in re.finditer(r'\\begin\{(table|longtable)\}.*?\\end\{\1\}',text,re.S) if r'\label{'+label+'}' in v.group())
        assert get(s)==get(old)
    assert r'\documentclass[11pt]' in s and r'\usepackage[margin=1in]' in s
    assert 'two three-epoch' not in s and 'initial epochs' not in s
    assert 'tab:ten_seed_mechanism' in s
    e=pd.read_csv(N/'mechanisms/edge-source-means.csv')
    for source_name in ['synthetic','jucars','mucars']:
        q=e[e.source==source_name].set_index('path_weight')
        row=f'{100*q.loc[0,"gain_violating_rate"]:.2f}/{100*q.loc[1,"gain_violating_rate"]:.2f} & {format(q.loc[0,"positive_increment_mean"],'.6f').lstrip('0')}/{format(q.loc[1,"positive_increment_mean"],'.6f').lstrip('0')}'
        assert row in s
    if not args.interim:
        assert r'\label{tab:stronger_gap}' in s
        assert json.loads((N/'gap/verification.json').read_text())['status']=='all_candidates_and_selection_checked'
    qa=N/('qa-interim' if args.interim else 'qa');qa.mkdir(exist_ok=True)
    reports=[]
    for name,path in [('main',source),('supplement',ROOT/'paper/review-supplement-v1/main.tex')]:
        text=path.read_text();log=path.with_suffix('.log').read_text();pdf=path.with_suffix('.pdf');doc=fitz.open(pdf)
        assert 'Overfull' not in log
        assert not re.search(r'undefined references|Citation.*undefined',log)
        labels=re.findall(r'\\label\{([^}]+)\}',text);refs=re.findall(r'\\(?:ref|eqref|pageref)\{([^}]+)\}',text)
        assert len(labels)==len(set(labels)) and set(refs)<=set(labels)
        names=['Yuchen Tang','Fengqin You','Junxiang Gu','Xin Pang'];title=doc[0].get_text()
        assert [title.index(v) for v in names]==sorted(title.index(v) for v in names)
        assert 'irisyou@njust.edu.cn' in title
        if not args.interim:assert 'still running' not in ' '.join(p.get_text() for p in doc)
        page_info=[];details={1}
        for i,page in enumerate(doc):
            ptext=page.get_text();(qa/f'{name}-{i+1:02d}.txt').write_text(ptext)
            assert '\ufffd' not in ptext
            if any(v in ptext for v in ['15.79/5.03','98.3%','61.7%','Table S','stronger-gap','corresponding','Version and evidence']):details.add(i+1)
            page_info.append(dict(page=i+1,opening=ptext[:100]))
        for start in range(0,len(doc),12):
            board=fitz.open();page=board.new_page(width=1000,height=1050)
            for k in range(start,min(start+12,len(doc))):
                rect=fitz.Rect((k-start)%4*250,(k-start)//4*350,(k-start)%4*250+250,(k-start)//4*350+330)
                page.show_pdf_page(rect,doc,k);page.insert_text((rect.x0+8,rect.y1+12),str(k+1),fontsize=10)
            page.get_pixmap(matrix=fitz.Matrix(1.1,1.1)).save(qa/f'{name}-contact-{start+1:02d}.png')
        for page in sorted(details):doc[page-1].get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(qa/f'{name}-detail-{page:02d}.png')
        reports.append(dict(name=name,source_sha256=sha(path),pdf_sha256=sha(pdf),pages=len(doc),
             overfull=0,underfull_warnings=log.count('Underfull'),labels_unique=True,refs_defined=True,
             author_order_verified=names,page_info=page_info,detail_pages=sorted(details)))
    citations={k for group in re.findall(r'\\cite\{([^}]+)\}',s) for k in group.split(',')}
    assert citations==set(re.findall(r'\\bibitem\{([^}]+)\}',s))
    report=dict(status='interim_source_and_numeric_checks_passed_visual_review_pending' if args.interim else 'source_and_numeric_checks_passed_visual_review_pending',
       timestamp=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds'),
       documents=reports,all_11_previous_figure_blocks_preserved=True,formal_propositions_and_proofs_preserved=True,
       previous_main_evidence_tables_preserved=True,reference_count=len(citations),visual_review='pending',
       new_gap_results_integrated=not args.interim)
    (N/('qa-interim.json' if args.interim else 'qa.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='documents'},indent=2))
    print([(r['name'],r['pages']) for r in reports])

if __name__=='__main__':main()
