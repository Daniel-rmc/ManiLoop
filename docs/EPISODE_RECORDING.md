# 完整 episode 录制

`benchmark --record-episode` 保存同一次 LIBERO 尝试的初始化画面、每个原生控制步的双相机图像、实际七维动作和独立最终评分。默认不录制；显式启用时必须使用 LIBERO、`controlled` 时序和相机渲染。它不调用额外模型，不修改官方物理、初始化、控制器或成功判定。

```bash
.venv/bin/python -m maniloop benchmark \
  --backend libero --libero-suite libero_spatial --libero-task-id 0 \
  --init-state-id 0 --seed 0 --agent llm_cloud --codex-login \
  --model gpt-6-astra --context-mode paired --reasoning-effort medium \
  --max-calls 0 --max-wall-seconds 3600 --record-episode \
  --output runs/recorded-demo
```

这条命令会使用已经登录的 Codex CLI 发起真实模型请求。`--max-calls 0` 取消人为决策次数上限，官方环境终止和墙钟预算仍有效。任务是否成功以本次结果为准；示例命令本身不是成功保证。模型如何接入和配置见 [GPT-6 demo 说明](GPT6_DEMO.md)。

每次运行在独立的 `runs/.../<episode>/` 下生成常规 manifest、事件、策略观测、结果和决策回看；新增 `recording/` 包含：

| 文件 | 内容 |
| --- | --- |
| `000000-external.jpg`、`000000-wrist.jpg` | 官方初始化并完成原有 10 步预热后的第 0 帧，尚未执行策略动作 |
| 后续连续编号 JPEG | 每个实际 20 Hz 原生控制步执行后的两路已有 RGB；不补帧、不插值 |
| `frames.jsonl` | 连续步号、仿真时间、实际动作、本体传感值、图像文件名与 SHA-256 |
| `episode.json` | 官方任务与初始化来源、初始与终态独立评分、帧数、索引 SHA-256、终止原因 |

完整性要求为 `frame_count = evaluation.control_steps + 1`。单次最多录制 991 组画面（原有官方 990 步上限加初帧）。失败和提前结束的尝试同样保存，不能把多次尝试拼接成成功 episode。若异常使捕获不完整，不能通过完整性校验，也不能作为成功录像导出。

策略只接收原有传感输入。录制的评分和最终汇总只供人类审阅；它们不进入模型图像、历史或执行反馈。原始运行目录受 `.gitignore` 忽略，公开示例需要另行选择和检查。

## 导出 MP4

安装好的 `ffmpeg` 可独立编码视频，无需在主 Python 环境安装 LeRobot、PyTorch 或视频推理依赖：

```bash
.venv/bin/python -m maniloop.recording.video runs/recorded-demo/<episode>/recording
```

如果编码器没有加入 PATH，用 `--ffmpeg /path/to/ffmpeg` 明确指定。已安装独立 VLA 环境且包含 `imageio_ffmpeg` 时，可先在该环境查询其自带编码器路径：

```bash
.venv-vla/bin/python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
```

导出器先核对整条索引、所有图片摘要、连续步号和评分步数，再生成左右双相机的 `episode.mp4` 与 `video.json`。默认要求初始 `success=false`、最后官方 `success=true`；审阅失败尝试时显式加 `--allow-failure`，其评分仍保持失败。已经存在的 `episode.mp4` 不会被覆盖。

视频按真实控制时钟 **20 fps** 播放，包含第 0 帧和所有控制步末帧；片长为 `frame_count / 20` 秒。它展示全部操作过程，省略了受控时序下物理静止的模型推理等待和人工暂停墙钟时间。这里的“完整”指该次 episode 的每个原生控制步，不是逐个 MuJoCo 物理子步，也不是浏览器屏幕录像。原有 `replay.html` 仍可查看决策文字与执行前后证据。

## 公开示例

[项目展示页](https://daniel-rmc.github.io/ManiLoop/#demo)包含一条 GPT-6 官方成功录像：46 次决策、706 控制步，707 帧、20 fps、35.35 秒。完整性与任务判定范围见[公开结果](RESULTS.md)。
