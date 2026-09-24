// Human jog controls only. Frame conversion stays on the server.
export const radians = degrees => degrees * Math.PI / 180;
const vector = (value, label) => {
  if (!Array.isArray(value) || value.length !== 3 || !value.every(Number.isFinite)) {
    throw new Error(`${label}必须包含三个有限数值`);
  }
  return [...value];
};
export function buildPoseCommand(position, rotation, reference, duration, state) {
  const p = vector(position, '平移'), r = vector(rotation, '旋转');
  if (!['fixed', 'tool'].includes(reference)) throw new Error('请选择固定轴或末端自身轴');
  const capability = state?.manual_control || {};
  const modern = capability.protocol === 'tcp_jog_fixed_tool_v1';
  if ((reference === 'tool' || r.some(v => v !== 0)) && !modern) {
    throw new Error('当前服务未加载六维控制，请更新服务后再操作');
  }
  const limits = state?.observation?.action_limits || {};
  for (const [v, key, label] of [[p, 'translation_max_m', '平移'], [r, 'rotation_max_rad', '旋转']]) {
    const limit = limits[key];
    if (!Number.isFinite(limit) || limit <= 0) throw new Error(`后端未声明${label}上限`);
    if (Math.hypot(...v) > limit + 1e-9) throw new Error(`${label}向量超过后端单步上限，请减小增量`);
  }
  const command = {kind: 'move', delta_position: p, delta_rotation: r, reference_frame: reference};
  if (capability.adjustable_target_duration) {
    if (!Number.isFinite(duration) || duration < 0.05 || duration > 10) throw new Error('手动跟踪时限须为 0.05 至 10 秒');
    command.target_duration_seconds = duration;
  }
  return command;
}

export function createManualControls({getState, perform, showError}) {
  const $ = id => document.getElementById(id);
  const fields = ['jog-step', 'rotation-step', 'manual-duration', 'manual-reference',
    'manual-dx', 'manual-dy', 'manual-dz', 'manual-rx', 'manual-ry', 'manual-rz'];
  let locked = true, sending = false;
  // No-op DOM writes can rebuild native select popups on macOS.
  // Polling updates status; it must not rewrite unchanged controls.
  const setText = (node, value) => { if (node.textContent !== value) node.textContent = value; };
  const setDisabled = (node, value) => { if (node.disabled !== value) node.disabled = value; };
  function number(id) {
    const input = $(id);
    if (!input.value.trim() || !input.checkValidity() || !Number.isFinite(Number(input.value))) {
      input.focus(); throw new Error('请填写有效的增量、角度或跟踪时限；空白不是零');
    }
    return Number(input.value);
  }
  async function run(callback) {
    if (locked || sending) return;
    sending = true;
    try { await callback(); } catch (error) { showError(error); }
    finally { sending = false; }
  }
  const sendPose = (position, rotation) => {
    const state = getState();
    const duration = state?.manual_control?.adjustable_target_duration ? number('manual-duration') : undefined;
    return perform('/api/manual', buildPoseCommand(position, rotation,
      $('manual-reference').value, duration, state));
  };
  for (const button of document.querySelectorAll('[data-axis], [data-rotation-axis]')) {
    button.addEventListener('click', () => run(() => {
      const p = [0, 0, 0], r = [0, 0, 0], sign = Number(button.dataset.sign);
      if (button.hasAttribute('data-rotation-axis')) r[Number(button.dataset.rotationAxis)] = sign * radians(number('rotation-step'));
      else p[Number(button.dataset.axis)] = sign * number('jog-step');
      return sendPose(p, r);
    }));
  }
  $('manual-pose-submit').addEventListener('click', () => run(() => sendPose(
    ['manual-dx', 'manual-dy', 'manual-dz'].map(id => number(id) / 1000),
    ['manual-rx', 'manual-ry', 'manual-rz'].map(id => radians(number(id))))));
  for (const [id, opening] of [['open-gripper', 1], ['close-gripper', 0]]) {
    $(id).addEventListener('click', () => run(() => perform('/api/manual', {kind: 'gripper', gripper_opening: opening})));
  }
  $('manual-zero').addEventListener('click', () => {
    if (locked) return;
    for (const id of fields.filter(id => /^manual-[dr][xyz]$/.test(id))) $(id).value = '0';
  });
  function updateFrame(state) {
    const tool = $('manual-reference').value === 'tool';
    setText($('manual-reference').options[0], state?.backend === 'mujoco' ? '固定轴（基座）' : '固定轴（世界）');
    setText($('manual-frame'), tool ? 'TCP 自身轴 · 平移 / 旋转' : `${state?.backend === 'mujoco' ? '基座' : '世界'}固定轴 · 平移 / 旋转`);
  }
  $('manual-reference').addEventListener('change', () => updateFrame(getState()));
  function update(state, disabled) {
    locked = disabled;
    const caps = state?.manual_control || {};
    const modern = caps.protocol === 'tcp_jog_fixed_tool_v1';
    for (const button of document.querySelectorAll('.manual-button')) {
      const requiresModern = button.hasAttribute('data-rotation-axis') || button.id === 'manual-pose-submit';
      setDisabled(button, disabled || (!modern && requiresModern));
    }
    for (const id of fields) {
      const unavailable = (!modern && ['manual-reference', 'rotation-step'].includes(id))
        || (id === 'manual-duration' && !caps.adjustable_target_duration);
      setDisabled($(id), disabled || unavailable);
    }
    if (!modern && $('manual-reference').value !== 'fixed') $('manual-reference').value = 'fixed';
    setDisabled($('manual-zero'), disabled);
    updateFrame(state);
    const limits = state?.observation?.action_limits || {};
    setText($('manual-limits'), Number.isFinite(limits.translation_max_m) && Number.isFinite(limits.rotation_max_rad)
      ? `单步向量上限：平移 ${(limits.translation_max_m * 1000).toFixed(0)} mm · 旋转 ${(limits.rotation_max_rad * 180 / Math.PI).toFixed(1)}°` : '正在读取后端动作范围…');
    const feedback = state?.last_feedback || {};
    const names = {ready: '等待操作', accepted: '指令已接受', executing: '正在跟踪',
      reached: '已到达', completed: '执行完成', timed_out: '跟踪超时', interrupted: '已停止', rejected: '指令被拒绝'};
    setText($('manual-status'), names[feedback.status] || '等待操作');
    if ($('manual-status').dataset.status !== (feedback.status || 'ready')) $('manual-status').dataset.status = feedback.status || 'ready';
    setText($('manual-position-error'), Number.isFinite(feedback.position_error_m) ? `${(feedback.position_error_m * 1000).toFixed(2)} mm` : '—');
    setText($('manual-rotation-error'), Number.isFinite(feedback.rotation_error_rad) ? `${(feedback.rotation_error_rad * 180 / Math.PI).toFixed(2)}°` : '—');
    setText($('manual-pose-feedback'), !modern ? '服务尚未加载新版六维控制；固定轴平移与夹爪仍可使用。'
      : state?.motion_busy ? '动作执行中；可随时使用上方“停止执行”。'
      : feedback.status === 'timed_out' ? '未在设定时限内达到目标。请检查误差，勿将超时当作到达。'
      : '误差由本体状态计算；执行完成不代表已抓取物体或任务成功。');
  }
  return {update};
}
