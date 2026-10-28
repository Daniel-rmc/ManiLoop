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
    "hero_description": "Connect model decisions to a physical feedback loop. Explore MuJoCo, LIBERO, robosuite and RoboCasa through one local workspace, with explicit actions and inspectable feedback.",
    "try_workspace": "Explore the recorded workspace",
    "watch_demo": "Watch the demo",
    "workspace_hint": "Inspect a saved LIBERO run in your browser. The live, modular workspace runs on your machine.",
    "tech_stack": "Technology stack",
    "observation_label": "OBSERVATION / 01",
    "hero_alt": "A recorded LIBERO scene with the Panda arm, bowls and a plate",
    "external_camera": "EXTERNAL CAMERA",
    "real_image": "An actual simulator frame",
    "browse_episode": "Explore the episode",
    "sensor_note": "The policy receives only declared sensor observations.",
    "score_note": "The evaluator stays separate.",
    "framework_eyebrow": "01 / THE FRAMEWORK",
    "framework_title": "Close the loop. Inspect every step.",
    "framework_intro": "Connect environment adapters, model policies and local control. Inspect the requested action, the measured motion and the independently recorded result.",
    "loop_aria": "Declared sensor observations feed the selected policy. Validated actions execute in a MuJoCo backend, then fresh sensor feedback informs the next decision. Evaluation is separate.",
    "observe": "Observe",
    "observe_inputs": "Camera RGB where supported\nRobot proprioception",
    "observe_tag": "SENSOR INPUT",
    "decide": "Decide",
    "decide_inputs": "GPT / VLA policies\nJev text primitives",
    "decide_tag": "POLICY",
    "act": "Act",
    "act_inputs": "Validate and track targets\nMuJoCo backends",
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
    "feature_a_description": "Connect GPT vision and structured actions, LIBERO-specific local VLA presets, or Jev text primitives. Each policy keeps its declared inputs and action protocol.",
    "architecture_link": "Explore the architecture",
    "feature_b_tag": "B / CONTROL",
    "feature_b_title": "Control a 6D TCP target",
    "feature_b_description": "Jog XYZ, rotate Rx/Ry/Rz, or combine translation and rotation in fixed or tool axes. Inspect position and orientation error. Manual control needs no model key.",
    "control_link": "Understand manual pose control",
    "feature_c_tag": "C / RECORDING",
    "feature_c_title": "Keep actions and evidence together",
    "feature_c_description": "Inspect decision-level observations, action notes and feedback across backends. LIBERO additionally supports complete control-step recordings and continuous MP4 export.",
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
    "start_intro": "Start with the local workspace and manual control, then choose an optional backend and policy. Simulation runtimes and VLA inference stay isolated.",
    "install_main_title": "Set up the main environment",
    "copy_main": "Copy main environment commands",
    "copy": "Copy",
    "install_main_note": "Open 127.0.0.1:8765 for the built-in tabletop workspace. Manual controls need no model key. Use another terminal, or stop with Ctrl+C, before installing an optional backend.",
    "install_full_link": "Full setup and Windows instructions",
    "install_libero_title": "Add LIBERO",
    "install_libero_subtitle": "A separate Python 3.10 simulation environment",
    "copy_libero": "Copy LIBERO setup commands",
    "install_libero_note": "Open 127.0.0.1:8767 on your machine. Git, network access and a supported graphics setup are required. VLA weights are optional.",
    "libero_requirements": "Requirements and headless setup",
    "connect_eyebrow": "CONNECT A MODEL",
    "connect_title": "Give the policy a turn.",
    "connect_description": "Choose GPT through a compatible image and structured-output API or official Codex login, a local LIBERO VLA preset, or Jev text primitives with a separate TypeSafe API key. Diagnose the connection before a small action.",
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
    "meta_description": "Explore four MuJoCo simulation backends with GPT, local VLA policies, Jev text primitives and a modular workspace for 6D control, recorded feedback and independent evaluation.",
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
    "comparison_wall_time_unknown": "Wall time: not recorded",
    "environments_title": "Four environments. Explicit boundaries.",
    "environments_intro": "Choose the scene in the local workspace. Optional backends keep separate runtimes, controllers and independent task evaluators.",
    "env_builtin": "Built-in MuJoCo",
    "env_builtin_description": "Panda and ARX5 tabletop scenes for manual control, pick-and-place and pushing experiments.",
    "env_libero_description": "Official task suites and initializations. The recorded GPT examples and local VLA presets on this page use LIBERO.",
    "env_robosuite_description": "Five Panda tasks: Lift, Stack, PickPlaceCan, Door and NutAssemblySquare, with dual-camera observation and local control.",
    "env_robocasa_description": "Four kitchen tasks: open or close a drawer, open a cabinet, and position a mug. Arm and gripper control; no navigation planner.",
    "env_documentation": "Setup and scope",
    "environments_scope": "Backend integration is not a model success result. The existing LeRobot presets remain LIBERO-specific; robosuite and RoboCasa do not yet provide complete control-step video export.",
    "workspace_eyebrow": "THE LOCAL APPLICATION",
    "workspace_title": "A workspace for the whole loop.",
    "workspace_description": "Manual control, model runs and scene settings have dedicated panels beside the cameras. These actual local-application screenshots use the built-in Panda tabletop scene; the website does not run their controls.",
    "workspace_manual_label": "01 / MANUAL CONTROL",
    "workspace_manual_alt": "The actual ManiLoop local workspace with camera observations and six-dimensional manual pose controls",
    "workspace_manual_caption": "Fixed or tool axes, translation, rotation and gripper control. Position and orientation feedback stay visible.",
    "workspace_model_label": "02 / MODEL RUNS",
    "workspace_model_alt": "The actual ManiLoop local workspace showing its separate model connection and task-running panel",
    "workspace_model_caption": "Connect a policy, inspect its settings, then step or run. Opening a panel does not submit a model request.",
    "workspace_full_image": "Open full-size screenshot",
    "workspace_scene_title": "Apply a scene when you are ready",
    "workspace_scene_description": "Choose a backend and task, then apply to rebuild the environment. Editing a task instruction does not change the official evaluator. The stop control remains available across panels.",
    "workspace_guide": "Local workspace guide",
    "optional_backends_title": "Add another environment",
    "optional_backends_description": "Use the dedicated installers for robosuite and RoboCasa. Each creates its own Python 3.11 runtime; RoboCasa additionally needs kitchen assets.",
    "robosuite_setup": "Set up robosuite",
    "robocasa_setup": "Set up RoboCasa",
    "jev_guide": "Jev text primitives",
    "jev_scope": "Jev receives explicit instructions and public proprioception, not images. It selects a bounded primitive; local code handles units, coordinates and motion. It does not visually locate objects or provide autonomous grasping.",
    "model_requests_note": "Model requests use the selected provider or account quota. Switching workspace panels does not trigger inference.",
    "env_builtin_tag": "01 / TABLETOP",
    "env_libero_tag": "02 / BENCHMARK",
    "env_robosuite_tag": "03 / MANIPULATION",
    "env_robocasa_tag": "04 / KITCHEN"
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
    "hero_description": "把模型判断放进物理闭环。在同一个本地工作台中连接 MuJoCo、LIBERO、robosuite 与 RoboCasa，检查明确的动作和实际执行反馈。",
    "watch_demo": "观看完整演示",
    "try_workspace": "探索回放工作台",
    "workspace_hint": "在浏览器中逐步检查已保存的 LIBERO 回合。实时的模块化工作台在你的电脑上运行。",
    "tech_stack": "技术栈",
    "observation_label": "观察画面 / 01",
    "hero_alt": "真实 LIBERO 画面：Panda 机械臂、碗与盘子",
    "external_camera": "外部相机",
    "real_image": "仿真器实际渲染画面",
    "browse_episode": "查看完整过程",
    "sensor_note": "策略只接收显式提供的传感观测。",
    "score_note": "独立评分与策略输入隔离。",
    "framework_eyebrow": "01 / 框架",
    "framework_title": "形成闭环，看清每一步。",
    "framework_intro": "连接环境适配器、模型策略与本地控制。核对请求动作、实测运动和独立记录的任务结果。",
    "loop_aria": "显式传感观测进入所选策略，校验后的动作在 MuJoCo 后端执行，新的传感反馈再用于下一次决策。任务评分独立保留。",
    "observe": "观察",
    "observe_inputs": "按策略支持提供相机 RGB\n机器人本体状态",
    "observe_tag": "传感器输入",
    "decide": "判断",
    "decide_inputs": "GPT / VLA 策略\nJev 文本原语",
    "decide_tag": "策略推理",
    "act": "执行",
    "act_inputs": "动作校验与目标跟踪\nMuJoCo 仿真后端",
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
    "feature_a_description": "连接 GPT 视觉与结构化动作、LIBERO 专用本地 VLA 预设，或 Jev 文本原语。每种策略保留其声明的输入与动作协议。",
    "architecture_link": "查看架构",
    "feature_b_tag": "B / 动作控制",
    "feature_b_title": "手动控制六维末端目标",
    "feature_b_description": "在固定轴或末端自身轴下点动 XYZ、旋转 Rx/Ry/Rz，也可组合六维增量。查看位置与姿态误差；手动控制无需模型密钥。",
    "control_link": "阅读手动位姿控制说明",
    "feature_c_tag": "C / 过程记录",
    "feature_c_title": "把动作与证据一起保留",
    "feature_c_description": "跨后端检查决策级观测、动作说明和反馈。LIBERO 还支持记录每个原生控制步，并导出连续 MP4 录像。",
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
    "start_intro": "先启动本地工作台和手动控制，再选择可选后端与策略。各仿真运行环境与 VLA 推理保持隔离。",
    "install_main_title": "准备主环境",
    "copy_main": "复制主环境安装命令",
    "copy": "复制",
    "install_main_note": "在本机打开 127.0.0.1:8765，进入内置桌面工作台。手动控制无需模型密钥。安装可选后端前，另开终端或先按 Ctrl+C 停止服务。",
    "install_full_link": "完整安装与 Windows 说明",
    "install_libero_title": "安装 LIBERO",
    "install_libero_subtitle": "独立的 Python 3.10 仿真环境",
    "copy_libero": "复制 LIBERO 安装命令",
    "install_libero_note": "在本机打开 127.0.0.1:8767。需要 Git、网络与可用图形环境；VLA 权重按需安装。",
    "libero_requirements": "环境要求与无显示器配置",
    "connect_eyebrow": "接入模型",
    "connect_title": "让策略开始操作。",
    "connect_description": "选择兼容图像和结构化输出的 GPT API 或官方 Codex 登录、本地 LIBERO VLA 预设，或使用独立 TypeSafe API Key 的 Jev 文本原语。先检查连接，再测试小动作。",
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
    "meta_description": "在四类 MuJoCo 仿真后端中连接 GPT、本地 VLA 与 Jev 文本原语，使用模块化工作台进行六维控制、反馈回看与独立评分。",
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
    "comparison_wall_time_unknown": "墙钟时间：未记录",
    "environments_title": "四类环境，明确各自的范围。",
    "environments_intro": "在本地工作台选择场景。可选后端分别维护运行环境、控制器与独立任务评分。",
    "env_builtin": "内置 MuJoCo",
    "env_builtin_description": "Panda 与 ARX5 桌面场景，用于手动控制、抓放和推动实验。",
    "env_libero_description": "沿用官方任务集与初始化。本页的 GPT 操作录像和本地 VLA 预设使用 LIBERO。",
    "env_robosuite_description": "接入 Panda 的 Lift、Stack、PickPlaceCan、Door 与 NutAssemblySquare 五项任务，提供双相机和本地控制。",
    "env_robocasa_description": "四项厨房任务：开抽屉、关抽屉、开柜门和摆放杯子。控制机械臂与夹爪，不包含导航规划。",
    "env_documentation": "安装与范围",
    "environments_scope": "后端接入不代表模型已完成任务。既有 LeRobot 预设仍限 LIBERO；robosuite 与 RoboCasa 暂不提供完整逐控制步视频导出。",
    "workspace_eyebrow": "本地应用",
    "workspace_title": "为完整闭环组织的工作台。",
    "workspace_description": "手动控制、模型运行与场景设置各有独立分区，与相机画面并排。下方为内置 Panda 桌面场景的真实本地工作台截图，网站不会执行图中的控件。",
    "workspace_manual_label": "01 / 手动控制",
    "workspace_manual_alt": "ManiLoop 当前本地工作台：相机观测与六维手动位姿控制面板",
    "workspace_manual_caption": "固定轴或末端自身轴、平移、旋转和夹爪控制，配合可直接查看的位置与姿态反馈。",
    "workspace_model_label": "02 / 模型运行",
    "workspace_model_alt": "ManiLoop 当前本地工作台：独立的模型连接与任务运行面板",
    "workspace_model_caption": "连接策略、核对参数，再单步或连续执行。切换到模型分区不会发起模型请求。",
    "workspace_full_image": "查看原始尺寸截图",
    "workspace_scene_title": "确认后再应用场景",
    "workspace_scene_description": "选择后端与任务，点击应用才会重建环境。修改任务指令不改变官方评分规则；停止按钮在各分区始终可用。",
    "workspace_guide": "本地工作台指南",
    "optional_backends_title": "接入其他环境",
    "optional_backends_description": "robosuite 和 RoboCasa 使用各自的安装器，分别创建独立 Python 3.11 运行环境；RoboCasa 还需下载厨房资产。",
    "robosuite_setup": "安装 robosuite",
    "robocasa_setup": "安装 RoboCasa",
    "jev_guide": "Jev 文本原语控制",
    "jev_scope": "Jev 接收明确指令与公开本体状态，不接收图像。它选择有界动作原语，由本地代码处理单位、坐标与运动；不进行视觉定位或自主抓取。",
    "model_requests_note": "模型请求使用所选服务或账户额度。切换工作台分区不会触发推理。",
    "env_builtin_tag": "01 / 桌面",
    "env_libero_tag": "02 / 基准任务",
    "env_robosuite_tag": "03 / 操作任务",
    "env_robocasa_tag": "04 / 厨房"
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
    document.dispatchEvent(new CustomEvent("maniloop:language", { detail: { language } }));
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
