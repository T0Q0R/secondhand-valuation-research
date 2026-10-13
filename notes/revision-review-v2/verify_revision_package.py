"""Verify bounded revision correspondence against source, PDF and receipts."""
from pathlib import Path
import hashlib, json, re
import pymupdf
ROOT=Path(__file__).resolve().parents[2]; H=Path(__file__).resolve().parent
source=ROOT/'paper/innovation-addendum-v1.tex'; pdf=source.with_suffix('.pdf'); s=source.read_text(); d=pymupdf.open(pdf)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
checks=[
 ('A',6,'What is tested in the learned-model experiment.'),
 ('A',16,'Recovery failures in the learned four-field class'),
 ('B',12,'Post-hoc simultaneous sensitivity.'),
 ('C',20,'Full-validation evaluation coverage'),
 ('D',4,'Inflation alone admits a degenerate solution.'),
 ('E',20,'Continuous effects and decision-threshold sensitivity'),
 ('F',11,'Audit dependency and independent state coverage.'),
 ('G',17,'Strong controls and the original candidate comparison'),
 ('H',8,'History dependence and a final-record alternative'),
 ('H',20,'Positive costs change the conditional feedback ranking'),
]
for key,page,phrase in checks:
 assert phrase in s, (key,'source',phrase)
 assert phrase in d[page-1].get_text(), (key,'page',page,phrase)
response=(H/'REVIEW_RESPONSE.zh.md').read_text()
assert set(re.findall(r'^## ([A-I])：',response,re.M))==set('ABCDEFGHI')
quotes=[]
for start, end in [
 ('A constant-quote model','For the unilateral audit,'),
 ('Equation~\\eqref{eq:frontier} applies','\\subsection{Compact implementability'),
 ('The historical outcome audit is a','A separate bit-mask oracle'),
 ('The inherited 10\\% inflation-reduction','At a 5\\% honest-error allowance'),
 ('JUCars and MUCars retain adverse mean inflation directions','\\subsection{Full-validation evaluation coverage}'),
]:
 a=s.index(start);b=s.index(end,a);q=s[a:b].strip();assert len(q)>40;quotes.append(q)
(H/'response-excerpts.tex').write_text('% Internal verbatim correspondence checks; not a replacement manuscript or a submitted letter.\n'+ '\n\n'.join('\\RevisedExcerpt{'+q+'}' for q in quotes)+'\n')
qa=json.loads((H/'qa/render-audit.json').read_text())
assert qa['source_sha256']==sha(source) and qa['pdf_sha256']==sha(pdf) and qa['pages']==30
assert qa['overfull']==0 and not qa['missing_refs'] and qa['all_page_visual_review'].startswith('completed')
for n in qa['figure_pages']:
 g=json.loads((H/f'qa/figure-page-{n:02d}.corrected-geometry-audit.json').read_text()); assert g['summary']['fail']==g['summary']['warn']==0
assert json.loads((H/'statistics/completion.json').read_text())['results']['core36']['core_feedback_upper_below_zero']==31
assert json.loads((ROOT/'outputs/review-expanded-primary-v2-analysis/jucars/completion.json').read_text())['cells']==240
r={'status':'passed_for_declared_checks','source_sha256':sha(source),'pdf_sha256':sha(pdf),
 'comment_count':9,'page_anchors':checks,'verbatim_excerpt_count':len(quotes),
 'scope':'mechanical anchors, declared receipts and layout; no independent peer review or submission readiness certification',
 'pending':['full MUCars evaluation and corroboration','public-release and actual author decisions','external-machine full training reproduction']}
(H/'qa/correspondence-audit.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
