# 下一步：短程残差训练分歧诊断

已有结果：8个阶段的输入、编码/合法状态指纹、树结构/叶值及基础预测相同，残差权重不同。严格数值复现未通过，原始失败不能改标为成功。

先定位，再决定是否修复实现。不要重跑完整矩阵，不要放宽原数值容差，也不要为了匹配而挑选外机运行结果。

## 另一台 Mac 可用时

在之前的仓库目录执行：

```sh
cd ~/Desktop/secondhand-reproduction/sav-val
git pull --ff-only
../.venv-gdfs/bin/python reproduction/macos-core-v2/trace_residual_probe.py --run ../external-rpl-synthetic --output ../external-rpl-residual-probe-v1.zip
```

把生成的 `external-rpl-residual-probe-v1.zip` 发回。输出必须是不存在的新文件；如果同名文件已存在，请换新名字保留旧文件。

该程序只读取自己先前训练的可信模型文件，不能用来打开陌生来源的joblib。它复用已核验的基础模型和训练划分，临时重置残差网络，直接调用冻结的原训练函数；λ=0/1各检查outer-0、outer-2，只运行首个epoch，共4段×24批。本机2026-10-16试跑7.68秒；外机速度尚未测量。

每批记录初始化、反向传播前、梯度裁剪前后、参数更新后的指纹；前3批另保留诊断数组。原检查点、报价、评估指标与论文均不修改。私下回传ZIP即可，数组/参数不上传普通Git。

## 如何判读

- 初始化不同：继续核验随机数状态与初始化路径。
- 输入和参数相同，但前向/梯度首次不同：检查相应数值运算的执行路径。
- 更新前的参数、梯度都相同，更新后不同：检查优化器步骤。
- 前面运算仅有细微差异，随后选态不同：检查离散选择是否放大了数值扰动。
- 首轮全部一致：继续检查原来的双线程执行、后续epoch/反馈轮，不能宣称问题已解决。

此诊断特意采用单线程、固定基础模型，减少运行因素。它不是对原双线程完整训练的逐步复刻；同机或跨机的这一短程匹配都不替代原六单元严格验收。没有两端轨迹对照之前，上面的解释只是假设，不是已经查明的原因。

若查明具体实现问题，修复必须另建版本并重跑受影响的核心对照，保留旧结果；若只能确认环境相关差异，则如实报告外部数值不匹配，并另行设计科学效应稳健性检验，不能用事后调大的数值容差替代。

## Windows

Windows原生六单元训练完成后，也可用同一诊断脚本读取那台机器自己的新检查点：

```powershell
..\.venv-gdfs\Scripts\python.exe reproduction\macos-core-v2\trace_residual_probe.py --run ..\external-rpl-windows-synthetic --output ..\external-rpl-residual-probe-windows-v1.zip
```

文件虽然位于`macos-core-v2`，但本脚本不导入Unix文件锁，并支持已声明的Mac/Windows两种原始合同。Windows实际执行仍待验证。不要为了这项短诊断先重复已经完成的完整训练。
