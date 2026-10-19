# 最新：更强gap90格全部完成，完整汇总核对通过，尚未最终入稿

2026-10-19T08:18:58+08:00：90新增格/360新拟合凭据及210候选/60选定结果核对；独立标量选择检查60/60通过。更强gap在30/30配对操纵增益更低，两组真实来源平均诚实/攻击MAE也更低，合成来源有误差权衡。必须收缩RPL普遍优势表述；无训练运行，未启动新计算。主稿26页/补充10页仍为工作版，完整新结果尚未回填。见notes/review-improvement-v1/gap/RESULTS.zh.md。

请以完整验证和结果为准。旧running/stopped检查点仅作历史，不要重复启动。

# 继续入口

目标仍活动：用户授权按判断改进全部必要证据与论文，不以启动计算为完成。

先查真实进程：v2父19418、worker19429/19430/19431，统一exec session55898；outputs/review-gap-controls-v2/execution.log与completion/failure/status。v1已主动终止，不重启。最多6计算线程、nice10。10个合成seed完整配对symlink复用v1，剩JU/MU共60新评估运行。v2省略policy=None训练中未使用的中间获取头，真实JU13完整单折逐参数/报价/日志一致；最终OOF头仍拟合。所有旧检查点保留。不要因一次观察超时重启。

2026-10-18T20:02+08:00 进程更正（历史保留）：原 v2 父 19418/worker 19429-19431 是 Codex exec 会话 55898 的子进程（PPID 9971），用户 19:54 关闭 Codex 时被整棵进程组终止，无 failure.json，checkpoint 完好。已用 setsid+nohup 脱离终端重启同一命令：新父 21937（PPID=1，launchd 直接接管），3 worker，同 6 线程/nice10，从检查点续算，未改源码/参数/manifest。旧日志保留为 execution-run1-codex-killed.log。当前进程以 pgrep 实测为准，勿按 19418 判断。

已完成：60模型/180旧格机制、1800批汇总、独立检查；数据流转/缺失/合法报告/合成方程；文稿+正式补充已整合上述证据；26页主稿+10页补充工作版内置编译和视觉QA通过，S4明确gap未完成。旧参数/种子四图原样在补充S7，仍保留其源路径与3个PDF副本；全11旧图/旧主表/正式定理证明保留。主稿当前图7、表9、引用21。

待完成：

1. 等现有v2完成90格（360科学价格拟合含复用阶段），inspect completion及全部30pair/90cell/360fit receipts，保留负结果。
2. 单线程运行notes/review-improvement-v1/analyze_gap.py（已切v2）。完整矩阵应210不重复候选格=120旧RPL+90新gap，60个OOF选定结果；训练选择每族4候选，不读正式指标。当前gap/仅partial synthetic，禁止拿它作全矩阵。独立重实现选择规则核查，不仅调用同一函数。打包标量fit/round/cell/selection凭据，禁模型/原始/逐条。
3. 运行plot_gap.py，仅在full verification通过后；所有7候选/10seed与选定配对6面板。nature-figure技能本轮已读，Python既有流程/偏好已保存；1.5pt对齐、源码预检、最低5pt字形和碰撞审计，修所有FAIL、逐panel视觉QA。脚本未运行，可能需布局调整。图存paper/figures/review-v1。
4. 将全部候选/OOF选择频率/配对效应/收敛值正式放S4（builder读取gap-supplement.tex），主稿§7.2补选定比较表tab:stronger_gap和基线权衡解释；摘要/引言/讨论及审计范围同步。不能声称RPL全面优于强gap，已完成合成结果显示gap更低I但更高H/A误差。
5. build_supplement.py输出/tmp/review-supplement-source.tex，需要复制到paper/review-supplement-v1/main.tex，并将includegraphics依赖复制到其images/figures/...（内置编译不允许读项目外图）；旧3PDF副本已有。新增权衡图也要复制。不改旧legacy-extended-appendix.tex（逐字保留合同）。版本映射添加v2等价加速commit7d870c2及最终gap证据commit。
6. 编译两文件、同源Tectonic导出；运行qa_paper.py（不带--interim，需要tab:stronger_gap/full gap verification），全页视觉/关键数字表检查，更新qa.json与完成矩阵、五维主张证据自审、打包交付、每阶段提交远程核对。可以在编译/重图时暂SIGSTOP一个本任务worker释放2线程，然后必须SIGCONT恢复同一PID；当前document-check-pause.json已resumed。不要暂停goal。

作者新顺序：汤宇晨/Yuchen Tang；游凤芹/Fengqin You（第二兼通讯irisyou@njust.edu.cn，导师）；顾峻祥/Junxiang Gu（第三、写作指导）；庞鑫/Xin Pang（第四，具体贡献未供不推断）。用户说论文都是自己写，已记录Tang撰写。基金/冲突用户要求不用管，不再追问、不代填无。论文/CFF/BibTeX/Zenodo当前元数据顺序已改，公开API验证published与原ZIP MD5不变；旧四作者顺序是历史。

Zenodo10.5281/zenodo.23447567 ZIP源89ad56e，包含旧90交叉/6格差表，不含此次后续diagnostics/gap或论文；不能声称当前新数据已进原不可变ZIP。实际新市场/跨真实来源外机验证未做，采取明确固定设计proof-of-concept边界，不能伪装已解决因果或数值失配。不要让用户重跑外机诊断。

截至本入口写入，最新远程main=7d870c267895e35e17685a443951a7a35085bc22；后续工作稿提交若已完成，须读取真实远程head。GitHub工具可create_blob/tree/commit/update_ref，不需要本地Git（此目录没有.git）。每个可独立检查单元须更新PROGRESS/STATUS并提交远程核验。functions store('reviewCommit')保存上一已验证提交；存在时可读，仍应检验远程冲突。

2026-10-18T22:35+08:00 按用户要求在当前组完成后停止（历史保留）
- run3（父PID 22619，PPID=launchd，已脱离终端）22:26:45 最后一对 mucars/seed-2026 写出 completion.json；22:26:47–22:26:53 由看守脚本按计划终止（日志 notes/review-improvement-v1/diag/stop-watch.log：kids=22621..22624 全部 SIGTERM，残留检查为空）。无 failure.json，全部检查点保留，写入均为 tmp+replace 原子写。
- 进度 69/90 cells = 23/30 对：synthetic 10 + jucars 10 + mucars 13/42/2026。被中止的在途对 mucars 101/211 只有数据绑定与 gap-1 起步，无损。
- 未完成：mucars 101/211/307/401/503/601/701 共 7 对（21 cells）。status.json 已改为 stopped_by_user_after_current_group_preserving_checkpoints。
- 恢复（在本目录）：env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 VECLIB_MAXIMUM_THREADS=2 nice -n 10 ../.venv-gdfs/bin/python experiments/run_review_gap_controls_v2.py --workers 3 >> outputs/review-gap-controls-v2/execution.log 2>&1；建议用 setsid/nohup 脱离终端，30 对全完成才写完成状态。
