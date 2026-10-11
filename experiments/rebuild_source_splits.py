"""Rebuild inherited train/validation inputs from pinned raw source bytes.

Import the inspected manifest builders without their output writers. Exact
CSV hashes must match the original inputs; historical test labels are neither
opened nor emitted here.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import pandas as pd

PARENT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PARENT/'experiments'))
import build_jucars_bvival_manifest as ju
import build_mucars_bvival_manifest as mu

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    for name in ('jucars-source','jucars-dictionary','mucars-source','input-receipt','output-root'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();recorded=json.loads(args.input_receipt.read_text())
    if args.output_root.exists():raise FileExistsError('Fresh reconstruction directory required')
    for name,path in [('jucars_source',args.jucars_source),('jucars_dictionary',args.jucars_dictionary),
                      ('mucars_source',args.mucars_source)]:
        if sha(path)!=recorded['raw_sha256'][name]:raise ValueError(f'Pinned raw bytes differ: {name}')
    for name,module in [('build_jucars_bvival_manifest.py',ju),('build_mucars_bvival_manifest.py',mu)]:
        if sha(Path(module.__file__))!=recorded['builder_sha256'][name]:
            raise ValueError(f'Inspected builder generation differs: {name}')
    args.output_root.mkdir(parents=True);outputs={};counts={}
    for name,path,builder in [('jucars',args.jucars_source,ju),('mucars',args.mucars_source,mu)]:
        frame,_=builder.build_manifest(pd.read_csv(path))
        directory=args.output_root/'experiments/data/processed'/f'{name}_bvival_v1'/'splits'
        directory.mkdir(parents=True)
        for split in ('train','validation'):
            relative=f'{name}/{split}.csv';target=directory/f'{split}.csv'
            selected=frame.loc[frame['split'].eq(split)].drop(columns='split')
            selected.to_csv(target,index=False);digest=sha(target)
            if digest!=recorded['processed_sha256'][relative]:raise ValueError(f'Reconstructed input differs: {relative}')
            outputs[relative]=digest;counts[relative]=len(selected)
    receipt={'status':'completed','scope':'exact inherited train/validation reconstruction only',
        'source_receipt_sha256':sha(args.input_receipt),'script_sha256':sha(Path(__file__)),
        'outputs_sha256':outputs,'row_counts':counts,'historical_test_labels_read':False}
    (args.output_root/'reconstruction_completion.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'completed','row_counts':counts}),flush=True)

if __name__=='__main__':main()
