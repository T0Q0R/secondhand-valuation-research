# 完整论文交付

主文件仍是原编辑器打开的 `paper/innovation-addendum-v1.tex`；同稿PDF为 `paper/innovation-addendum-v1.pdf`。26页，9节正文、5组附录、14篇已核对引用、2幅矢量图、11个编号表。作者与单位按用户要求暂留空。

论文把创新落实为受限信息前沿、恢复路径诊断和条件验证历史cap，并用完整匹配实验审计真实收益与代价。原 SAV/CDM、匹配实验和其他强基线保留各自身份；不再以局部胜出暗示普遍优势。

计算及四阶段审计完成：30组、4320单元、432万条输出、45372960个合法单边偏离。36个主容量反馈对比全部恶化inflation，34个未校正区间不利；MUCars的12个robust初始目标对比通过点门槛；18个联合干预无通过门槛。

交付包 `paper/manuscript-delivery-v1.zip` 包含可单独编译的同稿源/PDF、矢量图及图源、整合/核查脚本、全文核查记录、完整六预算分析证据和附录强基线的小型证据。`delivery_manifest.json` 给出每项SHA256；ZIP自身哈希在包外 `delivery_receipt.json`。

复核入口：`PRE_SUBMISSION_REVIEW.md`、`qa/render-audit.json`、`qa/vocabulary-scan.json`、嵌入图几何审计。原标准检测器的嵌入页假阳性报告也保留；校正仅改变text-trace提取，不改变阈值。

源文件没有外部图片或bibliography依赖，可用Tectonic编译。研究数据和完整训练/回放仍遵循仓库的数据、环境与复现说明：交付包不含大型模型、原始挂牌记录或逐条输出，也不意味着外部环境已重跑完整实验。

科学稿已写完并核查；正式投稿仍需作者责任与声明、单位适用的中科院分区确认、选刊模板和证据访问安排。见 `VENUE_PREPARATION.zh.md`。没有投稿或接收事实。
