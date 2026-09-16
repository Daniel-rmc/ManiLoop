# ManiLoop

A MuJoCo-based platform for studying and benchmarking LLM-driven robot manipulation.

ManiLoop 是用于评测机器人操作策略的 MuJoCo 仿真平台。评测对象是「模型 + 观测表示 + 动作接口 + 控制器」的完整配置，实验按这些条件分组，研究不同具身体、任务与交互方式下的闭环表现。

v0.2 提供 ARX X5 / Franka Panda、两个桌面布局、抓放 / 推物任务、云端 LLM API 闭环、命令行批量实验与网页调试。同时提供模拟动作块检查，以及独立 LeRobot 推理接口，支持 LIBERO 数据训练的 SmolVLA、ACT、Diffusion 检查点。默认采用受控时序：模型推理时暂停物理，动作执行后重新观察；实时模式单独记录和比较。

可选接入 **LIBERO 官方任务**：复用官方 Panda、场景、初始化和评分，使用独立运行环境。支持网页选择任务和批量实验，详见 [LIBERO 安装与使用](docs/LIBERO.md)。

GPT-6 闭环操作演示现支持 Codex 登录、单步／连续执行、前后视觉反馈和离线回看，见 [演示使用说明](docs/GPT6_DEMO.md)。

可选安装本地学习策略：[SmolVLA / ACT / Diffusion 安装与实验](docs/VLA.md)。其中 SmolVLA 来自 LeRobot 官方；ACT / Diffusion 为社区视觉模仿基线。

**先看场景、再接模型。** 不需要 API Key 就能启动仿真、手动移动和开合夹爪。接入模型时支持 Codex ChatGPT 登录、API Key、导入 `config.toml` 配合单独的 Key，以及可选的 CC Switch 配置读取。

![初始化场景](docs/images/scene.jpg)

换电脑继续开发请阅读 [迁移与工作交接](docs/HANDOFF.md)，包含仓库同步、环境重建、私人数据迁移和当前待办。

## 1. 环境要求

| 项目 | 要求 |
| --- | --- |
| Python | **推荐 Python 3.12**；当前依赖要求至少 3.12 |
| 操作系统 | macOS、Linux、Windows 均通过 Python 3.12 离线测试；渲染已验证 macOS 桌面与 Linux OSMesa，Windows 渲染尚未验证 |
| 图形环境 | 能创建 OpenGL 渲染上下文；普通桌面环境即可，Linux 无显示器配置见下文 |
| 模型服务 | GPT 控制需要网络和有效 Codex ChatGPT 登录，或支持 **Responses API、图像输入、JSON Schema 结构化输出** 的 API 服务与 Key |
| 本地模型/GPU | 云端 API 模式无需本地权重；可选本地学习策略支持 CPU / Apple MPS / CUDA，见 [VLA 说明](docs/VLA.md) |
| 其他工具 | 基础功能不需要 Node.js、ROS、Docker、CC Switch 或实体机械臂；LIBERO 额外需要 Git / uv，见专门说明 |

运行依赖固定在 [requirements.txt](requirements.txt)：MuJoCo 3.12.0、NumPy 2.5.3、Pillow 12.3.0、OpenAI Python SDK 3.8.0。测试依赖为 pytest 9.1.1，见 [requirements-dev.txt](requirements-dev.txt)。固定的是直接依赖版本，传递依赖由 pip 解析。

安装 [Python 3.12](https://www.python.org/downloads/) 后，通过仓库页面下载 ZIP 并解压，或执行 `git clone https://github.com/Daniel-rmc/ManiLoop.git maniloop`。以下命令都从 `maniloop` 仓库根目录执行。MuJoCo 的 Python 包已经包含引擎，无须单独安装 `mujoco-py` 或下载引擎二进制文件。参见 [MuJoCo 安装说明](https://mujoco.readthedocs.io/en/stable/python.html#installation)。

## 2. 从零启动

### macOS / Linux

```bash
cd maniloop
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m maniloop demo
```

如果系统中的 `python3` 已经是 3.12，也可用它创建虚拟环境。第一次安装需要联网下载依赖。以后直接在仓库根目录运行 `./run_demo.sh`，脚本会优先使用本仓库的 `.venv`，不依赖任何个人电脑路径。

### Windows PowerShell

```powershell
cd maniloop
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m maniloop demo
```

这里直接调用虚拟环境中的 Python，不需要修改 PowerShell 的脚本执行策略。

### 打开页面

终端出现 `ManiLoop demo: http://127.0.0.1:8765` 后，在浏览器打开 **http://127.0.0.1:8765**。

你应该看到桌面、红色方块、绿色目标区域和两个相机画面。在「实验环境」中选择机器人、布局、任务与时序，点击「应用并重置场景」。此时无需配置密钥：

1. 在「手动调试」中用 `− Z`、`+ Z` 小幅移动末端。
2. 测试打开/闭合夹爪。
3. 点击「重置场景」回到初始状态。
4. 选择「模拟 VLA · 离线接口检查」并开始，验证动作块闭环；它只做小幅关节动作，不负责完成抓放。

保持终端运行；终端按 `Ctrl+C` 关闭服务。页面的「停止」只停止任务，仿真服务仍保持运行。服务只监听本机 `127.0.0.1`，没有远程用户认证。

## 3. 接入 LLM API

首次接入可先运行 `python -m maniloop chat --port 8769`，打开 `http://127.0.0.1:8769/chat`。在独立聊天页填写 API 地址／Key、导入 TOML 或选择 CC Switch 配置，选择模型后直接聊天；支持 Responses 与 Chat Completions，显示回复、耗时、用量与失败原因。无需启动仿真，详见 [聊天测试说明](docs/API_CHAT.md)。

填写连接配置后，建议先依次运行「文本诊断」「图像诊断」「动作格式诊断」。每次诊断调用一次所选服务商，可能计费，但不会执行机器人动作；结果显示耗时、实际请求参数和返回内容。若文本诊断就超时，应先检查连接；若仅动作格式诊断失败，则检查结构化输出支持。

网页默认请求超时为 **120 秒**，可调整；总墙钟预算另行设置，不会因提高调用上限自动延长。LIBERO 的 LLM 默认采用 **512×512 双相机 + 目标跟踪**：一次增量确定一个固定目标，本地最多执行 20 个原生控制步（1 秒），反馈到位或超时及实际误差。可选择 128 像素与原生单步作为基线，实验分别记录。VLA 继续使用训练匹配的相机与动作配置。

「开始新实验时重置场景」默认勾选；更换相机配置或从已结束的环境启动也会重置。首次动作可只要求沿 Z 轴上移 1 cm、保持姿态，然后查看实际反馈。接口诊断通过不等于模型已经具备任务成功能力。

### 方式 A：直接填写 API Key（首次使用最简单）

1. 在「密钥来源」选择 **手动输入密钥**。
2. 填写 API Key；OpenAI 官方服务地址为 `https://api.openai.com/v1`。使用其他供应商时，填写与该 Key 对应的完整 API 基础地址。
3. 在「LLM 模型」选择或输入你有权限使用的模型 ID。可点击「刷新模型列表」；若供应商没有该接口，直接选择「自定义模型」填写即可。
4. 先把调用上限设为 **3**，输入：

   > 保持夹爪开度和末端姿态，将末端沿基座 Z 轴向下移动 1 厘米。只移动一次，检查动作成功后结束。

5. 点击「开始执行」，观察事件日志中的 API 请求、动作和执行反馈。

确认接入正常后，可重置场景，把调用上限调整为 40，尝试：

> 把红色方块抓起来，放到绿色目标区域，再松开夹爪。

本项目不承诺模型自主抓放的成功率。API 会产生供应商费用；深度查询与重新观察后的决策同样占用调用次数。停止不能撤回已经发出的请求。

### 方式 B：导入 config.toml + 单独填写 Key

1. 选择 **导入 config.toml + API Key**。
2. 点击选择文件，或粘贴 TOML 内容。可从 [官方服务示例](examples/openai.example.toml) 或 [自定义供应商示例](examples/custom.example.toml) 开始。
3. 在下方 **API Key** 密码框填写对应密钥。
4. 点击「读取配置」，检查 API 地址、模型和密钥状态，再开始任务。

TOML 示例（将模型与地址替换为供应商实际提供的值）：

```toml
model = "YOUR_VISION_MODEL_ID"
model_provider = "custom"

[model_providers.custom]
base_url = "https://api.example.com/v1"
wire_api = "responses"
```

单独填写的 Key 优先于文件中的 Key；只导入 TOML 也能预览地址和模型。上传模式只在内存中解析，不读取电脑上其他 `auth.json`，也不把导入文件写入仓库。刷新页面后需要重新选择文件和填写 Key。

供应商地址若带有专用路径，应完整保留；填写基础地址，不要自行追加 `/responses`。HTTP 只允许本机代理地址，例如 `http://127.0.0.1:15721/v1`。

### 方式 C：读取已有本地配置 / CC Switch（可选）

选择 **本地配置文件（CC Switch）**，从默认位置选择或填写绝对路径，然后点击「读取配置」。支持：

- `~/.cc-switch/cc-switch.db`：只读 **Codex 页当前选中的供应商**，不会更改 CC Switch。
- `~/.codex/config.toml` 与同目录 `auth.json`；也支持 `CODEX_HOME`、CC Switch 的 `codexConfigDir`。
- 自定义 TOML、`auth.json` 或 API JSON 文件；也可以在页面单独补填 Key。

路径模式每次决策前会重新读取所选文件。切换发生在 API 等待期间时，会丢弃旧供应商的响应，再重新观察。若单独填写了 Key 后文件中的 API 地址发生改变，任务会停止，要求为新地址重新配置 Key。

只有 ChatGPT/Codex OAuth 登录信息的配置不能直接作为 API Key；使用账户登录时请选择独立的「Codex」通道，见 [GPT-6 演示说明](docs/GPT6_DEMO.md)。API 配置通道仍需供应商的 API Key。CC Switch 不是启动本 Demo 的必要条件。

### 模型和密钥的保存方式

- 「跟随本地配置」使用文件指定的模型；显式选择的模型会保持不变。
- 默认模型 ID 是 `gpt-6-astra`；这是可覆盖的初始值，实际支持情况由你的 API 服务决定。
- 列出某个模型不代表它支持本 Demo 所需的图像、Responses 和结构化输出三项能力。
- Key 仅用于对应供应商认证，不进入模型提示词、实验日志或浏览器持久存储。
- 手动模式提交后清空密码框，Key 留在服务内存中；文件/导入模式的密码框会保留到页面刷新或关闭。
- 不必将 Key 写入示例文件，也不必提交个人配置到 Git。

## 4. 批量评测与可选参数

先运行八种机器人 / 布局 / 任务组合的离线接口检查，不需要 Key 或图形环境：

```bash
python -m maniloop list
python -m maniloop benchmark --suite examples/offline-suite.toml --no-render
```

离线示例会正常结束，但任务成功率为零是预期结果：模拟适配器不具备任务策略。每个 episode 都重新创建策略、重置历史与随机种子。

运行一次真实云端 LLM 评测（会调用你配置的服务）：

```bash
python -m maniloop benchmark --agent llm_cloud --robot panda --scene tabletop_a --task pick_place --provider-config /path/to/provider.toml --model YOUR_MODEL_ID --max-calls 3
```

Key 可来自该配置文件及其配套认证文件，也可通过 `OPENAI_API_KEY` 单独提供。批量评测期间若文件中的供应商、模型或 Key 改变，当前 episode 会终止，避免一条结果混用多个配置。网页调试仍支持 CC Switch 热切换。

矩阵 TOML 与供应商配置是两种文件：前者描述实验条件，后者描述 API 连接。复制 [离线矩阵](examples/offline-suite.toml)，将 `agent` 改为 `llm_cloud`，去掉 `--no-render`，再使用 `--provider-config` 即可批量调用。矩阵文件中指定的条件优先，`--model` 与 `--provider-config` 负责连接。

`--output` 指定输出目录，默认 `runs/`；每次实验包含 `manifest.json`、`events.jsonl`、传感观测和图像，批量实验额外包含 `result.json` 与汇总 JSONL。记录保存模型配置、代码摘要、机器人来源版本、种子、时序、终止原因、独立评分及服务返回的 token 用量。Key 不写入记录。不同 `comparison_group` 的结果不要直接合并；同组内仍需按机器人、任务和布局分别报告。

更多启动示例：

```bash
python -m maniloop demo --port 8766
python -m maniloop demo --model YOUR_MODEL_ID
python -m maniloop demo --robot panda --scene tabletop_b --task push
python -m maniloop demo --timing realtime
python -m maniloop smoke
```

更换端口后相应打开 `http://127.0.0.1:8766`。`smoke` 仅渲染双相机并推进物理，不启动网页、不请求模型；结果写入 `artifacts/<后端>/<机器人>/<布局>/<任务>/`。旧的 `python -m arx5_demo.app` 入口保留兼容。

| 环境变量 | 用途 / 默认值 |
| --- | --- |
| `OPENAI_API_KEY` | 手动配置模式可从启动环境读取 Key |
| `OPENAI_BASE_URL` | 手动模式的 API 基础地址；默认官方地址 |
| `OPENAI_MODEL` | 初始模型；页面和 `--model` 可覆盖 |
| `OPENAI_TIMEOUT_SECONDS` | 单次模型请求超时，默认 45 秒 |
| `OPENAI_MAX_OUTPUT_TOKENS` | 输出 token 上限，默认 4096 |
| `OPENAI_REASONING_EFFORT` | 可选推理强度；须是所选模型支持的值 |
| `ARX_CONFIG_PATH` | 优先显示的本地配置路径 |
| `ARX_OBSERVATION_MAX_AGE` | 实时模式允许引用的观测最大年龄，默认 60 秒；受控模式使用冻结快照及总时间预算 |
| `MUJOCO_GL` | 渲染后端；通常无需设置，Linux 无显示器时见下文 |

项目不会自动读取 `.env`；首次使用推荐通过网页配置 Key。

## 5. 常见问题

| 现象 | 处理方式 |
| --- | --- |
| 找不到 `python3.12` 或 `py` | 安装 Python 3.12，重新打开终端；确认 `python --version` 或 `py -3.12 --version` |
| `No matching distribution` / Python 版本不支持 | 使用 64 位 Python 3.12；本版 NumPy 要求 Python ≥3.12 |
| `No module named mujoco/openai` | 使用安装依赖时的同一个 `.venv`；重新执行对应平台的安装命令 |
| 页面无法连接 | 保持服务终端运行；检查启动输出和端口；端口被占用时用 `--port 8766` |
| 提示默认配置不存在 | 新用户直接选择「手动输入密钥」或「导入 config.toml + API Key」，不需要安装 Codex/CC Switch |
| macOS 提示 `invalid CoreGraphics connection` | 从登录桌面会话的普通终端运行；受限沙箱或无图形的远程会话可能无法创建渲染上下文 |
| Linux 报 GLFW / OpenGL / DISPLAY 错误 | 使用正常桌面会话，或按下方方式配置无显示器渲染 |
| 401 / 认证失败 | 核对 API 地址与 Key 是否属于同一供应商，必要时单独补填 Key |
| 429 / 限流或额度不足 | 更换可用 Key 后重新开始；系统不自动反复重试 |
| 模型列表失败 | 该供应商可能没有模型列表接口；直接输入模型 ID 后测试 |
| 输出达到 token 上限 | 简化任务，或设置更高的 `OPENAI_MAX_OUTPUT_TOKENS` 后重启服务 |
| 模型给出动作却未执行 | 查看事件日志；过期观测、超限、碰撞预测或 IK 失败都会被本地控制器拒绝 |

### Linux 无显示器运行（可选）

在 Ubuntu/Debian 上，可以安装 Mesa 软件渲染库，并在启动 Python **之前**设置 OSMesa：

```bash
sudo apt-get update
sudo apt-get install -y libosmesa6
source .venv/bin/activate
MUJOCO_GL=osmesa python -m maniloop smoke
MUJOCO_GL=osmesa python -m maniloop demo
```

如果已配置兼容的 GPU/EGL 驱动，可选择 `MUJOCO_GL=egl`。这两项是 Linux 配置，不要直接套用到 macOS。具体渲染后端要求见 [MuJoCo 编程说明](https://mujoco.readthedocs.io/en/stable/programming/index.html)。

## 6. 系统边界与已知限制

以下控制流程与数值限制描述自建桌面任务；LIBERO 的 OSC、RGB 观测和官方评分协议见 [后端说明](docs/LIBERO.md)。

```text
自然语言任务 + 双相机图像 + 机器人传感状态
                      ↓
              GPT / Responses API
                      ↓ 一个动作
           格式、观测、限位与碰撞检查
                      ↓
             IK + 轨迹 + MuJoCo 物理
                      ↓ 执行反馈和新观测
                  下一次决策
```

- 机器人采用标准 **ARX X5 六轴机械臂**模型及近似建模的平行夹爪。夹爪参数尚未依据真机标定；详见 [模型来源与修改](src/maniloop/assets/robots/arx5/SOURCES.md)。
- Franka Panda 使用 MuJoCo Menagerie 标准模型，保留双指联动约束，增加 TCP 与腕部相机。该约束只同步手指，不附着物体。
- 模型能读取两路 640×480 图像、相机标定、关节/TCP 状态、夹爪开度、动作限制和执行反馈。外部相机可按像素查询深度，腕部相机只有 RGB。
- **物体真值位置、仿真接触列表和独立评估结果不会传给 GPT。** 在线策略没有隐藏的自动抓取脚本、物体吸附或物体焊接。独立评分可读取物体真值，但与传感输入通道隔离。
- LLM 每次选择一个小动作：平移范数 ≤4 cm、旋转范数 ≤0.2 rad。VLA 适配器输出具有关节名称、单位、观测 ID 和采样间隔的动作块；本地控制器检查每个采样，停止或重置会取消剩余采样。
- 受控模式按固定物理步长执行；实时模式按墙钟推进并限制追赶量，不保证硬实时。两种时序不混合排名。
- 碰撞预检和图像变化判断是仿真中的近似检查，不能作为真机安全系统。
- 抓放任务要求先抬起方块，再完整放入绿色区域、释放并稳定 1 秒；推物任务要求沿桌面推动，过程中不能抬起，再离开并稳定 1 秒。自由输入的其他文字目标不改变评分规则；模型声明 `done` 不等于成功。
- 固定策略评测不更新权重或跨 episode 记忆。在线学习、其他厂商专有 API、双臂与灵巧手是后续扩展。真实学习策略目前限于已核对的 LIBERO 检查点，见 VLA 说明。
- 当前提供仿真 Demo，未连接真机；尚未建立真实 API 自主抓放的成功率基准。FC 兼容响应中空错误字段的误判已修正，并有离线回归覆盖。

## 7. 测试与实验记录

安装开发依赖后运行：

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m maniloop smoke
```

Windows 用户将 `python` 换成 `.\.venv\Scripts\python.exe`。pytest 使用真实物理引擎和模拟 API，不要求图形界面或真实 Key；`smoke` 需要图形后端。两者都不会调用付费 API。

覆盖项包括接触抓放、动作拒绝、传感数据隔离、观测更新、停止后丢弃响应、TOML/Key 配置、供应商切换和 SDK 请求解析。接触抓放测试使用确定性测试动作，验证的是控制与物理层，不代表 GPT 自主任务成功率。

## 8. 仓库结构

```text
src/maniloop/
  core/             # 观测与动作约定
  agents/           # 云端 LLM、模拟 VLA、独立 LeRobot 推理
  providers/        # API 协议、凭据配置、模型目录
  representations/  # 传感观测输入边界
  robots/           # 具身体、关节、夹爪及控制映射
  backends/         # 环境协议、工厂与可选 LIBERO 子进程适配
  simulation/       # 自建 MuJoCo 环境与场景组装
  controllers/      # IK、限位、碰撞检查、位置控制
  tasks/            # 布局、任务生命周期与独立评分
  runtime/          # CLI / 网页共用闭环、时钟、动作块执行
  evaluation/       # 固定策略批量评测与矩阵配置
  recording/        # 实验来源与配置记录
  ui/               # 本机网页服务与操作界面
  assets/           # 独立的 robots / scenes / objects 资源
arx5_demo/           # 旧入口兼容层
examples/            # 无密钥的供应商与实验 TOML 示例
tests/               # 离线回归、跨机器人接触物理与闭环测试
docs/                # 框架设计、扩展步骤与验证说明
  worknotes/         # worknote.md 里程碑记录及 README 记录规范
scripts/             # 可选后端安装工具
requirements/        # 隔离后端的依赖清单
pyproject.toml       # 可安装的 Python 包与 maniloop 命令
```

每个重要里程碑维护 [项目工作记录](docs/worknotes/worknote.md)，内容和更新规则见 [记录规范](docs/worknotes/README.md)。

接口职责、数据边界、时序和扩展方法见 [框架设计](docs/ARCHITECTURE.md)。新功能先通过最小可运行实验验证，再提炼共用抽象。

[Show-Harness 工程分析](docs/research/SHOW_HARNESS_ANALYSIS.md) 对照论文与固定版本源码，说明 VLM 语义动作闭环、厂商 agent 的使用边界、标定与评测协议，并给出 ManiLoop 的分阶段实施建议。相关资料见 [研究文档索引](docs/research/README.md)。

## 许可证与贡献

项目采用 [MIT](LICENSE)。ARX X5 资产保留上游 MIT 声明，Panda 资产保留 Apache-2.0 许可证，见 [第三方声明](THIRD_PARTY_NOTICES.md)。贡献流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。

API 协议参考：[图像输入](https://developers.openai.com/api/docs/guides/images-vision)、[结构化输出](https://developers.openai.com/api/docs/guides/structured-outputs)。
