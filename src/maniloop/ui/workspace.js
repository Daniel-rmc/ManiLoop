import {createManualControls} from './manual-control.js';
import {createWorkspaceLayout} from './workspace-layout.js';

const $ = id => document.getElementById(id);
const ui = {
  task: $('task-input'), model: $('model-input'), key: $('api-key'), maxSteps: $('max-steps'),
  source: $('credential-source'), configSelect: $('config-select'), configPath: $('config-path'),
  readConfig: $('read-config-button'), discoverConfigs: $('discover-configs-button'), modelSelect: $('model-select'), refreshModels: $('refresh-models-button'), baseUrl: $('base-url'),
  configKey: $('config-api-key'), configUpload: $('config-upload'), configToml: $('config-toml'), readUpload: $('read-upload-config-button'),
  start: $('start-button'), stop: $('stop-button'), step: $('step-button'), pause: $('pause-button'), resume: $('resume-button'), reset: $('reset-button'), error: $('action-error'),
  notice: $('session-notice')
};
let state = null;
let connected = false;
let pending = false;
let stateInFlight = false;
let configBusy = false;
let credentialsEdited = false;
let configOptions = {configs: [], models: [], default_path: ''};
let configPreview = null;
let previewRevision = -1;
let configRevision = 0;
let uploadName = 'config.toml';
let uploadReadSequence = 0;
let fetchedModels = [];
let lastLogFingerprint = '';
let toastTimer = 0;
let connectionFailures = 0;
let cameraCounter = 0;
const cameraLoading = {external: false, wrist: false};
const manualControls = createManualControls({getState: () => state, perform, showError});
const workspaceLayout = createWorkspaceLayout({perform});

function text(value) {
  if (value == null) return '';
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}
function numeric(value) { return typeof value === 'number' && Number.isFinite(value); }
function number(value, precision = 2) { return numeric(value) ? value.toFixed(precision) : '—'; }
function errorMessage(error) {
  const message = error && error.message ? error.message : text(error);
  if (/Failed to fetch|Load failed|NetworkError|fetch failed/i.test(message)) return '无法连接本地服务。请检查仿真服务是否仍在运行。';
  if (/AbortError|aborted|timeout|timed out/i.test(message)) return '本地服务响应超时，请稍后重试。';
  return message || '操作失败，请查看实验日志。';
}
function showError(error) { ui.error.textContent = errorMessage(error); ui.error.hidden = false; }
function clearError() { ui.error.textContent = ''; ui.error.hidden = true; }
function showToast(message) {
  $('toast').textContent = message;
  $('toast').hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $('toast').hidden = true; }, 3400);
}
async function request(path, body, timeout = 30000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(path, {
      method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? {Accept: 'application/json'} : {'Content-Type': 'application/json', Accept: 'application/json'},
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: 'no-store', signal: controller.signal, credentials: 'same-origin'
    });
    let data;
    try { data = await response.json(); } catch (_) { throw new Error('服务返回了无法读取的响应（HTTP ' + response.status + '）。'); }
    if (!response.ok || data.ok === false) throw new Error(text(data.error || data.detail || data.message) || '请求失败（HTTP ' + response.status + '）。');
    return data;
  } finally { clearTimeout(timer); }
}
function requestSettings() {
  return {timeout_seconds: Number($('request-timeout').value), reasoning_effort: $('reasoning-effort').value};
}
function environmentSettings() {
  const maxAge = Number($('observation-max-age').value);
  if ($('observation-max-age').value.trim() === '' || !Number.isFinite(maxAge) || maxAge < 0) throw new Error('观测有效期必须为非负有限秒数；0 表示不限时间');
  return {llm_control: $('llm-control').value, observation_profile: $('llm-resolution').value, observation_max_age_seconds: maxAge};
}
function selectedModel() { return ui.modelSelect.value === '__custom__' ? ui.model.value.trim() : ui.modelSelect.value; }
function selectedCredentials() {
  const body = {credential_source: ui.source.value};
  if (ui.source.value === 'codex') return body;
  if (ui.source.value === 'file') body.config_path = ui.configPath.value.trim();
  else if (ui.source.value === 'upload') {
    body.config_toml = ui.configToml.value;
    body.config_name = uploadName;
  }
  else {
    body.base_url = ui.baseUrl.value.trim();
    if (ui.key.value.trim()) body.api_key = ui.key.value.trim();
  }
  if (ui.source.value !== 'manual' && ui.configKey.value.trim()) body.api_key = ui.configKey.value.trim();
  return body;
}
function validateConfigSelection(body) {
  if (body.credential_source === 'file' && !body.config_path) {
    showError(new Error('请先选择或输入本地配置文件路径。')); ui.configPath.focus(); return false;
  }
  if (body.credential_source === 'upload' && !body.config_toml.trim()) {
    showError(new Error('请选择 config.toml 文件，或粘贴 TOML 配置内容。')); ui.configToml.focus(); return false;
  }
  return true;
}
function updateModelChoices() {
  const selected = ui.modelSelect.value;
  const models = [...new Set([
    ...configOptions.models,
    ...(ui.source.value !== 'manual' && previewRevision === configRevision && configPreview ? [...(configPreview.models || []), configPreview.model] : []),
    ...fetchedModels
  ].filter(model => typeof model === 'string' && model && model !== '__custom__'))];
  if (selected && selected !== '__custom__' && !models.includes(selected)) models.push(selected);
  ui.modelSelect.replaceChildren();
  const add = (value, label) => { const option = document.createElement('option'); option.value = value; option.textContent = label; ui.modelSelect.appendChild(option); };
  add('', ui.source.value === 'codex' ? 'GPT-6 Astra（默认）' : ui.source.value === 'manual' ? '使用服务默认模型' : '跟随配置中的模型');
  models.forEach(model => add(model, model));
  add('__custom__', '自定义模型…');
  ui.modelSelect.value = selected;
  updateModelInput();
}
function updateModelInput() {
  const custom = ui.modelSelect.value === '__custom__';
  $('custom-model-fields').hidden = !custom;
  ui.model.required = custom;
}
function renderConfigPreview(config) {
  const box = $('config-preview');
  box.replaceChildren();
  if (!config || config.error) {
    const message = document.createElement('p');
    message.className = config && config.error ? 'config-error' : 'config-empty';
    message.textContent = config && config.error ? config.error : '选择配置文件后点击「读取配置」，可查看服务商与密钥状态。';
    box.appendChild(message);
    return;
  }
  const rows = [
    ['服务商', config.provider || '未指定'], ['API 地址', config.base_url || '服务默认地址'],
    ['配置模型', config.model || '服务默认模型'],
    ['密钥状态', config.key_configured ? '已配置（不会显示密钥）' : '未找到 API 密钥；请在上方单独填写 API Key']
  ];
  const list = document.createElement('dl');
  for (const [label, value] of rows) {
    const term = document.createElement('dt'); term.textContent = label;
    const detail = document.createElement('dd'); detail.textContent = text(value);
    if (label === '密钥状态') detail.style.color = config.key_configured ? 'var(--green)' : 'var(--orange)';
    list.append(term, detail);
  }
  box.appendChild(list);
}
function updateCredentialStatus() {
  const codex = ui.source.value === 'codex';
  const file = ui.source.value === 'file';
  const upload = ui.source.value === 'upload';
  const usesConfig = file || upload;
  $('file-config-fields').hidden = !file;
  $('upload-config-fields').hidden = !upload;
  $('upload-preview-action').hidden = !upload;
  $('config-key-fields').hidden = !usesConfig;
  $('manual-config-fields').hidden = usesConfig || codex;
  $('codex-login-note').hidden = !codex;
  // A live run may refresh its provider after CC Switch changes. An idle preview remains independent.
  const metadata = state && state.running && state.credentials && state.credentials.source === ui.source.value && usesConfig
    ? state.credentials : previewRevision === configRevision ? configPreview : null;
  const configured = usesConfig ? !!(metadata && metadata.key_configured && !metadata.error) : !!(ui.key.value.trim() || (state && state.manual_key_configured));
  $('key-status').textContent = configBusy ? '正在读取…' : configured ? '已配置' : usesConfig && !metadata ? '等待读取' : '尚未配置 API 密钥';
  $('key-status').className = 'key-status' + (configured ? ' configured' : '');
  $('model-catalog-note').textContent = codex ? 'Codex 模式仅检查本机登录记录；模型是否可用须通过实际诊断验证。' : '刷新会请求当前服务商的模型列表。列出的模型仍需支持图像与结构化输出。';
  if (codex) { $('key-status').textContent = '使用 Codex 登录'; $('key-status').className = 'key-status'; }
  ui.key.placeholder = state && state.manual_key_configured ? '服务已保存手动密钥；留空继续使用，或输入新密钥' : '输入 API 密钥，或使用服务端环境变量';
  if (usesConfig) renderConfigPreview(metadata);
}
function invalidatePreview() {
  credentialsEdited = true;
  configRevision += 1;
  configPreview = null;
  previewRevision = -1;
  fetchedModels = [];
  updateCredentialStatus();
  updateModelChoices();
}
async function readConfig() {
  if (configBusy || pending || (state && (state.running || state.pending_request))) return;
  const body = selectedCredentials();
  if (body.credential_source === 'manual' || !validateConfigSelection(body)) return;
  const revision = configRevision;
  configBusy = true; clearError(); updateControls(); updateCredentialStatus();
  try {
    const result = await request('/api/config-preview', body);
    if (revision !== configRevision) return;
    configPreview = result.config;
    previewRevision = revision;
    fetchedModels = [];
    updateModelChoices();
  } catch (error) {
    if (revision === configRevision) { configPreview = {error: errorMessage(error)}; previewRevision = revision; }
  } finally { delete body.api_key; delete body.config_toml; configBusy = false; updateControls(); updateCredentialStatus(); }
}
async function loadConfigOptions(discover = false) {
  try {
    const result = await request('/api/config-options' + (discover ? '?discover=1' : ''));
    configOptions = {configs: Array.isArray(result.configs) ? result.configs : [], models: Array.isArray(result.models) ? result.models : [], default_path: result.default_path || ''};
    ui.configSelect.replaceChildren();
    for (const config of configOptions.configs) {
      const option = document.createElement('option'); option.value = config.path;
      option.textContent = config.label || config.path; option.title = config.path;
      ui.configSelect.appendChild(option);
    }
    const custom = document.createElement('option'); custom.value = '__custom__'; custom.textContent = '自定义本地路径…'; ui.configSelect.appendChild(custom);
    if (!credentialsEdited && typeof result.manual_base_url === 'string') ui.baseUrl.value = result.manual_base_url;
    if (!credentialsEdited || (discover && !ui.configPath.value)) {
      ui.configPath.value = configOptions.default_path;
    }
    ui.configSelect.value = configOptions.configs.some(config => config.path === ui.configPath.value) ? ui.configPath.value : '__custom__';
    updateModelChoices();
  } catch (error) {
    const custom = document.createElement('option'); custom.value = '__custom__'; custom.textContent = '自定义本地路径…'; ui.configSelect.replaceChildren(custom);
    if (!credentialsEdited) { configPreview = {error: errorMessage(error)}; previewRevision = configRevision; updateCredentialStatus(); }
  }
}
async function refreshModels() {
  if (ui.refreshModels.disabled) return;
  const body = selectedCredentials();
  if (!validateConfigSelection(body)) return;
  if (body.credential_source === 'manual' && !body.api_key && !(state && state.manual_key_configured)) { showError(new Error('请先输入 API 密钥，再刷新模型列表。')); ui.key.focus(); return; }
  configBusy = true; clearError(); updateControls(); updateCredentialStatus();
  ui.refreshModels.textContent = '正在刷新…';
  try {
    const result = await request('/api/models', body, 45000);
    fetchedModels = Array.isArray(result.models) ? result.models : [];
    if (body.credential_source !== 'manual' && result.config) { configPreview = result.config; previewRevision = configRevision; }
    updateModelChoices();
    showToast(body.credential_source === 'codex' ? '检测到本机登录记录；请用诊断验证模型可用性。' : '已读取 ' + fetchedModels.length + ' 个模型。任务需要模型支持图像与结构化输出。');
  } catch (error) { showError(error); }
  finally { delete body.api_key; delete body.config_toml; configBusy = false; ui.refreshModels.textContent = '刷新模型列表'; updateControls(); updateCredentialStatus(); }
}
function updateControls() {
  const running = !!(state && state.running);
  const paused = !!(state && state.paused);
  const pauseRequested = !!(state && state.pause_requested);
  const inFlight = !!(state && state.pending_request);
  const moving = !!(state && state.motion_busy);
  const cloud = $('agent-select').value === 'llm_cloud';
  const steppable = cloud || $('agent-select').value === 'jev';
  const ready = !!(connected && state && state.ready);
  const configLocked = pending || configBusy || running || inFlight;
  ['backend-select','robocasa-task','robocasa-layout','robocasa-style','robosuite-task','libero-suite','libero-task','libero-init','robot-select','layout-select','task-select','timing-select','apply-environment','demo-preset','agent-select','local-model'].forEach(id => { $(id).disabled = configLocked || !ready; });
  ui.start.disabled = pending || configBusy || !ready || running || inFlight || moving;
  ['request-timeout','reasoning-effort','llm-control','llm-resolution','wall-budget','sim-budget','reset-before-start','context-mode','observation-max-age'].forEach(id => { $(id).disabled = configLocked; });
  ['text','vision','action'].forEach(stage => { $('diagnose-' + stage).disabled = pending || configBusy || !ready || running || inFlight || moving; });
  ui.stop.disabled = pending || !connected || (!running && !moving);
  ui.step.disabled = !steppable || pending || configBusy || !ready || inFlight || moving || (running && !paused);
  ui.pause.disabled = !steppable || pending || !connected || !running || paused || pauseRequested;
  ui.resume.disabled = !steppable || pending || !connected || !running || !paused;
  [ui.step, ui.pause, ui.resume].forEach(button => { button.hidden = !steppable; });
  $('step-controls-note').hidden = !steppable;
  ui.step.textContent = paused ? '执行下一步' : '单步执行';
  ui.pause.textContent = pauseRequested && !paused ? '等待动作结束…' : '执行后暂停';
  $('replay-link').hidden = !(state && state.replay_available);
  ui.reset.disabled = pending || !connected || running;
  manualControls.update(state, pending || configBusy || !ready || running || inFlight || moving);
  workspaceLayout.update(state, {connected, pending});
  document.getElementById("connection-fold").hidden = !cloud;
  ui.task.disabled = pending || running;
  [ui.model, ui.key, ui.source, ui.configSelect, ui.configPath, ui.readConfig, ui.discoverConfigs, ui.modelSelect, ui.refreshModels, ui.baseUrl, ui.configKey, ui.configUpload, ui.configToml, ui.readUpload].forEach(control => { control.disabled = configLocked; });
  ui.key.disabled = configLocked || ui.source.value !== 'manual';
  ui.baseUrl.disabled = configLocked || ui.source.value !== 'manual';
  ui.maxSteps.disabled = pending || running;
  $('scene-seed').disabled = pending || running;
  if ($('backend-select').value !== 'mujoco') ['robot-select','layout-select','task-select'].forEach(id => { $(id).disabled = true; });
  ui.model.required = cloud && ui.modelSelect.value === '__custom__';
  updateJevControls(configLocked || !ready || moving);
  ui.start.querySelector('span').textContent = paused ? '实验已暂停' : running ? '执行中' : pending ? '正在处理…' : '连续执行';
}
function setConnection(ok) {
  connected = ok;
  $('connection-dot').className = 'dot ' + (ok ? 'ok' : 'error');
  $('connection-label').textContent = ok ? '本地服务已连接' : '连接已断开';
  updateControls();
}
function renderState(data) {
  if (!state) {
    if (data.credential_source === 'codex') ui.source.value = 'codex';
    $('context-mode').value = data.context_mode || 'current';
    $('observation-max-age').value = String(data.observation_max_age_seconds ?? 60);
    $('backend-select').value = data.backend || 'mujoco';
    if (data.backend === 'libero') {
      $('libero-suite').value = data.environment.suite;
      $('libero-init').value = data.environment.init_state_id;
      loadLiberoTasks(data.environment.task_id);
    } else if (data.backend === 'robosuite') {
      loadRobosuiteTasks(data.environment.task);
    } else if (data.backend === 'robocasa') {
      $('robocasa-layout').value = data.environment.layout;
      $('robocasa-style').value = data.environment.style;
      loadRobocasaTasks(data.environment.task);
    }
    updateBackendFields();
    $('robot-select').value = data.robot;
    if (data.backend === 'mujoco') { $('layout-select').value = data.scene; $('task-select').value = data.task_id; }
    $('timing-select').value = data.timing;
    ui.task.value = data.task_instruction;
  }
  $('active-environment').textContent = `${data.backend || 'mujoco'} · ${data.robot} · ${data.scene} · ${data.timing}`;
  const world = ['libero', 'robosuite', 'robocasa'].includes(data.backend);
  $('frame-label').textContent = world ? '世界坐标系 · m' : '机器人基座坐标系 · m';
  $('frame-metric').textContent = world ? 'WORLD FRAME · METERS' : 'BASE FRAME · METERS';
  state = data;
  const running = !!data.running;
  $('simulation-dot').className = 'dot ' + (data.error ? 'error' : running ? 'busy' : data.ready ? 'ok' : '');
  $('simulation-status').textContent = data.error ? '需要检查反馈' : data.paused ? '已暂停 · 可检查反馈并继续' : data.pause_requested ? '完成当前动作后暂停' : ({thinking:'模型正在观察与决策',executing:'动作执行中',completed:data.diagnostic_stage ? '诊断已完成' : data.agent === 'jev' ? 'Jev 指令序列已结束' : '模型已声明结束',stopped:'任务已停止'}[data.phase] || (running ? '闭环执行中' : data.ready ? '环境就绪' : '环境初始化中'));
  updateCredentialStatus();
  const xyz = Array.isArray(data.tcp_position) ? data.tcp_position : data.tcp_position && [data.tcp_position.x, data.tcp_position.y, data.tcp_position.z];
  $('tcp-position').textContent = xyz && xyz.length >= 3 ? xyz.slice(0, 3).map(value => number(value, 3)).join(' / ') : '— / — / —';
  $('gripper-opening').textContent = numeric(data.gripper_opening) ? String(Math.round(data.gripper_opening * 100)) : '—';
  $('step-value').textContent = Number.isInteger(data.api_calls) ? String(data.api_calls) : '0';
  $('evaluation-status').textContent = data.evaluation && data.evaluation.success ? '独立评估：所选任务已完成 ✓' : `独立评估：${data.backend === 'libero' ? 'LIBERO 官方' : ['robosuite','robocasa'].includes(data.backend) ? (data.backend + ' ' + data.task_id) : data.task_id === 'push' ? '推物' : '抓放'}任务尚未完成`;
  const latency = data.api_latency ?? data.last_api_latency_s ?? data.api_latency_s ?? data.last_api_duration_s ?? data.api_duration_s ?? (data.last_feedback && data.last_feedback.api_latency_s);
  $('api-latency').textContent = number(latency, 1);
  const simTime = numeric(data.sim_time) ? Math.max(0, data.sim_time) : 0;
  const minutes = Math.floor(simTime / 60);
  const seconds = (simTime % 60).toFixed(1).padStart(4, '0');
  $('sim-clock').textContent = 'SIM ' + String(minutes).padStart(2, '0') + ':' + seconds;
  if (running) {
    ui.notice.textContent = data.paused ? '已暂停：不会请求下一次模型决策。可检查画面与反馈，选择执行下一步或继续连续执行。' : data.pause_requested ? '等待本次决策和动作结束，随后暂停；不会额外请求下一次决策。' : (data.timing === 'controlled' ? '受控时序：模型思考期间暂停物理，动作执行后重新观察。' : '实时模式：模型思考期间物理持续推进。');
    ui.notice.className = 'session-notice running';
  } else {
    ui.notice.textContent = $('agent-select').value === 'jev' ? 'Jev 仅读取指令与本体状态；每行请求一次选择，本地执行后才处理下一行。' : $('agent-select').value === 'lerobot' ? '使用本机已安装的真实模型；ACT / DP 不使用语言。默认按官方任务与所选初始化执行。' : $('agent-select').value === 'mock_vla' ? '模拟 VLA 只做小幅关节动作来验证接口，不调用 API，也不代表真实模型能力。' : ui.source.value === 'codex' ? '预览和手动调试不调用模型。单步、连续执行或诊断通过 Codex 登录请求模型，使用账号额度。' : '无需密钥即可预览与手动调试。开始执行会向所选服务商发送相机观测和任务指令。';
    ui.notice.className = 'session-notice';
  }
  $('observation-content').textContent = data.observation && Object.keys(data.observation).length ? text(data.observation) : '等待第一份观测…';
  $('action-content').textContent = data.last_action ? text(data.last_action) : '尚未发出动作。';
  if (data.diagnostic_result) $('diagnostic-result').textContent = text(data.diagnostic_result);
  else if (data.diagnostic_stage) $('diagnostic-result').textContent = data.error || '正在等待诊断响应；不会执行动作…';
  renderFeedback(data);
  renderEvents(Array.isArray(data.events) ? data.events : []);
  updateControls();
}
function renderFeedback(data) {
  const feedback = data.last_feedback;
  if (data.error) {
    $('feedback-summary').hidden = false;
    $('feedback-content').textContent = '执行提示：' + text(data.error);
    $('feedback-details').hidden = !feedback;
    $('feedback-details').textContent = feedback ? text(feedback) : '';
  } else if (feedback) {
    $('feedback-summary').hidden = typeof feedback !== 'string';
    $('feedback-content').textContent = typeof feedback === 'string' ? feedback : '';
    $('feedback-details').hidden = typeof feedback === 'string';
    $('feedback-details').textContent = typeof feedback === 'string' ? '' : text(feedback);
  } else {
    $('feedback-summary').hidden = false;
    $('feedback-details').hidden = true;
    $('feedback-content').textContent = '初始化环境后，可先点动机械臂，观察末端位置与相机画面的变化。';
  }
}
function formatTime(value) {
  if (value == null) return '—';
  if (typeof value === 'number' && value < 1000000000) return value.toFixed(1) + ' s';
  const date = new Date(typeof value === 'number' && value < 100000000000 ? value * 1000 : value);
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 16);
  return date.toLocaleTimeString('zh-CN', {hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit'});
}
function renderEvents(events) {
  const fingerprint = JSON.stringify(events);
  if (fingerprint === lastLogFingerprint) return;
  lastLogFingerprint = fingerprint;
  const container = $('log-container');
  container.replaceChildren();
  $('log-count').textContent = events.length + ' EVENTS';
  if (!events.length) {
    const empty = document.createElement('div'); empty.className = 'log-empty';
    empty.textContent = '场景已连接。初始化、手动动作和模型决策将在这里留下记录。';
    container.appendChild(empty); return;
  }
  const fragment = document.createDocumentFragment();
  for (const event of events.slice(-80).reverse()) {
    const row = document.createElement('div'); row.className = 'log-row';
    const time = document.createElement('span'); time.className = 'log-time'; time.textContent = formatTime(event.time);
    const type = document.createElement('span');
    const category = String(event.type || 'event');
    type.className = 'log-type' + (/error|fail|reject/i.test(category) ? ' error' : /action|decision|api/i.test(category) ? ' action' : /success|ready|complete/i.test(category) ? ' success' : '');
    type.textContent = category; type.title = category;
    const message = document.createElement('span'); message.className = 'log-message'; message.textContent = text(event.message ?? event.detail ?? event);
    row.append(time, type, message); fragment.appendChild(row);
  }
  container.appendChild(fragment);
}
async function refreshState() {
  if (stateInFlight || document.hidden) return;
  stateInFlight = true;
  try {
    const data = await request('/api/state', undefined, 8000);
    connectionFailures = 0;
    setConnection(true);
    renderState(data);
  } catch (error) {
    connectionFailures++;
    if (connectionFailures >= 2 || !state) {
      setConnection(false);
      $('simulation-dot').className = 'dot error';
      $('simulation-status').textContent = '等待本地服务恢复';
      $('camera-placeholder').hidden = false;
      $('camera-placeholder').querySelector('span').textContent = '本地服务暂时不可用';
    }
  } finally { stateInFlight = false; }
}
function refreshCameras() {
  if (document.hidden) return;
  cameraCounter++;
  for (const name of ['external', 'wrist']) {
    if (cameraLoading[name]) continue;
    cameraLoading[name] = true;
    const img = $(name + '-camera');
    img.src = '/camera/' + name + '.jpg?v=' + Date.now() + '-' + cameraCounter;
  }
}
for (const name of ['external', 'wrist']) {
  const img = $(name + '-camera');
  img.addEventListener('load', () => {
    cameraLoading[name] = false;
    $(name === 'external' ? 'camera-placeholder' : 'wrist-placeholder').hidden = true;
  });
  img.addEventListener('error', () => {
    cameraLoading[name] = false;
    $(name === 'external' ? 'camera-placeholder' : 'wrist-placeholder').hidden = false;
    if (name === 'external') $('camera-placeholder').querySelector('span').textContent = '等待相机画面';
  });
}
async function perform(path, body, successMessage) {
  if (pending) return;
  pending = true; clearError(); updateControls();
  try {
    const result = await request(path, body, path === "/api/start" && body.agent === "lerobot" ? 360000 : path === "/api/configure" || path === "/api/start" ? 240000 : 30000);
    if (result.state) renderState(result.state);
    await refreshState();
    if (successMessage) showToast(successMessage);
    return result;
  } catch (error) { showError(error); }
  finally { pending = false; updateControls(); }
}
ui.modelSelect.addEventListener('change', updateModelInput);
ui.readConfig.addEventListener('click', readConfig);
ui.discoverConfigs.addEventListener('click', () => loadConfigOptions(true));
ui.readUpload.addEventListener('click', readConfig);
ui.refreshModels.addEventListener('click', refreshModels);
ui.source.addEventListener('change', () => {
  invalidatePreview(); updateControls();
});
ui.configSelect.addEventListener('change', () => {
  const choice = ui.configSelect.value;
  invalidatePreview();
  ui.configPath.value = choice === '__custom__' ? '' : choice;
  if (choice === '__custom__') ui.configPath.focus();
});
ui.configPath.addEventListener('input', () => {
  ui.configSelect.value = '__custom__'; invalidatePreview();
});
ui.configKey.addEventListener('input', invalidatePreview);
ui.configToml.addEventListener('input', () => {
  uploadReadSequence += 1;
  uploadName = 'config.toml';
  ui.configUpload.value = '';
  $('config-upload-name').textContent = '已手动编辑';
  invalidatePreview();
});
ui.configUpload.addEventListener('change', async () => {
  const sequence = ++uploadReadSequence;
  const file = ui.configUpload.files && ui.configUpload.files[0];
  if (!file) return;
  ui.configToml.value = '';
  uploadName = 'config.toml';
  $('config-upload-name').textContent = '正在读取文件…';
  invalidatePreview(); clearError();
  if (file.size > 1048576) {
    ui.configUpload.value = '';
    $('config-upload-name').textContent = '请选择不超过 1 MB 的文件';
    showError(new Error('配置文件过大，请选择不超过 1 MB 的 TOML 文件。')); return;
  }
  try {
    const content = await file.text();
    if (sequence !== uploadReadSequence) return;
    ui.configToml.value = content;
    uploadName = file.name;
    $('config-upload-name').textContent = file.name;
    invalidatePreview();
    await readConfig();
  } catch (_) {
    if (sequence !== uploadReadSequence) return;
    $('config-upload-name').textContent = '文件读取失败';
    showError(new Error('无法读取所选文件，请重新选择，或粘贴 TOML 配置内容。'));
  }
});
ui.key.addEventListener('input', updateCredentialStatus);
ui.baseUrl.addEventListener('input', () => { fetchedModels = []; updateModelChoices(); });
let taskCatalogSequence = 0;
function updateBackendFields() {
  const backend = $('backend-select').value;
  $('libero-options').hidden = backend !== 'libero';
  $('robosuite-options').hidden = backend !== 'robosuite';
  $('robocasa-options').hidden = backend !== 'robocasa';
  ['layout-select','task-select'].forEach(id => { $(id).closest('label').hidden = backend !== 'mujoco'; });
  if (backend !== 'mujoco') $('robot-select').value = backend === 'robocasa' ? 'panda_omron' : 'panda';
  else if ($('robot-select').value === 'panda_omron') $('robot-select').value = 'panda';
  const localOption = $('agent-select').querySelector('option[value="lerobot"]');
  if (localOption) localOption.disabled = backend !== 'libero';
  if (backend !== 'libero' && $('agent-select').value === 'lerobot') {
    $('agent-select').value = 'llm_cloud';
    $('agent-select').dispatchEvent(new Event('change'));
  }
}
async function loadLiberoTasks(selected = 0) {
  const sequence = ++taskCatalogSequence;
  try {
    const response = await fetch('/api/libero-tasks?suite=' + encodeURIComponent($('libero-suite').value));
    const data = await response.json();
    if (sequence !== taskCatalogSequence) return;
    if (!response.ok) throw new Error(data.error);
    $('libero-task').replaceChildren(...data.tasks.map(task => {
      const option = document.createElement('option');
      option.value = task.id; option.textContent = `${task.id} · ${task.instruction}`; return option;
    }));
    $('libero-task').value = String(selected);
  } catch (error) { if (sequence === taskCatalogSequence) showError(error); }
}
async function loadRobosuiteTasks(selected = 'Lift') {
  const sequence = ++taskCatalogSequence;
  try {
    const response = await fetch('/api/robosuite-tasks');
    const data = await response.json();
    if (sequence !== taskCatalogSequence) return;
    if (!response.ok) throw new Error(data.error || '任务目录读取失败');
    $('robosuite-task').replaceChildren(...data.tasks.map(task => {
      const option = document.createElement('option');
      option.value = task.id; option.textContent = `${task.id} · ${task.display_name}`; return option;
    }));
    $('robosuite-task').value = selected;
  } catch (error) { if (sequence === taskCatalogSequence) showError(error); }
}
async function loadRobocasaTasks(selected = 'OpenDrawer') {
  const sequence = ++taskCatalogSequence;
  try {
    const response = await fetch('/api/robocasa-tasks');
    const data = await response.json();
    if (sequence !== taskCatalogSequence) return;
    if (!response.ok) throw new Error(data.error || '任务目录读取失败');
    $('robocasa-task').replaceChildren(...data.tasks.map(task => {
      const option = document.createElement('option');
      option.value = task.id; option.textContent = `${task.id} · ${task.display_name}`; return option;
    }));
    $('robocasa-task').value = selected;
  } catch (error) { if (sequence === taskCatalogSequence) showError(error); }
}
$('backend-select').addEventListener('change', () => {
  updateBackendFields(); updateControls();
  if ($('backend-select').value === 'libero') loadLiberoTasks();
  if ($('backend-select').value === 'robosuite') loadRobosuiteTasks();
  if ($('backend-select').value === 'robocasa') loadRobocasaTasks();
});
$('libero-suite').addEventListener('change', () => loadLiberoTasks());
$('apply-environment').addEventListener('click', async () => {
  let settings;
  try { settings = environmentSettings(); } catch (error) { showError(error); return; }
  const result = await perform('/api/configure', {
    backend: $('backend-select').value,
    libero_suite: $('libero-suite').value, libero_task_id: Number($('libero-task').value),
    init_state_id: Number($('libero-init').value),
    robot: $('robot-select').value, scene: $('layout-select').value,
    robocasa_layout: Number($('robocasa-layout').value), robocasa_style: Number($('robocasa-style').value),
    task_id: $('backend-select').value === 'robocasa' ? $('robocasa-task').value : $('backend-select').value === 'robosuite' ? $('robosuite-task').value : $('task-select').value, timing: $('timing-select').value,
    seed: Number($('scene-seed').value), ...settings
  }, '实验环境已重置。');
  await refreshState();
  if (result && result.task_instruction) ui.task.value = result.task_instruction;
});
$('demo-preset').addEventListener('click', async () => {
  if ($('demo-preset').disabled) return;
  configBusy = true; clearError(); updateControls();
  try {
    $('backend-select').value = 'libero';
    $('libero-suite').value = 'libero_spatial';
    $('libero-init').value = '0';
    $('scene-seed').value = '0';
    $('timing-select').value = 'controlled';
    $('agent-select').value = 'llm_cloud';
    $('agent-select').dispatchEvent(new Event('change'));
    updateBackendFields();
    ui.modelSelect.value = '__custom__';
    ui.model.value = 'gpt-6-astra';
    updateModelInput();
    ui.maxSteps.value = '30';
    $('request-timeout').value = '120';
    $('reasoning-effort').value = 'low';
    $('llm-control').value = 'tcp_target_servo_v2';
    $('llm-resolution').value = 'llm_rgb512';
    $('wall-budget').value = '3600';
    $('sim-budget').value = '120';
    $('context-mode').value = 'current';
    $('reset-before-start').checked = true;
    await loadLiberoTasks(0);
    const result = await perform('/api/configure', {
      backend: 'libero', libero_suite: 'libero_spatial', libero_task_id: 0,
      init_state_id: 0, seed: 0, robot: 'panda', timing: 'controlled',
      ...environmentSettings()
    }, '抓放演示已准备好。点击单步或连续执行后才会调用模型。');
    if (result) {
      if (result.task_instruction) ui.task.value = result.task_instruction;
      $('demo-preset-note').hidden = false;
    }
  } finally { configBusy = false; updateControls(); updateCredentialStatus(); }
});
$('agent-select').addEventListener('change', () => {
  const local = $('agent-select').value === 'lerobot';
  $('local-policy-fields').hidden = !local;
  $('cloud-controls').hidden = $('agent-select').value !== 'llm_cloud';
  ui.modelSelect.parentElement.hidden = $('agent-select').value !== 'llm_cloud';
  document.querySelector('.model-tools').hidden = $('agent-select').value !== 'llm_cloud';
  if ($('agent-select').value !== 'llm_cloud') $('custom-model-fields').hidden = true;
  document.querySelector('.credentials-section').hidden = $('agent-select').value !== 'llm_cloud';
  ui.maxSteps.max = local ? '1000' : '100';
  ui.maxSteps.value = local ? '500' : '40';
  updateControls();
});
function jevCredentials() {
  const key = $('jev-api-key').value.trim();
  if (key && (key.length > 1000 || /[^\x21-\x7e]/.test(key))) throw new Error('TypeSafe API Key 格式无效，请检查空格或换行');
  if (!key && !state?.typesafe_key_configured) throw new Error('请在 Jev API Key 输入框填写 TypeSafe 专用密钥');
  return key ? {typesafe_api_key: key} : {};
}
function clearSubmittedJevKey(body, result) {
  if (result?.ok && body.typesafe_api_key && $('jev-api-key').value.trim() === body.typesafe_api_key) {
    $('jev-api-key').value = '';
  }
}
function jevSettings() {
  const numericFields = ['jev-timeout','jev-distance','jev-angle','jev-probability','jev-duration'];
  for (const id of numericFields) {
    const input = $(id);
    if (!input.value.trim() || !input.checkValidity() || !Number.isFinite(Number(input.value))) {
      throw new Error('请检查 Jev 步长、概率阈值和时限');
    }
  }
  return {model: $('jev-model').value.trim(), timeout_seconds: Number($('jev-timeout').value),
    translation_m: Number($('jev-distance').value) / 1000,
    rotation_degrees: Number($('jev-angle').value), min_probability: Number($('jev-probability').value),
    target_duration_seconds: Number($('jev-duration').value)};
}
function updateJevControls(locked) {
  const jev = $('agent-select').value === 'jev';
  $('jev-fields').hidden = !jev;
  for (const id of ['jev-model','jev-timeout','jev-distance','jev-angle','jev-probability','jev-duration','jev-diagnose','jev-example']) {
    const disabled = locked || !jev || !state?.jev_available;
    if ($(id).disabled !== disabled) $(id).disabled = disabled;
  }
  const entered = !!$('jev-api-key').value.trim();
  const keyControlsLocked = locked || !jev || !state?.typesafe_key_input_available;
  for (const [id, disabled] of [['jev-api-key', keyControlsLocked],
      ['jev-save-key', keyControlsLocked || !entered],
      ['jev-clear-key', keyControlsLocked || (!entered && !state?.typesafe_browser_key_configured)]]) {
    if ($(id).disabled !== disabled) $(id).disabled = disabled;
  }
  const message = !state?.typesafe_key_input_available ? '当前服务未加载网页密钥入口，请更新服务后刷新。'
    : entered ? '已填写，尚未提交；保存不收费，连接有效性请用下方诊断验证。'
    : state.typesafe_key_source === 'browser' ? '已保存在本次服务内存；留空复用。是否有效请查看诊断结果。'
    : state.typesafe_key_source === 'environment' ? '使用服务启动环境中的 TypeSafe 密钥；可在上方填写新密钥覆盖。'
    : '尚未配置。请在上方填写 TypeSafe 专用密钥，无需设置终端环境变量。';
  if ($('jev-key-status').textContent !== message) $('jev-key-status').textContent = message;
  if (jev && !state?.jev_available) ui.start.disabled = ui.step.disabled = true;
  if (jev && state?.policy_decision) $('jev-result').textContent = text(state.policy_decision);
  if (jev && state?.diagnostic_result?.provider === 'TypeSafe') $('jev-result').textContent = text(state.diagnostic_result);
}
$('jev-api-key').addEventListener('input', updateControls);
$('jev-save-key').addEventListener('click', async () => {
  if ($('jev-save-key').disabled) return;
  let body = {};
  try {
    body = jevCredentials();
    if (!body.typesafe_api_key) return;
    const result = await perform('/api/typesafe-key', body, 'Jev 密钥已保存在本次服务内存；没有调用模型。');
    clearSubmittedJevKey(body, result);
  } catch (error) { showError(error); }
  finally { delete body.typesafe_api_key; updateControls(); }
});
$('jev-clear-key').addEventListener('click', async () => {
  if ($('jev-clear-key').disabled) return;
  const result = await perform('/api/typesafe-key', {clear: true}, '已清除网页密钥；服务环境变量不受影响。');
  if (result?.ok) $('jev-api-key').value = '';
  updateControls();
});
$('jev-example').addEventListener('click', () => {
  if ($('jev-example').disabled) return;
  ui.task.value = 'Move up along world Z by 10 mm.\nRotate about the tool Z axis by 5 degrees.\nOpen the gripper.';
});
$('jev-diagnose').addEventListener('click', async () => {
  if ($('jev-diagnose').disabled) return;
  let body = {};
  try {
    body = {agent: 'jev', stage: 'action', jev_options: jevSettings(), ...jevCredentials()};
    const result = await perform('/api/diagnose', body, '已提交一次 Jev 选择诊断；不执行机器人动作。');
    clearSubmittedJevKey(body, result);
  } catch (error) { showError(error); }
  finally { delete body.typesafe_api_key; updateControls(); }
});

for (const stage of ['text','vision','action']) $('diagnose-' + stage).addEventListener('click', async () => {
  const body = {...selectedCredentials(), model: selectedModel(), request_options: requestSettings(), stage};
  if (!validateConfigSelection(body)) return;
  $('diagnostic-result').textContent = '正在提交诊断…';
  await perform('/api/diagnose', body, '已提交一次诊断请求，不执行机器人动作。');
  delete body.api_key; delete body.config_toml;
});
async function startEpisode(singleStep = false) {
  if (ui.start.disabled) return;
  if (!$('task-form').reportValidity()) return;
  const task = ui.task.value.trim();
  const model = selectedModel();
  const maxSteps = Number(ui.maxSteps.value);
  if (!task) { showError(new Error('请先输入任务指令。')); ui.task.focus(); return; }
  if ($('agent-select').value === 'llm_cloud' && ui.modelSelect.value === '__custom__' && !model) { showError(new Error('请填写自定义模型名称。')); ui.model.focus(); return; }
  if (!Number.isInteger(maxSteps) || maxSteps < 0 || maxSteps > Number(ui.maxSteps.max)) { showError(new Error('决策次数超出当前策略允许范围；0 表示不限次数。')); return; }
  const agent = $('agent-select').value;
  const body = {task, max_steps: maxSteps, agent, single_step: singleStep};
  if (agent === 'llm_cloud') Object.assign(body, selectedCredentials(), environmentSettings(), {
    model, request_options: requestSettings(), reset_on_start: $('reset-before-start').checked,
    context_mode: $('context-mode').value,
    max_wall_seconds: Number($('wall-budget').value), max_sim_seconds: Number($('sim-budget').value)
  });
  if (agent === 'jev') {
    try { body.jev_options = jevSettings(); Object.assign(body, jevCredentials()); }
    catch (error) { showError(error); return; }
  }
  if (agent === 'lerobot') Object.assign(body, {local_model: $('local-model').value, device: 'auto'});
  if (agent === 'llm_cloud' && !validateConfigSelection(body)) return;
  if (agent === 'llm_cloud' && body.credential_source === 'manual' && !body.api_key && !(state && state.manual_key_configured)) { showError(new Error('请填写 API 密钥，或选择本地配置文件。')); ui.key.focus(); return; }
  if (agent === 'llm_cloud') ui.key.value = '';
  try {
    const result = await perform('/api/start', body, singleStep ? '已提交一次模型决策；动作结束后暂停。' : '任务已提交，正在准备第一次模型决策。');
    if (agent === 'jev') clearSubmittedJevKey(body, result);
  } finally {
    delete body.api_key;
    delete body.config_toml;
    delete body.typesafe_api_key;
    updateControls();
  }
}
$('task-form').addEventListener('submit', event => {
  event.preventDefault();
  startEpisode(false);
});
ui.step.addEventListener('click', () => {
  if (ui.step.disabled) return;
  if (state && state.running && state.paused) perform('/api/step', {}, '已提交下一步；动作结束后暂停。');
  else startEpisode(true);
});
ui.pause.addEventListener('click', () => perform('/api/pause', {}, '完成当前动作后暂停。'));
ui.resume.addEventListener('click', () => perform('/api/resume', {}, '已恢复连续执行。'));
ui.task.addEventListener('keydown', event => {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    if (!ui.start.disabled) $('task-form').requestSubmit();
  }
});
ui.stop.addEventListener('click', () => perform('/api/stop', {}, '已请求停止后续决策。'));
ui.reset.addEventListener('click', () => {
  const seed = Number($('scene-seed').value);
  if (!Number.isInteger(seed) || seed < 0 || seed > 2147483647) { showError(new Error('场景种子应为 0 到 2147483647 之间的整数。')); return; }
  perform('/api/reset', {seed}, '场景已重新初始化。');
});
const tabs = [$('tab-observation'), $('tab-action')];
function selectTab(selected, focus = false) {
  for (const tab of tabs) {
    const active = tab === selected;
    tab.setAttribute('aria-selected', String(active));
    tab.tabIndex = active ? 0 : -1;
    $(tab.getAttribute('aria-controls')).hidden = !active;
  }
  if (focus) selected.focus();
}
tabs.forEach((tab, index) => {
  tab.addEventListener('click', () => selectTab(tab));
  tab.addEventListener('keydown', event => {
    if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      const next = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs[1] : tabs[1 - index];
      selectTab(next, true);
    }
  });
});
document.addEventListener('visibilitychange', () => { if (!document.hidden) { refreshState(); refreshCameras(); } });
window.addEventListener('pagehide', () => { ui.key.value = ''; $('jev-api-key').value = ''; });
updateModelChoices(); updateCredentialStatus();
refreshState(); refreshCameras(); loadConfigOptions();
setInterval(refreshState, 500);
setInterval(refreshCameras, 200);
