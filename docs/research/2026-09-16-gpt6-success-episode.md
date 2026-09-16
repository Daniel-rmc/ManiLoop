# GPT-6 完整成功 episode：官方 LIBERO 抓放任务

2026-09-16，GPT-6 Astra 在一次从官方初始化开始的完整运行中，触发了 **LIBERO 官方 `check_success=true`**。该回合的初始评分为 false，终态 `success`、`current_success` 和 `terminated` 均为 true。官网展示这条运行的完整录像，不拼接不同尝试。

这是一条开发演示，不能据此声称多初始化成功率、整体 LIBERO 成功率或对照实验结论。

## 条件与实际结果

| 项目 | 本次记录 |
| --- | --- |
| 任务 | libero_spatial task 0：将盘子与小碗之间的黑碗放到盘子上 |
| 初始化 | 官方 init 0 / seed 0，固定上游版本与原有 10 步预热 |
| 模型 | GPT-6 Astra，官方 Codex CLI / ChatGPT 登录，medium 推理 |
| 观测 | 双相机 RGB512，paired 前后传感上下文；没有物体真值或评分输入 |
| 执行 | tcp_target_servo_v2，官方 Panda OSC，controlled 时序 |
| 决策上限 | 用户要求取消次数截断，`max_calls=0`；保留官方 990 步边界与 3600 秒墙钟保护 |
| GPT 请求 / 动作 | 46 / 46，无协议错误、人工暂停、重置或在线改配置 |
| 官方控制步 | 706，仿真时间 35.30 秒 |
| 运行墙钟 | 667.33 秒，包含模型等待及录制开销，不作为标准性能比较 |
| 终止原因 | environment_terminated；成功后没有新的模型请求 |
| 完整录像 | 707 组双相机画面，初帧加全部控制步；20 fps、1024×568、35.35 秒 |

运行编号为 `20260916-172331-d3bc5ef2`，比较组为 `08dc4e9dc355800d`。运行时源码摘要：

```text
bd90cbeefe2baf5cf7f3789433ac28d0a26fe4ed45d257e451c10e6d79389b52
```

## 完整过程与判定边界

模型先接近并张开夹爪。前四次闭合后的抬升检查未确认抓持，模型分别重新张开并调整；这些重试全部保留在同一条录像中。第 37 次决策再次闭合以夹持碗沿，第 38–39 次抬升并核对随动，随后向盘子上方移动和下降。

**官方成功在第 46 次下降动作执行中触发，环境随即终止。** 最后实际动作仍保持夹爪闭合，没有随后额外执行松爪或退离，模型也没有声明 done。因此本记录证明的是官方任务成功，不能扩张成“完全释放、退离之后的稳定放置也已额外验收”。这保持了用户指定的“仿真器返回成功就停止”的 episode 边界，没有继续推进已终止环境或改变评分。

与[首轮失败](2026-09-16-gpt6-demo-first-run.md)相比，本次调整了上下文、推理档位、决策预算，并补充通用的抬升后随动核对、释放后退离再观察提示。因此不能把改善单独归因于 paired 或任意一个因素。本轮只执行了这一次新的真实 GPT episode，没有批量筛选任务、换初始化、训练或临时接管动作。

## 录像与证据核对

- result、review 和录制元数据中的独立评分完全一致；初态 false，终态 true。
- 连续控制步为 0–706，707 组双相机即 1414 张 JPEG；索引与每张图片的 SHA-256 全部通过校验。
- 46 份策略观测和 46 份上下文通过传感边界检查。成功信号仅供调度终止及人类审阅，没有传给策略。
- 原始事件中有连续编号的 46 次请求与动作；成功终止是最后事件，没有后续请求。
- 运行时保存的 60 份源码文件重新计算摘要，与 manifest 和冻结快照一致。发布前仅清理了新录制元数据中的过时默认适配器文案；本次高层控制模式以父目录 manifest 为准，原始运行文件未改写。
- MP4 经独立解码确认 707 帧、20 fps、35.35 秒。初帧占 0.05 秒，因此视频比控制步仿真时间多一帧；没有插值、删去失败抓取或拼接其他运行。

视频按仿真时间播放，省略受控时序下物理静止的模型等待。原始 episode、策略上下文、完整事件、评分与源码快照保存在被忽略的本地运行目录；官网只发布经复核的视频、精选帧与必要摘要。

## 复现入口

安装独立 LIBERO 环境，并按 [GPT-6 demo 说明](../GPT6_DEMO.md)选择可用的官方 Codex CLI 和完成登录后：

```bash
python -m maniloop benchmark \
  --backend libero --libero-suite libero_spatial --libero-task-id 0 \
  --init-state-id 0 --seed 0 --agent llm_cloud --codex-login \
  --model gpt-6-astra --context-mode paired --reasoning-effort medium \
  --llm-control tcp_target_servo_v2 --observation-profile llm_rgb512 \
  --max-calls 0 --max-wall-seconds 3600 --max-sim-seconds 120 \
  --request-timeout-seconds 120 --record-episode --output runs/gpt6-success-demo
```

模型输出并非确定性重播，重新执行不保证得到相同成功结果。完整录制、导出与失败审阅方法见 [episode 录制说明](../EPISODE_RECORDING.md)。
