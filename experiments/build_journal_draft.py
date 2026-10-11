"""Flatten audited development material into an eight-display journal draft."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile


DEFAULT_EVIDENCE_RECEIPTS = (
    'manuscript-main-evidence-revision17.json',
    'manuscript-followup-evidence-revision27.json',
    'manuscript-equal-benefit-evidence-revision29.json',
    'manuscript-comparator-resource-evidence-revision10.json',
    'manuscript-diagnostics-evidence-revision06.json',
    'manuscript-robust-benefit-evidence-revision11.json',
    'manuscript-cdm-deviation-evidence-revision17.json',
)
EVIDENCE_FAMILIES = tuple(name.split('-revision')[0] for name in DEFAULT_EVIDENCE_RECEIPTS)


def extension_scope(receipts):
    """Only matching complete table receipts can remove the pending qualifier."""
    families = [path.name.split('-revision')[0] for path in receipts]
    if len(families) != 7 or set(families) != set(EVIDENCE_FAMILIES):
        raise ValueError('Exactly one receipt from each of the seven evidence families required')
    records = {family: json.loads(path.read_text())
               for family, path in zip(families, receipts)}
    tuning = records['manuscript-followup-evidence']
    benefit = records['manuscript-equal-benefit-evidence']
    tuning_complete = tuning.get('all_scheduled_tuning_cases_in_manuscript', False)
    benefit_complete = benefit.get('all_scheduled_reference_cases_in_manuscript', False)
    expected = {(source, cap) for source in ('synthetic', 'jucars', 'mucars')
                for cap in (1000, 2500, 5000)}
    if tuning_complete:
        assert tuning['retained_tuning_cells'] == 972
        assert {tuple(row) for row in tuning['completed_tuning_source_caps']} == expected
        assert not tuning['unfinished_tuning_source_caps']
    if benefit_complete:
        assert benefit['reference_cells_in_statistics'] == 324
        assert {tuple(row) for row in benefit['completed_source_caps']} == expected
        assert not benefit['incomplete_captured_source_caps']
    return bool(tuning_complete and benefit_complete)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def author_block(path):
    if path is None:
        return r'\author{Anonymous development manuscript}', ''
    record = json.loads(path.read_text())
    assert record['status'] == 'supplied_chinese_metadata_with_provisional_english_rendering'
    assert record['english_names_and_department_translation_provisional'] is True
    # This title page labels the email as a general contact; it does not assign
    # the unidentified corresponding author or invent any declarations.
    def safe(value):
        assert not re.search(r'[\\{}%$&#_^~]', value), 'Plain author metadata required'
        return value
    names = record['authors_in_supplied_order']
    assert len(names) == 3
    lines = [r'\author[1]{\fnm{'+safe(name['given_name'])+r'} \sur{'+
             safe(name['family_name'])+'}}' for name in names]
    lines.append(r'\affil[1]{\orgdiv{'+safe(record['department_english'])+
                 r'}, \orgname{'+safe(record['institution_english'])+
                 r'}, \orgaddress{\city{'+safe(record['city'])+
                 r'}, \country{'+safe(record['country'])+'}}}')
    note = (r'\noindent\textit{Working draft. English author names and the department '
            'translation are provisional.} '+r'Contact: \texttt{'+
            safe(record['contact_email'])+r'}.\par'+'\n')
    return '\n'.join(lines), note


def conference_style_fix(original):
    """Keep the official style intact; repair its conference booktitle stack."""
    data = original.read_bytes()
    start = data.index(b'FUNCTION {format.in.ed.booktitle}')
    end = data.index(b'FUNCTION {empty.misc.check}', start)
    old = data[start:end].replace(b'\r\n', b'\n')
    expected = b'''FUNCTION {format.in.ed.booktitle}
{  duplicate$ empty$ 'skip$
    { 
editor "editor" format.names.ed duplicate$ empty$ 'pop$
        {  
format.booktitle swap$
"(" editor num.names$ #1 > 'bbl.in.editors 'bbl.editor if$  * swap$   ") " *
          * swap$
          * }
      if$ 
    }  
  if$
}
'''
    assert old == expected, 'Pinned official conference function required'
    replacement = b'''FUNCTION {format.in.ed.booktitle}
{ booktitle empty$
    { "" }
    { format.booktitle
      editor empty$
        'skip$
        { " (" * editor "editor" format.names.ed *
          ", " * editor num.names$ #1 > 'bbl.in.editors 'bbl.editor if$ *
          ")" * }
      if$
    }
  if$
}
'''
    if b'\r\n' in data:
        replacement = replacement.replace(b'\n', b'\r\n')
    return data[:start]+replacement+data[end:]


def expand(path, paper):
    text = Path(path).read_text()
    return re.sub(r'\\input\{([^}]+)\}',
                  lambda match: expand(paper/(match[1]+'.tex'), paper), text)


def table(text, label, fit_displays=False):
    tables = re.findall(r'\\begin\{table\*\}.*?\\end\{table\*\}', text, re.S)
    selected = [block for block in tables if r'\label{'+label+'}' in block]
    if len(selected) != 1:
        raise ValueError('Exactly one source table required: '+label)
    # The official class wraps unstarred tables in threeparttable; that
    # measuring hook conflicts with resizebox. Its ordinary starred float
    # preserves the caption styling without that extra measuring group.
    text = selected[0]
    if label == 'tab:equal_benefit_reference':
        # Keep one display/caption while separating nine columns into two
        # stacked panels. All original numeric cells remain present.
        match = re.search(r'\\begin\{tabular\}\{[^}]+\}(.*?)\\end\{tabular\}', text, re.S)
        assert match
        inflation, errors = [], []
        for line in match[1].splitlines():
            if '&' not in line:
                inflation.append(line); errors.append(line); continue
            assert line.endswith(r'\\')
            values = [value.strip() for value in line[:-2].split('&')]
            assert len(values) == 9, 'Nine complete source columns'
            inflation.append(' & '.join(values[:7])+r'\\')
            errors.append(' & '.join(values[:3]+values[7:])+r'\\')
            assert values[:7]+(values[:3]+values[7:])[3:] == values
        panels = (r'\textbf{Inflation and paired interval}\par\smallskip'+'\n'+
                  r'\resizebox{\linewidth}{!}{\begin{tabular}{lrlrrrr}'+'\n'+
                  '\n'.join(inflation)+'\n'+r'\end{tabular}}'+'\n'+
                  r'\par\medskip\textbf{Native-price error changes}\par\smallskip'+'\n'+
                  r'\begin{tabular}{lrlrr}'+'\n'+'\n'.join(errors)+'\n'+r'\end{tabular}')
        if fit_displays:
            panels = (r'\sbox0{\begin{minipage}{\linewidth}'+'\n'+panels+'\n'+
                      r'\end{minipage}}'+'\n'+
                      r'\ifdim\dimexpr\ht0+\dp0\relax>.72\textheight'+'\n'+
                      r'\resizebox*{!}{.72\textheight}{\usebox0}'+'\n'+
                      r'\else\usebox0\fi')
        return text[:match.start()]+panels+text[match.end():]
    # Keep every numeric cell; resize the vector table to the journal text width.
    text = text.replace(r'\begin{tabular}', r'\resizebox{\linewidth}{!}{\begin{tabular}')
    return text.replace(r'\end{tabular}', r'\end{tabular}}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--paper', type=Path, default=Path('paper'))
    parser.add_argument('--journal-figures', type=Path)
    parser.add_argument('--training-size-figures', type=Path,
                        help='Reviewed paired-effect bundle; adds two supplementary figures only')
    parser.add_argument('--evidence-receipts', type=Path, nargs=7,
                        help='Seven matching immutable manuscript evidence receipts')
    parser.add_argument('--author-metadata', type=Path,
                        help='Supplied author order/contact, with provisional English renderings')
    parser.add_argument('--conference-style-fix', action='store_true',
                        help='Use separately named conference-booktitle stack repair; retain official style')
    parser.add_argument('--fit-journal-displays', action='store_true',
                        help='Bound journal figure and two-panel reference-table heights; retain every cell')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); paper, output = args.paper.resolve(), args.output.resolve()
    if output.exists():
        raise ValueError('Fresh journal generation required')
    receipts = (args.evidence_receipts or
                [Path('notes')/name for name in DEFAULT_EVIDENCE_RECEIPTS])
    full_extensions = extension_scope(receipts)
    for path in receipts:
        record = json.loads(path.read_text())
        for name, digest in record.get('sections', {}).items():
            assert sha(paper/'sections'/name) == digest, (path, name)
        if 'section_sha256' in record:
            # Receipt locations record where the first draft was emitted.
            # Verify the corresponding current package section after relocation.
            section = paper/'sections'/Path(record.get('section', 'saved_model_diagnostics.tex')).name
            assert sha(section) == record['section_sha256'], path
        if 'main-evidence' in path.name:
            assert sha(paper/'sections/results_development.tex') == record['source_sha256']
        if 'robust-benefit-evidence' in path.name:
            assert sha(paper/'sections/robust_benefit_reference_results.tex') == record['source_sha256']
    template = Path('notes/venue-assets/springer-nature-december-2024-template.zip')
    retrieval = json.loads(template.with_name('springer-template-retrieval.json').read_text())
    assert sha(template) == retrieval['sha256']
    output.mkdir(parents=True)
    with zipfile.ZipFile(template) as package:
        for member, name in [('sn-article-template/sn-jnl.cls', 'sn-jnl.cls'),
                             ('sn-article-template/bst/sn-nature.bst', 'sn-nature.bst'),
                             ('sn-article-template/user-manual.pdf', 'template-user-manual.pdf')]:
            (output/name).write_bytes(package.read(member))
    shutil.copyfile(template, output/template.name)
    shutil.copyfile(paper/'ref.bib', output/'ref.bib')
    bibliography_style = 'sn-nature'
    if args.conference_style_fix:
        bibliography_style = 'sn-nature-compatible'
        (output/(bibliography_style+'.bst')).write_bytes(
            conference_style_fix(output/'sn-nature.bst'))
    journal_figures = (args.journal_figures.resolve() if args.journal_figures
                       else paper/'figures/journal-legible-v3')
    figure_receipt = journal_figures/'figure_receipt.json'
    figure_record = json.loads(figure_receipt.read_text())
    assert figure_record['status'] == 'completed'
    for name, digest in figure_record['files'].items():
        assert sha(journal_figures/name) == digest, ('Journal figure binding', name)
    figures = [('missingness_example.pdf', 'fig:missingness',
                'At a fixed rule realization, identical public inputs require identical query decisions. '
                'Identifiers and peer reports remain fixed across these alternative hidden states. '
                'The private recorded state determines replay success; both outcomes consume capacity. '
                'The illustrative mileage is not an observed fraud label or physical inspection.'),
               ('sav_val_overview.pdf', 'fig:overview',
                'Nested target construction, deployment fitting and online allocation. '
                'Each held-out outcome remains outside its corresponding fitting and feedback loop. '
                'Teacher and deployment sample sizes differ; runtime inputs are public reports.'),
               ('capacity_frontiers.pdf', 'fig:capacity',
                'The SAV-Val comparison with static robust pricing depends on source and capacity. '
                'Rows are sources; left: means and sample standard deviations across three fitted seeds. '
                'Right: static robust control minus SAV-Val inflation, with unadjusted conditional '
                r'95\% shared-batch intervals. Paired seed contrasts are averaged before resampling '
                r'ten common batches. The vertical line marks the primary 10\% capacity.'),
               ('cdm_capacity_frontiers_full.pdf', 'fig:cdm_capacity',
                'CDM does not consistently reduce inflation relative to risk priority. '
                'Rows are sources; left: mask-aware pricing; right: robust pricing. Points average three fitting seeds; '
                'bars are their sample standard deviations. Every preset capacity is retained. '
                'These rule comparisons do not constitute a matched feedback-estimator comparison.')]
    display_blocks = []
    graphic_options = (r'width=\linewidth,height=.72\textheight,keepaspectratio'
                       if args.fit_journal_displays else r'width=\linewidth')
    for name, label, caption in figures:
        shutil.copyfile(journal_figures/name, output/name)
        shutil.copyfile(paper/'figures'/name, output/('sup_'+name))
        display_blocks.append(r'\begin{figure}[p]'+'\n'+r'\centering'+'\n'+
                              r'\includegraphics['+graphic_options+']{'+name+'}\n'+
                              r'\caption{'+caption+'}\n'+r'\label{'+label+'}\n'+r'\end{figure}')
    table_sources = [('results_development.tex', 'tab:synthetic_development'),
                     ('robust_benefit_reference_results.tex', 'tab:robust_benefit_reference'),
                     ('cdm_development_results.tex', 'tab:cdm_development'),
                     ('equal_benefit_reference_results.tex', 'tab:equal_benefit_reference')]
    for name, label in table_sources:
        display_blocks.append(table((paper/'sections'/name).read_text(), label,
                                    fit_displays=args.fit_journal_displays))
    prose = (paper/'journal-main-prose.tex').read_text()
    methods = (paper/'journal-methods-prose.tex').read_text()
    abstract = r'''Development version; follow-up experiments remain incomplete. We study
budgeted verification when sellers can withhold recorded vehicle attributes.
Public absence does not identify concealment, and one seller's report can
displace another's query.
SAV-Val combines missingness-aware prediction, suppression-value acquisition
and nested policy-aware training. CDM-Val optimizes a distribution over
complete verification rules against finite, batch-reallocated unilateral
payoff rows. Queries use publicly absent fields, and failed recorded-value
replay consumes capacity. In the complete three-source, three-seed main study
at 10\% capacity, SAV-Val has 11.42\% less positive log-quote inflation than
the ordinary-benefit static robust reference on MUCars, but more inflation
on synthetic and Jordanian cohorts. Its feedback component comparisons are
also heterogeneous. The complete fixed-estimator CDM study does not establish
a consistent advantage over a simple risk rule. Equal-allowance retraining,
declared comparator adaptations, common-report transfer and missingness
diagnostics further restrict general improvement claims. Honest and attacked
valuation error remain necessary alongside incentive measures. The evidence
concerns historical advertised prices and stipulated responses, rather than
transactions, observed concealment or physical inspection.'''
    if full_extensions:
        abstract = abstract.removeprefix(
            'Development version; follow-up experiments remain incomplete. ')
        benefit_record = next(json.loads(path.read_text()) for path in receipts
                              if 'equal-benefit-evidence' in path.name)
        largest = {row['dataset']: row for row in benefit_record['evidence']
                   if row['role'] == 'tuned' and row['train_cap'] == 5000
                   and row['metric'] == 'positive_log_inflation'}
        assert set(largest) == {'synthetic', 'jucars', 'mucars'}
        assert largest['mucars']['relative_reduction_percent'] > 0
        assert all(largest[source]['relative_reduction_percent'] < 0
                   for source in ('synthetic', 'jucars'))
        matched = (f"Complete equal-allowance retraining at the largest cap yields "
                   f"{largest['mucars']['relative_reduction_percent']:.2f}\\% less inflation "
                   f"on MUCars but {-largest['synthetic']['relative_reduction_percent']:.2f}\\% "
                   f"and {-largest['jucars']['relative_reduction_percent']:.2f}\\% more "
                   "on synthetic and Jordanian cohorts against ordinary-benefit pricing. "
                   "Comparator adaptations, common-report transfer and missingness "
                   "diagnostics further restrict general improvement claims.")
        abstract = abstract.replace(
            'Equal-allowance retraining,\n'
            'declared comparator adaptations, common-report transfer and missingness\n'
            'diagnostics further restrict general improvement claims.', matched)
    assert len(abstract.split()) <= 200
    title = 'Budgeted verification under strategic withholding in used vehicle valuation'
    assert len(title.split()) <= 20
    authors, author_note = author_block(args.author_metadata)
    text = (r'''\documentclass[pdflatex,sn-nature]{sn-jnl}
\usepackage{amsmath,amssymb,booktabs,graphicx,url}
\begin{document}
\title{Budgeted verification under strategic withholding in used vehicle valuation}
''' + authors + '\n'+r'\abstract{' + abstract + r'''}
\keywords{Strategic missingness, Vehicle valuation, Feature acquisition, Verification, Robust prediction, Counterfactual deviations}
\maketitle
''' + author_note + prose + '\n'+r'\section{Methods}'+'\n'+methods+'\n'+
           expand(paper/'sections/data_code_availability.tex', paper)+'\n'+
           r'\bibliography{ref}'+'\n'+r'\clearpage'+'\n'+'\n'.join(display_blocks)+'\n'+r'\end{document}'+'\n')
    assert len(re.findall(r'\\begin\{figure\}', text)) == 4
    assert len(re.findall(r'\\begin\{table\*\}', text)) == 4
    assert re.search(r'\\title\{([^}]+)\}', text)[1] == title
    keyword_count = len(re.search(r'\\keywords\{([^}]+)\}', text)[1].split(','))
    assert keyword_count <= 6
    assert r'\input{' not in text and 'figures/' not in text
    (output/'main.tex').write_text(text)
    if args.conference_style_fix:
        # The class schedules its bibliography style while loading. Redirect
        # that one call, then immediately restore LaTeX's original command.
        class_line = r'\documentclass[pdflatex,sn-nature]{sn-jnl}'
        redirected = (r'\let\SAVbibliographystyle\bibliographystyle'+'\n'+
                      r'\def\bibliographystyle#1{\SAVbibliographystyle{'+
                      bibliography_style+'}}'+'\n'+class_line+'\n'+
                      r'\let\bibliographystyle\SAVbibliographystyle')
        text = text.replace(class_line, redirected, 1)
        (output/'main.tex').write_text(text)
    supplement = expand(paper/'main.tex', paper).replace('figures/', '')
    for name, _, _ in figures:
        supplement = supplement.replace('{'+name+'}', '{sup_'+name+'}')
    supplement = supplement.replace(r'\title{Budgeted Verification against Strategic Withholding in Second-Hand Valuation}',
                                    r'\title{Supplementary Information: Budgeted verification under strategic withholding in used vehicle valuation}')
    supplement = supplement.replace(r'\begin{document}', r'''\renewcommand{\thetable}{S\arabic{table}}
\renewcommand{\thefigure}{S\arabic{figure}}
\begin{document}''', 1)
    supplementary_inputs = []
    if args.training_size_figures:
        bundle = args.training_size_figures.resolve()
        qa = json.loads((bundle/'qa_receipt.json').read_text())
        assert qa['status'] == 'completed', 'Reviewed training-size figure bundle required'
        for name, digest in qa['files'].items():
            assert sha(bundle/name) == digest, ('Supplementary figure binding', name)
        rendered = json.loads((bundle/'render_receipt.json').read_text())
        if full_extensions:
            assert rendered['all_scheduled_cases_complete']
            assert rendered['tuning_cells'] == 972 and rendered['benefit_cells'] == 324
        captured = (f"The captured evidence contains {rendered['tuning_cells']} of 972 tuning "
                    f"cells and {rendered['benefit_cells']} of 324 ordinary-BEN cells. ")
        if full_extensions:
            captured = ('All 972 scheduled tuning cells and all 324 ordinary-BEN '
                        'cells are included. ')
        pending = ('Missing points denote pending audited cohorts; '
                   if not rendered['all_scheduled_cases_complete'] else '')
        supplementary_inputs = [bundle/'qa_receipt.json',
                                *(bundle/name for name in qa['files'])]
        blocks = []
        for role in ('tuned', 'fixed'):
            name = f'training_size_{role}.pdf'
            shutil.copyfile(bundle/name, output/name)
            caption = ('Training-size effects vary with source and reference under '+
                ('equal-budget tuned' if role == 'tuned' else 'fixed-weight')+
                r' SAV-Val at the primary 10\% query capacity. '
                'Rows stratify sources; columns show positive log-quote inflation, honest MAE and attacked MAE. '
                'Every signed contrast is reference minus SAV, so positive values favor SAV. '
                'Inflation contrasts are in millilog units; MAE retains source-native price units. '
                r'Centers average three fitted-seed paired contrasts; bars are unadjusted 95\% '
                'bootstrap intervals from ten shared evaluation batches, conditional on fitted models. '
                'They do not represent training-population uncertainty. Reference positions are offset by '
                '60 training records for visibility. '+captured+pending+
                'All adverse effects remain visible.')
            blocks.append(r'\begin{figure*}[p]'+'\n'+r'\centering'+'\n'+
                          r'\includegraphics[width=.98\textwidth]{'+name+'}\n'+
                          r'\caption{'+caption+'}\n'+r'\label{fig:training_size_'+role+'}\n'+
                          r'\end{figure*}'+'\n'+r'\clearpage')
        supplement = supplement.replace(r'\end{document}',
                                        r'\clearpage'+'\n'+'\n'.join(blocks)+'\n'+r'\end{document}')
    assert r'\input{' not in supplement
    (output/'supplement.tex').write_text(supplement)
    inputs = [paper/'main.tex', paper/'journal-main-prose.tex', paper/'journal-methods-prose.tex',
              paper/'ref.bib', template, *receipts,
              *list((paper/'sections').glob('*.tex')), *list((paper/'figures').glob('*.pdf'))]
    inputs.extend([figure_receipt, *list(journal_figures.glob('*.pdf')),
                   *list(journal_figures.glob('*.csv'))])
    inputs.extend(supplementary_inputs)
    if args.author_metadata:
        inputs.append(args.author_metadata)
    record = {'status': 'built_uncompiled_development', 'main_display_items': 8,
              'supplement_extra_display_items': 2 if supplementary_inputs else 0,
              'supplement_figure_bundle': str(bundle.relative_to(paper)) if supplementary_inputs else None,
              'abstract_words_by_whitespace': len(abstract.split()),
              'title_words_by_whitespace': len(title.split()),
              'keywords': keyword_count,
              'main_prose_words_by_whitespace': len(prose.split()),
              'methods_words_by_whitespace': len(methods.split()),
              'input_hashes': {str(p.resolve()): sha(p) for p in inputs},
              'builder_sha256': sha(Path(__file__)),
              'all_scheduled_extensions_in_manuscript': full_extensions,
              'evidence_receipts': {str(path.resolve()): sha(path) for path in receipts},
              'author_metadata_sha256': sha(args.author_metadata) if args.author_metadata else None,
              'bibliography_style': bibliography_style,
              'conference_style_repair': bool(args.conference_style_fix),
              'display_height_bounds': bool(args.fit_journal_displays),
              'files': {p.name: sha(p) for p in output.iterdir() if p.is_file()},
              'scope': 'conditional Scientific Reports-style main article and complete technical supplement; '
                       'not a certified Q3 venue, prospective market study or submission-ready package'}
    (output/'build_receipt.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
    print('Built flat eight-display main article and full technical supplement.', flush=True)


if __name__ == '__main__':
    main()
