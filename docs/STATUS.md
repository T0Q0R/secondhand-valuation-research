# 当前交付状态

快照：2026-10-13 09:05:02 UTC；Asia/Shanghai。

**本轮计算、全量复核、统计和论文结果回填全部完成。没有尚待运行的大计算。** 当前30页稿题为 *When Does Verification Help? A Controlled Audit of Strategy-Aware Valuation*，16引用、2幅矢量图，作者/单位按用户要求留空。正式投稿准备尚未完成。

原训练/四阶段核对：30/30组、4320单元、432万重复行、45372960个合法偏离。补充全验证评价：JU1374条/14批、MU10672条/107批，同10seed，共480单元、29040批、2891040重复行；31269840合法单边偏离及最终分配/状态/指标核对通过。全部返回真实源批次满足有限单边regret容差，不是任意策略或全局联合最优保证。旧PID都是已退出的历史记录，不能重启或在别处复用。

完整真实来源的24个反馈inflation点仍全不利；JU12个未校正区间排除零，MU10个排除零、masking/suppression两个跨零。原36对比的事后同时敏感性保留31/27/20不利区间，对应36/108/1536家族。更大评价集和bootstrap不使已看过队列成为确证，也不覆盖新训练人口。

三seed正成本子集的synthetic robust/suppression/top-B仍有局部排序反转与四指标均值改善；保留所有成本条件、失败和20个未收敛批次。不能宣称反馈普遍有害、SAV普遍更优或首创已认证。审计共享原语已披露，独立性仅限明确的bit-mask/分配等重实现范围。

当前源文件和同稿PDF已内置编译及导出核查；30页联系表、改变页20–23/28–30全尺寸核查、引用/页界/对应摘录检查通过，0 Overfull/未定义引用、1 Underfull保留。当前源SHA256 9560dbc977cbf14e92ea8c07080560453837cdf36dc899e1d81c9b3eb6da4d2e；PDF a5487a675585f120661a41a0f17e0402a5d65002cd806b756e2f2b03b8ba8849。

同机新环境1536汇总行和阈值复算通过；**外部机器全训练、公开/许可/DOI、真实作者责任及期刊/单位分区适配仍未完成**。私有上传不等于公开或投稿。历史26页包与旧PRE_SUBMISSION_REVIEW的可投稿性判断已superseded。

[当前源文件](../paper/innovation-addendum-v1.tex) · [同稿PDF](../paper/innovation-addendum-v1.pdf) · [论文修订包](../paper/revision-delivery-v2.zip) · [完整扩评价证据](../notes/revision-review-v2/evaluation/full-expanded-evidence.zip) · [A–I回应](../notes/revision-review-v2/REVIEW_RESPONSE.zh.md)


2026-10-14 新增：冻结产物机制诊断完成，论文回填待做；不再存在未完成的原扩评计算。见 notes/revision-mechanisms-v3/DIAGNOSTICS.md。扩评后两个MU对比的seed主方差占98.3%–98.4%；不能解释成零效应或训练人口不确定性。正成本隐瞒强度报告保留非收敛批次的识别范围。
