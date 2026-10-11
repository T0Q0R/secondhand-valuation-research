"""Paper-sized capacity curves from hash-bound independently audited results."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit, output = args.audit.resolve(), args.output.resolve()
    if output.exists():
        raise FileExistsError("Figure evidence outputs are immutable")
    receipt = json.loads((audit / "analysis_completion.json").read_text())
    for name in ["method_seed_summary.csv", "paired_capacity_frontiers.csv"]:
        if sha(audit / name) != receipt["outputs"][name]:
            raise ValueError("Audited input changed: " + name)
    summary = pd.read_csv(audit / "method_seed_summary.csv")
    paired = pd.read_csv(audit / "paired_capacity_frontiers.csv")
    sources = [s for s in ["synthetic", "jucars", "mucars"] if s in summary.dataset.unique()]
    # Draw only sources whose complete scheduled seed sets were audited.
    complete = paired.groupby("dataset").all_scheduled_seeds_complete.all()
    sources = [s for s in sources if complete.loc[s]]
    if not sources:
        raise ValueError("No complete source seed cohort")
    plt.rcParams.update({"font.family": "DejaVu Serif", "font.size": 8.5,
        "axes.titlesize": 9., "axes.labelsize": 8.5, "xtick.labelsize": 8.,
        "ytick.labelsize": 8., "legend.fontsize": 8.5, "pdf.fonttype": 42, "svg.fonttype": "none"})
    fig, axes = plt.subplots(len(sources), 2, figsize=(7.1, 2.25 * len(sources) + 1.05), squeeze=False)
    styles = {"masking_benefit": ("Mask + benefit", "#E69F00", "^", ":"),
              "robust_no_feedback": ("Robust, no feedback", "#009E73", "s", "--"),
              "sav_benefit_head": ("SAV + benefit output", "#0072B2", "D", "-."),
              "sav_val": ("SAV-Val", "#000000", "o", "-")}
    names = {"synthetic": "Synthetic", "jucars": "JUCars", "mucars": "MUCars"}
    for i, dataset in enumerate(sources):
        left, right = axes[i]
        for method, (label, color, marker, line) in styles.items():
            rows = summary[(summary.dataset == dataset) & (summary.method == method)].sort_values("budget")
            if len(rows) != 6:
                raise ValueError("Incomplete preset capacity curve")
            left.errorbar(100 * rows.budget, rows.mean_inflation, yerr=rows.seed_sd_inflation,
                          label=label, color=color, marker=marker, ls=line, lw=1.15,
                          ms=4., capsize=2., elinewidth=.65)
        rows = paired[(paired.dataset == dataset) & (paired.reference == "robust_no_feedback") &
                      (paired.metric == "positive_log_inflation")].sort_values("budget")
        if len(rows) != 6 or not rows.all_scheduled_seeds_complete.all():
            raise ValueError("Incomplete paired capacity evidence")
        right.axhline(0, color="#777777", lw=.7)
        right.errorbar(100 * rows.budget, rows.difference,
                      yerr=np.stack([rows.difference - rows.lower, rows.upper - rows.difference]),
                      color="#000000", marker="o", ms=4., lw=1.15, capsize=2.)
        for ax in [left, right]:
            ax.axvline(10, color="#999999", lw=.6, ls=":", zorder=0)
            ax.spines[["top", "right"]].set_visible(False)
            ax.set(xlim=(-1., 31.), xticks=[0, 5, 10, 20, 30])
            ax.grid(axis="y", color="#DDDDDD", lw=.4)
            ax.set_xlabel("Available query capacity (%)")
        left.set_title(f"({chr(97 + 2*i)}) {names[dataset]}: mean and seed SD", loc="left")
        right.set_title(f"({chr(98 + 2*i)}) {names[dataset]}: paired batch interval", loc="left")
        left.set_ylabel("Positive log-quote inflation")
        right.set_ylabel("Robust minus SAV-Val inflation")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(.5, .995), columnspacing=1.6)
    fig.subplots_adjust(left=.115, right=.985, bottom=.095, top=.78 if len(sources) == 1 else .845,
                        wspace=.45, hspace=.60)
    output.mkdir(parents=True)
    for extension in ["pdf", "svg", "png"]:
        fig.savefig(output / f"capacity_frontiers.{extension}", dpi=220)
    plt.close(fig)
    (output / "draw_audited_frontiers.py").write_bytes(Path(__file__).read_bytes())
    provenance = {"audit": str(audit), "audit_receipt_sha256": sha(audit / "analysis_completion.json"),
                  "run_binding": receipt["run_binding"], "run_complete": receipt["run_complete"],
                  "sources_with_all_training_seeds": sources,
                  "input_hashes": {name: receipt["outputs"][name] for name in ["method_seed_summary.csv", "paired_capacity_frontiers.csv"]},
                  "script_sha256": sha(Path(__file__)),
                  "scope": "all six preset budgets, retrospective development; seed SD on left and unadjusted conditional shared-batch 95% interval on right; positive right-panel difference favors SAV-Val; primary capacity 10%"}
    provenance["outputs"] = {p.name: sha(p) for p in output.iterdir() if p.is_file()}
    (output / "figure_receipt.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"Exported audited curves for {sources}: {output}")


if __name__ == "__main__":
    main()
