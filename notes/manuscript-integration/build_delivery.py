"""Package existing audited evidence and the reviewed manuscript; no training."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'notes/manuscript-integration'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def archive(path, members):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for member in sorted(set(members)):
            z.write(member, member.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        for member in set(members):
            assert hashlib.sha256(z.read(member.relative_to(ROOT).as_posix())).hexdigest() == digest(member)


qa = json.loads((HERE / 'qa/render-audit.json').read_text())
assert qa['all_page_visual_review'] == 'completed'
assert qa['pages'] == 26 and qa['missing_citations'] == qa['missing_refs'] == []
assert qa['source_sha256'] == digest(ROOT / 'paper/innovation-addendum-v1.tex')
assert qa['pdf_sha256'] == digest(ROOT / 'paper/innovation-addendum-v1.pdf')

# Validate the previously released complete six-capacity analysis archive.
evidence_index = ROOT / 'notes/factorial-final/EVIDENCE_INDEX.json'
evidence = json.loads(evidence_index.read_text())
analysis_zip = evidence_index.parent / evidence['archive']
assert digest(analysis_zip) == evidence['archive_sha256']
with zipfile.ZipFile(analysis_zip) as z:
    for row in evidence['contents']:
        assert hashlib.sha256(z.read(row['archive_path'])).hexdigest() == row['sha256']

# Include all top-level aggregate comparisons, receipts and snapshots for
# Appendix E, including unfavorable budgets, sizes and declared sensitivities.
folders = [
    'grouped-smi-development-v2-interval-cached-audit',
    'aco1-development-v2-audit',
    'robust-benefit-reference-v1-audit',
    'equal-benefit-size-reference-development-v1-contrasts-full-01',
    'equal-benefit-size-reference-development-v1-audit-full-01',
    'equal-tuning-size-development-v1-audit-full-01',
]
legacy_members = []
verified = []
for name in folders:
    directory = ROOT / 'outputs' / name
    receipts = list(directory.glob('*completion.json'))
    assert len(receipts) == 1, name
    record = json.loads(receipts[0].read_text())
    assert record['status'] == 'completed', name
    for key in ('files', 'outputs'):
        for filename, expected in record.get(key, {}).items():
            path = directory / filename
            if path.exists():
                assert digest(path) == expected, str(path)
                verified.append(str(path.relative_to(ROOT)))
    legacy_members += [p for p in directory.iterdir() if p.is_file() and p.suffix in {'.csv', '.json', '.md', '.py'}]
for name in ('grouped-smi-development-v2', 'aco1-development-v2', 'robust-benefit-reference-v1',
             'equal-benefit-size-reference-development-v1', 'equal-tuning-size-development-v1'):
    directory = ROOT / 'outputs' / name
    legacy_members += [directory / filename for filename in ('summary.csv', 'completion.json', 'run_manifest.json') if (directory / filename).exists()]

legacy_zip = HERE / 'additional-comparator-evidence.zip'
archive(legacy_zip, legacy_members)
write_json(HERE / 'additional-comparator-evidence-index.json', {
    'scope': 'all archived aggregate results and completion receipts for Appendix E; no new experiment',
    'archive_sha256': digest(legacy_zip),
    'receipt_bound_files_verified': verified,
    'contents': [{'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in sorted(set(legacy_members))],
    'excluded': 'raw listing outcomes, fitting records and model weights; not external full reproduction',
})

members = [ROOT / 'paper/innovation-addendum-v1.tex', ROOT / 'paper/innovation-addendum-v1.pdf',
           ROOT / 'paper/innovation-addendum-v1.log', analysis_zip, evidence_index,
           ROOT / 'notes/build_factorial_final_report.py', ROOT / 'notes/factorial-final/requirements-report.txt',
           ROOT / 'notes/factorial-final/RESULTS.zh.md', ROOT / 'notes/factorial-final/report_provenance.json',
           ROOT / 'notes/factorial-final/QA.json', ROOT / 'notes/factorial-final/figure-source-audit.json',
           ROOT / 'notes/citation-verification.csv', ROOT / 'notes/venue-evidence-2026-10-07-v1.md']
members += [p for p in (ROOT / 'paper/figures/factorial-final').iterdir() if p.suffix in {'.pdf', '.svg', '.csv'}]
members += [p for p in HERE.iterdir() if p.is_file() and p.suffix in {'.py', '.tex', '.csv', '.md', '.zip', '.json'}
            and p.name not in {'delivery_manifest.json', 'delivery_receipt.json', 'github-sync-receipt.json'}]
members += [p for p in (HERE / 'qa').iterdir() if p.suffix in {'.json', '.pdf'} and p.name != 'pre-final-page-hashes.json']
members = sorted(set(members))
manifest = {
    'scope': 'reviewed scientific manuscript with author/affiliation omitted; not an actual submission',
    'pages': 26,
    'files': [{'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in members],
    'analysis_archive_verified': True,
    'additional_comparator_receipt_bound_files_verified': len(verified),
    'full_external_training_reproduction': False,
}
write_json(HERE / 'delivery_manifest.json', manifest)
members.append(HERE / 'delivery_manifest.json')
packet = ROOT / 'paper/manuscript-delivery-v1.zip'
archive(packet, members)
receipt = {'archive': str(packet.relative_to(ROOT)), 'bytes': packet.stat().st_size,
           'sha256': digest(packet), 'contents': len(members), 'member_checksums_verified': True,
           'scientific_manuscript_complete': True, 'submission_complete': False}
write_json(HERE / 'delivery_receipt.json', receipt)
print(json.dumps(receipt))
