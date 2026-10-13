"""Resolve grouped XeTeX text-trace bounding boxes without weakening tolerances.

The standard collision audit unions an entire PDF text trace into its first
matched line. XeTeX can place many independently positioned labels in one
trace, producing a page-size false collision box. Here rendered line/glyph
boxes replace only that extraction step; the same stroke geometry and default
collision thresholds are retained. Original failed reports are preserved.
"""
from pathlib import Path
import sys,json,hashlib
import pymupdf
sys.path.insert(0,'/Users/tqr/.codex/skills/nature-figure/scripts')
import audit_figure_collisions as checker
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'notes/manuscript-integration/qa'
# Ensure the chosen default detector still rejects actual collisions.
probe=checker.PageGeometry(page=1,bbox=(0,0,100,100),texts=[checker.TextBox(0,'a',(10,10,30,20)),checker.TextBox(1,'b',(15,10,35,20))])
assert checker.audit_geometries([probe])['summary']['fail']>0
probe.texts=[checker.TextBox(0,'a',(10,10,30,20)),checker.TextBox(1,'b',(40,10,60,20))]
assert checker.audit_geometries([probe])['summary']['fail']==0
probe.strokes=[checker.StrokePath(0,(10,15,30,15),1.,(((10,15),(30,15)),))]
assert checker.audit_geometries([probe])['summary']['fail']>0
for number in [12,13]:
 path=OUT/f'figure-page-{number:02d}.pdf'
 geometry=checker.extract_pdf_geometry(path);doc=pymupdf.open(path)
 for g,page in zip(geometry,doc):
  g.texts=[];g.traces=[]
  for b in page.get_text('dict')['blocks']:
   for line in b.get('lines',[]):
    spans=[s for s in line['spans'] if s['text'].strip()]
    if spans:
     bbox=checker.union_rects(s['bbox'] for s in spans)
     g.texts.append(checker.TextBox(len(g.texts),''.join(s['text'] for s in spans),bbox))
  for b in page.get_text('rawdict')['blocks']:
   for line in b.get('lines',[]):
    for span in line['spans']:
     for c in span['chars']:
      if c['c'].strip():g.traces.append(checker.TraceBox(len(g.traces),c['c'],tuple(c['bbox'])))
 result=checker.audit_geometries(geometry)
 result['extraction']='rendered line boxes and per-glyph clipping; grouped text trace union avoided'
 result['default_thresholds_unchanged']=True
 result['original_pdf_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
 result['detector_sha256']=hashlib.sha256(Path(checker.__file__).read_bytes()).hexdigest()
 result['real_collision_probes_rejected']=True
 (OUT/f'figure-page-{number:02d}.corrected-geometry-audit.json').write_text(json.dumps(result,indent=2)+'\n')
 print(number,result['verdict'],result['summary'])
 assert result['summary']['fail']==result['summary']['warn']==0
