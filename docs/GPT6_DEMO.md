# GPT-6 仿真操作演示

本入口复用 ManiLoop 的 LIBERO / MuJoCo、官方 Panda 控制器和独立评分。GPT-6 读取相机与机器人本体状态，每次返回一个经过本地校验的动作；执行后重新观察。工程入口已实现，任务表现以本次实测记录为准，不能由接口测试推断。

## 启动与登录

先完成 [主环境](../README.md) 和 [LIBERO 环境](LIBERO.md) 安装。本入口不需要 VLA 权重，独立 API 聊天页仍按 [API_CHAT.md](API_CHAT.md) 使用。

使用近期官方 Codex CLI，并在同一台电脑执行 `codex login`，通过 ChatGPT 登录。`codex login status` 只验证本地登录记录，不能证明访问令牌有效或模型可用。实际请求曾确认 0.144.1 被 GPT-6 拒绝，服务器要求更新客户端；本机使用应用自带 0.154.0-alpha.6.2。官方版本见 [Codex releases](https://github.com/openai/codex/releases)。

默认使用 PATH 中的 `codex`。如果系统安装了多个版本，可通过 `MANILOOP_CODEX_BIN` 指定官方可执行文件的绝对路径。这个变量是程序路径，不是密钥；CLI 的登录状态检查与推理共用该路径。本次 Mac 上的启动方式：

```bash
export MANILOOP_CODEX_BIN="/Applications/ChatGPT.app/Contents/Resources/codex"
.venv/bin/python -m maniloop demo \
  --backend libero --libero-suite libero_spatial --libero-task-id 0 --init-state-id 0 \
  --timing controlled --llm-control tcp_target_servo_v2 \
  --observation-profile llm_rgb512 --codex-login \
  --port 8767 --output runs/gpt6-demo
```

其他电脑应替换为实际的官方 CLI 路径，不能假定应用安装位置相同。

打开 <http://127.0.0.1:8767/>，认证来源选择「Codex · 使用当前 ChatGPT 登录」。ManiLoop 不读取或复制 token；官方 CLI 处理认证。该通道使用账户 Codex 额度，和普通 API Key 计费通道分别记录。不会自动换模型或供应商。

每次调用使用临时传感输入目录、独立 ephemeral 会话、`--ignore-user-config`、禁用外部工具与本机 skill。临时目录仅有显式相机图像和动作 schema。输出出现工具事件或不完整响应会被拒绝。CLI 自带的 code-mode-disabled 启动告警仅按精确文本识别；不会为了消除告警启用代码执行。

## 演示步骤

1. 点击「加载 GPT-6 抓放演示」。预设选择 spatial task 0 / init 0 / seed 0、RGB512 双相机、受控时序、固定 TCP 目标跟踪、low 推理、30 次决策和 3600 秒墙钟预算。此操作只准备场景，不调用模型。
2. 依次做文字、图像、动作格式诊断。每个按钮提交一次请求，不执行动作。诊断结果不能代替操作验收。
3. 点击「单步执行」：请求一次决策，等动作执行或超时结束后暂停。可查看理由、实际位移、残差和前后帧，然后选择「下一步」或「继续连续执行」。
4. 「执行后暂停」会完成当前在途决策和动作，然后暂停，不再请求下一次决策。「停止」终止本轮，取消 Codex 子进程并丢弃迟到响应；「重新初始化」开始新的场景。
5. 暂停或结束后点「回看最近实验」。每个运行目录也有独立 `replay.html`，可离线用浏览器打开。重启网页服务后会从相同输出目录恢复最近的已保存回放。它展示每次决策的前后图像、动作与反馈，以及分开展示的模型声明和官方评分。

暂停时不推进物理，墙钟预算继续累计。人工暂停/继续会记录在事件与运行摘要中，不应将带人工干预的演示当作固定策略评测。手动点动和改任务必须先停止本轮。

## 两种视觉上下文

- `current`：当前外部与腕部相机、机器人本体和近期动作反馈。
- `paired`：额外提供最近一次动作前的双相机，以及版本为 `sensor_transition_v1` 的前后本体状态、动作与最终执行反馈。`previous/` 图像标签明确表示旧帧，不能在旧帧上发起深度查询。

`reached` 表示末端到位，夹爪 `completed` 表示控制过程结束；二者都不证明抓住物体。物体坐标、接触真值、奖励、任务成功信号及其嵌套字段不会进入模型输入。独立评分只进入人类界面和回放。官方评分触发终止后不再请求策略。

运行目录记录 manifest、策略观测、上下文、每次相机帧、动作/反馈事件、回放和独立摘要。上下文模式、动作协议、CLI 版本、请求参数、预算和代码摘要进入 provenance；临时 CLI 原始输出、认证文件和推理内部文本不落盘。

## 批量入口

先通过小范围诊断后，才按确定预算使用：

```bash
.venv/bin/python -m maniloop benchmark \
  --backend libero --libero-suite libero_spatial --libero-task-id 0 --init-state-id 0 \
  --agent llm_cloud --codex-login --model gpt-6-astra --context-mode paired \
  --max-calls 30 --max-wall-seconds 3600 --request-timeout-seconds 120 \
  --output runs/gpt6-demo-benchmark
```

`--max-calls` 限制策略请求次数；Codex CLI 内部的网络重试由官方客户端管理，所以它不等于 HTTP 尝试次数。输出 schema 与客户端响应长度有限制，CLI 没有本接口可用的服务端 `max_output_tokens` 参数，不宣称它是硬 token 预算。

原始 [改造计划](design/GPT6_SIM_DEMO_PLAN.md)保留设计过程；本轮实际结果见 [worknote 的 M13](worknotes/worknote.md)。未进行大规模实验或训练，三个初始化的复验仍需在最终配置冻结后另行安排。
