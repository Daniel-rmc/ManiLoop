# GPT-6 仿真操作演示

GPT-6 读取双相机与机器人本体状态，每次返回一个经过本地校验的动作，由 LIBERO 的官方 Panda 控制器执行。动作后重新观察，独立评分不进入模型输入。[观看完整演示](https://daniel-rmc.github.io/ManiLoop/#demo)或阅读[模型对比与结果](RESULTS.md)。

## 启动与登录

公开成功演示使用 paired、medium 和 `--max-calls 0`，46 次决策后通过官方评分。要使用相同配置，请在网页预设基础上设置这三个选项，或使用下方完整命令；模型输出不是确定性重播。

先完成 [主环境](../README.md) 和 [LIBERO 环境](LIBERO.md) 安装。本入口不需要 VLA 权重，独立 API 聊天页仍按 [API_CHAT.md](API_CHAT.md) 使用。

使用支持所选模型、图像与结构化输出的近期[官方 Codex CLI](https://github.com/openai/codex)，并执行 `codex login`，通过自己的 ChatGPT 账号登录。`codex login status` 只验证本地登录记录，模型权限和服务可用性由实际请求决定。

默认使用 PATH 中的 `codex`。如果系统安装了多个版本，可通过 `MANILOOP_CODEX_BIN` 指定所需官方可执行文件的路径。启动网页：

```bash
.venv/bin/python -m maniloop demo \
  --backend libero --libero-suite libero_spatial --libero-task-id 0 --init-state-id 0 \
  --timing controlled --llm-control tcp_target_servo_v2 \
  --observation-profile llm_rgb512 --codex-login \
  --port 8767 --output runs/gpt6-demo
```

打开 <http://127.0.0.1:8767/>，认证来源选择「Codex · 使用当前 ChatGPT 登录」。ManiLoop 不读取或复制 token；官方 CLI 处理认证。该通道使用账户 Codex 额度，和普通 API Key 计费通道分别记录。不会自动换模型或供应商。

每次调用使用临时传感输入目录、独立 ephemeral 会话、`--ignore-user-config`，并禁用外部工具。临时目录仅有显式相机图像和动作 schema。输出出现工具事件或不完整响应会被拒绝。

## 演示步骤

1. 点击「加载 GPT-6 抓放演示」。预设选择 spatial task 0 / init 0 / seed 0、RGB512 双相机、受控时序、固定 TCP 目标跟踪、low 推理、30 次决策和 3600 秒墙钟预算。此操作只准备场景，不调用模型。
2. 依次做文字、图像、动作格式诊断。每个按钮提交一次请求，不执行动作。诊断结果不能代替操作验收。
3. 点击「单步执行」：请求一次决策，等动作执行或超时结束后暂停。可查看理由、实际位移、残差和前后帧，然后选择「下一步」或「继续连续执行」。
4. 「执行后暂停」会完成当前在途决策和动作，然后暂停，不再请求下一次决策。「停止」终止本轮，取消 Codex 子进程并丢弃迟到响应；「重新初始化」开始新的场景。
5. 暂停或结束后点「回看最近实验」。每个运行目录也有独立 `replay.html`，可离线用浏览器打开。重启网页服务后会从相同输出目录恢复最近的已保存回放。它展示每次决策的前后图像、动作与反馈，以及分开展示的模型声明和官方评分。

调用上限填 `0` 表示不按决策次数截断；检测到官方环境成功／终止后，调度器停止后续请求，评分仍不进入策略输入。环境自身的回合边界和墙钟预算继续生效。

需要从初态到终止的完整操作录像时，使用批量入口的 `--record-episode`；它保存每个真实控制步，和上述决策前后帧回看分别记录。导出 MP4 与完整性验收见 [完整 episode 录制](EPISODE_RECORDING.md)。

暂停时不推进物理，墙钟预算继续累计。人工暂停/继续会记录在事件与运行摘要中，不应将带人工干预的演示当作固定策略评测。手动点动和改任务必须先停止本轮。

## 两种视觉上下文

- `current`：当前外部与腕部相机、机器人本体和近期动作反馈。
- `paired`：额外提供最近一次动作前的双相机，以及版本为 `sensor_transition_v1` 的前后本体状态、动作与最终执行反馈。`previous/` 图像标签明确表示旧帧，不能在旧帧上发起深度查询。

### 模型会收到哪些执行反馈

控制器根据机器人可观测的本体状态与模型上一条指令，计算执行反馈，并通过下一次观测的 `last_feedback` 和近期动作历史提供给模型。`paired` 模式还在前后状态转换中携带这份反馈。

其中 `position_error_m = ‖实测 TCP 位置 − 指令 TCP 目标位置‖`，网页换算为毫米显示为“TCP误差”。它反映机器人是否执行到自己被要求的位置，**不是夹爪与目标物体的距离，也不使用目标物体位置真值**。目标位置由动作开始时的末端位置加上模型请求的位移得到；夹爪动作则保持当前末端目标。

`reached` 表示指令末端目标到位，夹爪 `completed` 表示动作已稳定，原始反馈明确注明抓取未验证；二者都不证明抓住物体或完成任务。物体坐标、接触真值、奖励、任务成功信号及其嵌套字段不会进入模型输入。独立评分只进入人类界面和回放；官方评分触发终止后不再请求策略。

这份反馈由 ManiLoop 允许的 observation 和动作指令派生，属于本体控制反馈。跨策略比较需记录是否提供该反馈，不能仅凭所有策略运行相同任务就认定其信息条件相同。计算实现见 [PoseTarget](../src/maniloop/controllers/target.py)，输入字段约束见 [observations](../src/maniloop/core/observations.py)。

运行目录记录 manifest、策略观测、上下文、每次相机帧、动作/反馈事件、回放和独立摘要。上下文模式、动作协议、CLI 版本、请求参数、预算和代码摘要进入 provenance；临时 CLI 原始输出、认证文件和推理内部文本不落盘。

## 批量入口

运行完整 episode 并记录所有控制步：

```bash
.venv/bin/python -m maniloop benchmark \
  --backend libero --libero-suite libero_spatial --libero-task-id 0 --init-state-id 0 \
  --seed 0 --agent llm_cloud --codex-login --model gpt-6-astra \
  --context-mode paired --reasoning-effort medium \
  --llm-control tcp_target_servo_v2 --observation-profile llm_rgb512 \
  --max-calls 0 --max-wall-seconds 3600 --max-sim-seconds 120 \
  --request-timeout-seconds 120 --record-episode \
  --output runs/gpt6-demo-benchmark
```

`--max-calls` 限制策略请求次数；Codex CLI 内部的网络重试由官方客户端管理，所以它不等于 HTTP 尝试次数。输出 schema 与客户端响应长度有限制，CLI 没有本接口可用的服务端 `max_output_tokens` 参数，不宣称它是硬 token 预算。
