"""Adapt checked PDF geometry for the existing standalone editor, including rotated labels.
Original PDF/SVG/source tables remain authoritative. Alpha is flattened onto white;
vector geometry is unchanged, overlapping uncertainty fills use white-backdrop colors.
"""
from pathlib import Path
import sys,math,json
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'notes/results-visual-v5'))
import inline_vectors as old
# This module is loaded as __main__, so the imported name resolves to the old adapter.
import pymupdf as fitz

def convert(name):
 path=ROOT/f'paper/figures/postcompute-v1/{name}.pdf';page=fitz.open(path)[0];w,h=page.rect.width,page.rect.height
 out=[r'\begingroup',r'\setlength{\unitlength}{1bp}',rf'\begin{{picture}}({w:.4f},{h:.4f})']
 for d in page.get_drawings():
  col=d.get('color') or (0,0,0);fill=d.get('fill');opacity=d.get('stroke_opacity');opacity=1 if opacity is None else opacity;col=tuple(1-opacity+opacity*v for v in col)
  ops=['q',f'{(d.get("width") or .5):.4f} w',' '.join(f'{v:.4f}' for v in col)+' RG']
  if fill:
   alpha=d.get('fill_opacity');alpha=1 if alpha is None else alpha;fill=tuple(1-alpha+alpha*v for v in fill);ops.append(' '.join(f'{v:.4f}' for v in fill)+' rg')
  ops.append((d.get('dashes') or '[] 0')+' d');previous=None
  for item in d['items']:
   kind=item[0]
   if kind in ['l','c']:
    if previous!=item[1]:ops.append(old.point(item[1],h)+' m')
    ops.append((' '.join(old.point(v,h) for v in item[2:])+' c') if kind=='c' else old.point(item[2],h)+' l');previous=item[-1]
   elif kind=='re':
    r=item[1];ops.append(f'{r.x0:.4f} {h-r.y1:.4f} {r.width:.4f} {r.height:.4f} re');previous=None
   elif kind=='qu':
    q=item[1];ops.append(old.point(q.ul,h)+' m');ops.extend(old.point(p,h)+' l' for p in [q.ur,q.lr,q.ll]);ops.append('h');previous=None
   else:raise ValueError(kind)
  if d.get('closePath'):ops.append('h')
  op='B' if d['type']=='fs' else ('f' if d['type']=='f' else 'S');ops += [op,'Q'];out.append(r'\put(0,0){\AuditVector{'+' '.join(ops)+'}}')
 for block in page.get_text('dict')['blocks']:
  for line in block.get('lines',[]):
   angle=-math.degrees(math.atan2(line['dir'][1],line['dir'][0]));assert round(angle) in [0,90]
   for span in line['spans']:
    x,y=span['origin'];size=span['size'];text=old.escape(span['text']);rgb=span['color'];color=','.join(f'{((rgb>>shift)&255)/255:.4f}' for shift in [16,8,0]);body=r'\color[rgb]{'+color+'}'+(r'\bfseries ' if 'Bold' in span['font'] else '')+text
    box=r'\makebox(0,0)[bl]{\fontsize{'+f'{size:.4f}'+'}{'+f'{size*1.2:.4f}'+r'}\fontfamily{lmss}\selectfont '+body+'}'
    if round(angle):box=r'\rotatebox{90}{'+box+'}'
    out.append(r'\put('+f'{x:.4f},{h-y:.4f}'+'){'+box+'}')
 out += [r'\end{picture}',r'\endgroup'];return '\n'.join(out)
if __name__=='__main__':
 for name in json.loads((ROOT/'notes/postcompute-figures-v1/figure-index.json').read_text())['figures']:
  (Path(__file__).parent/(name+'.inline.tex')).write_text(convert(name)+'\n')
