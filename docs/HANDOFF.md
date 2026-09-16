# ManiLoop：新电脑迁移与继续工作交接

> 更新日期：2026-09-16。本文面向项目作者和接手的开发助手。
> 最新状态：已加入 Codex 登录、单步／暂停、前后图像、回放及完整 episode 录制。新一轮 GPT-6 运行在 46 次决策、706 控制步后通过 LIBERO 官方成功判定，完整录像包含全部重试；成功触发后立即终止，未额外验收松爪退离。见 [当前演示说明](GPT6_DEMO.md)、[成功报告](research/2026-09-16-gpt6-success-episode.md) 和最新 worknote。[首次失败](research/2026-09-16-gpt6-demo-first-run.md)及下文原迁移基线保留为历史证据。
> 仓库：<https://github.com/Daniel-rmc/ManiLoop>；默认分支：`main`。
> 本次迁移核对时，已有代码基线为 `d3530ed`，本地工作区干净，GitHub 远端 `main` 与本地一致。本文和对应工作记录会在此基线上作为新的交接提交同步。
>
> 新电脑第一次下载仓库使用 **`git clone`**；已有仓库获取更新使用 **`git pull`**；**`git push` 是把本地提交上传到 GitHub**。

## 1. 最短恢复路线

1. 安装 Git 和 64 位 Python 3.12，克隆仓库。
2. 在新电脑创建主环境 `.venv`，安装依赖，运行离线检查。
3. 启动 `chat`，重新填写自己的 TOML 与 API Key，测试文字通信。
4. 需要继续机器人实验时，安装独立 LIBERO 环境，打开仿真网页。
5. 需要继续本地 SmolVLA／ACT／Diffusion 实验时，再安装 VLA 环境和权重。
6. 阅读本文第 7–9 节及最新 worknote，再确定下一项工作。

**不需要把旧电脑的虚拟环境复制到新电脑。** 新电脑的目录可以不同；所有命令从仓库根目录执行。基础功能不依赖旧电脑的外置 MuJoCo 环境、Codex、CC Switch、Node.js、ROS、Docker 或实体机械臂。

## 2. 获取仓库并建立主环境

### 2.1 macOS / Linux

在希望保存项目的父目录打开终端：

```bash
git clone https://github.com/Daniel-rmc/ManiLoop.git maniloop
cd maniloop
git status --short --branch
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m maniloop list
python -m pytest -q
```

`requirements-dev.txt` 同时安装主程序和测试依赖。以后每次开新终端，先进入仓库并执行 `source .venv/bin/activate`。如果系统的 `python3` 已是 3.12，可以用它替代 `python3.12` 创建环境。

### 2.2 Windows PowerShell

```powershell
git clone https://github.com/Daniel-rmc/ManiLoop.git maniloop
cd maniloop
git status --short --branch
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m maniloop list
.\.venv\Scripts\python.exe -m pytest -q
```

Windows 不必激活环境，也不必调整脚本执行策略。后文每条以 `python` 开始的命令，在 PowerShell 中替换为 `.\.venv\Scripts\python.exe`。

### 2.3 检查安装是否正常

```bash
python -m pip check
python -m maniloop benchmark --suite examples/offline-suite.toml --no-render
```

这两项不调用云端模型，第二项也不需要图形环境。离线矩阵采用模拟适配器，任务成功率为零是预期结果；它验证接口，不验证抓取能力。

项目主环境固定 Python 3.12 对应的直接依赖：MuJoCo 3.12.0、NumPy 2.5.3、Pillow 12.3.0、OpenAI SDK 3.8.0。安装文件是依据；不要为了消除版本冲突，把 LIBERO 的依赖装进这个主环境。

新电脑首次检查应保存系统、Python 版本及实际测试结果。旧电脑的通过记录不等于新电脑已经通过。普通测试会跳过未启用的可选 LIBERO 集成检查。

## 3. 先恢复聊天与网页

### 3.1 独立聊天服务

```bash
python -m maniloop chat --port 8769
```

在运行服务的这台电脑上打开：<http://127.0.0.1:8769/chat>。

1. 选择手动配置，或导入／粘贴自己的 `config.toml`。
2. 重新填写 API Key，读取配置并确认服务地址、模型 ID 和协议。
3. 发送短消息，查看正文、响应完成状态、耗时和用量。

聊天页支持 Responses 与 Chat Completions。**机器人策略目前使用 Responses**，并要求图像输入及结构化动作输出；聊天协议兼容不代表机器人协议已兼容。

Key、导入配置和聊天内容不由 Git 同步，也不保存在浏览器持久存储中。旧电脑页面内尚未保存的配置，在新电脑要重新填写。不要把 Key 写入本文、示例配置、提交或 issue。

CC Switch 是可选配置来源：如新电脑已安装，可重新选择 Codex 页的供应商。默认可读 `~/.cc-switch/cc-switch.db`、`~/.codex/config.toml` 和对应认证文件；也支持显式路径。**旧电脑的绝对路径不能直接复用。** 不要把 CC Switch 数据库或认证文件提交到仓库。

Base URL 要保留供应商要求的专用前缀；填基础地址，不额外追加 `/responses` 或 `/chat/completions`。供应商没有模型列表接口时，可以直接输入模型名称。完整说明见 [API_CHAT.md](API_CHAT.md)。

### 3.2 自建 MuJoCo 场景

保持聊天服务终端运行，另开终端、进入仓库并激活主环境，再执行：

```bash
python -m maniloop smoke --robot panda
python -m maniloop demo --robot panda --port 8765
```

打开 <http://127.0.0.1:8765>。先检查双相机、手动移动、夹爪开合和重置；这些操作不需要 Key。终端 `Ctrl+C` 关闭服务，网页“停止”只停止当前任务。

端口只是惯例：8765 为自建场景，8767 为 LIBERO，8769 为聊天。若端口被占用，用 `--port` 指定其他值，并打开相应地址。旧电脑的运行进程和浏览器标签不会迁移。

### 3.3 渲染环境差异

- macOS：从已登录桌面的普通终端启动。不要设置 Linux 专用的 OSMesa 环境变量。
- Linux 无显示器：Ubuntu/Debian 可先安装 `libosmesa6`，在 Python 启动前设置 `MUJOCO_GL=osmesa`；例如 `MUJOCO_GL=osmesa python -m maniloop smoke --robot panda`。EGL 需要相应驱动。
- Windows：基础离线测试已有 CI 通过记录，但 Windows 图像渲染与 LIBERO 运行尚未实机验证；应在新机器分别确认。

详见 [README 的环境与故障说明](../README.md)。服务默认只监听本机 `127.0.0.1`；在另一台电脑的浏览器输入同一地址，不会连接到这台服务。

## 4. 恢复 LIBERO 官方任务

主环境装好后执行：

```bash
python -m pip install uv
python scripts/setup_libero.py
python -m maniloop list --backend libero
python -m maniloop smoke --backend libero
python -m maniloop demo --backend libero --port 8767
```

打开 <http://127.0.0.1:8767>。默认是 Panda、`libero_spatial`、task 0、init-state 0。

安装器需要 Git、网络和 uv，自动准备独立 Python 3.10、固定上游源码及资产。为依赖与缓存预留数 GB 空间。无需单独下载示范数据集，也无需先安装模型权重。

Windows 未激活主环境时，给安装器明确指定 uv，避免 PATH 找不到：

```powershell
.\.venv\Scripts\python.exe -m pip install uv
.\.venv\Scripts\python.exe scripts/setup_libero.py --uv .\.venv\Scripts\uv.exe
.\.venv\Scripts\python.exe -m maniloop list --backend libero
.\.venv\Scripts\python.exe -m maniloop smoke --backend libero
.\.venv\Scripts\python.exe -m maniloop demo --backend libero --port 8767
```

运行主程序仍使用 `.venv`，不手动激活 `.venv-libero`。主程序会启动独立 worker。LIBERO 使用 MuJoCo 2.3.7 / robosuite 1.4.0，与主环境 MuJoCo 3.12.0 隔离，这是设计安排。

固定 LIBERO 提交为 `8f1084e3132a39270c3a13ebe37270a43ece2a01`。不要通过更新上游源码或改依赖来“顺便升级”，否则实验协议会变化。安装脚本发现既有源码修改或版本不符会停止，保留现场后再处理。

可选真实集成检查，macOS / Linux：

```bash
MANILOOP_TEST_LIBERO=1 python -m pytest tests/test_libero_integration.py -q
```

Windows PowerShell：

```powershell
$env:MANILOOP_TEST_LIBERO = "1"
.\.venv\Scripts\python.exe -m pytest tests/test_libero_integration.py -q
Remove-Item Env:MANILOOP_TEST_LIBERO
```

这需要 LIBERO 安装与渲染均可用。后端路径、协议和更多任务选择见 [LIBERO.md](LIBERO.md)。

## 5. 恢复可选本地学习策略

先完成第 4 节。只继续云端 VLM 工作时可以跳过本节。

```bash
python scripts/setup_vla.py
```

默认安装独立 LeRobot 推理环境并下载 SmolVLA。需要三个模型时：

```bash
python scripts/setup_vla.py --models smolvla-libero act-libero diffusion-libero
```

Windows 相应使用：

```powershell
.\.venv\Scripts\python.exe scripts/setup_vla.py --uv .\.venv\Scripts\uv.exe --models smolvla-libero act-libero diffusion-libero
```

主环境 `.venv`、仿真 `.venv-libero`、推理 `.venv-vla` 三者分开。模型与分词器固定版本由 [catalog.py](../src/maniloop/agents/lerobot/catalog.py) 管理，下载到 `.runtime/models/`。首次下载需要数 GB 网络流量与磁盘空间。

先做少量真实本地推理，不会调用云端 API：

```bash
python -m maniloop benchmark --backend libero --agent lerobot --local-model smolvla-libero --max-calls 2 --max-wall-seconds 600
```

设备自动选择 MPS／CUDA／CPU；硬件变化可能影响耗时与数值结果。两步运行只是加载与接口检查，不预期完成任务。完整预算和模型边界见 [VLA.md](VLA.md)。

## 6. GitHub 包含什么，哪些需要另行保留

| 内容 | 是否随 clone 获取 | 新电脑处理 |
|---|---|---|
| `src/`、兼容入口、测试、脚本、示例、文档、CI | 是 | 直接使用 |
| 自建 ARX5／Panda 机器人资产及来源许可 | 是 | 随仓库获取 |
| `.venv/`、`.venv-libero/`、`.venv-vla/` | 否 | 按本文重建，不能跨电脑直接搬虚拟环境 |
| `.external/LIBERO/`、`.runtime/python/` | 否 | 安装脚本按固定版本重建 |
| `.runtime/models/` | 否 | 重新下载；需节省流量时可私下迁移完整模型目录，再运行安装器核验／补全 |
| `runs/`、`artifacts/`、`arx5_demo/artifacts/` | 否 | 需要历史轨迹时，从旧电脑另行复制 |
| API Key、私人 TOML、认证文件、CC Switch 数据库 | 否 | 在新电脑重新配置，或通过自己的安全渠道迁移 |
| 旧浏览器聊天内容、内存中的 Key、运行中任务 | 否 | 重新启动和填写；运行进程不提供跨机器续跑 |
| 已写入文档的结果、分析与里程碑 | 是 | 见 experiments、research 和 worknotes |

**迁移时已确认旧电脑 `runs/` 存有约 253 MB 原始实验文件。它们不会从 GitHub 下载回来。** 如果未来论文需要重看原始轨迹，应在清理旧电脑前单独备份。`.runtime/models/` 约 2 GB，可重新下载；体积是本次盘点值，后续会变化。

macOS / Linux 可在旧仓库根目录执行下面的可选备份命令，只打包实验记录和渲染产物：

```bash
tar -czf ../maniloop-private-runs-2026-09-16.tar.gz runs artifacts arx5_demo/artifacts
```

Windows 可通过文件管理器复制上述目录；若使用 PowerShell：

```powershell
Compress-Archive -Path runs,artifacts,arx5_demo/artifacts -DestinationPath ../maniloop-private-runs-2026-09-16.zip
```

这些命令是手动备份示例，**本次没有自动创建或上传实验压缩包**。只包含旧机器实际存在的目录，并使用未占用的目标文件名。通过私有渠道传到新电脑后再解压，已有同名记录时先比对，避免覆盖。不要将原始日志压缩包推送到公开仓库。

## 7. 当前进展：哪些结论可靠

| 项目 | 交接状态 |
|---|---|
| 自建 MuJoCo | ARX5／Panda、两个布局、抓放／推物、网页与批量入口已实现 |
| LIBERO | 复用固定官方任务、初始化、Panda OSC 与独立 `check_success()`；不是对所有任务的完整验证 |
| 本地策略 | 同一 spatial task 0 / init 0 / seed 0：SmolVLA 79 步成功、Diffusion 108 步成功、ACT 500 步预算内未成功；不能外推整个 benchmark |
| 云端文字通信 | 用户配置的供应商通过 Responses 返回完整文字；SDK 空错误对象误判已经修复 |
| 云端视觉／动作 | GPT-6 真实文字、图像、结构化动作及 5 毫米上移通过；首次完整抓放 24 次决策后官方评分 false，稳定自主抓放尚未通过 |
| LLM 执行器 | `tcp_target_servo_v2` 已实现，依据本体反馈追踪固定目标；保留 `osc_step` 作基线 |
| 语义九动作 | Show-Harness 分析与设计建议已完成，适配器尚未实现 |
| 论文研究 | 正在选题讨论；还没有锁定假设、预算、任务集合或实验方案，没有启动论文实验 |

已知通信问题的修复位置是 `providers/responses.py`：供应商空错误对象经 SDK 反序列化后会出现默认字段，现使用 `model_dump(exclude_unset=True)` 避免将 SDK 补充字段误判为服务错误。真实非空错误、不完整响应与非法动作仍应拒绝；不要为了“跑起来”取消完整性检查。

原有离线、集成和 GitHub Actions 结果按提交记录在 [VALIDATION.md](VALIDATION.md) 与 [worknote.md](worknotes/worknote.md)。此前普通离线回归记录为 142 项通过、13 项可选检查跳过、58 项子测试通过。本文交接本身只核验版本同步、命令入口和文档，不冒充在新电脑重跑了这些测试。

## 8. 下一步接着做什么

### 8.1 工程上的第一个门槛

在新机器恢复环境后，按顺序验证：

1. 离线接口和相机正常。
2. 用户重新配置 API，文字聊天返回完整正文。
3. 仿真页文本、单图、双图动作格式诊断分别通过；诊断不会执行动作。
4. 从新初始化发出一次小位移，检查请求值、实际位移、执行残差和终止原因。
5. 再确定正式任务与实验预算，开始闭环评测。

第 2–4 步可能调用付费 API；本次迁移不代表已经发起这些测试。机器人入口要支持 Responses、图像和结构化动作，不能只因聊天页的 Chat Completions 成功就继续执行。

### 8.2 论文讨论上下文

用户希望约两周内探索一个有意义、可检验的观点并写出论文。已经确认长期平台强调：完整策略配置分组比较、传感器输入边界、固定策略评测与学习模式分开，以及“先完成，再完善”。

目前仅有下列候选，**尚未决定采用哪一项**：

- A：冻结云端 VLM 能否区分持续执行偏差与临时阻挡，并依据真实执行反馈采取不同的修正动作。
- B：模型能正确描述执行不足，是否也会在下一步控制中实际利用这个判断。
- C：视觉成功检测的连续错误结构，是否比逐帧准确率更能解释闭环失败。

讨论中建议先探索 A、以 B 为诊断，但用户尚未确认。也未确认交付目标、付费预算、每日人工投入和是否接受条件性／负结果；**之前提出的预算数字只是建议，不能视为实验授权**。下一位助手应先继续这轮讨论，再敲定假设与实验。

已查到的近邻用于防止重复选题：

- [Show-Harness](https://arxiv.org/abs/2609.10522)：语义动作与明确约定、历史、恢复等已有消融；仓库已有 [工程报告](research/SHOW_HARNESS_ANALYSIS.md)。
- [AxisGuide](https://arxiv.org/abs/2606.06761)：动作坐标的视觉提示。
- [Reflective VLA](https://arxiv.org/abs/2606.25215)：观察—动作—后果上下文及跨环境适应。
- [How Should VLAs Use Proprioceptive State?](https://arxiv.org/abs/2608.03052)：本体状态接口与历史。
- [What Matters in Orchestrating Robot Policies](https://arxiv.org/abs/2606.10267)：层级策略编排与成功检测。

这些候选尚未完成充分查新。不能将“增加反馈有用”或“语义动作优于数字”直接宣称为首创。需要区分增加传感信息与对相同信息换一种表达，并保留简单确定性基线。当前阶段没有训练任务、已批准的大规模模型调用或确定的投稿场所。

## 9. 接手者必须阅读的文件与代码入口

按以下顺序阅读：

1. [AGENTS.md](../AGENTS.md)：仓库工作约束。
2. [工作记录规范](worknotes/README.md) 与 [最新工作记录](worknotes/worknote.md)。
3. [框架设计](ARCHITECTURE.md)：接口与数据边界。
4. [LLM loop v2 诊断](design/LLM_LOOP_V2.md)：为什么需要固定目标控制。
5. [Show-Harness 分析](research/SHOW_HARNESS_ANALYSIS.md)：来源核对与尚未落地的方案。
6. 按需要阅读 [LIBERO](LIBERO.md)、[VLA](VLA.md)、[聊天配置](API_CHAT.md) 和 [真实本地策略实验](experiments/2026-09-15-libero-local.md)。

| 代码入口 | 职责 |
|---|---|
| `src/maniloop/cli.py` | chat / demo / smoke / benchmark 命令 |
| `src/maniloop/ui/server.py`、`ui/chat.html`、`ui/index.html` | 网页与服务入口 |
| `src/maniloop/providers/credentials.py`、`providers/chat.py`、`providers/responses.py` | 配置读取、聊天、机器人模型请求 |
| `src/maniloop/runtime/runner.py` | 生命周期、时序、预算、旧响应丢弃与日志 |
| `src/maniloop/core/observations.py`、`representations/sensors.py` | 策略可读取的传感器边界 |
| `src/maniloop/controllers/target.py` | 固定 TCP 目标与执行反馈 |
| `src/maniloop/backends/libero/` | 官方仿真、独立 worker、控制与评分 |
| `src/maniloop/agents/lerobot/` | 真实本地策略与固定检查点 |
| `src/maniloop/evaluation/benchmark.py`、`recording/manifest.py` | 批量实验与配置溯源 |

模型、planner、恢复模块和视觉辅助都不得读取仿真物体真值或独立评分。不得悄悄改变官方控制器、动作缩放、初始状态分布或成功判定。运行模式和辅助条件改变后，结果必须分组。每个重要里程碑更新 worknote，区分“接口通过”“模型运行”“任务成功”。

## 10. 新电脑继续提交与同步

克隆公开仓库通常无需登录；以后 push 需要在新电脑配置自己的 GitHub 写权限，例如系统凭据管理器或 SSH。作者名／邮箱只标识提交作者，不等于 GitHub 登录凭据。不要把 token 放进 remote URL。

按项目作者信息设置当前仓库：

```bash
git config --local user.name "Daniel-rmc"
git config --local user.email "2459944653@qq.com"
```

以上命令需要在新电脑的仓库中实际执行；仅修改本文不会更新 Git 配置，仓库级配置也不会随 clone／pull 传到另一台电脑。可用 `git config --local --get user.email` 核对。修改配置只影响后续提交，已有提交保留当时的作者邮箱。

GitHub 根据提交邮箱与账号的关联识别贡献者，作者名称相同并不足够。发现旧提交未关联时，可在自己的 GitHub 邮箱设置中添加对应旧邮箱，保留提交历史；若决定重写已发布提交，需要先明确对其他克隆的影响，不能用一次普通配置修改代替。参见 [GitHub 提交邮箱说明](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address)。

已有 checkout 且工作区干净时更新：

```bash
git status --short --branch
git switch main
git pull --ff-only origin main
git log -5 --oneline
```

有未提交工作或分支分叉时，先检查并保留自己的改动，不使用 `reset --hard` 或强制推送来处理。开始新功能可建立独立分支：

```bash
git switch -c work/next-step
```

修改后先检查 `git diff`，只暂存本次代码、测试和文档；提交前检查 `git diff --staged` 与 `git diff --cached --check`，确认没有 Key、环境目录、权重、实验输出。创建提交后，用 `git push -u origin HEAD` 上传当前分支，再按 [贡献流程](../CONTRIBUTING.md) 提交 PR。

GitHub 的 push / PR 会触发 [Actions](https://github.com/Daniel-rmc/ManiLoop/actions)，运行三平台离线测试和 Linux OSMesa 渲染。它不自动运行付费 API，也不证明云端任务成功。确认同步可执行：

```bash
git fetch origin
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
```

在 `main` 上核对时，两个提交值应一致、工作区应干净；在功能分支上则比较其对应远端分支。后续推送后要查看实际 Actions 结果，不沿用旧提交的通过状态。

## 11. 可以发给新电脑助手的交接说明

下面这段可直接复制，路径以新电脑实际仓库为准：

```text
请接手 ManiLoop 仓库。先阅读 docs/HANDOFF.md、AGENTS.md、
docs/worknotes/README.md 和 docs/worknotes/worknote.md，并检查 Git 当前状态。

先按交接文档确认新电脑环境与离线检查，不沿用旧电脑的绝对路径或虚拟环境。
API Key 和 TOML 由我在新电脑重新提供，或通过官方 Codex CLI 重新登录。
GPT-6 真实诊断与小位移已经通过，首次完整抓放未成功；
Show-Harness 九动作适配仍是设计。不要把聊天通过、mock 运行或控制器测试
写成模型抓取成功。

我希望约两周完成一个有价值的 VLM 机器人控制研究与论文初稿。
研究问题、预算、时间投入及结论目标尚未最终确认；先继续讨论并收敛实验，
不要直接启动大规模付费调用或训练。严格保留传感器输入和独立评分边界。
每个重要里程碑更新 worknote，记录真实验证结果与剩余问题。
```
