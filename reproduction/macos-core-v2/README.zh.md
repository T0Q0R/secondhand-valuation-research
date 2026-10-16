# 另一台macOS机器的核心从头训练复现

本包是待执行的复现入口，不是外部机器已复现的证明。请在另一台电脑运行，保留日志和receipt；不能把本机旧模型/旧输出复制过去冒充从头训练。

## 环境

使用Python3.12和现有固定依赖。创建独立目录后：

```sh
git clone https://github.com/T0Q0R/secondhand-valuation-research.git sav-val
cd sav-val
python3.12 -m venv ../.venv-gdfs
../.venv-gdfs/bin/python -m pip install -r requirements-lock.txt
```

安装失败应保留错误与系统/架构信息，不自动放宽依赖版本。合成来源不需要下载真实数据。

## 先检查输入，再训练

```sh
../.venv-gdfs/bin/python reproduction/macos-core-v2/run_from_scratch.py --dataset synthetic --check-only --output ../external-rpl-synthetic
../.venv-gdfs/bin/python reproduction/macos-core-v2/run_from_scratch.py --dataset synthetic --output ../external-rpl-synthetic > ../external-rpl-synthetic.log 2>&1
```

固定完整训练规模/12个残差epoch、3外层折和160棵采集树；只跑seed13、λ0与1、预算0/0.1/0.3，共6单元。所有价格模型从源数据重训，OOF预测和部署采集头重新构造。阶段模型可断点复用；程序不读本机历史模型或生产结果，参考汇总只在训练和评估结束后读取。

准备真实来源时，按[输入布局](../../docs/PORTABLE_SETUP.md)和[数据重建说明](../../REPRODUCING.md)取得合法原数据，安装source_inputs两个脚本到父目录并核对处理后SHA。可先运行runtime/check_project_inputs.py。不得改旧哈希以迁就不同版本的数据。

准备完全部数据后，用新的输出目录运行：

```sh
../.venv-gdfs/bin/python reproduction/macos-core-v2/run_from_scratch.py --dataset all --check-only --output ../external-rpl-all
../.venv-gdfs/bin/python reproduction/macos-core-v2/run_from_scratch.py --dataset all --output ../external-rpl-all > ../external-rpl-all.log 2>&1
```

三个来源总18单元。无需重跑其它方法、全部参数矩阵或完整历史实验。

## 回传与验收

请回传external-training-receipt.json、summary.csv、reference-comparison.csv和执行日志，并说明确实在另一台电脑运行。模型和逐条输出留在那台机器，不上传普通Git。差异和未收敛响应必须保留；价格模型在平台间的浮点差异可能改变接近并列的分配，不能删除不匹配结果。

对照阈值为绝对1e-7加相对1e-5；这只是预先声明的数值复现检查阈值，不是统计显著性或科学等价界。原始汇总、固定人群/源码哈希均在contract.json绑定。

即使这18单元匹配，也只能写“另一台机器从头重训并复现了指定核心子集”，不能写“全论文/1719单元已完成外部复现”。当前包只在本机完成语法与合同静态核查，外部运行仍待实际执行。
