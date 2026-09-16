# Results / 实测结果

[English](#english) · [简体中文](#简体中文) · [Project demo / 项目演示](https://daniel-rmc.github.io/ManiLoop/#demo)

## English

These are four selected, real model episodes recorded on **2026-09-16**, one per model, on the same LIBERO task and initialization. They demonstrate working integrations and observed task outcomes. They are **not a success-rate estimate, an efficiency ranking, or a reproduction of a LIBERO paper benchmark**.

### Observed outcomes

| Model | Official task result | Policy calls | Local model inferences | Control steps | Simulation seconds | Wall seconds |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| GPT-6 Astra | Success | 46 | — | 706 | 35.30 | 667.33 |
| SmolVLA | Success | 78 | 2 | 78 | 3.90 | — |
| ACT | Not successful within budget | 500 | 5 | 500 | 25.00 | 66.13 |
| Diffusion Policy | Success | 79 | 10 | 79 | 3.95 | 57.35 |

**Policy calls have different meanings.** GPT uses one model-service request per high-level action. Local policies call LeRobot `select_action` once per control step; most calls consume an existing action queue. “Local model inferences” counts queue-generation calls reported by the local worker, not diffusion sampling iterations. GPT's internal server-side inference count is unavailable. SmolVLA's web run did not preserve wall time with the CLI result's timing definition, so its value is left blank.

CLI wall time starts after scene creation and policy loading. It includes inference, communication, simulation and recording. GPT also includes network/model-service waiting and full-episode capture. Different execution paths, budgets and background load make these values unsuitable for a speed ranking.

Simulation and local-policy inference ran on an Apple M4 Mac with 24 GiB unified memory and macOS 15.7.9. Local models used PyTorch MPS, while GPT inference was hosted remotely.

### Task and execution conditions

All four episodes use `libero_spatial`, task `0`, official initialization `0`, seed `0`: **pick up the black bowl between the plate and the ramekin and place it on the plate**. They retain official Panda / `OSC_POSE`, the original ten zero-action warmup steps, 20 Hz control, and independent `check_success`. LIBERO is pinned to [`8f1084e3132a39270c3a13ebe37270a43ece2a01`](https://github.com/Lifelong-Robot-Learning/LIBERO/tree/8f1084e3132a39270c3a13ebe37270a43ece2a01), with robosuite 1.4.0 and MuJoCo 2.3.7.

| Model | Sensor inputs and execution | Configured limits |
| --- | --- | --- |
| GPT-6 Astra | Two RGB512 cameras; paired before/after sensor context; medium reasoning; bounded TCP target tracking through official OSC | No decision-count cap; 120 simulation seconds; 3600 wall seconds; official 990-step episode limit still applies |
| SmolVLA | Two RGB256 cameras, 8-D proprioception and language; native OSC; 50-step action queue, 10 sampling steps; local MPS | 500 policy calls; web entry: 120 simulation seconds / 600 wall seconds |
| ACT | Two RGB256 cameras and 8-D proprioception; no language input; native OSC; 100-step action queue; local MPS | 500 policy calls; CLI: 25 simulation seconds / 1800 wall seconds |
| Diffusion Policy | Two RGB256 cameras and 8-D proprioception; no language input; native OSC; two-observation history, 8-step action queue, 100 DDPM sampling steps; local MPS | 500 policy calls; CLI: 25 simulation seconds / 1800 wall seconds |

Physics pauses during inference in every episode. GPT and local policies have different image sizes, control interfaces and action scheduling; their manifests belong to different comparison groups. The local runs use LeRobot 0.4.4 and PyTorch 2.10.0. Checkpoint postprocessing is retained; native actions are bounded to `[-1, 1]`, with 53 / 251 / 0 scalar clips recorded for SmolVLA / ACT / Diffusion respectively. ACT's observed failure is a result for this checkpoint and initialization, not a conclusion about the ACT method.

Object state, contact truth, reward and task-success signals are excluded from policy inputs. Independent evaluation is used to stop the episode and produce human-facing results.

### Complete GPT episode

[Watch the complete episode](https://daniel-rmc.github.io/ManiLoop/#demo) · [Open the MP4](https://daniel-rmc.github.io/ManiLoop/assets/episodes/20260916-172331-d3bc5ef2/episode.mp4)

Initial official success is `false`. After 46 valid requests and 706 native control steps, terminal `success`, `current_success` and `terminated` are all `true`. There were no protocol errors, human pauses, resets or online configuration changes during this episode, and no additional model request followed termination. The repeated grasp attempts remain in the recording.

**Success occurs during the final downward action, and the environment stops immediately.** The gripper remains commanded closed; no additional release or withdrawal was executed. This demonstrates the official task condition, not a separate verification of stable placement after full release and withdrawal.

The MP4 contains initialization plus every control-step frame from this single episode: **707 dual-camera frames, 20 fps, 1024×568, 35.35 seconds**. It omits only wall-clock waiting while controlled physics is frozen. No attempts were spliced together and no frames were interpolated. The extra initial frame accounts for the 0.05-second difference from simulation duration. All 1,414 source images and the continuous frame index passed SHA-256 checks; the recording, result and review share the same official evaluation. See [episode recording](EPISODE_RECORDING.md) for capture and export behavior.

### Fixed local checkpoints

| Model | Public checkpoint | Revision |
| --- | --- | --- |
| SmolVLA | [lerobot/smolvla_libero](https://huggingface.co/lerobot/smolvla_libero) — official LeRobot | `31d453f7edd78c839a8bbc39744a292686daf0de` |
| ACT | [Deepkar/libero-test-act](https://huggingface.co/Deepkar/libero-test-act) — community | `b6a5253edf0c9d9e458629fdeb489f514ff6300f` |
| Diffusion Policy | [ttotmoon/diffusion-libero-v3](https://huggingface.co/ttotmoon/diffusion-libero-v3) — community | `5825af28c585ade6827ea7e8f6234f3ab04e8ab1` |

Installation and execution: [GPT demo](GPT6_DEMO.md), [local policies](VLA.md), [LIBERO](LIBERO.md). Re-running a model is not deterministic playback and is not guaranteed to reproduce a selected outcome.

## 简体中文

这里展示 **2026-09-16** 记录的四条真实模型运行示例，每个模型选取一条，使用相同 LIBERO 任务与初始化。结果说明接口能够运行及这些回合的实际任务表现，**不构成成功率估计、效率排行或 LIBERO 论文基准复现**。

### 实际结果

| 模型 | 官方任务结果 | 策略调用 | 本地模型推理 | 控制步 | 仿真秒 | 墙钟秒 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| GPT-6 Astra | 成功 | 46 | — | 706 | 35.30 | 667.33 |
| SmolVLA | 成功 | 78 | 2 | 78 | 3.90 | — |
| ACT | 预算内未成功 | 500 | 5 | 500 | 25.00 | 66.13 |
| Diffusion Policy | 成功 | 79 | 10 | 79 | 3.95 | 57.35 |

**策略调用不是统一的模型推理计数。** GPT 每次向模型服务提交请求并取得一个高层动作。本地策略每个控制步调用一次 LeRobot `select_action`，多数调用取出已有动作队列中的动作。“本地模型推理”是本地进程报告的动作队列生成次数，不是扩散采样迭代次数；GPT 服务内部的推理次数不可得。SmolVLA 的网页回合没有保存与 CLI 结果口径一致的墙钟值，因此留空。

CLI 墙钟从场景创建及策略加载之后开始，包含推理、通信、仿真和记录；GPT 还包含网络与模型服务等待、完整录像开销。入口、预算和后台负载不同，这些时间不能用于速度排名。

仿真与本地策略运行于 Apple M4 Mac（24 GiB 统一内存、macOS 15.7.9）。本地模型使用 PyTorch MPS，GPT 推理由远端服务完成。

### 任务与执行条件

四条记录均为 `libero_spatial` task `0`、官方 init `0`、seed `0`：**将盘子与小碗之间的黑碗放到盘子上**。保留官方 Panda / `OSC_POSE`、原有 10 步零动作预热、20 Hz 控制和独立 `check_success`。LIBERO 固定为 [`8f1084e3132a39270c3a13ebe37270a43ece2a01`](https://github.com/Lifelong-Robot-Learning/LIBERO/tree/8f1084e3132a39270c3a13ebe37270a43ece2a01)，搭配 robosuite 1.4.0 与 MuJoCo 2.3.7。

| 模型 | 传感输入与执行方式 | 配置的边界 |
| --- | --- | --- |
| GPT-6 Astra | 双 RGB512；paired 前后传感上下文；medium 推理；通过官方 OSC 跟踪有限 TCP 目标 | 不按决策次数截断；120 秒仿真／3600 秒墙钟；仍受官方 990 控制步边界约束 |
| SmolVLA | 双 RGB256、8 维本体与语言；原生 OSC；50 步动作队列、10 次采样；本地 MPS | 500 次策略调用；网页入口为 120 秒仿真／600 秒墙钟 |
| ACT | 双 RGB256 与 8 维本体；无语言输入；原生 OSC；100 步动作队列；本地 MPS | 500 次策略调用；CLI 为 25 秒仿真／1800 秒墙钟 |
| Diffusion Policy | 双 RGB256 与 8 维本体；无语言输入；原生 OSC；两帧历史、8 步动作队列、100 次 DDPM 采样；本地 MPS | 500 次策略调用；CLI 为 25 秒仿真／1800 秒墙钟 |

各回合均在推理期间暂停物理。GPT 与本地模型的图像大小、控制接口、动作调度不同，manifest 属于不同比较组。本地策略使用 LeRobot 0.4.4 和 PyTorch 2.10.0，保留检查点的后处理；原生动作约束在 `[-1, 1]`，SmolVLA／ACT／Diffusion 分别记录 53／251／0 个标量裁剪。ACT 的这次失败仅说明该检查点在此初始化上的表现，不能代表整个方法。

策略输入不包含物体状态、接触真值、奖励或任务成功信号。独立评分只用于回合终止和人类可读的结果。

### GPT 完整回合录像

[观看完整 episode](https://daniel-rmc.github.io/ManiLoop/#demo) · [打开 MP4](https://daniel-rmc.github.io/ManiLoop/assets/episodes/20260916-172331-d3bc5ef2/episode.mp4)

初始官方成功为 `false`；46 次有效请求、706 个原生控制步后，终态 `success`、`current_success` 和 `terminated` 均为 `true`。回合中没有协议错误、人工暂停、重置或在线配置修改；终止后没有追加模型请求。同一回合中的抓取重试均保留。

**官方成功在最后一次下降动作执行中触发，环境立即终止。** 当时夹爪仍保持闭合，没有额外执行松爪或退离。因此证明的是官方任务条件满足，并未单独验证完全释放、退离后的稳定放置。

MP4 保存同一次运行的初始化及每个控制步画面：**707 组双相机、20 fps、1024×568、35.35 秒**。它仅省略受控时序下物理冻结的墙钟等待，没有拼接多次尝试或插值补帧。初帧多占 0.05 秒，因此片长比仿真时长多一帧。1414 张源图和连续帧索引全部通过 SHA-256 检查，录制元数据、结果与回看中的官方评分一致。捕获和导出方式见[完整 episode 录制](EPISODE_RECORDING.md)。

### 固定本地检查点

| 模型 | 公开检查点 | 固定版本 |
| --- | --- | --- |
| SmolVLA | [lerobot/smolvla_libero](https://huggingface.co/lerobot/smolvla_libero)，LeRobot 官方 | `31d453f7edd78c839a8bbc39744a292686daf0de` |
| ACT | [Deepkar/libero-test-act](https://huggingface.co/Deepkar/libero-test-act)，社区 | `b6a5253edf0c9d9e458629fdeb489f514ff6300f` |
| Diffusion Policy | [ttotmoon/diffusion-libero-v3](https://huggingface.co/ttotmoon/diffusion-libero-v3)，社区 | `5825af28c585ade6827ea7e8f6234f3ab04e8ab1` |

安装与运行见 [GPT 演示](GPT6_DEMO.md)、[本地策略](VLA.md)、[LIBERO](LIBERO.md)。再次执行模型并非确定性回放，不能保证重现所选结果。
