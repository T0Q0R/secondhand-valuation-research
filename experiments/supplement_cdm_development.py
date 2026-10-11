"""Complete only the unavailable parent pairs, with the frozen CDM algorithm.

This is mechanical completion of a fixed nine-pair study, not outcome-selected
replication. The two generations remain separate and hash-bound for union audit.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from analyze_nested import read,require,sha
from run_all import write_json
import resume_cdm_development


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-run',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    base,output=args.base_run.resolve(),args.output.resolve()
    manifest,complete=read(base/'manifest.json'),read(base/'completion.json')
    require(complete['status']=='completed' and not manifest['execution_smoke'],'Complete real-source base required')
    parent=Path(manifest['parent_path'])
    parent_manifest,parent_done=read(parent/'run_manifest.json'),read(parent/'completion.json')
    require(parent_done['status']=='completed','Completed full parent required')
    require(parent_done['binding']==parent_manifest['binding']==manifest['parent_binding'],'Parent generation')
    require(parent_manifest['config']==manifest['parent_config'],'Parent parameters changed')
    scheduled=[(d,s) for d in manifest['parent_config']['datasets'] for s in manifest['parent_config']['seeds']]
    require(complete['pairs']==manifest['pairs'],'Base pair completion')
    available=set(map(tuple,manifest['pairs']))
    require(available.issubset(set(scheduled)),'Unexpected base pair')
    missing=[list(p) for p in scheduled if p not in available]
    require(bool(missing),'No missing pairs to supplement')
    root=Path(__file__).parents[1]
    for name,digest in manifest['source_hashes'].items():
        current=(root/'plan'/name if name.endswith('.md') else
                 root/'tests'/name if name.startswith('test_') else root/'experiments'/name)
        require(sha(current)==sha(base/'source_snapshot'/name)==digest,'Frozen CDM source changed')
    for d,s in missing:
        require((parent/d/f'seed-{s}'/'evaluation_completion.json').exists(),'Required parent pair unavailable')
    require(not output.exists(),'Fresh supplement output required')
    output.mkdir(parents=True)
    snapshot=output/'source_snapshot';snapshot.mkdir()
    for name in manifest['source_hashes']:
        (snapshot/name).write_bytes((base/'source_snapshot'/name).read_bytes())
    extra=[Path(__file__),Path(resume_cdm_development.__file__)]
    hashes=dict(manifest['source_hashes'])
    for source in extra:
        hashes[source.name]=sha(source)
        (snapshot/source.name).write_bytes(source.read_bytes())
    supplement={**manifest,'pairs':missing,'parent_complete_at_start':True,'source_hashes':hashes,
                'base_run_path':str(base),'base_completion_sha256':sha(base/'completion.json'),
                'scope':'only originally unavailable pairs; same frozen rule bank/config/cohorts; union evidence required'}
    write_json(output/'manifest.json',supplement)
    old_argv=sys.argv
    try:
        sys.argv=['resume_cdm_development.py','--run',str(output)]
        resume_cdm_development.main()
    finally:sys.argv=old_argv


if __name__=='__main__':main()
