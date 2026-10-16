# 外部数值差异：读取已有模型，不重训

首次返回的6单元运行完成，但严格数值比较未通过；原失败凭据保留，不改容差。本机按同一入口从头重训6单元通过原容差，不能据此把外机结果改标为通过。下一步比较已保存的各阶段模型，确定最早发生差异的位置。

在另一台Mac原仓库目录运行：

```sh
cd ~/Desktop/secondhand-reproduction/sav-val
git pull --ff-only
../.venv-gdfs/bin/python reproduction/macos-core-v2/diagnose_saved_run.py --run ../external-rpl-synthetic --output ../external-rpl-synthetic-diagnostic.zip
```

程序只读取外机已经训练的8个阶段模型，生成编码/基础预测/残差/最终预测的指纹和用于差异诊断的数组。它不训练，不重新搜索卖方响应，不修改原结果或原通过阈值。出现8行FINGERPRINTED和末尾SAVED即完成。

把桌面secondhand-reproduction目录中的external-rpl-synthetic-diagnostic.zip回传给本次研究对话。该诊断包包含合成数据预测和部分模型参数，用于私下比对；普通Git只提交代码、哈希、环境信息和比较摘要，不提交诊断数组或模型权重。

本机测试：读取同机从头拟合的8个模型并生成诊断包成功；原外机包仍为严格数值不匹配，具体跨环境原因仍待外机诊断包。
