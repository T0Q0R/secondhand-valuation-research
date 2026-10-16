# Windows 原生核心训练与外机复现

这是另一台电脑的从头训练入口，不是训练完成或外部复现通过的证明。建议 Windows 10/11、Intel/AMD 64 位处理器、Python 3.12 64 位。当前不覆盖 Windows ARM64。使用 CPU，无需显卡或 CUDA；固定两计算线程，不改变模型规模、训练轮数或评估设置。

## 1. 安装工具

安装 [Python 3.12（64位）](https://www.python.org/downloads/windows/) 和 [Git for Windows](https://git-scm.com/download/win)。Python 安装时保留 Python Launcher 和 pip。关闭再打开 PowerShell，检查：

```powershell
py -3.12 --version
git --version
```

如 `py` 不存在，先修复 Python 安装，不能换成不明版本的 `python` 继续跑。

## 2. 在 PowerShell 逐段执行

建议独立英文目录，避免长路径。下列命令第一次执行；如果已有同名仓库/虚拟环境，请选新的独立父目录。

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\rpl-windows" | Out-Null
Set-Location "$env:USERPROFILE\rpl-windows"
git -c core.autocrlf=false clone https://github.com/T0Q0R/secondhand-valuation-research.git sav-val
if ($LASTEXITCODE -ne 0) { throw "Git clone failed" }
Set-Location sav-val
git config core.autocrlf false
py -3.12 -m venv ..\.venv-gdfs
if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed" }
..\.venv-gdfs\Scripts\python.exe -m pip install --only-binary=:all: -r reproduction\windows-core-v1\requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed; keep the error output" }
```

必须保留 `core.autocrlf=false`：源码按原始字节检查 SHA256，不能自动改成 Windows 换行。Windows 锁文件保留现有所有固定版本，另固定 pandas 在 Windows 所需的 `tzdata==2026.2`。安装失败请发错误，不要自行换版本。安装阶段需要网络，耗时取决于下载速度；不要用本机安装耗时估计训练耗时。

启动训练：

```powershell
..\.venv-gdfs\Scripts\python.exe reproduction\windows-core-v1\start.py
```

无需激活环境、修改 PowerShell 执行策略或管理员权限。程序先核验源码、依赖和固定数据人群，再训练。`FIT_STAGE` 表示正在拟合某折/部署模型，`EXTERNAL_CORE_CELL` 表示完成一项评估。训练期间接电并保持终端打开；启动器仅在本次运行中请求系统避免空闲睡眠，结束时恢复。

## 3. 完成后回传 ZIP

PowerShell 最后显示 `RETURN_ZIP ...`，文件位于：

```text
用户目录\rpl-windows\external-rpl-windows-return-时间戳.zip
```

把这个 ZIP 发回，并说明电脑 CPU、内存以及确实在另一台 Windows 电脑上运行。ZIP 包含摘要、对照、环境、日志与核验凭据；不包含模型权重或逐条结果。即使失败或数值不匹配也请原样回传。

如中途正常 Ctrl+C，已完成的阶段模型保留，再执行同一启动命令可复用通过哈希核验的检查点；尚未完成的阶段需要重算。如强制关机后遇到 `.run.lock`，先确认原进程已经结束，再移除该锁文件；不要同时启动两个训练。

## 科学范围与边界

合成数据由冻结生成器生成，不需要获取真实数据。固定训练 5,000 条、评估 1,000 条、seed 13、λ=0/1、预算 0/0.1/0.3，共 6 个评估单元。每个权重重新拟合 3 个外层折与 1 个部署价格模型，共 8 个价格模型；12 个残差 epoch、160 棵采集树和 250 棵 CatBoost 迭代保持原设置。参考结果只在训练和评估全部结束后读取，不用于选模型。

Windows 入口保留冻结科学源码；将仅用于分组的两个纯函数单独复制，运行前用 AST 检查与原函数完全一致，从而避免导入 Unix 专属 `fcntl`。数据哈希显式采用 UTF-8/LF，和原 macOS 人群绑定相同。运行时另保存 Windows、Python、所有安装包版本和 PyTorch 构建信息。

数值验收仍采用原阈值 `atol=1e-7 + rtol=1e-5 × |reference|`，不为跨平台事后放宽。退出码为 0 只表示计算完成；必须读取 receipt 区分通过与 `differences_require_review`。此前另一台 Mac 的严格数值复现未通过，原失败证据继续保留，不能用本入口抹掉。

此入口完成本机输入/分组等价性与工程核查，尚未在 Windows 机器实际执行。六单元通过也只覆盖这个核心子集，不能写全论文或全审计链已外部复现。本机后台十种子训练及核心审计不受此入口影响。

真实数据源可在合法准备相同处理数据后使用 `run_from_scratch.py --dataset all --output <仓库外新目录>`，但目前先跑上述合成核心，不扩展实验矩阵。

环境依据：[Python Windows 文档](https://docs.python.org/3.12/using/windows.html)、[PyTorch 官方安装说明](https://pytorch.org/get-started/locally/)。
