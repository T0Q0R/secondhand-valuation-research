"""Preserve v3 scientific evidence while delivering the current same-file revision."""
from pathlib import Path
import json,hashlib,zipfile
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
old=ROOT/'paper/revision-delivery-v3.zip';assert hashlib.sha256(old.read_bytes()).hexdigest()=='7fb038f974bdc921583c2c9e534b61f2b6ec24a3d2ae4506fe010cc4e2dc2f3a'
with zipfile.ZipFile(old) as z:payload={name:z.read(name) for name in z.namelist()}
files=[ROOT/'paper'/('innovation-addendum-v1'+s) for s in ['.tex','.pdf','.log']]
files += [p for p in HERE.iterdir() if p.suffix in ['.py','.md','.json','.tex','.csv','.patch'] and p.name not in ['delivery-index.json','github-sync-receipt.json']]
files += [HERE/'qa/render-audit.json']
for p in files:payload[str(p.relative_to(ROOT))]=p.read_bytes()
archive=ROOT/'paper/revision-delivery-v4.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for name,data in sorted(payload.items()):z.writestr(name,data)
index=dict(status='compiled_and_checked_teacher_advice_revision',archive=str(archive.relative_to(ROOT)),bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
 source_sha256=hashlib.sha256((ROOT/'paper/innovation-addendum-v1.tex').read_bytes()).hexdigest(),
 pdf_sha256=hashlib.sha256((ROOT/'paper/innovation-addendum-v1.pdf').read_bytes()).hexdigest(),
 scope='v3 supporting scientific evidence retained; current source/PDF and v4 bounded wording/accounting/price-normalization checks; no raw listings/weights/new training/public release',
 files=[dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for name,data in sorted(payload.items())])
(HERE/'delivery-index.json').write_text(json.dumps(index,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for f in index['files']:assert hashlib.sha256(z.read(f['path'])).hexdigest()==f['sha256']
print(json.dumps({k:v for k,v in index.items() if k!='files'},indent=2))
