"""Bind frozen-model sensitivity, closure and technical-stratum paper tables."""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from analyze_nested import read, require, sha
from backfill_development_tables import replace_table
from run_all import write_json

def main():
    parser = argparse.ArgumentParser()
    for name in ('run', 'audit', 'section', 'receipt'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    require(not args.receipt.exists(), 'Fresh evidence receipt')
    done, audit = read(args.run/'completion.json'), read(args.audit/'analysis_completion.json')
    require(done['status'] == audit['status'] == 'completed', 'Completed source and audit')
    require(audit['diagnostic_completion_sha256'] == sha(args.run/'completion.json'), 'Audit input binding')
    require(audit['audited_cells'] == 225, 'Complete sensitivity matrix')
    for name, digest in audit['outputs'].items():
        require(sha(args.audit/name) == digest, 'Audited output changed')
    require(sha(args.run/'source_missing_groups.csv') == done['group_sha256'], 'Stratum binding')
    sources = {'synthetic':'Synthetic', 'jucars':'JUCars', 'mucars':'MUCars'}
    require({tuple(p) for p in done['completed_source_seed_pairs']} ==
            {(d,s) for d in sources for s in (13,42,2026)}, 'All source seeds required')
    comparisons = pd.read_csv(args.audit/'paired_sensitivity_comparisons.csv')
    closure = pd.read_csv(args.audit/'closure_tradeoffs.csv')
    strata = pd.read_csv(args.run/'source_missing_groups.csv', dtype={'source_missing_group':str})
    text, evidence = args.section.read_text(), []
    settings = {'main-cost0-h2':'Primary: cost 0, H=2', 'cost-0.02':'Cost 0.02 / field',
        'cost-0.05':'Cost 0.05 / field', 'hidden-1':'H=1', 'hidden-3-ood':'H=3, without retraining',
        'added-natural-0.10':'Added natural missingness 10\\%',
        'added-natural-0.30':'Added natural missingness 30\\%'}
    rows = []
    for setting, label in settings.items():
        values = []
        for dataset in sources:
            cell = comparisons[(comparisons.dataset==dataset)&(comparisons.scenario==setting)&
                               (comparisons.reference=='robust_no_feedback')]
            require(len(cell)==1 and cell.iloc[0].training_seeds==3, 'Unique complete sensitivity contrast')
            row = cell.iloc[0]
            values.extend([f'{row.sav_inflation:.5f}', f'{row.reference_inflation:.5f}'])
            evidence.append({'table':'sensitivity', **row.to_dict()})
        rows.append(label+' & '+' & '.join(values)+'\\\\')
    text = replace_table(text, 'tab:frozen_sensitivities', rows)
    rows = []
    for dataset, label in sources.items():
        cell = closure[closure.dataset==dataset]
        require(len(cell)==1 and cell.iloc[0].closure_inflation==0, 'Complete zero-uplift diagnostic')
        row = cell.iloc[0]
        rows.append(f'{label} & {row.backbone_honest_mae:.2f} & {row.closure_honest_mae:.2f} & '
                    f'{row.mean_honest_log_quote_lift:.5f} & {row.closure_signed_log_bias:.5f} & 0\\\\')
        evidence.append({'table':'closure', **row.to_dict()})
    text = replace_table(text, 'tab:closure_tradeoffs', rows)
    rows = []
    for dataset, label in sources.items():
        groups = strata[strata.dataset==dataset].source_missing_group.unique()
        for group in sorted(groups, key=lambda g:int(g.rstrip('+'))):
            for i,(method, method_label) in enumerate([('robust_no_feedback','Robust'), ('sav_val','SAV-Val')]):
                cell = strata[(strata.dataset==dataset)&(strata.source_missing_group==group)&(strata.method==method)]
                require(set(cell.seed)=={13,42,2026} and len(cell)==3, 'Complete technical stratum seeds')
                require(cell.n.nunique()==1, 'Stratum membership stable across fitting seeds')
                values = cell[['n','honest_mae','attacked_mae','mean_positive_log_inflation',
                               'query_fraction','failed_query_fraction']].mean()
                rows.append(f'{label if i==0 else ""} & {group if i==0 else ""} & '
                            f'{int(values.n) if i==0 else ""} & {method_label} & '
                            f'{values.honest_mae:.2f} & {values.attacked_mae:.2f} & '
                            f'{values.mean_positive_log_inflation:.5f} & '
                            f'{100*values.query_fraction:.2f} & {100*values.failed_query_fraction:.2f}\\\\')
                evidence.append({'table':'technical_stratum','dataset':dataset,'group':group,
                                 'method':method, **values.to_dict()})
        if dataset!='mucars':rows.append('\\midrule')
    text = replace_table(text, 'tab:technical_strata', rows)
    args.section.write_text(text)
    write_json(args.receipt, {'audit_completion_sha256':sha(args.audit/'analysis_completion.json'),
        'source_completion_sha256':sha(args.run/'completion.json'),'evidence':evidence,
        'section_sha256':sha(args.section),'script_sha256':sha(Path(__file__)),
        'scope':'all seven settings, three-source closure and all observed technical strata; three seeds; retrospective'})
    print('Backfilled complete sensitivity, closure and technical-stratum tables.', flush=True)

if __name__=='__main__':main()
