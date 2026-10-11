"""Create a code/inputs-receipt development package, without raw data/models."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--journal-draft',type=Path)
    args=parser.parse_args();output=args.output.resolve();archive=output.with_suffix('.zip')
    if output.exists() or archive.exists():raise FileExistsError('Fresh source package required')
    files=[ROOT/n for n in ('README.md','REPRODUCING.md','requirements-lock.txt','paper.config.yaml','pytest.ini')]
    for directory,pattern in [('experiments','*.py'),('experiments/configs','*.json'),('tests','*.py'),
                              ('plan','*.md'),('paper/sections','*.tex'),('paper/figures','*.pdf')]:
        files.extend(sorted((ROOT/directory).glob(pattern)))
    figure_dir=ROOT/'paper/figures/journal-legible-v3'
    figure_receipt=json.loads((figure_dir/'figure_receipt.json').read_text())
    for name,digest in figure_receipt['files'].items():
        if sha(figure_dir/name)!=digest:raise ValueError('Journal figure bytes changed')
    files.extend(figure_dir/name for name in [*figure_receipt['files'], 'figure_receipt.json'])
    figure_qa=json.loads((figure_dir/'qa_receipt.json').read_text())
    if figure_qa['status']!='completed':raise ValueError('Reviewed journal figures required')
    for name,digest in figure_qa['files'].items():
        if sha(figure_dir/name)!=digest:raise ValueError('Journal native figure QA binding changed')
    known={path.resolve() for path in files}
    files.extend(figure_dir/name for name in [*figure_qa['files'],'qa_receipt.json'] if (figure_dir/name).resolve() not in known)
    files.extend(ROOT/'paper/figures'/name for name in ('missingness_example.tex','sav_val_overview.tex'))
    files.extend(ROOT/n for n in ('paper/main.tex','paper/main.pdf','paper/ref.bib','cdm-val/finite_demo.py',
        'notes/source-reproduction-inputs-v1.json','notes/design/创新候选-CDM-Val.md',
        'paper/journal-main-prose.tex','paper/journal-methods-prose.tex',
        'notes/citation-verification.csv','notes/manuscript-main-evidence-revision15.json',
        'notes/manuscript-main-evidence-revision11.json',
        'notes/manuscript-main-evidence-revision14.json',
        'notes/manuscript-followup-evidence-revision24.json',
        'notes/manuscript-comparator-resource-evidence-revision09.json',
        'notes/manuscript-cdm-deviation-evidence-revision16.json',
        'notes/manuscript-prose-polish-revision01.json',
        'notes/journal-missingness-padding-contract-v1.md',
        'notes/manuscript-followup-evidence-revision25.json',
        'notes/manuscript-equal-benefit-evidence-revision28.json',
        'notes/manuscript-cdm-deviation-evidence-revision17.json',
        'notes/manuscript-diagnostics-evidence-revision06.json',
        'notes/manuscript-comparator-resource-evidence-revision10.json',
        'notes/manuscript-robust-benefit-evidence-revision09.json',
        'notes/data-availability-development.md','notes/supporting-data-inventory.csv',
        'notes/venue-assets/springer-template-retrieval.json',
        'notes/venue-assets/springer-nature-december-2024-template.zip',
        'notes/venue-screening-2026-10-06.md','notes/development-v1-correction.md',
        'notes/nearest-audit-boundary-2026-10-07.md',
        'notes/source-package-data-guard-correction-2026-10-06.json',
        'artifacts/completed-evidence-components-v1.manifest.json',
        'artifacts/completed-evidence-components-v1-verification.json'))
    # Current complete-scope lineage and review accompany the reviewed maps.
    files.extend(ROOT/name for name in (
        'notes/manuscript-evidence-check-revision31.json',
        'notes/pre-submission-scan-revision31.json',
        'notes/pre-submission-review-revision31.json',
        'notes/pre-submission-review-revision31.md',
        'notes/full-manuscript-promotion-repair-v1.json',
        'notes/full-table-caption-boundary-repair-v1.json',
        'notes/full-author-wording-correction-v1.json',
        'notes/full-tuning-prior-numeric-preservation-2026-10-07-v1.json',
        'notes/full-BEN-prior-numeric-preservation-2026-10-07-v1.json',
        'notes/full-delivery-partial-rejection-2026-10-07-v1.json',
        'notes/venue-evidence-2026-10-07-v1.md',
        'notes/journal-compiler-compatibility-2026-10-07-v1.md',
        'notes/journal-conference-style-repair-2026-10-07-v1.json',
        'paper/issues/research.csv'))
    files.extend(ROOT/name for name in (
        'notes/manuscript-evidence-check-revision32.json',
        'notes/pre-submission-scan-revision32.json',
        'notes/pre-submission-review-revision32.json',
        'notes/pre-submission-review-revision32.md',
        'notes/completed-local-evidence-reproduction-v1.json',
        'notes/completed-local-evidence-reproduction-v1.md',
        'notes/local-copy-reproduction-prose-backfill-v1.json',
        'notes/local-copy-reproduction-spacing-repair-v1.json',
        'notes/full-source-package-duplicate-repair-v1.json',
        'artifacts/completed-delivery-copy-v1/assembly_receipt.json',
        'artifacts/completed-delivery-copy-v1/source-reconstruction-proof.json',
        'artifacts/completed-delivery-copy-v1/full-extension-saved-replay-proof/completion.json',
        'artifacts/completed-delivery-copy-v1/full-extension-saved-replay-proof/cell_checks.csv',
        'artifacts/completed-delivery-copy-v1/full-extension-saved-replay-proof/verifier_snapshot.py',
        'artifacts/completed-delivery-copy-v1/main-558-replay-proof.json',
        'artifacts/completed-delivery-copy-v1/figure-replay-driver.py'))
    files.extend(path for path in sorted(
        (ROOT/'artifacts/completed-delivery-copy-v1/figure-replay-proof').rglob('*'))
        if path.is_file())
    files.extend(ROOT/name for name in (
        'notes/manuscript-evidence-check-revision33.json',
        'notes/pre-submission-scan-revision33.json',
        'notes/pre-submission-review-revision33.json',
        'notes/pre-submission-review-revision33.md',
        'notes/aaai-bibliography-format-repair-2026-10-07-v1.json',
        'notes/submission-readiness-2026-10-07-v1.json',
        'notes/submission-readiness-2026-10-07-v1.md',
        'notes/cover-letter-body-scientific-reports-v1.md',
        'paper/qa-development-v2-revision33/qa-receipt.json'))
    files.extend(ROOT/'notes/source-inspection/audit-neighbors-2026-10-06'/name
                 for name in ('comparison.md','retrieval.json'))
    if args.journal_draft:
        journal=args.journal_draft.resolve()
        if not journal.is_relative_to(ROOT/'paper'):raise ValueError('Journal draft must be within current paper directory')
        review=json.loads((journal/'review_completion.json').read_text())
        if review['status']!='compiled_and_visually_reviewed_development':raise ValueError('Reviewed journal artifact required')
        for name,key in [('main.pdf','main_pdf_sha256'),('supplement.pdf','supplement_pdf_sha256')]:
            if sha(journal/name)!=review[key]:raise ValueError('Reviewed PDF binding changed')
        files.extend(journal/n for n in ('main.tex','supplement.tex','main.pdf','supplement.pdf',
            'ref.bib','sn-jnl.cls','sn-nature.bst','build_receipt.json','review_completion.json',
            'missingness_example.pdf','sav_val_overview.pdf','capacity_frontiers.pdf',
            'cdm_capacity_frontiers_full.pdf','sup_missingness_example.pdf','sup_sav_val_overview.pdf',
            'sup_capacity_frontiers.pdf','sup_cdm_capacity_frontiers_full.pdf',
            'compilation-main.log','compilation-supplement.log'))
        build=json.loads((journal/'build_receipt.json').read_text())
        for name,digest in build['files'].items():
            if sha(journal/name)!=digest:raise ValueError('Built journal file changed: '+name)
        known={path.resolve() for path in files}
        files.extend(journal/name for name in build['files']
                     if (journal/name).resolve() not in known)
        if build.get('conference_style_repair'):
            if build.get('bibliography_style')!='sn-nature-compatible':
                raise ValueError('Known separately named conference style required')
        # Include the exact receipt generation used by the reviewed article.
        # Historical maps above remain explicitly historical inputs.
        current_maps=[]
        author_inputs=[]
        for path_text,digest in build['input_hashes'].items():
            path=Path(path_text)
            if sha(path)!=digest:raise ValueError('Reviewed journal input changed: '+str(path))
            if path.name.startswith('manuscript-') and '-evidence-revision' in path.name:
                if not path.resolve().is_relative_to(ROOT/'notes'):
                    raise ValueError('Manuscript evidence receipt outside notes')
                current_maps.append(path)
            if path.name.startswith('manuscript-author-metadata-'):
                if not path.resolve().is_relative_to(ROOT/'notes'):
                    raise ValueError('Author metadata outside notes')
                author_inputs.append(path)
        if len(current_maps)!=7:raise ValueError('Seven reviewed manuscript evidence maps required')
        if build.get('author_metadata_sha256'):
            if len(author_inputs)!=1 or sha(author_inputs[0])!=build['author_metadata_sha256']:
                raise ValueError('Exact supplied author metadata required')
        known={path.resolve() for path in files}
        files.extend(path for path in current_maps+author_inputs if path.resolve() not in known)
        if build.get('supplement_extra_display_items',0):
            if build['supplement_extra_display_items']!=2:raise ValueError('Known supplementary figure contract required')
            bundle=(ROOT/'paper'/build.get('supplement_figure_bundle','figures/training-size-effects-v3')).resolve()
            if not bundle.is_relative_to(ROOT/'paper/figures'):raise ValueError('Supplementary bundle outside paper figures')
            qa=json.loads((bundle/'qa_receipt.json').read_text())
            if qa['status']!='completed':raise ValueError('Reviewed supplementary bundle required')
            for name,digest in qa['files'].items():
                if sha(bundle/name)!=digest:raise ValueError('Supplementary bundle changed')
            files.extend(bundle/name for name in [*qa['files'],'qa_receipt.json'])
            known={path.resolve() for path in files}
            files.extend(journal/name for name in ('training_size_tuned.pdf','training_size_fixed.pdf',
                'qa-notes.md','visual-page-identity.json','qa-main/qa-receipt.json',
                'qa-supplement/qa-receipt.json','qa-supplement/new-figure-pages.line-collision-v2.json')
                if (journal/name).resolve() not in known)
            if build.get('all_scheduled_extensions_in_manuscript'):
                files.extend(journal/name for name in (
                    'integrated-figure-QA.json',
                    'qa-supplement/new-figure-pages.raw-collision.json',
                    'qa-supplement/new-figure-pages.pdf'))
            files.extend(ROOT/name for name in ('notes/training-size-figure-contract-v2.md',
                'notes/full-evidence-archive-gate-partial-probe-v2.json',
                'artifacts/training-size-effects-v3-relocation-verification.json',
                'artifacts/document-collision-parser-probe-v1/receipt.json'))
    builders=[ROOT.parent/'experiments'/n for n in ('build_jucars_bvival_manifest.py','build_mucars_bvival_manifest.py')]
    pinned=json.loads((ROOT/'notes/source-reproduction-inputs-v1.json').read_text())
    for path in builders:
        if sha(path)!=pinned['builder_sha256'][path.name]:raise ValueError('Builder binding changed')
    pairs=[(path,Path('sav-val')/path.relative_to(ROOT)) for path in files]
    pairs.extend((path,Path('experiments')/path.name) for path in builders)
    if len({relative.as_posix() for _,relative in pairs})!=len(pairs):raise ValueError('Duplicate package entry')
    if any(not path.is_file() for path,_ in pairs):raise FileNotFoundError('Package input missing')
    output.mkdir(parents=True);hashes={}
    for path,relative in pairs:
        destination=output/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        digest=sha(path);shutil.copyfile(path,destination)
        if sha(path)!=digest or sha(destination)!=digest:raise ValueError('Package bytes changed')
        hashes[relative.as_posix()]=digest
    full_extensions=bool(args.journal_draft and build.get('all_scheduled_extensions_in_manuscript',False))
    remaining=('final combined reproduction/QA, venue selection and final author scope'
               if full_extensions else
               'full equal-trial size matrix, robust-benefit allowance extension, final evidence freeze/QA and venue selection')
    manifest={'status':'development_source_package','files':hashes,'script_sha256':sha(Path(__file__)),
        'all_scheduled_extensions_in_reviewed_manuscript':full_extensions,
        'reviewed_manuscript_evidence_maps':{str(path.relative_to(ROOT)):sha(path) for path in current_maps} if args.journal_draft else {},
        'scope':'runnable source code, pinned source builders/input hashes, manuscript and bounded evidence mappings',
        'exclusions':'raw source CSVs and original fitted models/outcomes are not bundled; obtain raw data and run fresh commands',
        'remaining':remaining}
    (output/'package_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zipped:
        for path in sorted(output.rglob('*')):
            if path.is_file():zipped.write(path,output.name/path.relative_to(output))
    receipt=output.with_name(output.name+'-receipt.json')
    receipt.write_text(json.dumps({'status':'created','archive':archive.name,'archive_sha256':sha(archive),
        'file_count':len(hashes),'manifest_sha256':sha(output/'package_manifest.json'),
        'scope':manifest['scope'],'remaining':manifest['remaining']},indent=2,sort_keys=True)+'\n')
    print(json.dumps({'archive':str(archive),'files':len(hashes),'bytes':archive.stat().st_size}),flush=True)

if __name__=='__main__':main()
