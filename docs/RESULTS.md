# Results / 实测结果

[English](#english) · [简体中文](#简体中文) · [Project demo / 项目演示](https://daniel-rmc.github.io/ManiLoop/#demo)

## English

The four-model comparison below uses selected, real episodes recorded on **2026-09-16**, one per model, on the same LIBERO task and initialization. Additional GPT tasks are reported separately. These demonstrate working integrations and observed task outcomes, **not a success-rate estimate, an efficiency ranking, or a reproduction of a LIBERO paper benchmark**.

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

**Execution feedback is provided to GPT.** The controller derives it from permitted robot proprioception and the previously issued command: `position_error_m = ‖measured TCP position − commanded TCP target‖`. It is a target-tracking residual, not the distance to an object or knowledge of its true position. `reached` means the commanded end-effector target was reached; gripper `completed` means motion settled, with grasp explicitly unverified. The next observation's `last_feedback` and recent action history carry these fields. This feedback is allowed by ManiLoop's observation contract; comparisons must still disclose which policies receive it, alongside the controller and observation settings.

### Complete GPT episode

[Watch the complete episode](https://daniel-rmc.github.io/ManiLoop/#demo) · [Open the MP4](https://daniel-rmc.github.io/ManiLoop/assets/episodes/20260916-172331-d3bc5ef2/episode.mp4)

Initial official success is `false`. After 46 valid requests and 706 native control steps, terminal `success`, `current_success` and `terminated` are all `true`. There were no protocol errors, human pauses, resets or online configuration changes during this episode, and no additional model request followed termination. The repeated grasp attempts remain in the recording.

**Success occurs during the final downward action, and the environment stops immediately.** The gripper remains commanded closed; no additional release or withdrawal was executed. This demonstrates the official task condition, not a separate verification of stable placement after full release and withdrawal.

The MP4 contains initialization plus every control-step frame from this single episode: **707 dual-camera frames, 20 fps, 1024×568, 35.35 seconds**. It omits only wall-clock waiting while controlled physics is frozen. No attempts were spliced together and no frames were interpolated. The extra initial frame accounts for the 0.05-second difference from simulation duration. All 1,414 source images and the continuous frame index passed SHA-256 checks; the recording, result and review share the same official evaluation. See [episode recording](EPISODE_RECORDING.md) for capture and export behavior.

### Additional GPT tasks

Four further tasks were each attempted once on the same date: three from `libero_goal` and one from `libero_object`, all with official initialization `0` and seed `0`. GPT-6 Astra retained the RGB512 paired sensor context, medium reasoning, `tcp_target_servo_v2`, controlled timing, no decision-count cap, 120 simulation seconds and 3600 wall seconds, with the official 990-step limit. All four used the same frozen source and protocol. The controller, task definitions and independent success rules were unchanged.

| Task | Official result | Model requests | Executed actions | Control steps | Simulation seconds | Wall seconds |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `goal 5`: push the plate to the front of the stove | Not successful | 33 | 32 | 607 | 30.35 | 576.97 |
| `goal 0`: open the middle drawer | Not successful | 50 | 49 | 890 | 44.50 | 702.41 |
| `goal 7`: turn on the stove | Success | 27 | 25 | 447 | 22.35 | 355.59 |
| `object 1`: place cream cheese in the basket | Success | 29 | 29 | 390 | 19.50 | 327.06 |

Request counts include rejected responses and completion declarations; executed actions count only commands accepted for execution. The plate episode stopped when a response failed the provider's complete, tool-free output validation. The drawer episode stopped when the model declared completion, while official success remained false. The stove episode included two rejected requests before any movement; neither rejection was executed. All four attempts are reported here, and only verified successes enter the [interactive skill gallery](https://daniel-rmc.github.io/ManiLoop/?lang=en#skills). These tasks were selected for demonstrations, not sampled to estimate benchmark success rates.

**Stove recording:** official success changed from `false` to `true` during the final knob rotation, and the environment immediately terminated. The last image still shows a dark burner; no subsequent release, withdrawal or sustained activation was verified. [The full video](https://daniel-rmc.github.io/ManiLoop/assets/episodes/20260916-192032-dfc63995/episode.mp4) contains all **448 dual-camera frames at 20 fps, 22.40 seconds**, including initialization. All 896 source images and the frame index passed SHA-256 and continuity checks. The gallery synchronizes 25 executed actions with their original request numbers and recorded brief action notes; it does not reconstruct private internal reasoning or call a model.

**Cream cheese recording:** after the gripper-opening action at request 28, official success occurred during the upward motion at request 29. The environment stopped with no further model requests. There were no rejected requests or protocol errors. [The full video](https://daniel-rmc.github.io/ManiLoop/assets/episodes/20260916-192749-a5d3f634/episode.mp4) contains all **391 dual-camera frames at 20 fps, 19.55 seconds**. All 782 source images and the frame index passed SHA-256 and continuity checks. Both new successful episodes retain every control step from a single attempt and exclude evaluator signals from policy inputs.

### Recorded wall-clock time

The three published GPT successes took **5.5 minutes** for cream cheese into the basket, **5.9 minutes** for the stove, and **11.1 minutes** for the bowl onto the plate. These are episode wall times, including online model planning and response waiting, communication, controller execution, simulation and frame capture. Timing begins after scene creation and policy loading; initial setup and later video encoding are excluded. The short videos show simulation time, not these wall times.

One accepted GPT action can drive several native control steps through the local target controller. This separates high-level model decisions from the 20 Hz control loop. The current records do not isolate how much this design, feedback, task difficulty, reasoning setting or service latency contributes to runtime. No matched cross-framework comparison or controller ablation has been run, so the examples establish neither a speed advantage nor its cause.

### Fixed local checkpoints

| Model | Public checkpoint | Revision |
| --- | --- | --- |
| SmolVLA | [lerobot/smolvla_libero](https://huggingface.co/lerobot/smolvla_libero) — official LeRobot | `31d453f7edd78c839a8bbc39744a292686daf0de` |
| ACT | [Deepkar/libero-test-act](https://huggingface.co/Deepkar/libero-test-act) — community | `b6a5253edf0c9d9e458629fdeb489f514ff6300f` |
| Diffusion Policy | [ttotmoon/diffusion-libero-v3](https://huggingface.co/ttotmoon/diffusion-libero-v3) — community | `5825af28c585ade6827ea7e8f6234f3ab04e8ab1` |

Installation and execution: [GPT demo](GPT6_DEMO.md), [local policies](VLA.md), [LIBERO](LIBERO.md). Re-running a model is not deterministic playback and is not guaranteed to reproduce a selected outcome.

## 简体中文

下方四模型比较来自 **2026-09-16** 的真实运行，每个模型选取一条，使用相同 LIBERO 任务与初始化；新增 GPT 任务单独报告。结果说明接口能够运行及这些回合的实际任务表现，**不构成成功率估计、效率排行或 LIBERO 论文基准复现**。

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

**执行反馈会提供给 GPT。** 控制器用允许的机器人本体观测与上一条指令计算：`position_error_m = ‖实测 TCP 位置 − 指令 TCP 目标位置‖`。这是目标跟踪残差，不是夹爪到物体的距离，也不需要知道物体位置真值。`reached` 只表示指令末端目标到位；夹爪 `completed` 表示运动已稳定，并明确未验证抓取。下一次观测的 `last_feedback` 和近期动作历史携带这些字段。这属于 ManiLoop 观测约定允许的反馈；跨策略比较时，仍应披露各策略是否获得此反馈，以及控制器和观测设置。

### GPT 完整回合录像

[观看完整 episode](https://daniel-rmc.github.io/ManiLoop/#demo) · [打开 MP4](https://daniel-rmc.github.io/ManiLoop/assets/episodes/20260916-172331-d3bc5ef2/episode.mp4)

初始官方成功为 `false`；46 次有效请求、706 个原生控制步后，终态 `success`、`current_success` 和 `terminated` 均为 `true`。回合中没有协议错误、人工暂停、重置或在线配置修改；终止后没有追加模型请求。同一回合中的抓取重试均保留。

**官方成功在最后一次下降动作执行中触发，环境立即终止。** 当时夹爪仍保持闭合，没有额外执行松爪或退离。因此证明的是官方任务条件满足，并未单独验证完全释放、退离后的稳定放置。

MP4 保存同一次运行的初始化及每个控制步画面：**707 组双相机、20 fps、1024×568、35.35 秒**。它仅省略受控时序下物理冻结的墙钟等待，没有拼接多次尝试或插值补帧。初帧多占 0.05 秒，因此片长比仿真时长多一帧。1414 张源图和连续帧索引全部通过 SHA-256 检查，录制元数据、结果与回看中的官方评分一致。捕获和导出方式见[完整 episode 录制](EPISODE_RECORDING.md)。

### 新增 GPT 任务

同日对另外四项任务各尝试一次：三项来自 `libero_goal`，一项来自 `libero_object`，均为官方 init `0`、seed `0`。保持 GPT-6 Astra、RGB512 paired 前后传感上下文、medium 推理、`tcp_target_servo_v2`、controlled 时序、不按决策次数截断、120 秒仿真／3600 秒墙钟和官方 990 步边界。四次使用相同冻结源码与协议；控制器、任务定义与独立成功规则均未改变。

| 任务 | 官方结果 | 模型请求 | 实际执行动作 | 控制步 | 仿真秒 | 墙钟秒 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `goal 5`：将盘子推到炉具前方 | 未成功 | 33 | 32 | 607 | 30.35 | 576.97 |
| `goal 0`：打开中层抽屉 | 未成功 | 50 | 49 | 890 | 44.50 | 702.41 |
| `goal 7`：打开炉具 | 成功 | 27 | 25 | 447 | 22.35 | 355.59 |
| `object 1`：将奶油奶酪放入篮子 | 成功 | 29 | 29 | 390 | 19.50 | 327.06 |

请求数包含被拒绝的响应和完成声明；实际执行动作只计入通过校验并被接受执行的命令。推盘因一次响应未通过通道的完整、无工具输出校验而停止；抽屉在模型声明完成时停止，官方成功仍为 false；炉具在首次移动前有两次请求被拒绝，均未执行。这里保留四次尝试的结果，[交互技能画廊](https://daniel-rmc.github.io/ManiLoop/?lang=zh#skills)仅收录经过核验的成功回合。这些任务按演示需求选择，不用于估计基准成功率。

**炉具录像：**官方成功在最后一次转动旋钮时从 `false` 变为 `true`，环境立即终止；终帧炉盘仍呈暗色，未额外验证松爪、退离或持续开启。[完整视频](https://daniel-rmc.github.io/ManiLoop/assets/episodes/20260916-192032-dfc63995/episode.mp4)包含初始帧及全部 **448 组双相机、20 fps、22.40 秒**。896 张源图及索引通过 SHA-256 与连续性检查。画廊按原始请求编号同步展示 25 次实际执行动作和模型当时的简短动作说明，不重构模型内部推理，也不发起模型请求。

**奶油奶酪录像：**第 28 次请求执行打开夹爪动作后，第 29 次请求的上移动作过程中触发官方成功。环境随即终止，没有追加模型请求；本回合无拒绝请求或协议错误。[完整视频](https://daniel-rmc.github.io/ManiLoop/assets/episodes/20260916-192749-a5d3f634/episode.mp4)包含全部 **391 组双相机、20 fps、19.55 秒**。782 张源图和索引通过 SHA-256 与连续性检查。两条新成功录像均保留同一次尝试的每个控制步，策略输入均不包含评分信号。

### 实际墙钟时间

三段公开 GPT 成功回合分别用时：奶油奶酪入篮 **5.5 分钟**、炉具 **5.9 分钟**、放碗 **11.1 分钟**。这是回合墙钟时间，包含在线模型规划与响应等待、通信、控制器执行、仿真和逐帧记录。计时从场景创建与策略加载之后开始，不包含初始安装加载及后续视频编码；短视频展示的是仿真时间，不是墙钟时间。

一个被接受的 GPT 动作可以通过本地目标控制器执行多个原生控制步，将模型高层决策与 20 Hz 控制循环分开。当前记录没有分离这一设计、执行反馈、任务难度、推理设置和服务延迟各自对时长的贡献。尚未进行条件匹配的跨框架比较或控制器消融，因此不能据这些样例证明速度优势或其原因。

### 固定本地检查点

| 模型 | 公开检查点 | 固定版本 |
| --- | --- | --- |
| SmolVLA | [lerobot/smolvla_libero](https://huggingface.co/lerobot/smolvla_libero)，LeRobot 官方 | `31d453f7edd78c839a8bbc39744a292686daf0de` |
| ACT | [Deepkar/libero-test-act](https://huggingface.co/Deepkar/libero-test-act)，社区 | `b6a5253edf0c9d9e458629fdeb489f514ff6300f` |
| Diffusion Policy | [ttotmoon/diffusion-libero-v3](https://huggingface.co/ttotmoon/diffusion-libero-v3)，社区 | `5825af28c585ade6827ea7e8f6234f3ab04e8ab1` |

安装与运行见 [GPT 演示](GPT6_DEMO.md)、[本地策略](VLA.md)、[LIBERO](LIBERO.md)。再次执行模型并非确定性回放，不能保证重现所选结果。
