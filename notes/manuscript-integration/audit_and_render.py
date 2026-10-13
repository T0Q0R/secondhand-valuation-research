"""Inspect the exported current manuscript and preserve page-level QA evidence."""
from pathlib import Path
import re,json,hashlib
import pymupdf
from PIL import Image,ImageOps,ImageDraw
ROOT=Path(__file__).resolve().parents[2]
source=ROOT/'paper/innovation-addendum-v1.tex'
pdf=source.with_suffix('.pdf');doc=pymupdf.open(pdf)
out=ROOT/'notes/manuscript-integration/qa';out.mkdir(exist_ok=True)
s=source.read_text();log=source.with_suffix('.log').read_text()
labels=re.findall(r'\\label\{([^}]+)\}',s)
refs=re.findall(r'\\(?:ref|eqref)\{([^}]+)\}',s)
bib=re.findall(r'\\bibitem\{([^}]+)\}',s)
cites=[k.strip() for group in re.findall(r'\\cite\{([^}]+)\}',s) for k in group.split(',')]
assert len(labels)==len(set(labels)) and set(refs)<=set(labels)
assert set(cites)==set(bib)
assert '\\author{}' in s and '\\date{}' in s
assert 'Overfull' not in log and 'undefined' not in log.lower()
rows=[];thumbs=[];figure_pages=[]
for i,page in enumerate(doc):
 text=page.get_text();assert '??' not in text
 spans=[v for b in page.get_text('dict')['blocks'] if 'lines' in b for line in b['lines'] for v in line['spans'] if v['text'].strip()]
 outside=[{'text':v['text'],'bbox':v['bbox']} for v in spans if v['bbox'][0]<0 or v['bbox'][1]<0 or v['bbox'][2]>page.rect.width+.5 or v['bbox'][3]>page.rect.height+.5]
 assert not outside,(i+1,outside)
 page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(out/f'page-{i+1:02d}.png')
 thumb=Image.open(out/f'page-{i+1:02d}.png').convert('RGB');thumb.thumbnail((330,460))
 plate=Image.new('RGB',(350,490),'#e7e7e7');plate.paste(thumb,((350-thumb.width)//2,15));ImageDraw.Draw(plate).text((12,473),f'Page {i+1}',fill='black');thumbs.append(plate)
 is_figure='Figure 1:' in text or 'Figure 2:' in text
 if is_figure:
  figure_pages.append(i+1)
  dest=pymupdf.open();dest.insert_pdf(doc,from_page=i,to_page=i);dest.save(out/f'figure-page-{i+1:02d}.pdf')
 rows.append({'page':i+1,'text_characters':len(text),'minimum_span_pt':min(v['size'] for v in spans),'outside_page_spans':len(outside),'drawings':len(page.get_drawings()),'contains_main_figure':is_figure})
for offset in range(0,len(thumbs),6):
 subset=thumbs[offset:offset+6];sheet=Image.new('RGB',(1050,980),'white')
 for j,thumb in enumerate(subset):sheet.paste(thumb,((j%3)*350,(j//3)*490))
 sheet.save(out/f'contact-{offset//6+1}.png')
result={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'pages':len(doc),'page_audits':rows,'figure_pages':figure_pages,'missing_citations':[],'uncited_references':[],'duplicate_labels':[],'missing_refs':[],'undefined_reference_markers':0,'overfull_boxes':0,'underfull_log_count':log.count('Underfull'),'all_page_visual_review':'pending','author_affiliation_omitted':True}
(out/'render-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='page_audits'}))
