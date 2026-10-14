# AI接手入口

先读AGENTS.md、docs/STATUS.md以及最新实验完整性记录。

快照：2026-10-14 04:17:36 UTC（Asia/Shanghai项目）。

当前优先事项为补齐实验，未补齐前不再改写或重新生成论文。先核已有经典/近年基线、参数选择与敏感性、组件单独/组合移除消融以及结果曲线。不得假定三个组件都是创新点，不得重跑已有完成实验，不得把负结果删掉。

四张结果图在该指示前已完成并嵌入同一稿：cap多目标取舍、成本/反馈差异、绝对方差分解、final-record覆盖/误差集中。当前保存稿36页、6图、15表、16参考文献，作者留空。内置编译、原图字体/碰撞、三组面板对齐、六个嵌入图页默认阈值几何检查通过；0Overfull/未定义引用、原1Underfull。新图源数据/脚本/矢量/PNG/QA见notes/results-visual-v5/visualization-assets-v5.zip。没有新模型训练、响应求解或置信区间。

本轮没有再生成全论文包。paper/revision-delivery-v4.zip是32页历史支持包，不是当前36页稿。当前源paper/innovation-addendum-v1.tex，SHA256 bf799e53b6ba4cbebf84ec78d6c2c3ffe581e6a9a21a8f4e312dd2646f656a24；PDF c11fd3e09c2e16da6e73e016f98f18c4635d34e47b48c07d9bbb00ee7704ad0b。保持原编辑器；旧v2/v3/v4或v5回填脚本都不能在补齐实验前随意运行。

原30/30组、4320单元训练审计和全真实来源480单元扩评仍已完成；所有旧PID已退出，不能重启。MU跨零不是零效应；seed主项98%仅uncapped两个条件，队列/加权变化已区分。正成本反转只在synthetic子集有条件描述性收益，完整四字段final-record机制仍未实测。详见notes/teacher-review-v4/REVIEW_RESPONSE.zh.md。

公开/许可/DOI、外部全训练、作者事实与实际投稿仍未完成。不得宣称SAV普遍优势或SCI接收保证。科学环境用../.venv-gdfs/bin/python原路径；原始数据和权重不上传普通Git。每独立完成工作依AGENTS提交、推送、回读。
