"""Export existing Matplotlib PDF paths as self-contained LaTeX picture vectors.

No data or statistical geometry is recomputed here. The original PDF/SVG and
source CSV remain authoritative; this adapter lets the standalone editor render
vector ink without external project files.
"""
from pathlib import Path
import pymupdf as fitz
import json,re
ROOT=Path(__file__).resolve().parents[2]

def point(p,height):return f'{p.x:.4f} {height-p.y:.4f}'
def escape(s):
 s=s.replace('−','-').replace('–','--').replace('×',r'$\times$').replace('^',r'\textasciicircum{}')
 for a,b in [('&',r'\&'),('%',r'\%'),('_',r'\_'),('#',r'\#')]:s=s.replace(a,b)
 return s

def convert(name):
 path=ROOT/f'paper/figures/results-visual-v5/{name}.pdf'
 page=fitz.open(path)[0];w,h=page.rect.width,page.rect.height
 out=[r'\begingroup',r'\setlength{\unitlength}{1bp}',rf'\begin{{picture}}({w:.4f},{h:.4f})']
 for drawing in page.get_drawings():
  ops=['q']
  col=drawing.get('color') or (0,0,0);fill=drawing.get('fill')
  ops += [f'{(drawing.get("width") or .5):.4f} w', ' '.join(f'{v:.4f}' for v in col)+' RG']
  if fill:ops.append(' '.join(f'{v:.4f}' for v in fill)+' rg')
  dash=drawing.get('dashes');ops.append((dash if dash else '[] 0')+' d')
  previous=None
  for item in drawing['items']:
   kind=item[0]
   if kind=='l':
    if previous!=item[1]:ops.append(point(item[1],h)+' m')
    ops.append(point(item[2],h)+' l');previous=item[2]
   elif kind=='c':
    if previous!=item[1]:ops.append(point(item[1],h)+' m')
    ops.append(' '.join(point(v,h) for v in item[2:])+' c');previous=item[-1]
   elif kind=='re':
    rect=item[1];ops.append(f'{rect.x0:.4f} {h-rect.y1:.4f} {rect.width:.4f} {rect.height:.4f} re');previous=None
   elif kind=='qu':
    quad=item[1];ops.append(point(quad.ul,h)+' m')
    for p in [quad.ur,quad.lr,quad.ll]:ops.append(point(p,h)+' l')
    ops.append('h');previous=None
   else:raise ValueError(kind)
  if drawing.get('closePath'):ops.append('h')
  style=drawing['type'];ops.append('B' if style=='fs' else ('f' if style=='f' else 'S'))
  ops.append('Q');out.append(r'\put(0,0){\AuditVector{'+ ' '.join(ops)+'}}')
 for block in page.get_text('dict')['blocks']:
  if 'lines' not in block:continue
  for line in block['lines']:
   assert line['dir']==(1.0,0.0),'Rotated text needs an explicit adapter'
   for span in line['spans']:
    x,y=span['origin'];size=span['size'];s=escape(span['text'])
    rgb=span['color'];color=','.join(f'{((rgb >> shift) & 255)/255:.4f}' for shift in [16,8,0]);s=r'\color[rgb]{'+color+'}'+(r'\bfseries ' if 'Bold' in span['font'] else '')+s
    out.append(r'\put(' + f'{x:.4f},{h-y:.4f}' + r'){\makebox(0,0)[bl]{\fontsize{' + f'{size:.4f}' + '}{' + f'{size*1.2:.4f}' + r'}\fontfamily{lmss}\selectfont ' + s + '}}')
 out += [r'\end{picture}',r'\endgroup']
 return '\n'.join(out)
if __name__=='__main__':
 for name in ['cap-tradeoffs','cost-mechanism','uncertainty-components','envelope-boundary']:
  result=convert(name);(ROOT/f'notes/results-visual-v5/{name}.inline.tex').write_text(result+'\n')
 print('four self-contained vector adapters generated')
