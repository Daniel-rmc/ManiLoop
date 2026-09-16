(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const messages = {
    en: {
      languageLabel: 'Language', projectAria: 'ManiLoop project', footerMark: 'MANILOOP · RECORDED WORKSPACE', flow: 'LANGUAGE → ACTION → OBSERVATION', videoStats: '707 FRAMES · 20 FPS', suite: 'Task suite', pageTitle: 'ManiLoop · Recorded interactive workspace', brand: 'Robot workspace', back: '← Project', recorded: 'Recorded interactive workspace',
      title: 'Look through the robot’s decisions.', intro: 'Explore the real workspace with a complete, recorded GPT-6 episode.', runLocal: 'Run your own task ↗',
      noticeTitle: 'You are browsing a recording.', notice: 'Controls navigate saved observations; they do not call a model or run new physics. All 46 decisions come from one uninterrupted episode.',
      cameraAria: 'Recorded dual-camera observations', cameraTitle: 'Simulation view', savedFrames: 'Saved camera frames', external: 'EXTERNAL CAMERA', wrist: 'WRIST CAMERA', world: 'WORLD FRAME',
      expandCameras: 'Side-by-side cameras', insetCameras: 'Inset wrist camera', phaseAria: 'Recorded view', before: 'Before action', after: 'After action', terminal: 'Final frame',
      sensorsAria: 'Robot sensors at the selected frame', tcp: 'TCP position · m', gripper: 'Gripper opening', gripperRange: '0 closed · 100 open', decision: 'Decision', simTime: 'Simulation time', recordedSensors: 'Recorded sensors',
      explanation: 'Model’s action explanation', explanationNote: 'The model’s stated interpretation, not an independent measurement.', originalEnglish: 'Original model text · English',
      playback: 'Episode playback', paused: 'Paused', playing: 'Replaying saved views', finished: 'End of recorded episode', loading: 'Loading saved frame…', play: '▶ Continuous replay', pause: 'Pause', previous: '← Previous decision', step: 'Single step →', jump: 'Jump to a decision', selectDecision: 'Decision', viewDuration: 'View duration', reset: '↺ Reset replay', finalJump: 'Final frame ↗',
      playbackNote: 'Single step alternates before/after views. Decision replay skips between recorded keyframes; the complete video below shows every control step.',
      configuration: 'Recorded configuration', readOnly: 'Read only', configNote: 'These are this episode’s settings. To change the task, model, or API connection, run ManiLoop locally.',
      finalResult: 'Episode’s final result', success: 'SUCCESS', finalResultNote: 'Official LIBERO success at control step 706. This is the episode’s final evaluation, not the score at the frame currently selected.', scope: 'Success triggered during the final lowering action. The environment stopped with the gripper still closed; release and retreat were not tested.', separation: 'Human review only · Evaluation was excluded from policy input.', results: 'Read the result and conditions ↗',
      diagnosticsAria: 'Recorded actions and feedback', fieldsAria: 'Recorded fields', observationTab: 'Robot sensors', actionTab: 'Action fields', originalFields: 'Original field names', feedback: 'Execution feedback', rawFeedback: 'Original recorded feedback', timelineTitle: 'All 46 decisions', timelineHint: 'Select any decision',
      videoTitle: 'The complete episode · every control step', videoNote: '35.35 seconds of simulation playback, including all grasp retries in this single attempt. Model waiting time is omitted. No cuts, interpolation, or newly generated actions.',
      localTitle: 'Use the live workspace on your computer', localNote: 'The local application lets you select tasks, configure model access, and execute new robot actions. Install the main and LIBERO environments, then run:', setup: 'Installation & model setup ↗', copy: 'Copy command', copied: 'Command copied.', copyFailed: 'Select and copy the command above.',
      footer: 'The layout and visual styles are reused from ManiLoop’s actual local workspace. This public view only reads a reviewed recording.',
      model: 'Model', environment: 'Environment', taskId: 'Task / init / seed', cameras: 'Cameras', context: 'Visual context', reasoning: 'Reasoning', controller: 'Controller', timing: 'Timing', decisionLimit: 'Decision limit', noCap: 'No count limit', wallLimit: 'Wall-clock limit', paired: 'Paired before / after', controlled: 'Controlled · physics pauses during inference',
      move: 'Move TCP', open: 'Open gripper', close: 'Close gripper', deltaPosition: 'Requested ΔXYZ · mm', deltaRotation: 'Requested rotation · rad', gripperCommand: 'Gripper command', retainedGrip: 'Arm move preserves gripper command', opened: 'Open', closed: 'Close',
      feedbackPending: 'This is the observation before the action. Select “After action” to inspect its recorded execution feedback.', feedbackTerminal: 'The environment terminated on official success during this action. No complete controller execution-end feedback was emitted; the terminal sensor frame is preserved.', noFeedback: 'No complete execution-end feedback recorded.',
      reached: 'Target reached', timed_out: 'Target timed out', completed: 'Gripper settled', accepted: 'Accepted for execution',
      reachedNote: 'The local controller reached the requested TCP target. This does not by itself establish a successful grasp.', timedOutNote: 'The target-tracking window ended before all completion conditions were met. Inspect the actual displacement and residual error.', completedNote: 'The gripper settled. This controller result does not verify that the object was grasped.',
      actualDelta: 'Actual ΔXYZ · mm', positionError: 'Position error · mm', rotationError: 'Rotation error · rad', controlSteps: 'Controller steps',
      eventDecision: 'Decision', eventAccepted: 'Accepted', eventExecution: 'Execution', eventTerminal: 'Terminal', acceptedEvent: 'A fixed TCP target was accepted for local tracking.', terminalEvent: 'Official success triggered environment termination. No subsequent model request was made.', beforeEventNote: 'Recorded decision associated with this before-action observation.',
      loadError: 'The recording could not be loaded. Reload this page or open it from the project website.', imageAlt: 'Recorded camera', beforeFeedback: 'Not executed in this view', keyboardHint: 'Use left/right arrows outside form controls to step through saved views.'
    },
    zh: {
      languageLabel: '语言', projectAria: 'ManiLoop 项目主页', footerMark: 'MANILOOP · 录制工作台', flow: '语言 → 动作 → 观测', videoStats: '707 组画面 · 20 FPS', suite: '任务集', pageTitle: 'ManiLoop · 录制交互工作台', brand: '机器人实验台', back: '← 项目主页', recorded: '录制交互工作台',
      title: '逐步查看机器人的决策。', intro: '沿用真实工作界面，交互探索一条完整的 GPT-6 运行记录。', runLocal: '运行自己的任务 ↗',
      noticeTitle: '当前正在浏览录制内容。', notice: '控件只切换已保存的观测，不调用模型，也不推进新的物理仿真。全部 46 次决策来自同一个连续 episode。',
      cameraAria: '已录制的双相机观测', cameraTitle: '仿真现场', savedFrames: '已保存相机帧', external: '外部相机', wrist: '腕部相机', world: '世界坐标系', expandCameras: '并排查看双相机', insetCameras: '腕部相机小窗', phaseAria: '录制画面', before: '执行前', after: '执行后', terminal: '终止末帧',
      sensorsAria: '所选画面的机器人传感状态', tcp: '末端位置 · 米', gripper: '夹爪开度', gripperRange: '0 闭合 · 100 张开', decision: '决策', simTime: '仿真时间', recordedSensors: '实际传感记录',
      explanation: '模型的动作理由', explanationNote: '这是模型当时的判断，不代表独立测量结论。中文为原始英文的译文。', originalEnglish: '查看模型英文原文',
      playback: 'Episode 回放', paused: '已暂停', playing: '正在回放已保存画面', finished: '已到达本回合末尾', loading: '正在加载录制画面…', play: '▶ 连续回放', pause: '暂停', previous: '← 上一决策', step: '单步查看 →', jump: '跳转到指定决策', selectDecision: '选择决策', viewDuration: '每帧停留', reset: '↺ 重置回放', finalJump: '跳到末帧 ↗',
      playbackNote: '单步依次切换执行前／后画面。决策回放在已记录的关键帧之间跳转，下方完整视频则包含每个控制步。',
      configuration: '本回合实际配置', readOnly: '只读', configNote: '这些是该次运行的固定配置。更换任务、模型或 API 连接，请在本地运行 ManiLoop。',
      finalResult: '本回合最终结果', success: '成功', finalResultNote: '官方 LIBERO 在第 706 个控制步判定成功。这是整个回合的最终评分，不是当前所选画面时刻的评分。', scope: '成功在最后一次下降时触发，环境随即终止，夹爪仍保持闭合；未额外验证松爪或退离。', separation: '仅供人类回看 · 独立评分没有进入策略输入。', results: '查看结果与实验条件 ↗',
      diagnosticsAria: '实际动作与执行反馈', fieldsAria: '录制字段', observationTab: '机器人传感状态', actionTab: '动作字段', originalFields: '保留原始字段名', feedback: '执行反馈', rawFeedback: '查看原始反馈字段', timelineTitle: '全部 46 次决策', timelineHint: '点击任意决策查看',
      videoTitle: '完整 episode · 每个实际控制步', videoNote: '35.35 秒仿真时间回放，保留这一次尝试中的全部抓取重试。省略模型等待，没有剪接、插值或新生成的动作。',
      localTitle: '在自己的电脑使用实时工作台', localNote: '本地程序可以选择任务、配置模型连接并执行新的机器人动作。安装主环境和独立 LIBERO 环境后运行：', setup: '安装与模型配置 ↗', copy: '复制命令', copied: '命令已复制。', copyFailed: '请选中并复制上方命令。',
      footer: '布局和视觉样式复用 ManiLoop 的真实本地工作台。此公开页面只读取经过审阅的运行记录。',
      model: '模型', environment: '环境', taskId: '任务 / 初态 / 种子', cameras: '相机', context: '视觉上下文', reasoning: '推理强度', controller: '控制器', timing: '执行时序', decisionLimit: '决策上限', noCap: '不按次数截断', wallLimit: '墙钟预算', paired: '执行前后配对', controlled: '受控 · 推理时暂停物理',
      move: '移动末端', open: '张开夹爪', close: '闭合夹爪', deltaPosition: '请求 ΔXYZ · 毫米', deltaRotation: '请求旋转 · 弧度', gripperCommand: '夹爪指令', retainedGrip: '机械臂移动保持已有夹爪指令', opened: '张开', closed: '闭合',
      feedbackPending: '当前是动作执行前的观测。切换到「执行后」可查看这次动作实际记录的执行反馈。', feedbackTerminal: '动作执行期间，环境因官方成功判定而终止，没有发出完整的控制器执行终态反馈；实际终止传感画面已保留。', noFeedback: '没有记录完整的执行终态反馈。',
      reached: '目标到位', timed_out: '目标跟踪超时', completed: '夹爪已稳定', accepted: '动作已接受', reachedNote: '本地控制器已到达请求的末端目标。目标到位本身不能证明成功抓住物体。', timedOutNote: '在跟踪时限内，未满足全部完成条件。可查看实际位移和剩余误差。', completedNote: '夹爪控制已稳定。这项控制结果不能证明抓住了物体。',
      actualDelta: '实际 ΔXYZ · 毫米', positionError: '位置误差 · 毫米', rotationError: '姿态误差 · 弧度', controlSteps: '该动作控制步', eventDecision: '模型决策', eventAccepted: '接受动作', eventExecution: '执行反馈', eventTerminal: '环境终止', acceptedEvent: '固定末端目标已被接受，由本地控制器跟踪。', terminalEvent: '官方成功触发环境终止，之后没有新的模型请求。', beforeEventNote: '这条记录是模型根据当前执行前观测给出的决策。',
      loadError: '无法加载运行记录。请刷新页面，或通过项目网站打开。', imageAlt: '已录制相机画面', beforeFeedback: '当前画面尚未执行动作', keyboardHint: '焦点不在表单控件时，可用左右方向键浏览录制画面。'
    }
  };
  const queryLanguage = new URLSearchParams(location.search).get('lang');
  let savedLanguage = null;
  try { savedLanguage = localStorage.getItem('maniloop-language'); } catch (_) { /* Storage is optional. */ }
  let language = ['en', 'zh'].includes(queryLanguage) ? queryLanguage
    : ['en', 'zh'].includes(savedLanguage) ? savedLanguage
    : navigator.language.startsWith('zh') ? 'zh' : 'en';
  let data = null, index = 0, phase = 'before', playing = false, timer = 0, drawVersion = 0, ready = false;
  const imageCache = new Map();
  const t = key => messages[language][key] || key;
  const scalar = (value, digits = 3) => Number.isFinite(value) ? value.toFixed(digits) : '—';
  const vector = (value, scale = 1, digits = 2) => Array.isArray(value) ? value.map(v => scalar(v * scale, digits)).join(' / ') : '—';
  const actionName = step => step.action.kind === 'gripper' ? t(step.action.gripper_opening === 1 ? 'open' : 'close') : t('move');
  const finalView = () => index === data.steps.length - 1 && phase !== 'before';
  const selected = () => { const step = data.steps[index]; return phase === 'before' ? step.frames.before : step.frames.after || step.frames.final; };
  const setText = (id, value) => { $(id).textContent = value; };
  function renderPairs(id, pairs) {
    const list = $(id); list.replaceChildren();
    for (const [key, value] of pairs) {
      const term = document.createElement('dt'), description = document.createElement('dd');
      term.textContent = key; description.textContent = value; list.append(term, description);
    }
  }
  function setLanguage(value) {
    language = value;
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
    document.title = t('pageTitle');
    for (const node of document.querySelectorAll('[data-i18n]')) node.textContent = t(node.dataset.i18n);
    for (const node of document.querySelectorAll('[data-i18n-aria]')) node.setAttribute('aria-label', t(node.dataset.i18nAria));
    for (const button of document.querySelectorAll('[data-lang]')) button.setAttribute('aria-pressed', String(button.dataset.lang === language));
    $('project-link').href = $('brand-link').href = `../?lang=${language}`;
    $('setup-link').href = language === 'zh' ? 'https://github.com/Daniel-rmc/ManiLoop/blob/main/README.zh-CN.md#在-libero-中运行-gpt' : 'https://github.com/Daniel-rmc/ManiLoop#run-gpt-on-libero';
    $('results-link').href = 'https://github.com/Daniel-rmc/ManiLoop/blob/main/docs/RESULTS.md' + (language === 'zh' ? '#简体中文' : '#english');
    setText('camera-layout', t($('viewport').classList.contains('side-by-side') ? 'insetCameras' : 'expandCameras'));
    if (!$('load-error').hidden) setText('load-error', t('loadError'));
    if (data) { renderConfiguration(); buildTimeline(); draw(); }
    try { localStorage.setItem('maniloop-language', language); } catch (_) { /* Storage is optional. */ }
    try {
      const url = new URL(location.href); url.searchParams.set('lang', language); history.replaceState(null, '', url);
    } catch (_) { /* The selected language also works without URL updates. */ }
  }
  function renderConfiguration() {
    const config = data.configuration;
    setText('task-description', data.task[language]);
    renderPairs('configuration-values', [
      [t('model'), data.model], [t('environment'), config.backend], [t('suite'), config.suite],
      [t('taskId'), `${config.task_id} / ${config.init_state_id} / ${config.seed}`], [t('cameras'), config.cameras],
      [t('context'), t('paired')], [t('reasoning'), config.reasoning], [t('controller'), config.controller],
      [t('timing'), t('controlled')], [t('decisionLimit'), t('noCap')], [t('wallLimit'), `${config.wall_limit_seconds} s`]
    ]);
  }
  function buildTimeline() {
    $('decision-rail').replaceChildren(); $('decision-select').replaceChildren();
    for (const [number, step] of data.steps.entries()) {
      const button = document.createElement('button'); button.type = 'button';
      button.className = 'decision-mark' + (step.action.kind === 'gripper' ? ' gripper' : '');
      button.textContent = step.decision; button.dataset.index = number;
      button.setAttribute('aria-label', `${t('decision')} ${step.decision}: ${actionName(step)}`);
      button.addEventListener('click', () => navigate(number, 'before'));
      $('decision-rail').append(button);
      const option = document.createElement('option'); option.value = number;
      option.textContent = `${String(step.decision).padStart(2, '0')} · ${actionName(step)}`;
      $('decision-select').append(option);
    }
  }
  function loadImage(src) {
    if (!/^frames\/\d{3}-(before|after|final)-(external|wrist)\.jpg$/.test(src)) return Promise.reject(new Error('Unexpected frame path'));
    if (!imageCache.has(src)) imageCache.set(src, new Promise((resolve, reject) => {
      const image = new Image(); image.onload = resolve; image.onerror = reject; image.src = src;
    }));
    return imageCache.get(src);
  }
  function renderFeedback(step) {
    const feedback = step.feedback;
    let description = t('feedbackPending'), chip = t('beforeFeedback'), pairs = [], raw = null;
    if (phase !== 'before') {
      if (selected().phase === 'final') {
        description = t('feedbackTerminal'); chip = t('eventTerminal');
      } else if (feedback) {
        chip = t(feedback.status);
        description = t(feedback.status === 'reached' ? 'reachedNote' : feedback.status === 'completed' ? 'completedNote' : 'timedOutNote');
        pairs = [[t('actualDelta'), vector(feedback.actual_delta_position, 1000)],
          [t('positionError'), scalar(feedback.position_error_m * 1000, 3)],
          [t('rotationError'), scalar(feedback.rotation_error_rad, 4)], [t('controlSteps'), String(feedback.control_steps ?? '—')]];
        raw = feedback;
      } else { description = t('noFeedback'); chip = '—'; }
    }
    setText('feedback-description', description); setText('feedback-chip', chip);
    renderPairs('feedback-values', pairs);
    setText('feedback-content', raw ? JSON.stringify(raw, null, 2) : t(phase === 'before' ? 'feedbackPending' : 'noFeedback'));
  }
  function renderEvents(step) {
    const log = $('event-log'); log.replaceChildren();
    const events = phase === 'before' ? step.events.filter(event => event.type === 'decision') : step.events;
    for (const event of events) {
      const label = t(event.type === 'decision' ? 'eventDecision' : event.type === 'accepted' ? 'eventAccepted' : 'eventExecution');
      const message = event.type === 'decision' ? (language === 'zh' ? step.explanation_zh : event.message) : event.type === 'accepted' ? t('acceptedEvent') : t(event.feedback?.status || 'noFeedback');
      appendEvent(log, step.decision, label, message, event.type === 'decision' ? 'action' : '');
    }
    if (phase !== 'before' && selected().phase === 'final') appendEvent(log, step.decision, t('eventTerminal'), t('terminalEvent'), 'terminal');
  }
  function appendEvent(log, number, label, message, style) {
    const row = document.createElement('div'); row.className = 'log-row';
    const count = document.createElement('span'); count.className = 'log-time'; count.textContent = `# ${String(number).padStart(2, '0')}`;
    const type = document.createElement('span'); type.className = `log-type ${style}`; type.textContent = label;
    const body = document.createElement('span'); body.className = 'log-message'; body.textContent = message;
    row.append(count, type, body); log.append(row);
  }
  function updateControls() {
    const atEnd = data && finalView();
    $('previous-button').disabled = !ready || index === 0;
    $('step-button').disabled = !ready || Boolean(atEnd);
    $('play-button').disabled = !ready || playing || Boolean(atEnd);
    $('pause-button').disabled = !playing;
    $('reset-button').disabled = $('final-button').disabled = $('decision-slider').disabled = $('decision-select').disabled = !ready;
    setText('play-status', !ready ? t('loading') : atEnd ? t('finished') : playing ? t('playing') : t('paused'));
  }
  async function draw() {
    if (!data) return;
    const version = ++drawVersion, step = data.steps[index], frame = selected();
    ready = false; updateControls(); $('viewport').setAttribute('aria-busy', 'true');
    try {
      await Promise.all(Object.values(frame.images).map(image => loadImage(image.src)));
      if (version !== drawVersion) return;
      for (const camera of ['external', 'wrist']) {
        $(`${camera}-image`).src = frame.images[camera].src;
        $(`${camera}-image`).alt = `${t('imageAlt')} · ${t(camera)} · ${t('decision')} ${step.decision} · ${t(frame.phase === 'final' ? 'terminal' : frame.phase)}`;
      }
      const sensors = frame.sensors;
      setText('frame-position', `${String(step.decision).padStart(2, '0')} / ${data.steps.length} · ${t(frame.phase === 'final' ? 'terminal' : frame.phase)}`);
      setText('frame-time', `${scalar(sensors.simulation_time, 2)} s`);
      setText('tcp-value', vector(sensors.tcp_position, 1, 3)); setText('gripper-value', scalar(sensors.gripper_opening * 100, 1));
      setText('decision-value', step.decision); setText('kind-value', actionName(step)); setText('time-value', scalar(sensors.simulation_time, 2));
      setText('action-kind', actionName(step)); setText('action-explanation', language === 'zh' ? step.explanation_zh : step.action.explanation);
      setText('original-text', step.action.explanation); $('original-explanation').hidden = language !== 'zh';
      renderPairs('action-values', step.action.kind === 'gripper' ? [[t('gripperCommand'), t(step.action.gripper_opening === 1 ? 'opened' : 'closed')]] : [
        [t('deltaPosition'), vector(step.action.delta_position, 1000)], [t('deltaRotation'), vector(step.action.delta_rotation, 1, 3)], [t('gripperCommand'), t('retainedGrip')]
      ]);
      setText('observation-content', JSON.stringify(sensors, null, 2)); setText('action-content', JSON.stringify(step.action, null, 2));
      renderFeedback(step); renderEvents(step);
      $('before-button').setAttribute('aria-pressed', String(phase === 'before'));
      $('after-button').setAttribute('aria-pressed', String(phase !== 'before'));
      setText('after-button', t(step.frames.final ? 'terminal' : 'after'));
      $('decision-slider').value = step.decision; $('decision-select').value = index; setText('slider-value', `${step.decision} / ${data.steps.length}`);
      for (const button of $('decision-rail').children) button.setAttribute('aria-current', String(Number(button.dataset.index) === index));
      document.body.dataset.decision = step.decision; document.body.dataset.phase = frame.phase;
      ready = true; $('viewport').setAttribute('aria-busy', 'false'); $('load-error').hidden = true;
      if (finalView()) stopPlayback();
      updateControls();
    } catch (_) {
      if (version !== drawVersion) return;
      stopPlayback(); ready = false; updateControls();
      setText('load-error', t('loadError')); $('load-error').hidden = false; $('viewport').setAttribute('aria-busy', 'false');
    }
  }
  function stopPlayback() { playing = false; clearTimeout(timer); timer = 0; updateControls(); }
  async function navigate(number, view = 'before') {
    if (!data) return;
    stopPlayback(); index = Math.max(0, Math.min(data.steps.length - 1, number)); phase = view; await draw();
  }
  async function stepForward() {
    if (!data || !ready || finalView()) return;
    if (phase === 'before') phase = 'after'; else { index += 1; phase = 'before'; }
    await draw();
  }
  function schedulePlayback() {
    clearTimeout(timer);
    if (!playing) return;
    timer = setTimeout(async () => { if (!playing) return; await stepForward(); if (playing) schedulePlayback(); }, Number($('play-speed').value));
  }
  function setTab(action) {
    for (const name of ['observation', 'action']) {
      const active = name === (action ? 'action' : 'observation');
      $(`tab-${name}`).setAttribute('aria-selected', String(active)); $(`tab-${name}`).tabIndex = active ? 0 : -1;
      $(`inspect-${name}`).hidden = !active;
    }
  }
  $('play-button').addEventListener('click', () => { if (!ready || finalView()) return; $('episode-video').pause(); playing = true; updateControls(); schedulePlayback(); });
  $('pause-button').addEventListener('click', stopPlayback);
  $('step-button').addEventListener('click', () => { stopPlayback(); stepForward(); });
  $('previous-button').addEventListener('click', () => navigate(index - 1, 'before'));
  $('reset-button').addEventListener('click', () => { $('episode-video').pause(); navigate(0, 'before'); });
  $('final-button').addEventListener('click', () => navigate(data.steps.length - 1, 'after'));
  $('before-button').addEventListener('click', () => navigate(index, 'before'));
  $('after-button').addEventListener('click', () => navigate(index, 'after'));
  $('decision-slider').addEventListener('input', event => navigate(Number(event.target.value) - 1, 'before'));
  $('decision-select').addEventListener('change', event => navigate(Number(event.target.value), 'before'));
  $('play-speed').addEventListener('change', schedulePlayback);
  $('episode-video').addEventListener('play', stopPlayback);
  $('camera-layout').addEventListener('click', () => {
    const expanded = $('viewport').classList.toggle('side-by-side'); $('camera-layout').setAttribute('aria-pressed', String(expanded));
    setText('camera-layout', t(expanded ? 'insetCameras' : 'expandCameras'));
  });
  for (const button of document.querySelectorAll('[data-lang]')) button.addEventListener('click', () => setLanguage(button.dataset.lang));
  $('tab-observation').addEventListener('click', () => setTab(false)); $('tab-action').addEventListener('click', () => setTab(true));
  for (const id of ['tab-observation', 'tab-action']) $(id).addEventListener('keydown', event => {
    if (['ArrowLeft', 'ArrowRight'].includes(event.key)) { event.preventDefault(); const action = id === 'tab-observation'; setTab(action); $(action ? 'tab-action' : 'tab-observation').focus(); }
  });
  document.addEventListener('keydown', event => {
    if (!ready || ['INPUT', 'SELECT', 'TEXTAREA', 'VIDEO', 'BUTTON'].includes(event.target.tagName) || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === 'ArrowRight') { event.preventDefault(); stopPlayback(); stepForward(); }
    if (event.key === 'ArrowLeft') { event.preventDefault(); navigate(index - 1, 'before'); }
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) { stopPlayback(); $('episode-video').pause(); } });
  $('copy-command').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText('python -m maniloop demo --backend libero --codex-login --port 8767'); setText('copy-status', t('copied')); }
    catch (_) { setText('copy-status', t('copyFailed')); }
  });
  setLanguage(language);
  fetch('data.json', {method: 'GET', credentials: 'omit', cache: 'force-cache'})
    .then(response => { if (!response.ok) throw new Error('Recording unavailable'); return response.json(); })
    .then(value => {
      if (value.format !== 'maniloop_public_workspace_v1' || value.steps?.length !== 46 || value.steps[45].feedback !== null || value.result?.control_steps !== 706) throw new Error('Unexpected recording');
      data = value; renderConfiguration(); buildTimeline(); return draw();
    }).catch(() => { setText('load-error', t('loadError')); $('load-error').hidden = false; });
})();
