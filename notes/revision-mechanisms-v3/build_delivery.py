"""Build a self-contained incremental scientific evidence bundle, no raw data."""
from pathlib import Path
import json,hashlib,zipfile
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
files=[ROOT/'paper/innovation-addendum-v1.tex',ROOT/'paper/innovation-addendum-v1.pdf',ROOT/'paper/innovation-addendum-v1.log']
files += [p for p in HERE.iterdir() if p.suffix in ['.py','.md','.json','.tex','.csv','.npz','.patch'] and p.name not in ['revision-delivery-index.json','github-sync-receipt.json']]
files += list((ROOT/'audit-protocol').glob('*.*'))
files += [HERE/'qa/render-audit.json',ROOT/'notes/revision-review-v2/evaluation/expanded-completion-summary.json']
files=sorted(set(files));archive=ROOT/'paper/revision-delivery-v3.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for p in files:z.write(p,str(p.relative_to(ROOT)))
index=dict(status='completed_incremental_scientific_revision',archive=str(archive.relative_to(ROOT)),bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
 source_sha256=hashlib.sha256(files[[str(p.relative_to(ROOT)) for p in files].index('paper/innovation-addendum-v1.tex')].read_bytes()).hexdigest(),
 scope='Current source/PDF and all v3 scientific diagnostics/protocol; excludes raw listings/weights/transitive original inputs. Older full-cohort evidence remains separately indexed. No public/external-training/submission claim.',
 files=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size) for p in files])
(HERE/'revision-delivery-index.json').write_text(json.dumps(index,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for f in index['files']:assert hashlib.sha256(z.read(f['path'])).hexdigest()==f['sha256']
print(json.dumps({k:v for k,v in index.items() if k!='files'},indent=2))
