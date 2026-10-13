# 完整科学稿核查记录

核查日期：2026-10-13（Asia/Shanghai）。对象：原编辑器文件 `paper/innovation-addendum-v1.tex` 及其同稿 PDF。作者与单位按用户要求暂留空。

本记录是 AI 辅助的文本、程序与视觉核查，不是独立人类同行评审或接收预测。科学正文当前未发现未解决的 CRITICAL 或 MAJOR 问题；保留 1 个 MINOR 排版提示。正式投稿的作者责任、声明和期刊口径另列，不冒充为已完成。

## 首要处理项与已完成修复

| 原文或对象 | 级别 | 处理与验证 |
|---|---|---|
| 原生成稿中 “Table B retains all four rule comparisons” | MINOR | 将固定-profile 表的 label 移到 caption 后；最终 PDF 第20页显示 “Table 7”。 |
| “valuation outcomes? A finite oracle…” | MINOR | 将研究问题与方法概述分成两段，形成六段引言。 |
| “Yet feedback increased inflation under both allocators” | MINOR | 删除连接词 Yet；保留两种分配都恶化 inflation 的原数值。 |
| 声明设置表及未编号的 stability 诊断表 | MINOR | 增加表前引用、诊断表 caption 与 label；最终 Table 1 和 Table 11 均正确。 |

## 1. 宏观逻辑与创新边界

“a tight trade-off between uniform honest precision, query capacity and worst expected concealment gain” 对应第4节受限别名族证明，而非全体市场。第5节的 “weakly reduces unilateral gain for fixed peer reports” 对应固定-peer cap 证明；第7节另报告重新计算响应后的预测误差和查询失败代价，未把两者混为一个激励保证。

理论贡献是明确约束下的精度前沿、恢复路径分解及条件 cap。边际表示、水位分配、LP 和随机化属于已有技术；小型 context-aware comparator 闭合策略库例子的差距，因此没有将弱比较对象造成的差距宣称为求解器创新。文献核对不能证明绝对首创性。

“all 36 feedback comparisons increase mean inflation” 对应完整匹配实验，不对应原 SAV/static-robust 实验。24个因子单元、14个独立拟合头、30个来源/种子组和六个预算的身份保持明确。432万条输出是重复记录；每来源只有同一1000个评价 listing，不能当成432万个独立样本。所有负结果、失败查询和未收敛响应保留。

## 2. 写作与段落

引言由背景、失败例子、已有研究局限、研究问题、方法概述、贡献六段组成。10/12/14 报价例子在引言与恢复路径分析中一致，并明确标为示意值。相关工作、假设、结果和讨论各自承担不同论证任务。五组附录保留证明、完整原实验、稳定性条件及强基线适配范围。

## 3. 英文语法

按技能规则 G1–G8 检查冠词、主谓一致、时态、连接、限制性从句、被动语态、直译和引号。未发现需要改动科学含义的具体语法错误。方法使用现在时，已运行实验使用过去时或对保存结果的现在时描述；不机械改写公式条件和事实性的完成状态。没有为凑数生成语法问题。

## 4. LaTeX 与逐页核查

内置编译成功；同稿 Tectonic 导出26页 PDF。引用、标签、文献集合和全部页面边界经程序检查：14篇文献全部被引用，无未定义引用、重复 label、问号占位、Overfull 或页外文字。

逐页以实际渲染页面检查正文、公式、跨页表格、两幅图、附录与参考文献；最后修正仅改变第20页，随后再次检查。Table 4、Table 6 的跨页表头和全部行保留。字体最小5.98 pt来自数学上下标；图中最小文字9.02 pt。

剩余 MINOR：“Underfull \\hbox (badness 1715)” 位于附录 ACO-1 段落。其页面无越界或碰撞，属于行间空白警告，未用删减事实来消除。通用 article 排版已检查；尚不声称已套用任何特定期刊的最终模板或通过特定页数限制。

## 5. 图表质量与审计适配

“Policy feedback increases mean inflation…” 和 “Initial-objective effects depend on the source” 两幅图均为矢量，完整保留点、区间、零线和来源编码。图注给出效应方向、预算、重复单位和未校正区间含义。

原 Matplotlib PDF 使用标准 collision checker，均 PASS，0 fail/0 warn。嵌入 XeTeX 页面时，标准提取器将跨多个独立文字位置的 text trace 联合成大矩形，产生假阳性；原失败报告保留。适配器只使用实际 line/glyph 位置替代该提取步骤，未放宽碰撞阈值，且仍拒绝真实文字重叠和穿过文字的线段。最终两个嵌入页均 PASS，0 fail/0 warn。不得将其描述为未经适配的标准检测器通过。

## 6. 全文词汇扫描

整份最终源文件（含图注、附录、参考文献）执行精确词扫描。没有 Unicode 或 TeX 连接式 em-dash。两个保留命中为 “not yet a public archival release” 和 “declared direct reveal aliases”：前者准确说明发布状态，后者是输入排除类别；均非宣传性 AI 措辞。扫描定位与源文件哈希见 `qa/vocabulary-scan.json`。

## 完整性门与五个问题

1. 每个问题是否有原文/对象定位？是；修复项和剩余警告均有具体位置。
2. 是否保留所有关键比较？是；原十种子候选、匹配因子、冻结分配、cap 响应、ordinary-benefit、等规模调参、SMI 和 ACO-1 均有身份边界。
3. 理论是否支持真实世界普遍优势？否；明确限定别名族、固定-peer、单位预算和验证语义。
4. 区间是否覆盖新的训练总体并校正多重比较？否；固定训练记录的未校正探索区间已明确声明。
5. 是否已投稿、获得人类审阅或完成外部机器全流程复现？否；没有作此声明。

技能完整性门1–7通过：引用问题真实、严重性按证据、没有虚构 CRITICAL、语法检查按G1–G8、全文扫描有机器记录。科学稿内部核查评分8/10；不将此分数作为接收概率。

正式投稿前需作者填写责任与声明，确认单位使用的分区年份/类别并选定期刊，按其模板和实际访问政策处理外部证据获取。建议状态：科学稿可交付；正式投稿尚需作者与期刊层面的最终准备。
