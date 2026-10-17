"""Fresh geometry/font QA and a review-only9-page vector figure collection."""
from pathlib import Path
import os
for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']:
    os.environ[key] = '1'
os.nice(10)
import hashlib, json, subprocess, sys
import pymupdf

ROOT=Path(__file__).resolve().parents[2]
DATA=Path(__file__).parent
FIGURES=ROOT/'paper/figures/ten-seed-v1'
TOOLS=Path(os.environ.get('FIGURE_QA_TOOLS',str(Path.home()/'.codex/skills/nature-figure/scripts')))


def main():
    report=[]
    r=subprocess.run([sys.executable,str(TOOLS/'validate_figure.py'),str(DATA/'plot.py'),
        '--backend','python','--json'],capture_output=True,text=True)
    (DATA/'source-preflight.json').write_text(r.stdout)
    assert r.returncode==0,r.stdout
    index=json.loads((DATA/'figure-index.json').read_text())
    for item in index['figures']:
        name=item['name'];pdf=FIGURES/f'{name}.pdf'
        assert hashlib.sha256(pdf.read_bytes()).hexdigest()==item['pdf_sha256']
        alignment=json.loads((DATA/f'{name}.alignment.json').read_text())
        assert alignment['summary']['fail']==0 and alignment['auditable']
        r=subprocess.run([sys.executable,str(TOOLS/'audit_pdf_text.py'),str(pdf),
            '--min-pt','5','--json'],capture_output=True,text=True)
        (DATA/f'{name}.fonts.json').write_text(r.stdout)
        c=subprocess.run([sys.executable,str(TOOLS/'audit_figure_collisions.py'),str(pdf),
            '--json-out',str(DATA/f'{name}.collisions.json'),
            '--overlay-pdf',str(DATA/f'{name}.collision-overlay.pdf')],capture_output=True,text=True)
        report.append(dict(name=name,font_exit=r.returncode,collision_exit=c.returncode))
        print(name,'font',r.returncode,'collision',c.returncode,flush=True)
        with pymupdf.open(pdf) as doc:
            assert len(doc)==1 and doc[0].get_text().strip()
            assert not any(font[2]=='Type3' for font in doc[0].get_fonts())
    (DATA/'QA-summary.json').write_text(json.dumps(report,indent=2)+'\n')
    assert all(v['font_exit']==v['collision_exit']==0 for v in report),report
    collection=pymupdf.open()
    for item in index['figures']:
        with pymupdf.open(FIGURES/f"{item['name']}.pdf") as doc:
            collection.insert_pdf(doc)
    collection.set_metadata(dict(title='Audited valuation evidence: figure review',
        subject='Nine figures for review; not an updated manuscript'))
    collection.save(FIGURES/'figure-review.pdf',deflate=True)
    collection.close()
    print('PASS9 figure exports;42 panels; review collection saved')


if __name__=='__main__':
    main()
