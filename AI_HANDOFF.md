# AI 接手入口

先读 AGENTS.md、docs/STATUS.md、CURRENT_DELIVERY.md 和 notes/revision-review-v2/REVIEW_RESPONSE.zh.md。每完成独立工作先提交成果、追加进度、同步状态、推送并回读验证。用户目标：真实创新、严格证据、单位口径中科院三区论文；不得虚构优势、作者审批、投稿或接收。

快照：2026-10-13 07:39:12 UTC；研究时区 Asia/Shanghai。

**科学修订进行中，尚未达到正式投稿准备状态。** 当前标题 *When Does Verification Help? A Controlled Audit of Strategy-Aware Valuation*；同一编辑器源文件原位修改，30页、16引用、2幅矢量图，作者与单位留空。

原训练与四阶段核对完成：30/30组、4320单元、432万行、45372960个合法单边偏离。新增20000次事后同时敏感性保留31/27/20个不利反馈inflation区间，对应36/108/1536家族；不是确证或有限样本FWER保证。新增独立bit-mask状态oracle、真实模型恢复诊断、完整阈值网格；共享审计原语已公开。

正成本保留108新单元与36零成本对照。异质成本下synthetic robust/suppression/top-B反馈的四指标均值改善、三seed inflation方向均有利；仅局部事后三seed子集，非普遍或显著优势。JU/MU子集方向仍不利，20个未收敛批次保留。

JUCars全1374条/14批/10seed/240单元已完成及复核。**MUCars全10672条/107批仍运行**；扩评价阶段快照383/480，不是最终完成。现有6worker producer完成后，已启动的finalizer自动接全量复核和加权统计；后台不会自动改正文或推送GitHub。

内置编译、30页联系表视觉核查及14页全尺寸检查、页界/引用和5段逐字摘录检查通过。无Overfull或未定义引用，一个Underfull保留。图使用line/glyph提取适配、默认阈值未放宽，原始提取假阳性报告保留。

同一物理机器新环境的1536行汇总复算及阈值网格一致；**未完成外部干净机器全训练复现**。公开/DOI/许可证、真实作者责任、单位适用分区及期刊适配仍待决定；没有公开、投稿或接收事实。旧26页包是历史稿，旧PRE_SUBMISSION_REVIEW可投稿性判断已superseded。

[当前源文件](paper/innovation-addendum-v1.tex) · [PDF](paper/innovation-addendum-v1.pdf) · [修订包](paper/revision-delivery-v2.zip) · [A–I回应](notes/revision-review-v2/REVIEW_RESPONSE.zh.md) · [哈希索引](notes/revision-review-v2/revision-delivery-index.json)

[汇总复算](notes/revision-review-v2/REPRODUCING_AGGREGATES.md) · [原全量训练协议](REPRODUCING_MATCHED_FACTORIAL.md) · [公开候选清单](notes/revision-review-v2/PUBLIC_RELEASE_CHECKLIST.zh.md)

## 首先继续哪里

检查 outputs/review-expanded-primary-v2/progress.json、controller.log、finalizer.log 和 notes/revision-review-v2/evaluation/running-processes.json。原机器producer9952、finalizer12200只适用于本次本机，其他机器不可复用PID；先核身份/路径/锁。6worker producer完成后finalizer已配置做全量复核与10000次记录数加权统计。不要重复启动，不改运行中的expanded_evaluation.py/finalize_supplements.py或任何冻结源码；凭据绑定脚本SHA。

全量completion与finalizer确实完成后：核对480单元、两个来源、原1000条前缀、末批74/72条权重及未收敛保留；在notes/revision-review-v2/revise_manuscript.py回填MU，用同一tex原位修改，内置compile_latex_document检查、用户已授权的同稿PDF导出/视觉核查、重新生成diff/回应/包、再提交。不要单独运行旧integrate_manuscript.py覆盖本轮。

用../.venv-gdfs/bin/python原路径，不能解析symlink绕过venv。seed共用评价样本，挂牌价不是成交价，按来源本币不可池化MAE。权重和逐条原结果仍保留，普通Git只存小型证据；没有原始输出删除授权的推定。准备具体公开候选可以，未经用户决策不得公开私有仓库或自行选择许可证/编造DOI。
