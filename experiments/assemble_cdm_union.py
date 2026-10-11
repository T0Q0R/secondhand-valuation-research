"""Assemble completed frozen CDM generations without refitting or rewriting them.

The union links immutable source/seed directories, retains both generations'
receipts, and requires a separate independent union audit before paper claims.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from analyze_nested import read, require, sha
from run_all import write_json

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    runs, output = [p.resolve() for p in args.runs], args.output.resolve()
    require(len(set(runs))==len(runs) and len(runs)>1, 'Distinct completed input generations')
    require(not output.exists(), 'Fresh immutable union output')
    manifests, completions, summaries, origins, snapshots, provenance = [], [], [], {}, {}, []
    for run in runs:
        manifest, done = read(run/'manifest.json'), read(run/'completion.json')
        require(done['status']=='completed' and not manifest['execution_smoke'], 'Completed real-source generation')
        require(done['pairs']==manifest['pairs'], 'Generation pair completion')
        require(sha(run/'all_summary.csv')==done['summary_sha256'], 'Generation summary binding')
        if manifests:
            for key in ('parent_binding','parent_path','parent_config','config','prices','policies','execution_smoke'):
                require(manifest[key]==manifests[0][key], 'Common frozen protocol: '+key)
            for name, digest in manifests[0]['source_hashes'].items():
                require(manifest['source_hashes'].get(name)==digest, 'Common algorithm/source bytes')
        table = pd.read_csv(run/'all_summary.csv')
        require(len(table)==done['cells'], 'Input cell count')
        require(set(zip(table.dataset,table.seed))==set(map(tuple,manifest['pairs'])), 'Input pair matrix')
        for dataset,seed in manifest['pairs']:
            pair = (dataset,seed)
            require(pair not in origins, 'No duplicated pair across generations')
            folder = run/dataset/f'seed-{seed}'
            receipt = read(folder/'completion.json')
            require(receipt['status']=='completed' and receipt['parent_binding']==manifest['parent_binding'], 'Pair parent binding')
            count = len(manifest['prices'])*len(manifest['config']['budgets'])*(len(manifest['policies'])+2)
            require(receipt['cells']==count and len(table[(table.dataset==dataset)&(table.seed==seed)])==count, 'Pair cells')
            for price in manifest['prices']:
                for budget in manifest['config']['budgets']:
                    bf = folder/price/f'budget-{int(round(budget*10000)):04d}'
                    budget_done = read(bf/'completion.json')
                    for name,digest in budget_done['files'].items():
                        require(sha(bf/name)==digest, 'Frozen budget artifact')
            origins[pair] = folder
        for name,digest in manifest['source_hashes'].items():
            source = run/'source_snapshot'/name
            require(sha(source)==digest, 'Input source snapshot')
            if name in snapshots:require(sha(snapshots[name])==digest, 'Compatible source snapshots')
            snapshots[name] = source
        provenance.append({'run':str(run),'manifest_sha256':sha(run/'manifest.json'),
            'completion_sha256':sha(run/'completion.json'),'summary_sha256':done['summary_sha256'],
            'pairs':manifest['pairs'], 'pair_receipts':{f'{d}/seed-{s}':sha(run/d/f'seed-{s}'/'completion.json')
                for d,s in manifest['pairs']}})
        manifests.append(manifest); completions.append(done); summaries.append(table)
    base = manifests[0]
    scheduled = [(d,s) for d in base['parent_config']['datasets'] for s in base['parent_config']['seeds']]
    require(set(origins)==set(scheduled), 'Complete intended source/seed matrix')
    keys = ['dataset','seed','price','budget','method']
    summary = pd.concat(summaries,ignore_index=True).sort_values(keys).reset_index(drop=True)
    require(not summary.duplicated(keys).any(), 'No repeated final cells')
    parent = Path(base['parent_path'])
    parent_done = read(parent/'completion.json')
    require(parent_done['status']=='completed' and parent_done['binding']==base['parent_binding'], 'Full parent completed')
    output.mkdir(parents=True); snapshot = output/'source_snapshot'; snapshot.mkdir()
    for name,source in snapshots.items():(snapshot/name).write_bytes(source.read_bytes())
    (snapshot/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    for (dataset,seed),folder in origins.items():
        (output/dataset).mkdir(exist_ok=True)
        (output/dataset/f'seed-{seed}').symlink_to(folder,target_is_directory=True)
    write_json(output/'union_provenance.json', {'kind':'mechanical completed-evidence union; no refitting',
        'generations':provenance,'pair_paths':{f'{d}/seed-{s}':str(p) for (d,s),p in origins.items()},
        'independent_union_audit_required':True,'assembler_sha256':sha(Path(__file__))})
    hashes = {name:sha(path) for name,path in snapshots.items()}
    hashes[Path(__file__).name] = sha(Path(__file__))
    write_json(output/'manifest.json', {**base,'pairs':[list(p) for p in scheduled],
        'parent_complete_at_start':True,'source_hashes':hashes,'evidence_union':True,
        'union_provenance_sha256':sha(output/'union_provenance.json'),
        'scope':'complete nine-pair frozen CDM study assembled from two immutable generations; separate audit required'})
    summary.to_csv(output/'all_summary.csv',index=False)
    write_json(output/'completion.json', {'status':'completed','pairs':[list(p) for p in scheduled],
        'cells':len(summary),'summary_sha256':sha(output/'all_summary.csv'),
        'all_scheduled_pairs_completed':True,'execution_smoke':False,'evidence_union':True,
        'union_provenance_sha256':sha(output/'union_provenance.json')})
    for item in provenance:
        source = Path(item['run'])
        require(sha(source/'manifest.json')==item['manifest_sha256'] and
                sha(source/'completion.json')==item['completion_sha256'] and
                sha(source/'all_summary.csv')==item['summary_sha256'], 'Input generation changed during assembly')
    print(f'Assembled {len(summary)} frozen CDM cells; independent union audit remains required.',flush=True)

if __name__=='__main__':main()
