# 审计恢复与精度错误说明

RPL十种子30组/540单元已计算完成，完整四阶段审计仍待。原审计队列在ACO停止，原三种子RPL162、搜索强度90以及SEFA/GDFS/DIME/EFA各108，共684单元的四阶段链已经完成；其产物已补传并核对远程提交。区间仍属探索性，科学人工复核和论文整合未完成。

## 失败原因与验证

原ACO审计器在独立距离计算中直接使用归档float32 bank/query；生产ConditionalNeighborHead构造时将bank转float64，评分时将query转float64。减法前的精度不同能改变邻居排序。synthetic/seed13/masking全11000状态中，旧审计器k25有1228个有限评分不同，最大差0.0069592。不是生产参数、模型或数据变化。

新增audit_core_aco_v3.py在减法前明确把bank/query提升为float64，继续独立逐坐标距离计算。k25/10/50与原生产评分全部精确相同；两种价格后端、全部16单元/16000行/166736个合法单边偏离的工程复核通过。完整ACO矩阵尚待复核；不得把该样例通过冒称全阶段通过。engineering.json记录全部检查。原失败记录保留，不放宽任何容差。

## 恢复范围

独立run_core_evidence_recovery_v3.py仅继续ACO144和RPL10共540（其中162与既有RPL重复），不重训、不重跑前六阶段。保留v2源码/manifest/失败状态和六个已完成源闭包；ACO旧部分审计凭据移入新runtime的superseded-aco-v2并记录哈希，避免错误复用。仍使用原fit/outcome、分析与独立统计程序；新增源闭包显式包含v3校正器。

计算预算最多8个单线程审计worker，内存不足时限流。完成后自动保存凭据并提交小型汇总，论文保持原稿。原机器数据/权重不入Git。启动状态以outputs/core-evidence-recovery-runtime-v3/status.json为准；不得按旧队列失败状态重复启动。
