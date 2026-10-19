"""Release only whitelisted scalar receipts; never weights or listing rows."""
from pathlib import Path
import hashlib,json,zipfile

ROOT=Path(__file__).resolve().parents[2]
N=Path(__file__).parent
RUN=ROOT/'outputs/review-gap-controls-v2'
SEEDS=[13,42,2026,101,211,307,401,503,601,701]

def main():
    assert json.loads((N/'gap/verification.json').read_text())['new_fit_receipts_checked']==360
    files=[]
    for name in ['manifest.json','completion.json','summary.csv']:
        files.append((RUN/name,name))
    for source in ['synthetic','jucars','mucars']:
        for seed in SEEDS:
            pair=RUN/source/f'seed-{seed}'
            for name in ['training-selection.json','completion.json','summary.csv','data-binding.json']:
                files.append((pair/name,f'{source}/seed-{seed}/{name}'))
            for beta in [1,2,4]:
                cell=pair/f'path-0-gap-{beta}'
                for name in ['deployment_model.json','evaluation-1000/completion.json']:
                    files.append((cell/name,f'{source}/seed-{seed}/path-0-gap-{beta}/{name}'))
                for stage in ['outer-0','outer-1','outer-2','deployment']:
                    # Full fit receipts contain both rounds' scalar loss logs.
                    p=cell/stage/'completion.json'
                    files.append((p,f'{source}/seed-{seed}/path-0-gap-{beta}/{stage}/completion.json'))
    rows=[];archive=N/'gap/scalar-receipts-v2.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path,slot in files:
            assert path.exists() and path.suffix in ['.json','.csv']
            data=path.read_bytes()
            if path.suffix=='.json':json.loads(data)
            info=zipfile.ZipInfo(slot,date_time=(2026,10,19,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,data)
            rows.append(dict(path=slot,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
        z.writestr('MANIFEST.json',json.dumps(rows,indent=2)+'\n')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for row in rows:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
    index=dict(status='verified',path=str(archive.relative_to(ROOT)),files=len(rows),new_fit_receipts=360,
      new_evaluation_receipts=90,selection_receipts=30,bytes=archive.stat().st_size,
      sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
      scope='Whitelisted scalar completion, fit-round logs, configuration, hash bindings, selection scores and aggregate CSV. No raw records, per-listing rows, arrays, model weights or credentials.',
      files_manifest=rows)
    (N/'gap/scalar-receipts-index.json').write_text(json.dumps(index,indent=2)+'\n')
    print({k:v for k,v in index.items() if k!='files_manifest'})

if __name__=='__main__':main()
