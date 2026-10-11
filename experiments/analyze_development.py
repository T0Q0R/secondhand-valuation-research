"""Recompute saved metrics and produce a bounded development report."""
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    root = args.run.resolve()
    completion = json.loads((root / "completion.json").read_text())
    if completion["status"] != "completed":
        raise ValueError("Run did not complete")
    actual_hash = hashlib.sha256((root / "all_summary.csv").read_bytes()).hexdigest()
    if actual_hash != completion["summary_sha256"]:
        raise ValueError("Saved summary differs from completion binding")
    manifest = json.loads((root / "run_manifest.json").read_text())
    config = manifest["protocol"]
    summary = pd.read_csv(root / "all_summary.csv")
    analysis = root / "analysis"
    analysis.mkdir(exist_ok=False)
    checks, comparisons = [], []
    for dataset in config["datasets"]:
        for seed in config["seeds"]:
            folder = root / dataset / f"seed-{seed}"
            outcomes = pd.read_csv(folder / "per_listing_outcomes.csv.gz")
            if outcomes.duplicated(["listing_id", "method", "budget"]).any():
                raise ValueError("Repeated outcome key")
            for (method, budget), group in outcomes.groupby(["method", "budget"]):
                row = summary[(summary.dataset == dataset) & (summary.seed == seed) & (summary.method == method) & (summary.budget == budget)].iloc[0]
                recomputed = {
                    "clean_rmsle": np.sqrt(group.clean_sq_log_loss.mean()),
                    "attack_rmsle": np.sqrt(group.attack_sq_log_loss.mean()),
                    "clean_mae": group.clean_absolute_error.mean(),
                    "attack_mae": group.attack_absolute_error.mean(),
                    "mean_positive_log_inflation": group.positive_log_inflation.mean(),
                    "mean_positive_price_inflation": group.positive_price_inflation.mean(),
                    "actual_audit_fraction": (group.action >= 0).mean(),
                }
                for field, value in recomputed.items():
                    if not np.isclose(value, row[field], atol=1e-9, rtol=1e-9):
                        raise ValueError(f"Metric mismatch: {dataset}/{method}/{budget}/{field}")
                for batch, rows in group.groupby("batch"):
                    if (rows.action >= 0).sum() > int(np.floor(budget * len(rows))):
                        raise ValueError("Hard batch capacity exceeded")
                # Verify price-space metrics from logs, rather than merely
                # checking the summary against a duplicated formula field.
                expected_clean_abs = np.abs(np.expm1(group.clean_prediction_log) - np.expm1(group.target_log))
                expected_attack_abs = np.abs(np.expm1(group.attacked_prediction_log) - np.expm1(group.target_log))
                if not np.allclose(group.clean_absolute_error, expected_clean_abs, rtol=1e-9, atol=1e-8):
                    raise ValueError("Clean price-space errors differ from saved predictions")
                if not np.allclose(group.attack_absolute_error, expected_attack_abs, rtol=1e-9, atol=1e-8):
                    raise ValueError("Attack price-space errors differ from saved predictions")
                checks.append({"dataset": dataset, "seed": seed, "method": method,
                    "budget": budget, "records": len(group), "metric_checks": len(recomputed),
                    "price_space_checked": True, "hard_budget_checked": True})
            primary = summary[(summary.dataset == dataset) & (summary.seed == seed) & (summary.budget == 0.1)].set_index("method")
            ours, reference = primary.loc["sav_val"], primary.loc["sav_benefit_head"]
            baseline = summary[(summary.dataset == dataset) & (summary.seed == seed) & (summary.method == "masking_no_audit")].iloc[0]
            interval = json.loads((folder / "primary_interval.json").read_text())
            reduction = 100 * (reference.mean_positive_log_inflation - ours.mean_positive_log_inflation) / reference.mean_positive_log_inflation if reference.mean_positive_log_inflation > 0 else np.nan
            clean_change = 100 * (ours.clean_mae / reference.clean_mae - 1)
            comparisons.append({"dataset": dataset, "seed": seed,
                "relative_inflation_reduction_percent": reduction,
                "honest_mae_change_percent_vs_robust_benefit": clean_change,
                "honest_mae_change_percent_vs_masked_backbone": 100 * (ours.clean_mae / baseline.clean_mae - 1),
                "cluster_interval_lower": interval["conditional_batch_cluster_95_interval"][0],
                "cluster_interval_upper": interval["conditional_batch_cluster_95_interval"][1],
                "ours_mean_inflation_log": ours.mean_positive_log_inflation,
                "reference_mean_inflation_log": reference.mean_positive_log_inflation,
                "ours_clean_mae": ours.clean_mae, "reference_clean_mae": reference.clean_mae,
                "ours_attack_mae": ours.attack_mae, "reference_attack_mae": reference.attack_mae,
                "ours_max_remaining_regret_log": ours.max_remaining_response_regret,
                "ours_nonconverged_batch_fraction": ours.nonconverged_batch_fraction,
                "passes_development_threshold": bool(reduction >= 10 and clean_change <= 5 and interval["conditional_batch_cluster_95_interval"][0] > 0)})
    pd.DataFrame(checks).to_csv(analysis / "metric_recomputation.csv", index=False)
    compare = pd.DataFrame(comparisons)
    compare.to_csv(analysis / "primary_development_comparisons.csv", index=False)
    fig, axes = plt.subplots(len(config["datasets"]), 2, figsize=(10, 3 * len(config["datasets"])), squeeze=False)
    selected = ["masking_benefit", "robust_no_feedback", "sav_val", "sav_no_gap", "sav_benefit_head"]
    labels = {"masking_benefit": "Masking + value", "robust_no_feedback": "Robust / no feedback", "sav_val": "SAV-Val", "sav_no_gap": "No gap penalty", "sav_benefit_head": "Ordinary value head"}
    for r, dataset in enumerate(config["datasets"]):
        for method in selected:
            group = summary[(summary.dataset == dataset) & (summary.method == method)].groupby("budget").mean(numeric_only=True).sort_index()
            axes[r, 0].plot(group.index * 100, group.mean_positive_log_inflation, marker="o", ms=3, label=labels[method])
            axes[r, 1].plot(group.index * 100, group.attack_mae, marker="o", ms=3, label=labels[method])
        axes[r, 0].set_ylabel(f"{dataset}\nMean positive log-price inflation")
        axes[r, 1].set_ylabel("Attacked MAE (source currency)")
        for ax in axes[r]:
            ax.set_xlabel("Available verification capacity (%)")
            ax.grid(alpha=0.2)
            ax.spines[["top", "right"]].set_visible(False)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("Exploratory development — one training seed; approximate seller responses", fontsize=11)
    fig.tight_layout()
    fig.savefig(analysis / "development_budget_frontiers.pdf")
    fig.savefig(analysis / "development_budget_frontiers.png", dpi=180)
    lines = ["# SAV-Val 首轮开发实验报告", "", "状态：开发性证据。算法实现与实际运行完成，本报告不是最终三区论文，也不构成真实卖家行为或成交价格验证。", "",
        "主比较：10% 核验容量下，完整算法对比同一训练框架的普通信息价值头。价格抬升是相对各模型完整披露预测的正向 log-price 差。", "",
        "| 数据 | 隐瞒收益下降 | 正常 MAE 变化 | 开发门槛 |", "|---|---:|---:|---|"]
    for row in comparisons:
        lines.append(f"| {row['dataset']} | {row['relative_inflation_reduction_percent']:.2f}% | {row['honest_mae_change_percent_vs_robust_benefit']:+.2f}% | {'达到' if row['passes_development_threshold'] else '未达到'} |")
    lines.extend(["", "门槛：收益下降至少 10%、正常 MAE 恶化不超过 5%，且条件批次 bootstrap 差值区间下界为正。单种子开发达到门槛仍不是最终方法成功。", "",
        "## 需要继续处理的问题", "", "- 只有一个训练种子；必须补充固定设计后的多种子实验。", "- 部分卖家响应搜索未收敛；已保存最大剩余单方偏离收益，不能称为精确均衡。", "- 当前采用估价与动作头样本隔离；完整多折交叉拟合尚未实现。", "- 两个真实来源用于过往项目，当前结果属于回顾性开发实验。核验只补回记录值，并不验证记录真实性。", "- 直接策略性回归方法的适用性和公平对照仍需审计。", "- 必须同时对比无反馈鲁棒模型、真实标签误差和正常价格偏差；不能只选择有利的对照或指标。", "",
        "可检查文件：`primary_development_comparisons.csv`、`metric_recomputation.csv`、预算前沿图，以及上一级逐条预测、模型、源文件哈希和完成记录。"])
    (analysis / "development-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(compare.to_string(index=False))
    print(f"Verified {len(checks)} method/budget cells. Report: {analysis / 'development-report.md'}")


if __name__ == "__main__":
    main()
