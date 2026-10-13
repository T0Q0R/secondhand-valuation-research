# A–I 科学评审：逐项修改与核对

对象是用户对历史26页稿的投稿前科学评审；没有期刊编辑决定，本文件不是已发送的返修信。现稿标题为 *When Does Verification Help? A Controlled Audit of Strategy-Aware Valuation*，同一编辑器源文件原位修改，30页。原实验未重训，冻结代码和凭据保持不变。旧PRE_SUBMISSION_REVIEW的可投稿性判断已显式标为失效。

## A：理论与真实模型不耦合

采用评审允许的“理论界定scope”路线。§4.1（第6页）明确单可恢复字段、verification-neutral报价、uniform error不构成四字段学得模型的实测最优界，也不预测反馈符号。新增§7.2（第16–17页）在真实模型的合法预测表上验证恢复路径：三个来源均存在两字段隐瞒后的不利部分恢复；具有正查询概率的返回报告行分别为synthetic 82、JUCars 1733、MUCars 2829。720主容量单元、720000重复报告的E+R+C=G复算最大误差为0，另提供MUCars具体预测表证人。

这些是有限、依赖的模型表诊断，不是独立卖家样本、真实查询次数或人类行为发生率。没有声称求出真实数据T*，也没有用此诊断因果解释反馈为何失败。

证据：`evaluation/recovery_completion.json`；`completed-supplements-stage1.zip`中的恢复路径CSV与输入哈希。

## B：联合推断与确证结论

§7.1（第12页）补20000次中心化交叉bootstrap，用条件bootstrap标准差作固定尺度、保留方法和指标配对，报告36、108、1536三个完整家族。36个核心不利点不变；不利inflation区间数依次为31、27、20，source-wise Bonferroni敏感性为31、27、19。原34个区间被明确标为未校正。全部1536点与冻结CSV一致，结构性零项和所有家族保留。

这是事后、近似的同时敏感性分析，不是每次重估尺度的studentized max-t或完整Romano–Wolf stepdown实现，不获得有限样本FWER定理，也不会把已看过的队列变成confirmatory数据。没有新增独立训练人口样本。B的报告与多重比较敏感性已处理；“确证研究”仍未建立。

证据：`statistics/completion.json`；`statistics/simultaneous_primary_contrasts.csv`；独立新环境汇总复算`isolated-replay-receipt.json`。

## C：取消评价hash cap

§6.1/§7.1说明10个训练seed共用同一确定性评价样本，训练随机性不是十份独立评价数据。§7.8（第20–21页）现同时报告两个完整验证队列：JUCars全部1374条、14批；MUCars全部10672条、107批；末批74/72条、容量均7。共480单元、29040个seed/cell批次、2891040条重复结果及31269840个合法单边偏离均复核完成。所有返回的真实来源批次满足有限单边regret容差，但不证明任意动作或全局联合最优响应。

全部24个feedback inflation点仍不利；记录数加权10000次探索区间中，JU12个全部不利，MU10个不利，masking/suppression的两个分配区间跨零。保留原1000条前缀并核对复用；未重训。C的全覆盖与复核已完成，原1000条主比较保留；更大的评价数据不修复训练人口推断，也不消除retrospective属性。

证据：`evaluation/expanded-completion-summary.json`；`evaluation/full-expanded-evidence.zip`及逐文件索引；`outputs/review-expanded-primary-v2-analysis/completion.json`。运行PID现在是已完成的历史记录，不能据此重启。

## D：inflation退化与cap指标

§3.3（第4页）正面举出恒定报价inflation恒为0的退化。inflation、attacked MAE、failed-query作为并列描述性主结果，honest MAE是精度坐标，明确这是回顾性报告选择。§7.5（第19页）将核心解释改为94个attacked-error恶化及145个失败概率恶化，而不是279个inflation下降的计数。

一个必要区分：432个cap比较重新搜索了响应，固定peer单调性不自动涵盖这些不同的peer profiles。文中同时区分固定-peer定理与重新计算响应的经验结果；各项计数都是描述性的，没有以计数充当独立统计检验。

## E：10%/5%阈值

§7.6（第20页）明确原门槛是继承的heuristic，而非预注册或外部验证的实际重要差异。保留连续效应及完整inflation阈值0/5/10/15/20% × honest-error允许0/1/5/10%的网格。在honest-error≤5%下，原18个分配比较通过数为8/4/2/0/0；JUCars robust-benefit精确降幅约9.985%，无实用价值的断点解释。未为近miss放宽门槛，也未编造平台偏好或决策论校准。

证据：`statistics/threshold_sensitivity.csv`、`frozen_allocation_threshold_sensitivity.csv`及连续效应CSV。

## F：审计依赖与独立状态交叉检查

§6.2（第11页）公开历史审计共享StateSpace、query/state原语、数据加载、model.predict/head.score等依赖，改称corroborating re-derivation或separate checker。新增独立整数bit-mask oracle：生产StateSpace只作为被测对象，oracle不调用其构造、查询或replay；覆盖所有16种天然缺失mask、max-hidden 0…4、1188个fixture转换。直接读取全JU/MU验证CSV覆盖521164个合法字段转换，4个注入的枚举/转换/物化错误均被拒绝。

这补上状态空间盲点，但不独立重实现预测器、scorer、训练库或整个数据构建流水线。独立性仅限明确检查的原语，不能包装成从零重实现的全流程。

证据：`state-audit/check_state_space.py`与`state-audit/completion.json`。

## G：强基线被埋在附录

§7.3（第17页）把ordinary-benefit及ACO-1在synthetic/JUCars上inflation优于原SAV的结果移到正文，并在摘要/引言突出。“普遍SAV优势”在这些受控比较中没有复现。保留MUCars的条件性收益、ACO跨零区间、调参及适配范围；三seed原方法比较与十seed匹配因子实验的模型身份严格区分。

没有把inflation单指标胜出改写成全面Pareto支配，也没有声称所有来源/所有SAV条件都失败。

## H：历史依赖、最终记录机制及正成本

§5.3（第8–9页）新增final-record consistency、解释/纠正/申诉和选择差异的讨论。给出最终记录补全域上的最小报价包络；保证依赖真实记录覆盖、非空嵌套completion sets及非负成本。它可以降低honest报价、恶化MAE，域外需abstain或明确不保证的fallback。这是解析备选机制，未进行模型全量实证，也不声称新发明了单调插补。

§7.7/Table8（第20–21页）实际重新搜索统一0.005、统一0.02、异质0.02h_i成本的108个cell，全部三来源、三seed、两个feedback和两个allocator条件保留；并保留36个原零成本对照。不是从旧效用简单减一个cost。

新的重要正面结果：synthetic robust/suppression/top-B在异质成本下三个seed的inflation反馈方向均有利，honest MAE/attacked MAE/failed-query的均值也改善；uniform0.02只有一个seed的inflation方向有利。异质条件inflation均值差约+0.000553、honest MAE改善4.293、attacked MAE改善12.198、失败概率改善0.100个百分点（差值均为无反馈减反馈）。绝对失败概率仍约9.4%/9.3%。JU/MU在所有正成本条件中的inflation方向仍不利，20个未收敛seed/cell批次保留。

这是事后三seed子集的均值Pareto改善，没有显著性、全面因子扩展或普遍优势声明。成本未校准成人类行为/货币处罚。正面反转已同时写入摘要和结论。

证据：`outputs/review-cost-sensitivity-v2-analysis/completion.json`；全部条件在`completed-supplements-stage1.zip`。

## I：仓库状态

CURRENT_DELIVERY、状态与AI交接入口统一指向30页修订及当前阶段。原训练/四阶段审计确实30/30；原26页交付包标为历史稿。原PRE_SUBMISSION_REVIEW明确superseded，不再用其“无MAJOR”结论证明可投稿性。每个完成阶段私有仓库提交并回读核对；后台进程自身不会自动推送GitHub。

## 中文核对：仍然没完成的是什么

- 两个完整真实队列的计算、复核、加权统计和正文回填均已完成；原负结果、局部正成本反转及探索性边界继续保留。
- 独立新队列/训练人口确证、真实卖家行为和成本校准；当前研究没有这些证据。
- 外部机器完整训练复现；已完成的只是同一物理机器新依赖环境的1536行汇总统计复算。
- 公开仓库/归档DOI/许可证决策与真实作者责任；私有仓库不等于公开可复现。没有自行公开、生成DOI或虚构作者审批。
- 最终期刊模板和用户单位适用中科院三区口径；没有投稿或接收事实。

当前完成的是实质修订与有限证据补强，不是可投稿性或接收保证。
