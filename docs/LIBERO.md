# LIBERO 官方任务接入

ManiLoop 将 [LIBERO](https://github.com/Lifelong-Robot-Learning/LIBERO) 作为可选环境后端。物理引擎仍然是 MuJoCo；LIBERO 和 robosuite 提供官方任务、资源、Panda 机器人、OSC 控制器与成功判定。无需另外安装 Isaac Sim，也无需下载示范数据集或模型权重。

## 安装与启动

先按照根目录 README 安装 ManiLoop 的 Python 3.12 主环境，然后在仓库根目录执行：

```bash
python -m pip install uv
python scripts/setup_libero.py
python -m maniloop list --backend libero
python -m maniloop smoke --backend libero
python -m maniloop demo --backend libero --port 8767
```

打开 `http://127.0.0.1:8767`。默认使用 `libero_spatial` 的 task 0、init 0：把盘子与小碗之间的黑碗放到盘子上。先测试手动点动或选择「模拟 VLA · 离线接口检查」，无需 Key。接云端模型时，沿用主 README 中的 TOML / Key 配置入口。

安装脚本需要 **Git、联网和 uv**。uv 自动准备 Python 3.10，不要求你手工安装第二个 Python。请为 Python、PyTorch、robosuite、LIBERO 资源与缓存预留数 GB 空间。脚本安装到：

| 位置 | 内容 |
| --- | --- |
| `.venv/` | 原有 ManiLoop 主程序环境，保持 Python 3.12 依赖 |
| `.venv-libero/` | 独立 Python 3.10 仿真依赖 |
| `.external/LIBERO/` | 完整固定版本的官方源码、任务及资源 |
| `.runtime/python/` | uv 下载的 Python 运行时 |

这些生成目录均被 Git 忽略，不属于开源代码包。脚本可重跑；发现已有上游源码被修改或版本不符会停止，不覆盖你的修改。若 uv 未在 PATH 中，可传入 `--uv /path/to/uv`。

Windows PowerShell 中可用 `.\.venv\Scripts\python.exe` 替换 `python`。LIBERO 渲染已在 macOS Apple Silicon 验证；Linux 提供可手动触发的 CI 集成检查，Windows LIBERO 尚未实机验证。无显示器的 Ubuntu/Debian 安装 `libosmesa6`，在运行前设置 `MUJOCO_GL=osmesa`；有正确 GPU 驱动时可使用 EGL。macOS 从已登录的桌面会话启动，不需要设置该变量。

已在其他目录安装时，启动主程序前设置：

```bash
export MANILOOP_LIBERO_PYTHON=/path/to/libero-env/bin/python
export MANILOOP_LIBERO_ROOT=/path/to/LIBERO
```

默认从当前工作目录寻找 `.venv-libero` 和 `.external/LIBERO`。源码必须是安装脚本固定的 Git 版本；不支持把任意版本冒充同一实验协议。

## 在另一个 Git 工作区复用已安装的环境

新建 worktree 不会自动带上被 Git 忽略的虚拟环境和资产目录。若原工作区已安装，
可在新工作区根目录执行（将路径换成原工作区）：

```bash
python scripts/setup_libero.py --reuse-from ../ManiLoop
python -m maniloop list --backend libero
python -m maniloop smoke --backend libero
```

该命令校验固定源码版本与 Python 3.10 / MuJoCo 2.3.7 / robosuite 1.4.0，
只为 `.venv-libero` 和 `.external/LIBERO` 创建本地目录链接，不下载、不调用 pip。
可重复运行；已有目录、文件或其他链接不会被覆盖。两个目标都检查通过后才建立链接。
原工作区必须保留且不能随意移动；环境更新应由原工作区统一管理。
普通安装命令遇到共享链接会停止，避免误改另一个工作区的依赖。
系统不允许目录链接时，使用上文的两个环境变量指定 Python 和 LIBERO 路径。
链接建立后，已启动的服务在下一次加载目录/场景时即可找到运行时，无需更改 API 配置。

## 选择任务与批量运行

网页支持切换环境后端、官方任务集、任务编号和初始化编号。点击「应用并重置场景」后使用官方任务指令；首次加载可能需要等待数十秒。机器人固定为 Panda。换成 ARX5 属于新的跨具身体任务变体，需要另行验证，不能继续标作原版 LIBERO。

```bash
python -m maniloop list --backend libero --libero-suite libero_goal
python -m maniloop demo --backend libero --libero-suite libero_goal --libero-task-id 0 --init-state-id 0
python -m maniloop benchmark --backend libero --max-calls 3
python -m maniloop benchmark --suite examples/libero-offline-suite.toml
```

`--libero-suite` 可选 `libero_spatial`、`libero_object`、`libero_goal`、`libero_90`、`libero_10`。编号从 0 开始；具体名称通过 `list` 查询。`--suite` 是 ManiLoop 实验矩阵文件，和 `--libero-suite` 含义不同。

运行实际云端模型实验：

```bash
python -m maniloop benchmark --backend libero --agent llm_cloud --provider-config /path/to/provider.toml --model YOUR_VISION_MODEL_ID --max-calls 10
```

Key 与模型服务要求沿用主 README。此命令会调用付费 API；离线模拟适配器不会。`--no-render` 仅用于离线接口检查，不能用于 LLM 视觉评测。

## 保留什么，适配什么

固定上游版本：[`8f1084e3132a39270c3a13ebe37270a43ece2a01`](https://github.com/Lifelong-Robot-Learning/LIBERO/tree/8f1084e3132a39270c3a13ebe37270a43ece2a01)。保留官方 BDDL、资产、初始化状态、Panda、robosuite `OSC_POSE` 配置和 `check_success()`。初始化遵循官方示例的 10 个零动作预热步骤，之后开始计量 episode 时间。

ManiLoop 保留 `maniloop_libero_rgb_proprio_v1` 作为基线，并增加 LLM 观测配置 `maniloop_libero_llm_rgb512_v2`：

- 底层环境和离线模拟基线观测是外部 / 腕部 128×128 RGB、相机标定、关节编码器、机器人运动学 TCP、夹爪开度。图像垂直翻转为左上角原点，并编码为 JPEG。**不提供物体状态、物体相对位姿、分割、接触列表、奖励或成功状态给策略，也不提供深度查询。**
- 原生 VLA 接口是 `Action(kind="osc_pose", values=(七个归一化值), frame="world")`。前六维为世界坐标系 TCP 平移 / 旋转增量，最后一维 -1 张开、+1 闭合。每维范围 [-1,1]，采样间隔必须为 0.05 秒（20 Hz）。动作由官方控制器执行；已接入真实 SmolVLA / ACT / Diffusion 学习策略，使用独立推理环境；见 [本地策略说明](VLA.md)。
- 原生单步基线 `osc_step` 使用米 / 弧度动作；适配器显式转换为原生 OSC 输入。平移范数最多 0.05 m，旋转范数最多 0.5 rad，每次 move 执行一个控制步。并不保证末端立即到达目标，模型须重新观察。夹爪只接受 0 / 1，执行 10 个控制步；wait 为一个零机械臂增量控制步。
- 网页与云端批量实验默认使用 `llm_rgb512` 的 512×512 JPEG 和 `tcp_target_servo_v2`。米／弧度增量转换为固定目标位姿，本地以 20 Hz 原生 OSC 反馈追踪，最多 20 步；位置容差 2 mm、姿态容差 0.02 rad，低于速度门槛并稳定两步才报告 reached。夹爪命令保持 TCP 目标至少 10 步，并等待位姿与开度变化速度稳定；张开时还要求开度达到 90%。completed 表示夹爪稳定，不代表抓到物体；超过 20 步仍未满足条件则报告 timed_out。位姿和夹爪均只使用本体反馈。
- `--llm-control osc_step --observation-profile debug_rgb128` 可复现原始基线；批量实验支持 `--request-timeout-seconds 120 --reasoning-effort low`，套件相应字段为 `llm_control`、`observation_profile`、`request_timeout_seconds`、`reasoning_effort`。模式、图像、控制器容差与实际请求参数分别进入 manifest 和比较组。
- 保留官方控制器意味着不会套用自建任务的 IK、碰撞预检或运动规划。两类环境的动作能力不同，分别形成比较组。
- 模型推理时默认冻结物理；实时模式单独比较。网页闲置时不会消耗 LIBERO 控制步预算。成功或预算终止后不再推进；没有自建任务的额外 1.2 秒静置窗口。
- 官方 horizon 为 1000，其中包含 10 步预热，正式 episode 最多执行 990 步，另受 CLI 仿真 / 墙钟 / 决策预算约束。这个时间协议需要与目标论文的评测协议逐项核对。

因此，**复用官方任务不等于原样复现论文评测**。记录明确写入 `paper_comparable=false`，保存上游版本、BDDL / 初始化文件摘要、控制器配置、图像处理、依赖版本及实际初始化编号。比较时同时核对任务、初始化集合、控制步数、输入信息与动作编排，不能只比较模型名字。

## 依赖与维护

[requirements/libero.txt](../requirements/libero.txt) 固定直接仿真依赖：Python 3.10、MuJoCo 2.3.7、robosuite 1.4.0、NumPy 1.23.5、PyTorch 2.2.2 等。PyTorch 用来读取上游初始化文件；无需训练或下载权重。这是经过接入验证的**仿真运行环境**，不是官方训练依赖复刻；传递依赖仍由安装器解析。

worker 用自己的临时 `LIBERO_CONFIG_PATH`，避免首次导入交互询问，也不改用户 `~/.libero`。macOS 上只绕过 MuJoCo 2.3.7 未使用的 CGL 加载入口，实际使用 robosuite 自己的 GLFW 上下文；不修改上游模型、控制器或任务文件。

本地学习策略另用 `lerobot_rgb256`：256×256 无损 RGB，以及 TCP 四元数和两个夹指关节位置，经 LeRobot 官方处理器组成 8 维本体状态。四种模型的已记录结果及指标定义见 [模型对比](RESULTS.md)。

离线测试和真实集成检查分开：

```bash
python -m pytest -q
MANILOOP_TEST_LIBERO=1 python -m pytest tests/test_libero_integration.py -q
```

第二项需要安装 LIBERO 和可用渲染环境；验证官方重置一致性、双相机、物理运动、独立评分及五个任务目录。未设置变量时会明确跳过。每个目录可列出不等于所有任务逐一通过物理验证，当前重点验证 spatial task 0。
