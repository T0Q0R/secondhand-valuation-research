# 独立克隆后的输入准备

本指南补齐初次源码快照遗漏的两个父目录处理脚本与输入哈希凭据。
原实验的路径约定和数值代码保持不变；不是已通过清洁环境全流程复现的声明。

## 目录布局

推荐把仓库克隆到独立工作区中的 `sav-val` 子目录：

```text
research-workspace/
  .venv-gdfs/
  experiments/
    build_jucars_bvival_manifest.py
    build_mucars_bvival_manifest.py
    data/processed/{jucars,mucars}_bvival_v1/splits/{train,validation}.csv
  sav-val/                       # 本仓库
    source_inputs/               # 两个原始处理脚本的原字节副本
    notes/source-reproduction-inputs-v1.json
```

在独立工作区克隆：

```sh
git clone https://github.com/T0Q0R/secondhand-valuation-research.git sav-val
cd sav-val
python3.12 -m venv ../.venv-gdfs
../.venv-gdfs/bin/python -m pip install -r requirements-lock.txt
mkdir -p ../experiments
```

把 `source_inputs/` 的两个脚本复制到 `../experiments/`。已有同名文件时先比对
SHA256，不能直接覆盖其他项目的代码。`notes/source-reproduction-inputs-v1.json`
包含这两个脚本、三个原始输入和四个处理后输入的预期SHA256。

## 取得并重建数据

原数据版本、文件名和重建命令见 [REPRODUCING.md](../REPRODUCING.md)
的 Source inputs and reconstruction 部分；公共DOI与许可见
[data/README.md](../data/README.md)。原始数据不在仓库内。

重建程序读取合法下载的原始表，在新的输出目录中只写训练/验证分割，并验证
四个输出的字节哈希。它不读取或导出历史测试标签。通过后把新目录的
`experiments/data/processed/` 放到工作区父目录的相应位置。已有输入不得覆盖。

下载平台若更换文件编码、换行或内容，原始SHA256可能不同。遇到不一致先检查
版本和字节，不能为了让检查通过而改旧凭据。任何新输入版本需要单独实验与审计。

## 训练前只读核对

从仓库根目录运行：

```sh
../.venv-gdfs/bin/python runtime/check_project_inputs.py
```

该命令核对仓库中两个脚本、父目录安装的两个脚本、四个处理后CSV；缺文件或
哈希不符时返回非零退出码。可用 `--parent-root` 检查明确指定的父目录。
它不训练、不修改输入、不接触历史测试标签，也不核查全部依赖版本。

输入通过后按 [匹配因子复现说明](../REPRODUCING_MATCHED_FACTORIAL.md)
使用新输出路径运行。复制原运行凭据、模型或输出到另一台机器并不自动保留
原审计保证。先做小范围检查，完整重训仍可能需要较长时间。

## 已验证范围

2026-10-11：原机器上的8项输入/脚本检查全部匹配；不存在的父目录被拒绝。
这只证明输入检查工具与原记录相符，不证明独立机器上的完整数据重建、训练、
统计或论文复现已经完成。
