"""Mechanical checks and page rendering for the current in-place revision."""
from pathlib import Path
import hashlib, json, re
import pymupdf
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / 'paper/innovation-addendum-v1.tex'
PDF = SOURCE.with_suffix('.pdf')
OUT = HERE / 'qa'; OUT.mkdir(exist_ok=True)
s = SOURCE.read_text(); log = SOURCE.with_suffix('.log').read_text()
labels = re.findall(r'\\label\{([^}]+)\}', s); refs = re.findall(r'\\(?:ref|eqref)\{([^}]+)\}', s)
bib = re.findall(r'\\bibitem\{([^}]+)\}', s)
cites = [k.strip() for group in re.findall(r'\\cite\{([^}]+)\}', s) for k in group.split(',')]
assert len(labels) == len(set(labels)) and set(refs) <= set(labels)
assert set(cites) == set(bib)
assert 'Overfull' not in log and 'undefined' not in log.lower()
assert r'\author{}' in s and r'\date{}' in s
doc = pymupdf.open(PDF); rows = []; thumbs = []; figures = []
for i, page in enumerate(doc):
    text = page.get_text(); assert '??' not in text
    spans = [v for b in page.get_text('dict')['blocks'] for line in b.get('lines', []) for v in line['spans'] if v['text'].strip()]
    outside = [v for v in spans if v['bbox'][0] < 0 or v['bbox'][1] < 0 or v['bbox'][2] > page.rect.width + .5 or v['bbox'][3] > page.rect.height + .5]
    assert not outside, (i + 1, outside)
    path = OUT / f'page-{i+1:02d}.png'; page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(path)
    figure = 'Figure 1:' in text or 'Figure 2:' in text
    if figure:
        figures.append(i + 1); output = pymupdf.open(); output.insert_pdf(doc, from_page=i, to_page=i); output.save(OUT / f'figure-page-{i+1:02d}.pdf')
    thumb = Image.open(path).convert('RGB'); thumb.thumbnail((330, 460))
    plate = Image.new('RGB', (350, 490), '#e7e7e7'); plate.paste(thumb, ((350-thumb.width)//2, 15)); ImageDraw.Draw(plate).text((12,473), f'Page {i+1}', fill='black'); thumbs.append(plate)
    rows.append({'page': i+1, 'outside_spans': 0, 'minimum_span_pt': min(v['size'] for v in spans),
                 'render_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'figure': figure})
for offset in range(0, len(thumbs), 6):
    sheet = Image.new('RGB', (1050, 980), 'white')
    for j, thumb in enumerate(thumbs[offset:offset+6]): sheet.paste(thumb, ((j%3)*350, (j//3)*490))
    sheet.save(OUT / f'contact-{offset//6+1}.png')
result = {'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(), 'pdf_sha256': hashlib.sha256(PDF.read_bytes()).hexdigest(),
          'pages': len(doc), 'references': len(bib), 'missing_refs': [], 'missing_citations': [], 'overfull': 0,
          'underfull_count': log.count('Underfull'), 'figure_pages': figures, 'page_audits': rows,
          'all_page_visual_review': 'pending', 'builtin_compilation': 'success'}
(OUT / 'render-audit.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k:v for k,v in result.items() if k != 'page_audits'}))
