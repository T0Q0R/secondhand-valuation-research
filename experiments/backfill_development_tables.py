"""Bind two current development-draft tables to independently audited CSVs."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from analyze_nested import read, require, sha
from run_all import write_json


def decimal(value, digits=5):
    return f"{value:.{digits}f}".removeprefix("0")


def inflation(value):
    if value == 0:
        return "0"
    if value < .0001:
        mantissa, exponent = f"{value:.2e}".split("e")
        return f"${mantissa}\\!\\times\\!10^{{{int(exponent)}}}$"
    return decimal(value)


def replace_table(text, label, rows):
    matches = list(re.finditer(r"\\begin\{table\*\}.*?\\end\{table\*\}", text, flags=re.S))
    selected = [m for m in matches if f"\\label{{{label}}}" in m.group()]
    require(len(selected) == 1, "Unique labeled table required")
    match = selected[0]
    table = match.group()
    start, end = table.index("\\midrule") + len("\\midrule"), table.index("\\bottomrule")
    table = table[:start] + "\n" + "\n".join(rows) + "\n" + table[end:]
    return text[:match.start()] + table + text[match.end():]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--numeric-audit", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--sources", nargs="+", choices=("synthetic", "jucars", "mucars"),
                        default=["synthetic", "jucars"])
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    require(len(set(args.sources)) == len(args.sources), "Unique source selection")
    if args.receipt:
        require(not args.receipt.exists(), "Fresh manuscript evidence receipt required")
    main_receipt = read(args.audit / "analysis_completion.json")
    numeric_receipt = read(args.numeric_audit / "analysis_completion.json")
    require(sha(args.audit / "method_seed_summary.csv") == main_receipt["outputs"]["method_seed_summary.csv"], "Main summary hash")
    require(sha(args.numeric_audit / "rechecked_summary.csv") == numeric_receipt["outputs"]["rechecked_summary.csv"], "Numerical summary hash")
    require(main_receipt["run_binding"] == numeric_receipt["parent_binding"], "Same parent binding")
    main_table = pd.read_csv(args.audit / "method_seed_summary.csv")
    numeric_table = pd.read_csv(args.numeric_audit / "rechecked_summary.csv")
    source_names = {"synthetic": "Synthetic", "jucars": "JUCars", "mucars": "MUCars"}
    methods = {"masking_benefit": "Mask + benefit", "robust_no_feedback": "Robust, no feedback",
               "sav_benefit_head": "SAV + benefit output", "sav_val": "SAV-Val"}
    rows = []
    evidence = []
    for s, source in enumerate(args.sources):
        pairs = [p for p in main_receipt["completed_source_seed_pairs"] if p[0] == source]
        require({p[1] for p in pairs} == {13, 42, 2026}, "Three complete source seeds")
        if s:
            rows.append("\\midrule")
        for k, (method, label) in enumerate(methods.items()):
            cell = main_table[(main_table.dataset == source) & (main_table.method == method) & (main_table.budget == .1)]
            require(len(cell) == 1, "Unique main summary cell")
            row = cell.iloc[0]
            name = source_names[source] if k == 0 else ""
            rows.append(f"{name} & {label} & {decimal(row.mean_inflation)} ({decimal(row.seed_sd_inflation)}) & {row.mean_clean_mae:.2f} & {row.mean_attack_mae:.2f}\\\\")
            evidence.append({"table": "main", "dataset": source, "method": method,
                             **row.to_dict()})
    text = args.source.read_text()
    text = replace_table(text, "tab:synthetic_development", rows)
    numeric_methods = {"linear_svr_median": "Median SVR", "smi_free_with_fallback": "SMI / free",
                       "smi_nonnegative_with_fallback": "SMI / nonnegative", "smi_unit_box_with_fallback": "SMI / unit box"}
    rows = []
    for s, source in enumerate(source_names):
        if s:
            rows.append("\\midrule")
        for k, (method, label) in enumerate(numeric_methods.items()):
            cell = numeric_table[(numeric_table.dataset == source) & (numeric_table.method == method)]
            require(len(cell) == 1, "Unique numerical summary cell")
            row = cell.iloc[0]
            require(row.n == 1000 and row.fallback_fraction == 0, "Current numerical caption contract")
            name = source_names[source] if k == 0 else ""
            rows.append(f"{name} & {label} & {row.honest_mae:.2f} & {inflation(row.mean_positive_log_inflation)} & {row.imputation_outside_training_range_fraction:g}\\\\")
            evidence.append({"table": "numeric_smi", **row.to_dict()})
    text = replace_table(text, "tab:numeric_smi", rows)
    args.source.write_text(text)
    if args.receipt:
        write_json(args.receipt, {"main_audit_sha256": sha(args.audit / "analysis_completion.json"),
            "numeric_audit_sha256": sha(args.numeric_audit / "analysis_completion.json"),
            "run_binding": main_receipt["run_binding"], "run_complete": main_receipt["run_complete"],
            "sources": args.sources, "evidence": evidence, "script_sha256": sha(Path(__file__)),
            "source_sha256": sha(args.source)})
    print(f"Backfilled {4 * len(args.sources)} main rows and 12 numerical rows from hash-bound independent audits.")


if __name__ == "__main__":
    main()
