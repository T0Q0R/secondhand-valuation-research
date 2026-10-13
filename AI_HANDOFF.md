# AI 接手入口

先读AGENTS.md、docs/STATUS.md、CURRENT_DELIVERY.md、notes/revision-review-v2/REVIEW_RESPONSE.zh.md。每完成独立工作提交成果、追加进度、同步状态、推送并回读。用户目标为真实创新/严格证据/单位口径中科院三区论文；不得虚构方法优势、作者批准、许可、DOI或投稿事实。

快照：2026-10-13 09:05:02 UTC；Asia/Shanghai。

**本轮计算、全量复核、统计和论文结果回填全部完成。没有尚待运行的大计算。** 当前30页稿题为 *When Does Verification Help? A Controlled Audit of Strategy-Aware Valuation*，16引用、2幅矢量图，作者/单位按用户要求留空。正式投稿准备尚未完成。

原训练/四阶段核对：30/30组、4320单元、432万重复行、45372960个合法偏离。补充全验证评价：JU1374条/14批、MU10672条/107批，同10seed，共480单元、29040批、2891040重复行；31269840合法单边偏离及最终分配/状态/指标核对通过。全部返回真实源批次满足有限单边regret容差，不是任意策略或全局联合最优保证。旧PID都是已退出的历史记录，不能重启或在别处复用。

完整真实来源的24个反馈inflation点仍全不利；JU12个未校正区间排除零，MU10个排除零、masking/suppression两个跨零。原36对比的事后同时敏感性保留31/27/20不利区间，对应36/108/1536家族。更大评价集和bootstrap不使已看过队列成为确证，也不覆盖新训练人口。

三seed正成本子集的synthetic robust/suppression/top-B仍有局部排序反转与四指标均值改善；保留所有成本条件、失败和20个未收敛批次。不能宣称反馈普遍有害、SAV普遍更优或首创已认证。审计共享原语已披露，独立性仅限明确的bit-mask/分配等重实现范围。

当前源文件和同稿PDF已内置编译及导出核查；30页联系表、改变页20–23/28–30全尺寸核查、引用/页界/对应摘录检查通过，0 Overfull/未定义引用、1 Underfull保留。当前源SHA256 9560dbc977cbf14e92ea8c07080560453837cdf36dc899e1d81c9b3eb6da4d2e；PDF a5487a675585f120661a41a0f17e0402a5d65002cd806b756e2f2b03b8ba8849。

同机新环境1536汇总行和阈值复算通过；**外部机器全训练、公开/许可/DOI、真实作者责任及期刊/单位分区适配仍未完成**。私有上传不等于公开或投稿。历史26页包与旧PRE_SUBMISSION_REVIEW的可投稿性判断已superseded。

[当前源文件](paper/innovation-addendum-v1.tex) · [同稿PDF](paper/innovation-addendum-v1.pdf) · [论文修订包](paper/revision-delivery-v2.zip) · [完整扩评价证据](notes/revision-review-v2/evaluation/full-expanded-evidence.zip) · [A–I回应](notes/revision-review-v2/REVIEW_RESPONSE.zh.md)

## 下一步

没有待恢复计算；不要重启9952/15837/17329/12200或重跑训练。先核当前证据索引，再处理具体的选刊模板、作者事实与证据访问/公开决策，或用户明确提出的新研究问题。理论是受限精度边界和恢复机制，不是普遍算法优势；审计质量不替代创新与可投稿性判断。

当前唯一论文源paper/innovation-addendum-v1.tex；当前生成器notes/revision-review-v2/revise_manuscript.py从baseline-reviewed-source.tex与已完成结果原位生成，不能用旧integrate_manuscript.py覆盖修订。任何后续改文后都重新内置compile_latex_document、同稿PDF导出与布局/对应核查。用户已授权导出同稿PDF，保持原编辑器，不创建替代稿。

源码/小型分析在仓库，权重与逐条输出在原机器，普通Git不包含约24GB全结果。新机器提取revision-delivery-v2.zip，再提取其中completed-supplements-stage1.zip和单独full-expanded-evidence.zip，保持项目相对路径；文件绑定见各索引。仅汇总统计复算见REPRODUCING_AGGREGATES.md；不要把它说成外部端到端重训。原科学环境用../.venv-gdfs/bin/python原路径，解析symlink会绕过venv。

原1000条主比较保持声明，全JU/MU扩评是补充；seed共享评价数据、按记录数加权尾批，MAE按来源本币，挂牌价不是成交价。保留负结果、跨零和非收敛。数据源CC BY不自动给代码指定许可；没有用户公开授权时不得公开私有仓库。
