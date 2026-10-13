# 二手物品估值：策略性缺失与预算核验

这是个人研究与 AI 接手仓库。目标是实现有可核查创新的算法，开展严格实验，形成符合学校“三区”口径的论文。期刊分类、首创性和接收结果均未确定。

## 从这里开始

- [AI 接手说明](AI_HANDOFF.md)：研究目标、证据边界及下一步。
- [当前状态](docs/STATUS.md) / [机器可读状态](docs/STATUS.json)。
- [研究想法与创新边界](docs/RESEARCH.md)。
- [数据入口](data/README.md)、[证据索引](evidence/INDEX.json)。
- [匹配因子实验复现](REPRODUCING_MATCHED_FACTORIAL.md)、[稳定性复现](REPRODUCING_STABILITY.md)。
- [完整论文源文件](paper/innovation-addendum-v1.tex) · [PDF](paper/innovation-addendum-v1.pdf) · [交付包](paper/manuscript-delivery-v1.zip)。
- [完整因子结果、图表与复核入口](docs/FINAL_RESULTS.md)。

## 实现

`experiments/` 保存估值、查询分配、卖家响应、交叉拟合、审计及分析代码；`oqbo-val/` 保存可观测报告 oracle、精度前沿和条件稳定性检查；`tests/` 保存测试；`plan/` 与 `notes/design/` 保留设计和预先记录的实验协议。BRC/CDM/EMC 等目录属于探索分支，其结果不可混作同一算法。

30 个来源/种子组合、4320 个因子实验单元的训练评估、训练审计、结果回放审计、统计分析和独立统计检查均已完成，覆盖432万条结果。主容量10%下，36个匹配反馈对比均恶化inflation；MUCars的12个robust初始目标对比均通过点估计门槛。区间是固定训练记录上的未校正探索结果，不能宣称通用优势。26页完整科学稿已交付，内置编译与逐页检查完成；作者与单位按用户要求留空。正式投稿和学校分区认证尚未完成。

[完整分析与审计证据包](notes/factorial-final/audited-analysis-evidence.zip)含所有容量的对比CSV、张量/重采样和完成凭据；[清单与哈希](notes/factorial-final/EVIDENCE_INDEX.json)便于外部AI复核。GitHub仍是有时间戳的快照。

本仓库提供代码、文稿、方案和小型证据，不包含约24GB的全部本地输出、模型权重或逐条挂牌记录。完整复现仍需获取数据与运行实验，详见数据说明。软件许可与对外发布尚未确定；数据源许可不能替代软件许可。

## 最终科学稿交付

完整科学稿已交付：26页、9节正文、5组附录、14篇引用、2幅矢量图、11个编号表；作者与单位留空。内置编译、逐页视觉检查、引用/边界检查和证据包逐文件校验完成。

[完整源文件](paper/innovation-addendum-v1.tex) · [同稿PDF](paper/innovation-addendum-v1.pdf) · [论文与证据包](paper/manuscript-delivery-v1.zip) · [核查记录](notes/manuscript-integration/PRE_SUBMISSION_REVIEW.md) · [投稿准备](notes/manuscript-integration/VENUE_PREPARATION.zh.md)

科学稿写作已完成；正式投稿、单位适用分区确认、作者声明与证据访问仍需准备。没有新增训练或外部机器全流程重跑，原模型及逐条结果仍保留。
