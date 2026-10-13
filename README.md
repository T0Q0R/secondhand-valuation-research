# 二手物品估值：策略性缺失与预算核验

个人研究与AI接手仓库，目标为有可核查创新、严格实验和中科院三区论文；分类、首创性与接收结果尚未确定。

[AI接手](AI_HANDOFF.md) · [当前状态](docs/STATUS.md) · [机器状态](docs/STATUS.json) · [进度](docs/PROGRESS.md) · [研究边界](docs/RESEARCH.md) · [数据入口](data/README.md)

[当前源文件](paper/innovation-addendum-v1.tex) · [PDF](paper/innovation-addendum-v1.pdf) · [修订包](paper/revision-delivery-v2.zip) · [A–I回应](notes/revision-review-v2/REVIEW_RESPONSE.zh.md) · [哈希索引](notes/revision-review-v2/revision-delivery-index.json)

[汇总复算](notes/revision-review-v2/REPRODUCING_AGGREGATES.md) · [原全量训练协议](REPRODUCING_MATCHED_FACTORIAL.md) · [公开候选清单](notes/revision-review-v2/PUBLIC_RELEASE_CHECKLIST.zh.md)

快照：2026-10-13 07:39:12 UTC；研究时区 Asia/Shanghai。

**科学修订进行中，尚未达到正式投稿准备状态。** 当前标题 *When Does Verification Help? A Controlled Audit of Strategy-Aware Valuation*；同一编辑器源文件原位修改，30页、16引用、2幅矢量图，作者与单位留空。

原训练与四阶段核对完成：30/30组、4320单元、432万行、45372960个合法单边偏离。新增20000次事后同时敏感性保留31/27/20个不利反馈inflation区间，对应36/108/1536家族；不是确证或有限样本FWER保证。新增独立bit-mask状态oracle、真实模型恢复诊断、完整阈值网格；共享审计原语已公开。

正成本保留108新单元与36零成本对照。异质成本下synthetic robust/suppression/top-B反馈的四指标均值改善、三seed inflation方向均有利；仅局部事后三seed子集，非普遍或显著优势。JU/MU子集方向仍不利，20个未收敛批次保留。

JUCars全1374条/14批/10seed/240单元已完成及复核。**MUCars全10672条/107批仍运行**；扩评价阶段快照393/480，不是最终完成。现有6worker producer完成后，已启动的finalizer自动接全量复核和加权统计；后台不会自动改正文或推送GitHub。

内置编译、30页联系表视觉核查及14页全尺寸检查、页界/引用和5段逐字摘录检查通过。无Overfull或未定义引用，一个Underfull保留。图使用line/glyph提取适配、默认阈值未放宽，原始提取假阳性报告保留。

同一物理机器新环境的1536行汇总复算及阈值网格一致；**未完成外部干净机器全训练复现**。公开/DOI/许可证、真实作者责任、单位适用分区及期刊适配仍待决定；没有公开、投稿或接收事实。旧26页包是历史稿，旧PRE_SUBMISSION_REVIEW可投稿性判断已superseded。

experiments/保存训练、分配、响应、交叉拟合和核对；oqbo-val/保存有限信息边界与oracle。随机化、水位法、LP和minimum是已有工具。约24GB完整本地输出及权重不进入普通Git，完整复现仍需获取数据与运行实验。源码许可和对外发布尚未决定。按AGENTS.md每完成工作上传验证与下一步。
