# ManiLoop

[English](README.md) · **[简体中文](README.zh-CN.md)**

**面向跨策略、跨基准的机器人闭环评测。** ManiLoop 以公平、可复现的比较为目标，将内置 MuJoCo 场景、LIBERO、robosuite 和 RoboCasa 接入同一个本地浏览器工作台与命令行。从手动控制开始，再选择 GPT、兼容的视觉模型 API、受支持的本地 LeRobot 检查点，或 Jev 文本原语。

**[开始使用 ↓](#第一步--打开本地工作台)** · [连接模型](#第三步--连接模型) · [实测结果](docs/RESULTS.md#简体中文) · [项目网站](https://daniel-rmc.github.io/ManiLoop/?lang=zh)

![当前 ManiLoop 手动工作区中的内置 Panda 抓放场景](docs/images/current-workspace-manual.png)

*当前本地程序的中文界面，预览内置 Panda 抓放场景。这里的控件用于操作仿真；项目网站另提供已录制 episode 的回放。*

[观看 GPT 放碗、转动炉具旋钮、将奶油奶酪放入篮子](https://daniel-rmc.github.io/ManiLoop/?lang=zh#skills)：播放经过核验的回合，逐步暂停，对照模型当时的动作说明与控制器反馈，并查看完整录像和执行条件。

这三段 GPT 成功回合的实测墙钟时间为 **5.5–11.1 分钟**，包含模型规划、通信、执行与录制，从场景和策略加载完成后计时。这是选定示例，不是平均完成时间或速度排名。[查看计时口径与结果](docs/RESULTS.md#实际墙钟时间)。

## 可以运行哪些任务

工作台将**相机观测、动作、控制器反馈与独立评分**放在一起。你可以手动调试、逐步执行模型决策、暂停和继续、对照执行前后观测，并通过命令行批量运行实验。完整逐控制步录像目前支持受控时序下的 LIBERO；其他后端提供决策日志与回看画面。

| 后端 | 机器人与可用任务 | 接入范围 |
| --- | --- | --- |
| 内置 MuJoCo | ARX X5／Franka Panda；`pick_place` 抓放、`push` 推物；`tabletop_a`／`tabletop_b` 布局 | 基于接触物理的桌面操作、手动与模型控制、独立任务评分 |
| [LIBERO](docs/LIBERO.md) | 官方 Panda；五个任务套件 | 官方初始状态、OSC 控制器与成功规则；下文展示选定的真实模型回合 |
| [robosuite](docs/ROBOSUITE.md) | Panda；`Lift`、`Stack`、`PickPlaceCan`、`Door`、`NutAssemblySquare` | 五项任务已接入相机、步进、重置与评分检查；采用世界系 OSC 适配 |
| [RoboCasa](docs/ROBOCASA.md) | PandaOmron；`OpenDrawer`、`CloseDrawer`、`OpenCabinet`、`CoffeeSetupMug` | 四项厨房任务；控制机械臂与夹爪，底座速度和躯干增量为零；不含导航 |

LIBERO 目录包括 **spatial 10 项、object 10 项、goal 10 项、`libero_90` 90 项、`libero_10` 10 项**，覆盖物体放置、抽屉、炉具、堆叠和较长操作。这里是目录规模，不是模型已经完成的任务数量。RoboCasa 四任务的接口检查范围为 macOS／Apple Silicon、布局 11／风格 14／seed 0；其他场景组合及机械臂可达性需另行检查。修改文字指令不会改变上游评分器。

视觉策略接收图像与机器人传感状态；**Jev 只接收显式文字与本体状态**。物体真值、仿真接触、奖励和任务成功信号均不进入策略输入。独立评估可以读取仿真状态并终止 episode；模型声明 `done`、控制器返回 `reached`、指令序列结束，与任务成功分别记录。

本地工作台分为三个面板：

| 面板 | 可以做什么 |
| --- | --- |
| 手动控制 | 沿固定轴或 TCP 自身轴平移、旋转，开合夹爪，提交六维组合增量，查看位置与姿态误差。 |
| 模型运行 | 输入指令、选择连接、运行诊断，使用单步、连续执行、暂停与继续。 |
| 场景设置 | 选择后端、任务、机器人和场景参数，点击应用后重建环境。 |

“停止执行”跨面板保持可见。切换面板或画中画／双相机并排布局，不会启动推理或推进物理。当前任务、动作和请求结束后，才能提交手动控制。手动目标跟踪预算独立于模型预算；TCP 旋转不是单关节点动。详见[工作台使用说明](docs/WORKSPACE.md)和[六维手动控制](docs/MANUAL_CONTROL.md)。

## 第一步 · 打开本地工作台

准备 **Python 3.12**、Git 和可用的 OpenGL 环境。使用云端 GPT 不需要本地模型权重或 GPU；基础程序不依赖 ROS、Docker 或实体机械臂。

**macOS / Linux**

```bash
git clone https://github.com/Daniel-rmc/ManiLoop.git
cd ManiLoop
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m maniloop demo
```

**Windows PowerShell**

```powershell
git clone https://github.com/Daniel-rmc/ManiLoop.git
cd ManiLoop
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m maniloop demo
```

打开 [http://127.0.0.1:8765](http://127.0.0.1:8765)。工作台默认显示“手动控制”；可到“场景设置”选择机器人、布局和任务，应用后返回手动面板试用机械臂与夹爪。**这一步不需要 API Key。** 服务只监听本机地址；使用时保持终端运行，按 `Ctrl+C` 关闭。如需换端口，启动时加 `--port 8766`。

继续以下步骤前，先停止服务，并保持在仓库根目录操作。**Windows 用户**将后续 `python` 命令替换为 `.\.venv\Scripts\python.exe`；多行 Bash 示例合并为一行，并去掉行尾的 `\`。安装 `uv` 后，运行任一安装脚本时加 `--uv .\.venv\Scripts\uv.exe`。无需执行激活脚本或修改执行策略。

无显示器的 Ubuntu/Debian 可安装 `libosmesa6`，在启动 Python 前设置 `MUJOCO_GL=osmesa`；已有兼容 GPU 驱动时也可使用 EGL。这些 Linux 设置不适用于 macOS。

<a id="在-libero-中运行-gpt"></a>

## 第二步 · 选择仿真后端

完成第一步即可使用内置场景。选择下方需要的可选后端，从仓库根目录运行对应命令；改用另一条启动示例前先停止现有 demo。各后端通过独立 Python worker 运行；启动工作台仍使用主环境的 `python`。

```bash
python -m pip install uv
```

### LIBERO

```bash
python scripts/setup_libero.py
python -m maniloop list --backend libero --libero-suite libero_goal
python -m maniloop smoke --backend libero
python -m maniloop demo --backend libero --port 8767
```

打开 [http://127.0.0.1:8767](http://127.0.0.1:8767)。在“场景设置”选择任务套件、任务 ID 与初始化 ID。ID 从零开始，`list` 会列出任务名称。默认是 `libero_spatial` 任务 0、初始化 0：将盘子与小碗之间的黑碗放到盘子上。安装需要网络与数 GB 磁盘空间，无需示范数据集或策略权重。详见 [LIBERO 安装说明](docs/LIBERO.md)。

### robosuite

```bash
python scripts/setup_robosuite.py
python -m maniloop list --backend robosuite
python -m maniloop demo --backend robosuite --task Lift --port 8870
```

打开 [http://127.0.0.1:8870](http://127.0.0.1:8870)。五项 Panda 任务在独立环境使用 robosuite 1.5.2／MuJoCo 3.3.7。适配器明确采用世界系 OSC，并记录这一配置。相机、手动控制和模型接口已接入；这些任务尚无模型成功率结论。详见[控制语义与检查范围](docs/ROBOSUITE.md)。

### RoboCasa

```bash
python scripts/setup_robocasa.py --download-assets
python -m maniloop list --backend robocasa
python -m maniloop demo --backend robocasa --task OpenDrawer \
  --robocasa-layout 11 --robocasa-style 14 --port 8872
```

打开 [http://127.0.0.1:8872](http://127.0.0.1:8872)。安装器固定 RoboCasa 及其配套 robosuite 源码，与独立 robosuite 后端分开。五组必需资产解压约 11.1 GB，另需源码和运行环境空间。控制 PandaOmron 机械臂和夹爪时，底座接收零速度、躯干接收零增量；本接口不提供导航。默认场景接口检查不代表自主任务成功，也不保证所有场景都能仅靠机械臂完成。详见 [RoboCasa 安装与限制](docs/ROBOCASA.md)。

### 保持运行环境独立

| 环境 | 职责 |
| --- | --- |
| `.venv` · Python 3.12 | 主程序、网页、模型连接与内置 MuJoCo 场景 |
| `.venv-libero` · Python 3.10 | LIBERO 仿真及固定依赖 |
| `.venv-robosuite` · Python 3.11 | 独立 robosuite 仿真 |
| `.venv-robocasa` · Python 3.11 | RoboCasa 仿真及兼容的上游依赖 |
| `.venv-vla` · Python 3.12 | 可选的 LeRobot 与学习策略推理 |

不要将这些依赖合并安装到主环境。RoboCasa worker 是仿真专用安装，不是上游完整训练环境。可选资产、运行环境与模型权重在本地下载，不随仓库分发。

## 第三步 · 连接模型

选择以下一种方式；更换启动命令前，先停止已有的本地服务。

| 模型接入方式 | 如何连接 | 兼容边界 |
| --- | --- | --- |
| ChatGPT 套餐直连 | 选择直连来源，在浏览器中为 ManiLoop 独立授权 | 使用账号可用的 Responses 模型，不经过 Codex CLI；当前预览无服务端 token 硬上限 |
| 通过 Codex 使用 GPT | 在官方 Codex CLI 登录，选择 Codex 来源 | 使用该 CLI／账户可用的模型；ManiLoop 不提取登录 token |
| 云端或自托管视觉模型 | 填写服务基础地址、模型 ID、API Key，或导入供应商 TOML | 机器人控制需要 **Responses API、图像输入和 JSON Schema 输出** |
| 本地 LeRobot 检查点 | 选择由独立推理进程加载的支持模型 | 当前提供三个已核对的 LIBERO 检查点预设，不是任意模型文件夹导入 |
| Jev 文本原语 | 在模型面板填写独立的 TypeSafe 密钥 | 显式文字与机器人本体状态；有限的机械臂／夹爪指令，无图像与物体定位 |

<details><summary>查看实际本地程序中的模型配置</summary>

![当前 ManiLoop 本地程序中的模型运行面板](docs/images/current-workspace-model.png)

*当前中文“模型运行”面板，载入的是内置 Panda 场景，尚未发起模型请求。这里的连接和指令用于真实执行，与网站使用已保存数据的体验工作台分开。*
</details>

### GPT 与兼容模型 API

使用 ChatGPT 套餐直连时，先运行 `python -m pip install -e '.[chatgpt]'`，正常启动本地 demo，在模型面板选择 **ChatGPT 套餐直连 · 独立授权**。点击 **Continue with ChatGPT** 授权 ManiLoop，刷新账号模型列表，再运行文字、图像和动作格式诊断。该方式使用 ManiLoop 自己的提示和闭环，不启动 Codex CLI；账号资格与模型访问以诊断结果为准。详见[双语接入与比较指南](docs/CHATGPT_PLAN.md)。

现有 Codex CLI 入口继续保留，作为单独标记的 harness 配置：

安装近期官方 [Codex CLI](https://github.com/openai/codex)，然后运行：

```bash
codex login
python -m maniloop demo --backend libero --codex-login --port 8767
```

选择 Codex 来源并加载 GPT 演示预设。该预设会选择 LIBERO；在其他后端使用模型时，保留所选场景并直接配置连接。从文字、图像、动作格式诊断或单个动作开始。安装了多个 CLI 版本时，可用 `MANILOOP_CODEX_BIN` 选择所需程序。详见 [GPT 操作说明](docs/GPT6_DEMO.md)。

通过 API 连接时，选择手动填写或导入配置来源，填写模型 ID、供应商基础地址与密钥。可参考 [OpenAI 配置](examples/openai.example.toml)和[自定义供应商配置](examples/custom.example.toml)。自己部署的本地模型也可走这条路径，**前提是服务端实现所需的 Responses 协议**，例如使用本地地址 `http://127.0.0.1:8000/v1`。仅支持 Chat Completions 的服务不能用于机器人控制；独立的[文字聊天页](docs/API_CHAT.md)支持这两种协议。填写模型 ID 不代表模型一定支持视觉与结构化动作。模型请求使用所选账户额度或供应商计费；打开网页不会自动推理。

### 本地 SmolVLA、ACT 与 Diffusion Policy

```bash
python scripts/setup_vla.py --models smolvla-libero act-libero diffusion-libero
python -m maniloop demo --backend libero --port 8767
```

在页面选择本地 LeRobot 来源与已下载模型。省略 `--models` 则只安装 SmolVLA。即使安装了其他后端，这些预设仍**仅用于 LIBERO**。推理可离线运行于 CPU、Apple MPS 或 CUDA，保留检查点保存的预处理与动作队列。

也可直接通过命令行调用本地检查点；将 `smolvla-libero` 替换为 `act-libero` 或 `diffusion-libero` 即可选择其他已安装的预设：

```bash
python -m maniloop benchmark --backend libero --agent lerobot \
  --local-model smolvla-libero --libero-suite libero_spatial --libero-task-id 0 \
  --init-state-id 0 --seed 0 --max-calls 500 --max-sim-seconds 25 \
  --max-wall-seconds 1800 --output runs/local-demo
```

| 预设 | 检查点 | 输入 |
| --- | --- | --- |
| `smolvla-libero` | [lerobot/smolvla_libero](https://huggingface.co/lerobot/smolvla_libero) · 官方 | 图像、机器人状态与语言 |
| `act-libero` | [Deepkar/libero-test-act](https://huggingface.co/Deepkar/libero-test-act) · 社区 | 图像与机器人状态 |
| `diffusion-libero` | [ttotmoon/diffusion-libero-v3](https://huggingface.co/ttotmoon/diffusion-libero-v3) · 社区 | 图像与机器人状态 |

如果这些预设**已经存放在另一块本地磁盘**，将 `MANILOOP_MODELS_ROOT` 设为它们的父目录。目录内须包含与预设同名的文件夹，如 `smolvla-libero/`，SmolVLA 还需要 `smolvlm-tokenizer/`。`MANILOOP_VLA_PYTHON` 可指向兼容的推理环境。这些设置用于更换受支持快照的存放位置，不会导入任意 Hugging Face 仓库或自定义权重。目录要求与固定版本见[本地模型指南](docs/VLA.md)。

### Jev：显式文本指令

在“模型运行”中选择 **Jev · 文本原语控制**，输入 TypeSafe API Key。该密钥与 OpenAI 连接分开，只保存在服务内存，不写入文件或浏览器存储。保存密钥不调用模型；连接诊断和指令执行会使用 TypeSafe API。无需安装 Jev 权重或 TypeSafe SDK。

每行输入一个动作，例如：

```text
Move up along world Z by 10 mm.
Rotate about the tool Z axis by 5 degrees.
Open the gripper.
```

Jev 根据文字与机器人本体状态选择有限原语，单位、坐标系和执行由本地代码处理。它不接收相机图像，不能自主定位物体进行抓取。该模式要求受控时序；每组最多 20 行，遇到含糊指令、低候选概率、API 错误或控制失败会停止。现有仿真检查使用模拟 Jev 响应；真实服务能力需单独运行诊断或指令验证。详见 [Jev 设置与验证范围](docs/JEV.md)。

### 接入自己的检查点或策略

新的检查点需要单独注册模型，配置正确的预处理、动作映射与来源信息。不要直接替换预设文件后仍将它标作原预设。若要使用自己的推理实现，可实现 [`Agent`](src/maniloop/agents/base.py) 的 `reset()` 与 `decide(task, observation, images, history, geometry_results)`，返回动作字典或 [`ActionChunk`](src/maniloop/core/actions.py)，再接入 `EpisodeRunner`，按需增加 CLI／UI 选项；当前没有自动加载任意检查点的通用入口。

增加仿真后端时，实现 [`Environment`](src/maniloop/backends/base.py)，并在[环境工厂](src/maniloop/backends/factory.py)中注册。需要匹配相机与状态输入、动作维度、单位和时序，并保持独立评分隔离。详见[架构与扩展接口](docs/ARCHITECTURE.md)。

## 第四步 · 录制完整尝试，检查结果

普通模型运行可查看决策日志、控制反馈、前后帧和独立结果。完整逐控制步录制与视频导出目前要求 **LIBERO 和受控时序**。以下命令从官方初始化运行一次新的 GPT-6 尝试，并录制每个控制步：

```bash
python -m maniloop benchmark \
  --backend libero --libero-suite libero_spatial --libero-task-id 0 \
  --init-state-id 0 --seed 0 --agent llm_cloud --codex-login \
  --model gpt-6-astra --context-mode paired --reasoning-effort medium \
  --max-calls 0 --max-wall-seconds 3600 --record-episode \
  --output runs/gpt-demo
```

默认 `controlled` 时序在模型推理期间暂停物理。`--max-calls 0` 取消决策次数上限，官方终止、仿真时长与墙钟预算仍生效。每次尝试生成独立目录，包含 `manifest.json`、`events.jsonl`、`result.json` 和 `replay.html`。检查 **`result.json → evaluation.success`** 获取独立结果；本地打开 `replay.html`，按决策回看过程。完整画面与校验信息存于 `recording/`。

安装 `ffmpeg` 后导出视频：

```bash
python -m maniloop.recording.video runs/gpt-demo/EPISODE_ID/recording
```

将 `EPISODE_ID` 替换为实际运行目录名。导出器先核对帧序列与摘要，再生成 `episode.mp4`；需要时用 `--ffmpeg /path/to/ffmpeg` 指定编码器。失败尝试同样保存，可加 `--allow-failure` 导出。视频按仿真时间播放，省略物理冻结的模型等待。详见[录制与导出说明](docs/EPISODE_RECORDING.md)。使用[示例矩阵](examples/libero-local-suite.toml)批量运行三个本地模型：`python -m maniloop benchmark --suite examples/libero-local-suite.toml --output runs/local-suite`。

## 录制示例与实测结果

无需安装，也可[探索录制工作台](https://daniel-rmc.github.io/ManiLoop/playground/?lang=zh)或[观看成功 episode](https://daniel-rmc.github.io/ManiLoop/?lang=zh#demo)。公开回放使用已保存的数据；**新的任务执行和模型请求需要在本地程序中运行**。试试「单步查看」，对照「执行前」与「执行后」，再跳到第 46 次决策的最终画面。

这条 GPT episode 包含 46 次决策、706 个控制步，其中包括抓取重试。完整视频含 707 组双相机画面，20 fps，时长 35.35 秒。官方成功在最后一次下降时触发，环境立即停止，没有额外验证松爪与退离。

| 模型 | 官方结果 | GPT 请求／本地推理次数 | 控制步数 | 仿真时间 |
| --- | --- | ---: | ---: | ---: |
| GPT-6 Astra | 成功 | 46 | 706 | 35.30 秒 |
| SmolVLA | 成功 | 2 | 78 | 3.90 秒 |
| ACT | 预算内未成功 | 5 | 500 | 25.00 秒 |
| Diffusion Policy | 成功 | 10 | 79 | 3.95 秒 |

每行是在 `libero_spatial` 任务 0／初始化 0／seed 0 上**选取的一次运行，不是成功率或模型排名**。GPT 产生高层动作，本地推理生成供多个控制步使用的动作队列。输入、控制器、预算和运行入口不同，墙钟耗时也不能直接比较。重新运行模型可能得到不同结果。详见[完整结果与运行条件](docs/RESULTS.md#简体中文)。

## 使用指南、检查与适用范围

[工作台](docs/WORKSPACE.md) · [手动控制](docs/MANUAL_CONTROL.md) · [LIBERO](docs/LIBERO.md) · [robosuite](docs/ROBOSUITE.md) · [RoboCasa](docs/ROBOCASA.md) · [GPT 操作](docs/GPT6_DEMO.md) · [Jev](docs/JEV.md) · [本地检查点](docs/VLA.md) · [API 文字聊天](docs/API_CHAT.md) · [录制](docs/EPISODE_RECORDING.md) · [架构](docs/ARCHITECTURE.md)

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m maniloop smoke
```

这些检查不发送模型请求。离线测试覆盖 macOS、Linux 和 Windows；主程序渲染已在 macOS 与 Linux OSMesa 上验证。可选后端的真实集成检查需按各自指南显式启用；普通 pytest 不会验证尚未安装的后端。Windows 上的渲染与 LIBERO 运行尚未验证。渲染需要图形后端。ManiLoop 用于仿真：ARX 夹爪采用近似模型，软件未作为真机控制或安全系统验收。环境接入、控制器检查与真实模型任务结果分别记录。

<a id="许可证与贡献"></a>

## 许可证

ManiLoop 采用 [MIT 许可证](LICENSE)。ARX X5 资产保留 MIT，Panda 资产保留 Apache-2.0。LIBERO、robosuite、RoboCasa、LeRobot 及下载的资产和检查点分别保留自己的许可证。详见[第三方声明](THIRD_PARTY_NOTICES.md)与[贡献指南](CONTRIBUTING.md)。
