"use strict";

(() => {
  const messages = {
  "en": {
    "skip": "Skip to content",
    "home": "ManiLoop home",
    "navigation": "Main navigation",
    "nav_framework": "Framework",
    "nav_demo": "Demo",
    "nav_models": "Models",
    "nav_start": "Get started",
    "language": "Language",
    "hero_eyebrow": "OPEN ROBOT MANIPULATION",
    "hero_see": "See.",
    "hero_act": "Act.",
    "hero_observe": "Observe again.",
    "hero_description": "Connect model decisions to a physical feedback loop. Run GPT and local VLA policies in MuJoCo, inspect each action, and replay the complete episode.",
    "try_workspace": "Try the workspace",
    "watch_demo": "Watch the demo",
    "workspace_hint": "Explore the recorded run interactively in your browser. Live simulation runs locally.",
    "tech_stack": "Technology stack",
    "observation_label": "OBSERVATION / 01",
    "hero_alt": "A recorded LIBERO scene with the Panda arm, bowls and a plate",
    "external_camera": "EXTERNAL CAMERA",
    "real_image": "An actual simulator frame",
    "browse_episode": "Explore the episode",
    "sensor_note": "The policy sees images and robot state.",
    "score_note": "The evaluator stays separate.",
    "framework_eyebrow": "01 / THE FRAMEWORK",
    "framework_title": "Close the loop. Inspect every step.",
    "framework_intro": "A shared interface for model inference, simulator control and recorded feedback. See what the policy asked for and what the robot actually did.",
    "loop_aria": "Cameras and robot state feed the policy. Validated actions execute in the simulator, then fresh sensor feedback informs the next decision. Evaluation is separate.",
    "observe": "Observe",
    "observe_inputs": "Dual-camera RGB\nRobot proprioception",
    "observe_tag": "SENSOR INPUT",
    "decide": "Decide",
    "decide_inputs": "Structured GPT actions\nor a local VLA policy",
    "decide_tag": "POLICY",
    "act": "Act",
    "act_inputs": "Validate and track targets\nMuJoCo / LIBERO",
    "act_tag": "LOCAL CONTROL",
    "check": "Check",
    "check_inputs": "New images and motion\nExecution status and error",
    "check_tag": "FEEDBACK",
    "loop_return": "Fresh sensor evidence for the next decision",
    "independent_evaluation": "Independent evaluation",
    "boundary_description": "Object ground truth, rewards and success signals go to the viewer and result records only.",
    "boundary_label": "EVALUATOR ≠ POLICY INPUT",
    "feature_a_tag": "A / INTERFACES",
    "feature_a_title": "One framework, multiple policies",
    "feature_a_description": "Use GPT vision and structured output, or run SmolVLA, Diffusion Policy and ACT in an isolated inference environment. Each adapter preserves its observation and action protocol.",
    "architecture_link": "Explore the architecture",
    "feature_b_tag": "B / CONTROL",
    "feature_b_title": "Debug a single action",
    "feature_b_description": "Step once, pause after an action, or continue. Inspect the requested TCP target, actual displacement and controller error before allowing the next decision.",
    "control_link": "Use the control interface",
    "feature_c_tag": "C / RECORDING",
    "feature_c_title": "Replay the complete episode",
    "feature_c_description": "Record the initial scene and every native control step. Review both cameras, action notes and the independent result, or export a continuous MP4.",
    "recording_link": "Record and export",
    "demo_eyebrow": "02 / THE EPISODE",
    "demo_title": "One task. Every step recorded.",
    "demo_intro": "Actual simulator footage with an independent task result. This page plays saved media; it does not call a model or run a simulator.",
    "recorded_demo": "RECORDED DEMO",
    "loading_task": "Loading the task record",
    "loading_model": "Model and settings are loaded from the episode",
    "complete_episode": "COMPLETE EPISODE",
    "video_aria": "Complete robot manipulation episode",
    "video_fallback": "Your browser does not support embedded video. Open the recording using the link below.",
    "episode_caption": "One continuous attempt, from initialization to the independently scored terminal state.",
    "episode_timing_default": "Playback follows simulation time; inference waits do not advance the physics.",
    "download_episode": "Open the full video",
    "selected_title": "Selected decision frames",
    "selected_description": "Observation points from the same episode, paired with action notes. These are not continuous video.",
    "external_label": "01 / EXTERNAL",
    "external_alt": "Recorded external camera frame",
    "wrist_label": "02 / WRIST",
    "wrist_alt": "Recorded wrist camera frame",
    "previous_frame": "Previous frame",
    "play_frames": "Play frames",
    "next_frame": "Next frame",
    "select_frame": "Select a recorded frame",
    "playback_note": "Selected decision frames · Original order · Not continuous video",
    "record_detail": "Selected frame details",
    "observation_stage": "OBSERVATION",
    "loading_recording": "Loading the recording",
    "model_note_label": "Model action note · Recorded output",
    "action_feedback": "Action execution feedback",
    "position_error": "TCP position error",
    "feedback_caveat": "Action notes and controller feedback do not establish a secure grasp. Task success is reported by the independent evaluator.",
    "metrics_aria": "Independent result for this episode",
    "model_decisions": "model decisions",
    "control_steps": "native control steps",
    "simulation_time": "simulation time",
    "pending": "Pending",
    "independent_result": "Independent task result",
    "loading_conditions": "Loading run conditions",
    "result_default": "Task completion is determined by the independent simulator evaluator.",
    "single_episode_note": "One episode does not establish a benchmark success rate.",
    "results_link": "Read the results",
    "models_eyebrow": "03 / MODEL EXAMPLES",
    "models_title": "What each model actually did.",
    "comparison_scope": "Recorded examples on an official LIBERO task. Each row describes one run, with its own controller and inference setup.",
    "comparison_aria": "Model example results; scroll horizontally to see all columns",
    "comparison_caption": "Actual model runs with independently scored task results",
    "col_model": "Model",
    "col_result": "Official result",
    "col_policy": "Policy calls",
    "col_inference": "Inference calls",
    "col_steps": "Control steps",
    "col_setup": "Configuration and scope",
    "comparison_loading": "Loading recorded model examples",
    "comparison_caveat": "These are individual examples, not success-rate estimates. Budgets, action chunks and control methods differ; step counts and timings do not form a speed ranking.",
    "comparison_results": "Check configurations and results",
    "start_eyebrow": "04 / GET STARTED",
    "start_title": "Run the loop on your machine.",
    "start_intro": "Start with simulation and manual control, then connect a model. The main application, LIBERO and VLA inference use separate environments.",
    "install_main_title": "Set up the main environment",
    "copy_main": "Copy main environment commands",
    "copy": "Copy",
    "install_main_note": "Open 127.0.0.1:8765 for the default tabletop demo. Starting the simulator and using manual controls requires no model key. Use another terminal, or stop the demo with Ctrl+C, before installing LIBERO.",
    "install_full_link": "Full setup and Windows instructions",
    "install_libero_title": "Add LIBERO",
    "install_libero_subtitle": "A separate Python 3.10 simulation environment",
    "copy_libero": "Copy LIBERO setup commands",
    "install_libero_note": "Open 127.0.0.1:8767 on your machine. Git, network access and a supported graphics setup are required. VLA weights are optional.",
    "libero_requirements": "Requirements and headless setup",
    "connect_eyebrow": "CONNECT A MODEL",
    "connect_title": "Give the policy a turn.",
    "connect_description": "Connect an API service with image and structured-output support, or use the ChatGPT login channel of a recent official Codex CLI. Run diagnostics, then try a small movement. Model requests use your provider or account quota.",
    "gpt_guide": "GPT simulation guide",
    "api_guide": "API chat and diagnostics",
    "vla_guide": "Local LeRobot / VLA policies",
    "invitation": "Connect your model.\nInspect its actions.",
    "issues_link": "Questions and contributions",
    "footer_tagline": "Open framework. Observable actions.",
    "source": "Source",
    "license": "MIT License",
    "documentation": "Documentation",
    "footer_note": "Recorded episodes here. Simulation runs locally.",
    "page_title": "ManiLoop — See. Act. Observe again.",
    "meta_description": "Connect GPT and local VLA policies to MuJoCo and LIBERO. Inspect visual feedback, structured actions, complete episodes and independent task results.",
    "og_description": "An open robot manipulation framework with visual feedback, local control and independently scored episodes.",
    "missing_model": "Model not recorded",
    "missing_date": "Date not recorded",
    "context_current": "Current camera views",
    "context_paired": "Before/after camera views",
    "reasoning": "{level} reasoning",
    "reasoning_low": "Low",
    "reasoning_medium": "Medium",
    "reasoning_high": "High",
    "task_key": "task",
    "init_key": "init",
    "seed_key": "seed",
    "timing_controlled": "controlled timing",
    "timing_realtime": "real-time timing",
    "conditions_report": "Full configuration in the results",
    "success": "Success",
    "failure": "Not successful",
    "unverified": "Unverified",
    "official_true": "Official LIBERO result · true",
    "official_false": "Independent result · false",
    "not_verified": "Success has not been independently verified",
    "verified_episode": "VERIFIED EPISODE",
    "recorded_attempt": "RECORDED ATTEMPT",
    "result_verified": "The terminal state of this run was checked: LIBERO check_success returned true. Evaluation was kept out of the policy input.",
    "result_failed": "This attempt returned independent success = false. {reason}.",
    "result_unverified": "The independent result still needs verification. A model declaration or a reached controller target does not establish task success.",
    "termination_success": "The official task conditions were met",
    "termination_decision_budget": "Decision budget exhausted",
    "termination_simulation_budget": "Simulation-time budget exhausted",
    "termination_wall_budget": "Wall-time budget exhausted",
    "termination_model_done": "The model declared completion",
    "termination_stopped": "The run was stopped",
    "termination_other": "See the result report for the termination reason",
    "demo_model_intro": "A recorded simulator episode from {model}. This page only plays saved media; it does not call a model or run a simulator.",
    "episode_aria": "{task}: complete episode from initialization to official success",
    "episode_meta": "{fps} FPS · {frames} FRAMES · {seconds} s SIM",
    "episode_verified_caption": "One attempt, from initialization to official LIBERO success. The initial image and every control step are included, with no footage from other runs.",
    "episode_timing": "Playback at 1× simulation time, {fps} frames/s. Physics pauses during model inference, so those waits are not part of the video duration.",
    "video_error": "The video could not be played. Refresh or open the video link; the independent result remains available in the report.",
    "pause_frames": "Pause frames",
    "play_frames_aria": "Play selected decision frames",
    "pause_frames_aria": "Pause selected decision frames",
    "frame_before": "BEFORE ACTION",
    "frame_after": "AFTER ACTION",
    "frame_final": "FINAL FRAME",
    "frame_generic": "RECORDED FRAME",
    "step_label": "STEP {step}",
    "frame_external_aria": "Decision {step}, {title}: external camera",
    "frame_wrist_aria": "Decision {step}, {title}: wrist camera",
    "slider_value": "Selected frame {index} of {total}: {title}",
    "not_recorded": "Not recorded",
    "status_reached": "Target reached",
    "status_timed_out": "Controller timed out",
    "status_completed": "Action completed",
    "hero_task_alt": "Recorded LIBERO scene: {task}",
    "load_failed": "Not loaded",
    "recording_unavailable": "Recording unavailable",
    "recording_retry": "Refresh the page, or read the result report using the link below.",
    "recording_error_note": "The recording could not be loaded. This page never calls a model or starts a simulator.",
    "copied": "Copied",
    "copy_done": "Commands copied to the clipboard.",
    "copy_manually": "Copy manually",
    "copy_fallback": "Commands selected. Use your system copy shortcut.",
    "comparison_unavailable": "Model examples could not be loaded. Read the result report below.",
    "comparison_sim_time": "Simulation: {seconds} s",
    "comparison_wall_time": "Wall time: {seconds} s",
    "comparison_wall_time_unknown": "Wall time: not recorded"
  },
  "zh": {
    "skip": "跳至正文",
    "home": "ManiLoop 首页",
    "navigation": "主导航",
    "nav_framework": "框架",
    "nav_demo": "演示",
    "nav_models": "模型",
    "nav_start": "开始使用",
    "language": "语言",
    "hero_eyebrow": "开放机器人操作框架",
    "hero_see": "让模型看见、",
    "hero_act": "行动，",
    "hero_observe": "再观察。",
    "hero_description": "把模型判断接入物理反馈闭环。在 MuJoCo 中运行 GPT 和本地 VLA 策略，检查每次动作，并回看完整操作过程。",
    "watch_demo": "观看完整演示",
    "try_workspace": "体验工作台",
    "workspace_hint": "在浏览器中交互查看实际运行记录；实时仿真在本地启动。",
    "tech_stack": "技术栈",
    "observation_label": "观察画面 / 01",
    "hero_alt": "真实 LIBERO 画面：Panda 机械臂、碗与盘子",
    "external_camera": "外部相机",
    "real_image": "仿真器实际渲染画面",
    "browse_episode": "查看完整过程",
    "sensor_note": "策略读取图像与机器人本体状态。",
    "score_note": "独立评分与策略输入隔离。",
    "framework_eyebrow": "01 / 框架",
    "framework_title": "形成闭环，看清每一步。",
    "framework_intro": "用统一接口连接模型推理、仿真控制和执行记录。对照策略请求与机器人实际动作，定位发生了什么。",
    "loop_aria": "相机与机器人本体状态输入策略，经过校验的动作在仿真中执行，再将新的传感反馈用于下一次判断。独立评分与策略输入隔离。",
    "observe": "观察",
    "observe_inputs": "双相机 RGB\n机器人本体状态",
    "observe_tag": "传感器输入",
    "decide": "判断",
    "decide_inputs": "GPT 结构化动作\n或本地 VLA 策略",
    "decide_tag": "策略推理",
    "act": "执行",
    "act_inputs": "动作校验与目标跟踪\nMuJoCo / LIBERO",
    "act_tag": "本地控制",
    "check": "核对",
    "check_inputs": "新图像与实际位移\n执行状态与控制误差",
    "check_tag": "执行反馈",
    "loop_return": "下一次判断，回到新的传感证据",
    "independent_evaluation": "独立评分",
    "boundary_description": "物体真值、奖励和成功信号仅进入查看界面与结果记录。",
    "boundary_label": "独立评分 ≠ 策略输入",
    "feature_a_tag": "A / 策略接口",
    "feature_a_title": "同一框架，多种策略",
    "feature_a_description": "连接 GPT 视觉与结构化输出，或在隔离的推理环境中运行 SmolVLA、Diffusion Policy 和 ACT。各适配器保留模型对应的观测与动作协议。",
    "architecture_link": "查看架构",
    "feature_b_tag": "B / 动作控制",
    "feature_b_title": "从一个动作开始调试",
    "feature_b_description": "单步执行、动作后暂停或连续运行。在下一次判断前，查看请求的 TCP 目标、实际位移和控制误差。",
    "control_link": "使用控制界面",
    "feature_c_tag": "C / 过程记录",
    "feature_c_title": "回看完整 episode",
    "feature_c_description": "记录初始场景与每个原生控制步。回看双相机画面、动作说明和独立结果，或导出连续 MP4 录像。",
    "recording_link": "录制与导出",
    "demo_eyebrow": "02 / 实际演示",
    "demo_title": "一项任务，记录完整过程。",
    "demo_intro": "仿真器实际画面与独立任务结果。此页面只播放保存的媒体，不会调用模型或运行仿真。",
    "recorded_demo": "已录制演示",
    "loading_task": "正在载入任务记录",
    "loading_model": "模型与配置以 episode 记录为准",
    "complete_episode": "完整 EPISODE",
    "video_aria": "完整机器人操作 episode",
    "video_fallback": "浏览器不支持内嵌视频，请使用下方链接打开录像。",
    "episode_caption": "同一次连续尝试，从初始化到独立评分终止。",
    "episode_timing_default": "按仿真时间播放；等待模型推理时不推进物理。",
    "download_episode": "打开完整录像",
    "selected_title": "精选决策帧",
    "selected_description": "同一回合的观察节点与动作说明，用于辅助阅读；不是连续录像。",
    "external_label": "01 / 外部相机",
    "wrist_label": "02 / 腕部相机",
    "external_alt": "已录制的外部相机画面",
    "wrist_alt": "已录制的腕部相机画面",
    "previous_frame": "上一帧",
    "next_frame": "下一帧",
    "play_frames": "播放精选帧",
    "select_frame": "选择记录帧",
    "playback_note": "精选决策帧 · 原始顺序 · 非连续录像",
    "record_detail": "当前帧说明",
    "observation_stage": "观察画面",
    "loading_recording": "正在载入演示记录",
    "model_note_label": "模型动作说明 · 原英文译文",
    "action_feedback": "本次动作执行反馈",
    "position_error": "末端位置误差",
    "feedback_caveat": "模型说明与控制反馈不等于稳定抓持证据。任务是否成功由独立评分报告。",
    "metrics_aria": "本回合的独立结果",
    "model_decisions": "次模型决策",
    "control_steps": "个原生控制步",
    "simulation_time": "仿真时间",
    "pending": "待载入",
    "independent_result": "独立任务结果",
    "loading_conditions": "正在载入运行条件",
    "result_default": "任务是否完成由仿真器独立评分判定。",
    "single_episode_note": "单次演示不代表基准成功率。",
    "results_link": "查看实际结果",
    "models_eyebrow": "03 / 模型示例",
    "models_title": "各模型实际完成了什么。",
    "comparison_scope": "官方 LIBERO 任务的单次运行示例。每行记录一轮运行及其控制器和推理配置。",
    "comparison_aria": "模型运行结果，可横向滚动查看所有列",
    "comparison_caption": "各模型实际运行及独立任务结果",
    "col_model": "模型",
    "col_result": "官方结果",
    "col_policy": "策略调用数",
    "col_inference": "推理调用数",
    "col_steps": "控制步数",
    "col_setup": "配置与适用范围",
    "comparison_loading": "正在载入模型运行示例",
    "comparison_caveat": "这些是单次示例，不能估计成功率。预算、动作块和控制方式不同，不能据步数或耗时进行速度排名。",
    "comparison_results": "核对模型配置与结果",
    "start_eyebrow": "04 / 开始使用",
    "start_title": "在你的电脑上运行闭环。",
    "start_intro": "先启动仿真与手动控制，再接入模型。主程序、LIBERO 与 VLA 推理分别使用独立环境。",
    "install_main_title": "准备主环境",
    "copy_main": "复制主环境安装命令",
    "copy": "复制",
    "install_main_note": "在本机打开 127.0.0.1:8765 进入默认桌面演示。启动仿真和手动控制不需要模型密钥。安装 LIBERO 时另开终端，或先按 Ctrl+C 停止演示。",
    "install_full_link": "完整安装与 Windows 说明",
    "install_libero_title": "安装 LIBERO",
    "install_libero_subtitle": "独立的 Python 3.10 仿真环境",
    "copy_libero": "复制 LIBERO 安装命令",
    "install_libero_note": "在本机打开 127.0.0.1:8767。需要 Git、网络与可用图形环境；VLA 权重按需安装。",
    "libero_requirements": "环境要求与无显示器配置",
    "connect_eyebrow": "接入模型",
    "connect_title": "让策略开始操作。",
    "connect_description": "使用支持图像和结构化输出的 API 服务，或近期官方 Codex CLI 的 ChatGPT 登录通道。先运行诊断，再尝试一个小位移。模型请求使用相应服务或账户额度。",
    "gpt_guide": "GPT 仿真操作指南",
    "api_guide": "API 聊天与诊断",
    "vla_guide": "本地 LeRobot / VLA 策略",
    "invitation": "接入你的模型，\n检查它的动作。",
    "issues_link": "交流问题与贡献代码",
    "footer_tagline": "开放框架，可观察的动作。",
    "source": "源码",
    "license": "MIT 许可证",
    "documentation": "使用文档",
    "footer_note": "此页回放已录制过程，仿真在本地运行。",
    "page_title": "ManiLoop — 让模型看见、行动，再观察。",
    "meta_description": "连接 GPT、本地 VLA 与 MuJoCo / LIBERO，检查视觉反馈和结构化动作，回看完整 episode 与独立任务结果。",
    "og_description": "具备视觉反馈、本地控制与独立评分 episode 的开放机器人操作框架。",
    "missing_model": "模型未记录",
    "missing_date": "日期未记录",
    "context_current": "当前相机画面",
    "context_paired": "动作前后配对画面",
    "reasoning": "{level} 推理",
    "reasoning_low": "低",
    "reasoning_medium": "中",
    "reasoning_high": "高",
    "task_key": "任务",
    "init_key": "初态",
    "seed_key": "随机种子",
    "timing_controlled": "受控时序",
    "timing_realtime": "实时时序",
    "conditions_report": "完整配置见实际结果",
    "success": "成功",
    "failure": "未成功",
    "unverified": "待核验",
    "official_true": "LIBERO 官方评分 · true",
    "official_false": "独立任务结果 · false",
    "not_verified": "成功结果尚未独立核验",
    "verified_episode": "独立验收通过",
    "recorded_attempt": "已录制尝试",
    "result_verified": "已核对同一次运行的终态：LIBERO check_success 返回 true。独立评分未进入策略输入。",
    "result_failed": "本次尝试的独立成功结果为 false。{reason}。",
    "result_unverified": "独立评分仍待核验。模型声明或末端到位不等于任务成功。",
    "termination_success": "官方任务条件满足",
    "termination_decision_budget": "决策预算耗尽",
    "termination_simulation_budget": "仿真时间预算耗尽",
    "termination_wall_budget": "墙钟时间预算耗尽",
    "termination_model_done": "模型声明结束",
    "termination_stopped": "运行停止",
    "termination_other": "终止原因见结果说明",
    "demo_model_intro": "{model} 的实际仿真操作记录。此页只播放已保存媒体，不会调用模型或运行仿真。",
    "episode_aria": "{task}：从初始化到官方成功的完整 episode",
    "episode_meta": "{fps} 帧/秒 · {frames} 帧 · {seconds} 秒仿真时间",
    "episode_verified_caption": "同一次尝试，从初始化到 LIBERO 官方成功。保留初始画面与每个控制步，未拼接其他回合。",
    "episode_timing": "按仿真时间 1× 播放，{fps} 帧/秒。模型推理期间物理暂停，等待时间不计入录像时长。",
    "video_error": "视频暂时无法播放。请刷新或直接打开录像链接；独立结果仍可在结果文档中查阅。",
    "pause_frames": "暂停精选帧",
    "play_frames_aria": "播放精选决策帧",
    "pause_frames_aria": "暂停精选决策帧",
    "frame_before": "动作前",
    "frame_after": "动作后",
    "frame_final": "最终帧",
    "frame_generic": "记录帧",
    "step_label": "第 {step} 步",
    "frame_external_aria": "第 {step} 次决策，{title}：外部相机",
    "frame_wrist_aria": "第 {step} 次决策，{title}：腕部相机",
    "slider_value": "精选帧 {index}，共 {total} 帧：{title}",
    "not_recorded": "未记录",
    "status_reached": "目标到位",
    "status_timed_out": "控制超时",
    "status_completed": "动作完成",
    "hero_task_alt": "真实 LIBERO 画面：{task}",
    "load_failed": "未载入",
    "recording_unavailable": "记录暂时无法载入",
    "recording_retry": "请刷新页面，或通过下方链接阅读实际结果。",
    "recording_error_note": "记录加载失败；此页面不会调用模型或启动仿真。",
    "copied": "已复制",
    "copy_done": "命令已复制到剪贴板。",
    "copy_manually": "请手动复制",
    "copy_fallback": "命令已选中，请使用系统复制快捷键。",
    "comparison_unavailable": "模型示例暂时无法载入，请阅读下方结果文档。",
    "comparison_sim_time": "仿真时间：{seconds} 秒",
    "comparison_wall_time": "墙钟时间：{seconds} 秒",
    "comparison_wall_time_unknown": "墙钟时间：未记录"
  }
};
  const byId = (id) => document.getElementById(id);
  const slider = byId("frame-slider");
  const playButton = byId("play-toggle");
  const previous = byId("previous-frame");
  const next = byId("next-frame");
  const imagePath = /^assets\/(frames|episodes)\/[a-zA-Z0-9_/-]+\.(jpg|jpeg|png|webp)$/;
  const videoPath = /^assets\/episodes\/[a-zA-Z0-9_/-]+\.mp4$/;
  let language = initialLanguage();
  let recording = null;
  let comparison = null;
  let recordingFailed = false;
  let comparisonFailed = false;
  let videoFailed = false;
  let frames = [];
  let index = 0;
  let timer = null;

  function initialLanguage() {
    const requested = new URLSearchParams(window.location.search).get("lang");
    if (requested === "en" || requested === "zh") return requested;
    try {
      const saved = localStorage.getItem("maniloop-language");
      if (saved === "en" || saved === "zh") return saved;
    } catch { /* Storage may be unavailable in a private browsing session. */ }
    return (navigator.language || "en").toLowerCase().startsWith("zh") ? "zh" : "en";
  }

  function t(key, values = {}) {
    const message = messages[language][key] || messages.en[key] || key;
    return message.replace(/\{(\w+)\}/g, (match, name) => String(values[name] ?? match));
  }

  function localized(value, chineseTranslation) {
    if (language === "zh" && typeof chineseTranslation === "string") return chineseTranslation;
    if (typeof value === "string") return value;
    if (value && typeof value === "object") return value[language] || value.en || value.zh || "";
    return "";
  }

  function localizedText(value) {
    return typeof value === "string" || (value && typeof value.en === "string" && typeof value.zh === "string");
  }

  function setLanguage(nextLanguage, persist = false) {
    language = nextLanguage === "zh" ? "zh" : "en";
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
    document.title = t("page_title");
    for (const [selector, key] of [["meta[name='description']", "meta_description"], ["meta[property='og:title']", "page_title"], ["meta[property='og:description']", "og_description"]]) {
      document.querySelector(selector).setAttribute("content", t(key));
    }
    for (const element of document.querySelectorAll("[data-i18n]")) element.textContent = t(element.dataset.i18n);
    for (const [dataName, attribute] of [["i18nAria", "aria-label"], ["i18nTitle", "title"], ["i18nAlt", "alt"]]) {
      const selector = "[data-" + dataName.replace(/[A-Z]/g, (letter) => "-" + letter.toLowerCase()) + "]";
      for (const element of document.querySelectorAll(selector)) element.setAttribute(attribute, t(element.dataset[dataName]));
    }
    for (const button of document.querySelectorAll("[data-language]")) button.setAttribute("aria-pressed", String(button.dataset.language === language));
    for (const link of document.querySelectorAll("[data-doc-link='readme']")) {
      link.href = "https://github.com/Daniel-rmc/ManiLoop/blob/main/" + (language === "zh" ? "README.zh-CN.md" : "README.md");
    }
    for (const link of document.querySelectorAll("[data-playground-link]")) link.href = "playground/?lang=" + language;
    updatePlaybackLabels();
    if (recording) { renderRecordingMetadata(recording); renderFrame(index); }
    if (recordingFailed) renderRecordingError();
    if (comparison) renderComparison(comparison);
    if (comparisonFailed) renderComparisonError();
    if (persist) {
      try { localStorage.setItem("maniloop-language", language); } catch { /* Switching still works without storage. */ }
      const url = new URL(window.location.href);
      url.searchParams.set("lang", language);
      window.history.replaceState(null, "", url);
    }
  }

  // Only the independent evaluator can verify task success, never a model's `done`.
  function hasVerifiedSuccess(data) {
    return data.summary?.success === true && data.evaluation?.success === true &&
      data.evaluation?.verified === true && data.evaluation?.source === "LIBERO check_success";
  }

  function nonnegativeNumber(value) {
    return typeof value === "number" && Number.isFinite(value) && value >= 0;
  }

  function metric(value, precision = 0) {
    return nonnegativeNumber(value) ? value.toLocaleString(language === "zh" ? "zh-CN" : "en-US", { maximumFractionDigits: precision }) : "—";
  }

  function safeReportUrl(value) {
    if (typeof value !== "string") return null;
    try {
      const url = new URL(value);
      return url.protocol === "https:" && !url.username && !url.password ? url.href : null;
    } catch { return null; }
  }

  function terminationText(reason) {
    if (reason === "success" || reason === "task_success") return t("termination_success");
    return t(messages.en["termination_" + reason] ? "termination_" + reason : "termination_other");
  }

  function renderRecordingMetadata(data) {
    const summary = data.summary || {};
    const context = data.context || {};
    const verified = hasVerifiedSuccess(data);
    const failed = summary.success === false;
    const model = typeof data.model === "string" ? data.model : t("missing_model");
    byId("record-task").textContent = localized(data.task);
    byId("record-date").textContent = /^\d{4}-\d{2}-\d{2}$/.test(data.date || "") ? data.date : t("missing_date");
    const modelDetails = [model];
    if (data.context_mode) modelDetails.push(t("context_" + data.context_mode));
    if (context.reasoning_effort) modelDetails.push(t("reasoning", { level: t("reasoning_" + context.reasoning_effort) }));
    byId("record-model").textContent = modelDetails.join(" · ");
    const conditions = [];
    if (typeof context.suite === "string") conditions.push(context.suite);
    for (const [key, label] of [["task_id", "task_key"], ["init_state_id", "init_key"], ["seed", "seed_key"]]) {
      if (Number.isInteger(context[key]) && context[key] >= 0) conditions.push(t(label) + " " + context[key]);
    }
    if (context.timing) conditions.push(t("timing_" + context.timing));
    byId("record-conditions").textContent = conditions.length ? conditions.join(" / ") : t("conditions_report");
    byId("metric-decisions").textContent = metric(summary.decisions);
    byId("metric-steps").textContent = metric(summary.control_steps);
    byId("metric-seconds").textContent = metric(summary.simulation_seconds, 2);
    byId("metric-outcome").textContent = t(verified ? "success" : failed ? "failure" : "unverified");
    byId("metric-result").dataset.result = verified ? "success" : failed ? "failure" : "unknown";
    byId("metric-evaluator").textContent = t(verified ? "official_true" : failed ? "official_false" : "not_verified");
    byId("record-tag").textContent = t(verified ? "verified_episode" : "recorded_attempt");
    byId("record-result-note").textContent = verified ? t("result_verified") : failed
      ? t("result_failed", { reason: terminationText(summary.termination_reason) }) : t("result_unverified");
    if (verified && data.outcome_note) byId("record-result-note").textContent += " " + localized(data.outcome_note);
    const reportUrl = safeReportUrl(data.report_url);
    if (reportUrl) byId("record-report").href = reportUrl;
    byId("demo-intro").textContent = t("demo_model_intro", { model });
    byId("hero-image").alt = t("hero_task_alt", { task: localized(data.task) });
    renderEpisode(data, verified);
  }

  function renderEpisode(data, verified) {
    const episode = data.episode;
    const summary = data.summary || {};
    const complete = episode && episode.complete === true &&
      episode.starts_at_initialization === true && episode.ends_at_terminal_state === true &&
      Number.isInteger(episode.frame_count) && Number.isInteger(summary.control_steps) &&
      episode.frame_count === summary.control_steps + 1 && summary.control_steps > 0 &&
      nonnegativeNumber(episode.fps) && episode.fps > 0 && nonnegativeNumber(summary.simulation_seconds) &&
      Math.abs(summary.control_steps / episode.fps - summary.simulation_seconds) < 0.001 &&
      typeof episode.video === "string" && videoPath.test(episode.video);
    byId("episode-player").hidden = !verified || !complete;
    if (!verified || !complete) return;
    const video = byId("episode-video");
    // A language switch updates labels without restarting or seeking the recording.
    if (video.getAttribute("src") !== episode.video) video.src = episode.video;
    if (typeof episode.poster === "string" && imagePath.test(episode.poster)) video.poster = episode.poster;
    video.setAttribute("aria-label", t("episode_aria", { task: localized(data.task) }));
    byId("episode-download").href = episode.video;
    byId("episode-meta").textContent = t("episode_meta", { fps: metric(episode.fps, 2), frames: metric(episode.frame_count), seconds: metric(summary.simulation_seconds, 2) });
    byId("episode-caption").textContent = t("episode_verified_caption");
    byId("episode-timing-note").textContent = videoFailed ? t("video_error") : t("episode_timing", { fps: metric(episode.fps, 2) });
  }

  function updatePlaybackLabels() {
    const playing = timer !== null;
    playButton.setAttribute("aria-pressed", String(playing));
    playButton.setAttribute("aria-label", t(playing ? "pause_frames_aria" : "play_frames_aria"));
    byId("play-icon").textContent = playing ? "Ⅱ" : "▶";
    byId("play-label").textContent = t(playing ? "pause_frames" : "play_frames");
  }

  function setPlaying(playing) {
    if (timer !== null) { window.clearInterval(timer); timer = null; }
    if (playing) {
      if (index === frames.length - 1) renderFrame(0);
      timer = window.setInterval(() => {
        if (index < frames.length - 1) renderFrame(index + 1);
        if (index === frames.length - 1) setPlaying(false);
      }, 3500);
    }
    updatePlaybackLabels();
  }

  function renderFrame(requestedIndex) {
    if (!frames.length) return;
    index = Math.max(0, Math.min(frames.length - 1, requestedIndex));
    const frame = frames[index];
    const title = localized(frame.title);
    byId("external-frame").src = frame.external;
    byId("wrist-frame").src = frame.wrist;
    byId("external-frame").alt = t("frame_external_aria", { step: frame.step, title });
    byId("wrist-frame").alt = t("frame_wrist_aria", { step: frame.step, title });
    byId("frame-stage").textContent = t(messages.en["frame_" + frame.stage] ? "frame_" + frame.stage : "frame_generic");
    byId("frame-step").textContent = t("step_label", { step: String(frame.step).padStart(2, "0") });
    byId("frame-title").textContent = title;
    byId("frame-explanation").textContent = localized(frame.explanation, frame.explanation_zh);
    const status = frame.feedback?.status;
    byId("frame-status").textContent = messages.en["status_" + status] ? t("status_" + status) : status || t("not_recorded");
    const error = frame.feedback?.position_error_m;
    byId("frame-error").textContent = nonnegativeNumber(error) ? (error * 1000).toFixed(2) + " mm" : t("not_recorded");
    slider.value = String(index);
    slider.setAttribute("aria-valuetext", t("slider_value", { index: index + 1, total: frames.length, title }));
    byId("frame-counter").textContent = String(index + 1).padStart(2, "0") + " / " + String(frames.length).padStart(2, "0");
    previous.disabled = index === 0;
    next.disabled = index === frames.length - 1;
  }

  function selectFrame(requestedIndex) { setPlaying(false); renderFrame(requestedIndex); }

  function renderRecordingError() {
    byId("metric-outcome").textContent = t("load_failed");
    byId("frame-title").textContent = t("recording_unavailable");
    byId("frame-explanation").textContent = t("recording_retry");
    byId("playback-note").textContent = t("recording_error_note");
  }

  async function loadRecording() {
    try {
      const response = await fetch("assets/demo-data.json?v=bilingual-workspace-1", { credentials: "omit" });
      if (!response.ok) throw new Error("Recording unavailable");
      const data = await response.json();
      if (!data || !Array.isArray(data.frames) || data.frames.length > 100) throw new Error("Invalid recording");
      const valid = data.frames.every((frame) => frame && Number.isInteger(frame.step) && frame.step >= 0 &&
        localizedText(frame.title) && localizedText(frame.explanation) &&
        typeof frame.external === "string" && imagePath.test(frame.external) &&
        typeof frame.wrist === "string" && imagePath.test(frame.wrist));
      if (!valid) throw new Error("Invalid frame");
      recording = data;
      frames = data.frames;
      renderRecordingMetadata(data);
      byId("selected-heading").hidden = !frames.length;
      byId("record-layout").hidden = !frames.length;
      if (!frames.length) return;
      slider.max = String(frames.length - 1);
      byId("hero-image").src = frames[0].external;
      renderFrame(0);
      byId("playback-controls").hidden = false;
      for (const frame of frames.slice(1)) {
        const external = new Image(); const wrist = new Image();
        external.src = frame.external; wrist.src = frame.wrist;
      }
    } catch { recordingFailed = true; renderRecordingError(); }
  }

  function cell(row, text, className) {
    const element = document.createElement("td");
    if (className) element.className = className;
    element.textContent = text;
    row.appendChild(element);
    return element;
  }

  function renderComparison(data) {
    byId("comparison-scope").textContent = localized(data.scope);
    byId("comparison-caveat").textContent = localized(data.caveat);
    const body = byId("comparison-rows"); body.replaceChildren();
    for (const item of data.rows) {
      const row = document.createElement("tr");
      cell(row, item.model, "comparison-model");
      const result = cell(row, localized(item.status), "comparison-result");
      result.dataset.result = item.success === true ? "success" : item.success === false ? "failure" : "unknown";
      cell(row, metric(item.decisions), "comparison-number");
      cell(row, metric(item.inference_calls), "comparison-number");
      cell(row, metric(item.control_steps), "comparison-number");
      const details = cell(row, "", "comparison-details");
      for (const [text, className] of [[localized(item.conditions), "comparison-conditions"], [localized(item.notes), "comparison-notes"]]) {
        const paragraph = document.createElement("p"); paragraph.className = className; paragraph.textContent = text; details.appendChild(paragraph);
      }
      const timings = document.createElement("p"); timings.className = "comparison-timings";
      timings.textContent = t("comparison_sim_time", { seconds: metric(item.simulation_seconds, 2) }) + " · " + (nonnegativeNumber(item.wall_seconds) ? t("comparison_wall_time", { seconds: metric(item.wall_seconds, 2) }) : t("comparison_wall_time_unknown"));
      details.appendChild(timings); body.appendChild(row);
    }
  }

  function renderComparisonError() {
    const body = byId("comparison-rows"); body.replaceChildren();
    const row = document.createElement("tr"); const text = cell(row, t("comparison_unavailable")); text.colSpan = 6; body.appendChild(row);
  }

  async function loadComparison() {
    try {
      const response = await fetch("assets/model-comparison.json?v=bilingual-workspace-1", { credentials: "omit" });
      if (!response.ok) throw new Error("Comparison unavailable");
      const data = await response.json();
      if (!Array.isArray(data.rows) || !data.rows.length || data.rows.length > 30 ||
          !localizedText(data.scope) || !localizedText(data.caveat) || !data.rows.every((row) =>
            row && typeof row.model === "string" && localizedText(row.status) && localizedText(row.conditions) && localizedText(row.notes))) {
        throw new Error("Invalid comparison");
      }
      comparison = data; renderComparison(data);
    } catch { comparisonFailed = true; renderComparisonError(); }
  }

  previous.addEventListener("click", () => selectFrame(index - 1));
  next.addEventListener("click", () => selectFrame(index + 1));
  playButton.addEventListener("click", () => setPlaying(timer === null && frames.length > 1));
  slider.addEventListener("input", () => selectFrame(Number(slider.value)));
  byId("playback-controls").addEventListener("keydown", (event) => {
    if (event.target === slider || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault(); selectFrame(index + (event.key === "ArrowRight" ? 1 : -1));
    }
  });
  byId("episode-video").addEventListener("error", () => { videoFailed = true; byId("episode-timing-note").textContent = t("video_error"); });
  document.addEventListener("visibilitychange", () => { if (document.hidden) setPlaying(false); });
  for (const button of document.querySelectorAll("[data-language]")) button.addEventListener("click", () => setLanguage(button.dataset.language, true));
  for (const button of document.querySelectorAll("[data-copy]")) {
    button.addEventListener("click", async () => {
      const code = byId(button.dataset.copy);
      try {
        if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
        await navigator.clipboard.writeText(code.textContent);
        button.textContent = t("copied"); byId("copy-status").textContent = t("copy_done");
        window.setTimeout(() => { button.textContent = t("copy"); }, 2200);
      } catch {
        const selection = window.getSelection(); const range = document.createRange();
        range.selectNodeContents(code); selection.removeAllRanges(); selection.addRange(range);
        button.textContent = t("copy_manually"); byId("copy-status").textContent = t("copy_fallback");
      }
    });
  }
  setLanguage(language, ["en", "zh"].includes(new URLSearchParams(window.location.search).get("lang")));
  loadRecording();
  loadComparison();
})();
