"""Local completed EMC evidence package; not the final SAV/CDM paper release."""
import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--include-scale',action='store_true');a=p.parse_args()
    output=a.output.resolve();archive=output.with_suffix('.zip')
    if output.exists() or archive.exists():raise ValueError('Fresh package required')
    run=ROOT/'outputs/emc-development-v1';done=read(run/'completion.json')
    assert done['status']=='completed' and not done['smoke'] and done['cell_count']==810 and done['case_count']==9
    assert done['summary_sha256']==sha(run/'summary.csv') and done['config_sha256']==sha(run/'config.json')
    for source in ('synthetic','jucars','mucars'):
        for seed in (13,42,2026):
            folder=run/source/f'seed-{seed}';receipt=read(folder/'completion.json')
            assert receipt['status']=='completed' and receipt['cells']==90
            for name,digest in receipt['files'].items():assert sha(folder/name)==digest
    for name in ('emc-development-v1-audit','emc-development-v1-audit-02'):
        receipt=read(ROOT/'outputs'/name/'completion.json')
        assert receipt['status']=='completed' and receipt['cell_count']==810 and receipt['run_completion_sha256']==sha(run/'completion.json')
        assert receipt['summary_sha256']==sha(ROOT/'outputs'/name/'summary.csv')
    stats=ROOT/'outputs/emc-development-v1-contrasts';receipt=read(stats/'completion.json')
    assert receipt['status']=='completed' and receipt['cells']==810 and receipt['contrasts']==1386
    for name,digest in receipt['files'].items():assert sha(stats/name)==digest
    paths=[ROOT/'experiments'/name for name in ('emc_val.py','savval.py','run_emc_development.py','analyze_emc_development.py','summarize_emc_development.py','package_emc_development.py','verify_emc_development_package.py')]
    paths += [ROOT/'tests/test_emc_certificates.py']
    paths += [ROOT/'pytest.ini',ROOT/'plan/emc-development-v1.md',ROOT/'requirements-lock.txt',
        ROOT/'notes/design/创新候选-EMC-Val.md',ROOT/'notes/emc-mechanism-boundary-2026-10-07.md',
        ROOT/'notes/emc-development-results-2026-10-07-v1.md']
    paths += sorted((ROOT/'notes/emc-audit-source-snapshots').glob('*.py'))
    for name in ('emc-development-v1','emc-development-v1-audit','emc-development-v1-audit-02','emc-development-v1-contrasts'):
        paths += [p for p in (ROOT/'outputs'/name).rglob('*') if p.is_file()]
    scale_binding=None
    if a.include_scale:
        scaled=ROOT/'outputs/emc-state-scale-development-v1'
        config=read(scaled/'config.json');complete=read(scaled/'completion.json')
        assert complete['status']=='completed' and not complete['smoke']
        assert complete['cell_count']==1080 and complete['case_count']==9
        assert config['sources']==['synthetic','jucars','mucars'] and config['seeds']==[13,42,2026]
        assert config['alphas']==[.05,.1] and config['budgets']==[0,.1,.3] and config['iterations']==160
        assert complete['parent_completion_sha256']==sha(run/'completion.json')
        assert complete['config_sha256']==sha(scaled/'config.json') and complete['summary_sha256']==sha(scaled/'summary.csv')
        assert complete['source_snapshot_sha256']==sha(scaled/'source_snapshot/hashes.json')
        for name,digest in read(scaled/'source_snapshot/hashes.json').items():assert sha(scaled/'source_snapshot'/name)==digest
        for source in config['sources']:
            for seed in config['seeds']:
                folder=scaled/source/f'seed-{seed}';case=read(folder/'completion.json')
                assert case['status']=='completed' and case['cells']==120
                assert case['source']==source and case['seed']==seed
                assert case['parent_case_completion_sha256']==sha(run/source/f'seed-{seed}/completion.json')
                assert case['config_sha256']==sha(scaled/'config.json')
                for name,digest in case['files'].items():assert sha(folder/name)==digest
        audit=ROOT/'outputs/emc-state-scale-development-v1-audit';checked=read(audit/'completion.json')
        assert checked['status']=='completed' and not checked['smoke'] and checked['cells']==1080 and checked['cases']==9
        assert checked['record_outcome_checks']==798120 and checked['forced_public_equivalence_checks']==2160
        assert checked['run_completion_sha256']==sha(scaled/'completion.json') and checked['parent_completion_sha256']==sha(run/'completion.json')
        assert checked['summary_sha256']==sha(audit/'summary.csv')
        assert checked['auditor_sha256']==sha(ROOT/'experiments/analyze_emc_scale_development.py')
        statistics=ROOT/'outputs/emc-state-scale-development-v1-contrasts-02';summary=read(statistics/'completion.json')
        assert summary['status']=='completed' and summary['cells']==1080 and summary['contrasts']==4032
        assert summary['median_contrasts']==6 and summary['coverage_diagnostics']==72
        assert summary['run_completion_sha256']==sha(scaled/'completion.json') and summary['audit_completion_sha256']==sha(audit/'completion.json')
        assert summary['source_sha256']==sha(ROOT/'experiments/summarize_emc_scale_development.py')
        assert summary['paired_source_sha256']==sha(ROOT/'experiments/summarize_emc_development.py')
        assert {(b['source'],b['seed']) for b in summary['case_bindings']}=={(s,t) for s in config['sources'] for t in config['seeds']}
        assert len(summary['case_bindings'])==9
        for binding in summary['case_bindings']:
            assert binding['case_completion_sha256']==sha(scaled/binding['source']/f"seed-{binding['seed']}"/'completion.json')
        for name,digest in summary['files'].items():assert sha(statistics/name)==digest
        failed=ROOT/'outputs/emc-state-scale-development-v1-contrasts';failure=read(failed/'failure.json')
        assert failure['status']=='failed' and not (failed/'completion.json').exists()
        assert failure['source_sha256']==sha(failed/'failed_source_snapshot.py')
        for name in ('paired_contrasts.csv','primary_contrasts.csv','coverage_diagnostics.csv'):
            assert sha(failed/name)==sha(statistics/name)
        gate=read(statistics/'decision_gate.json')
        assert gate['all_prespecified_checks_pass'] is False and gate['JUCars_gain_threshold']==.10
        for name in ('emc-state-scale-development-v1','emc-state-scale-development-v1-audit','emc-state-scale-development-v1-contrasts','emc-state-scale-development-v1-contrasts-02'):
            paths += [p for p in (ROOT/'outputs'/name).rglob('*') if p.is_file()]
        paths += [ROOT/'experiments'/name for name in ('run_emc_scale_development.py','analyze_emc_scale_development.py','summarize_emc_scale_development.py')]
        paths += [ROOT/'tests/test_emc_state_scale.py',ROOT/'plan/emc-state-scale-development-v1.md',
            ROOT/'notes/design/创新候选-EMC-Val-尺度修订.md',ROOT/'notes/emc-state-scale-results-2026-10-07-v1.md']
        scale_binding={'run_completion_sha256':sha(scaled/'completion.json'),'audit_completion_sha256':sha(audit/'completion.json'),
            'statistics_completion_sha256':sha(statistics/'completion.json'),'decision_gate_sha256':sha(statistics/'decision_gate.json'),
            'cells':1080,'cases':9,'contrasts':4032,'practical_gate_pass':False}
    entries={}
    for path in paths:
        if path.is_symlink():raise ValueError('Unexpected link in standalone EMC package')
        relative=Path('sav-val')/path.relative_to(ROOT);entries[str(relative)]=path
    for source in ('jucars','mucars'):
        relative=Path('experiments/data/processed')/f'{source}_bvival_v1/splits/train.csv'
        entries[str(relative)]=ROOT.parent/relative
    for relative,path in entries.items():
        if not path.is_file():raise FileNotFoundError(f'Missing package input: {relative}')
    output.mkdir(parents=True)
    manifest={}
    for relative,path in sorted(entries.items()):
        target=output/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
        manifest[relative]={'sha256':sha(target),'bytes':target.stat().st_size}
    text='''# EMC completed development evidence

This local bundle contains 810 independently audited development cells, source,
27 fitted CatBoost models, all state intervals/reports/replays, calibration,
1,386 conditional paired contrasts and two checksum-bound inherited training
CSVs. It is not the final SAV/CDM collection, a public deposit, a novel-method
certification or a finished Q3 submission. Three sources, three fitting seeds;
original validation/test files are excluded. Current conservative prices are
too low on JUCars; see the Chinese results note. No equilibrium acquisition
welfare claim is established.

JUCars: 2024 v2, DOI https://doi.org/10.17632/ddcz486x5t.2, CC BY 4.0;
MUCars: 2024 v2, DOI https://doi.org/10.17632/vjrbcb2rrt.2, CC BY 4.0.
The CSVs are inherited processed derivatives. Labels are advertised prices
(JOD/MAD), not transactions; synthetic units are stipulated. No project
software licence or public-release permission is implied.

From sav-val with the recorded dependencies installed:
python -m pytest tests/test_emc_certificates.py -q
python experiments/analyze_emc_development.py --run outputs/emc-development-v1 --output outputs/copied-audit
python experiments/run_emc_development.py --output outputs/new-independent-fit

The audit reconstructs saved-model arithmetic and allocations; it does not
refit models. The last command performs a fresh fit. Audit-v1 source is retained
under notes/emc-audit-source-snapshots; the current auditor also checks stored
fitting parameters and resolves inputs in this copied inherited data tree.
'''
    if a.include_scale:
        text+='''
## Retrospective state-scale refinement

The bundle additionally preserves1,080 state-scale cells,27 new fitted models,
4,032 paired mean contrasts,6 median contrasts and72 model coverage diagnostics.
The original parent810-cell evidence is included intact. Scale/query fitting
records are disjoint; the calibrated state normalization precedes certificate
intersection. All raw outcomes and adverse effects are retained. The failed
first summarizer and its failure receipt are preserved; contrasts-02 is the
authoritative corrected statistics generation.

The prespecified practical gate FAILED: JUCars honest median quote/label gain
was0.0703, below0.10. Do not treat a failed practical criterion as a method
success. This is seen-data development, not certified novelty, exchangeability,
global incentive compatibility, equilibrium welfare or a finished Q3 paper.

From sav-val:
python -m pytest tests/test_emc_certificates.py tests/test_emc_state_scale.py -q
python experiments/analyze_emc_scale_development.py --parent outputs/emc-development-v1 --run outputs/emc-state-scale-development-v1 --output outputs/copied-scale-audit
python experiments/run_emc_scale_development.py --parent outputs/emc-development-v1 --output outputs/new-scale-fit

The first audit command above and the scale audit use saved models. They do
not freshly refit models; the last command does fit new scale/query models.
'''
    (output/'README.md').write_text(text)
    manifest['README.md']={'sha256':sha(output/'README.md'),'bytes':(output/'README.md').stat().st_size}
    (output/'manifest.json').write_text(json.dumps({'status':'completed_EMC_development_evidence','files':manifest,
        'scale_refinement':scale_binding},ensure_ascii=False,indent=2)+'\n')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for relative in sorted(manifest):z.write(output/relative,relative)
        z.write(output/'manifest.json','manifest.json')
    receipt={'status':'created_local_complete_EMC_development_archive','entries':len(manifest)+1,'archive_sha256':sha(archive),
        'manifest_sha256':sha(output/'manifest.json'),'archive_bytes':archive.stat().st_size,'source_sha256':sha(__file__),
        'scale_refinement':scale_binding,'scope':'EMC development only; verify archive/copy separately; not full goal completion'}
    archive.with_name(archive.stem+'-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__':main()
