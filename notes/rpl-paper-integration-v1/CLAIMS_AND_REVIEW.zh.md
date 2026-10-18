# 证据链与逆向审阅

1. 开头问题：该用原生RPL、采集族，还是两者叠加？
2. 设计：同一gap/no-feedback拟合，λ0/1×五采集族；四神经评分不变，ACO按估价器重建训练损失，18原生head单元只复用。
3. 证据：45/45同seed配对inflation下降；三来源所有stacked族均值低于任何off族均值；对原生RPL参照仍有非均匀策略取舍。
4. 代价/范围：synthetic honest MAE+0.99%，失败查询会增加；n3且固定人口，18非收敛批次、最大regret.149163246，非新四阶段链。

Claim: 可与五族叠加 | Evidence: 90 cells/45 pairs | Supported, n3 retrospective only.
Claim: RPL stacking can improve on native-head RPL | Evidence: matched 18 reused native cells, changes -17.07/-4.76/-22.47% at observed lowest means | Supported descriptively, no validated optimal family.
Claim: 任意叠加都比原生RPL好 | Evidence: synthetic GDFS inflation .00907 >native .00639 | Rejected;正文显式保留反例。
Claim: 多目标全面占优或跨机数值复现通过 | Evidence: honest/failed-query costs and retained strict external failure | Rejected.

五维自审：贡献——只增强恢复项受控证据，不扩展原创性；清晰——说明native head含获取、三种子与十种子不同；效果——给绝对值及同seed对照；完整——五族/原生对照/多目标/非收敛均保留；方法——来源适配和ACO模型依赖明确，无评测选择默认。
