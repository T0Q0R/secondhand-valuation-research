# Research repository instructions

Read AI_HANDOFF.md and docs/STATUS.md before edits. Preserve scientific evidence boundaries; do not invent empirical results or novelty. Respect frozen source/hash closures and role-separated cross-fitting. Do not start duplicate jobs or reuse original-machine PIDs. Prefer small smoke checks before long computations. Keep negative results, failed verification attempts and nonconverged responses. Large raw data/model files are excluded; read data/README.md. User instructions take precedence.

## 必须遵守：每完成一项工作就提交进度

本要求适用于本项目的所有 AI 与协作者：每完成一个可独立检查的工作单元（代码修改、实验阶段、审计、分析、图表或论文修改），都必须在开始下一项工作前，将成果与进度提交并推送到本仓库。不能只在聊天中汇报，也不能把多项已完成工作留在本地等待项目结束才上传。

每次提交必须：

1. 上传本项工作的相关源码、配置、文稿或小型结果，写明具体完成了什么。
2. 在 `docs/PROGRESS.md` 追加带时区的时间记录：工作内容、成果路径、验证方法及结果、限制或失败、下一步。
3. 工作状态改变时，同步更新 `docs/STATUS.md` 和 `docs/STATUS.json`；区分“实现完成”“计算完成”“审计通过”和“最终交付完成”。
4. 用有具体含义的 commit message 提交，推送后核对远程提交成功；直接通过 GitHub 工具写入时也须核对返回结果或远程文件。

长任务开始时先记录配置、范围和状态为“运行中”，在每个可持久化检查点或阶段结束后提交进度；任务仍在运行时不得标记完成。失败、暂停或受阻也须记录实际状态及恢复步骤。

大型模型、原始数据与逐条实验输出继续遵循 `data/README.md`：提交摘要、数量、哈希和合法的获取路径，不强行放入普通 Git；密钥不得上传。提交进度不构成修改冻结实验源码或覆盖已有证据的授权。

若网络、权限或服务错误导致无法推送，保留本地成果与待提交记录，明确报告“尚未同步”；连接恢复后优先补交。没有远程成功证据，不能声称已上传。本规则不自动建立实时同步服务，也不表示后台进程会自行提交；执行工作的 AI 或协作者负责落实。
