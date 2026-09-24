// Presentation state never resets physics, starts a model, or stores credentials.
export function createWorkspaceLayout({perform}) {
  const $ = id => document.getElementById(id);
  const tabs = [...document.querySelectorAll('[data-workspace-tab]')];
  let initialized = false;
  function activate(view, focus = false) {
    for (const tab of tabs) {
      const selected = tab.dataset.workspaceTab === view;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      $(tab.getAttribute('aria-controls')).hidden = !selected;
      if (selected && focus) tab.focus();
    }
  }
  for (const [index, tab] of tabs.entries()) {
    tab.addEventListener('click', () => activate(tab.dataset.workspaceTab));
    tab.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1
        : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      activate(tabs[next].dataset.workspaceTab, true);
    });
  }
  $('task-form').addEventListener('invalid', event => {
    activate('model');
    for (let parent = event.target.parentElement; parent; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
    }
  }, true);
  $('workspace-stop').addEventListener('click', () => {
    if (!$('workspace-stop').disabled) perform('/api/stop', {}, '已请求停止执行。');
  });
  $('camera-layout-button').addEventListener('click', () => {
    const viewport = $('camera-viewport');
    const dual = viewport.dataset.layout !== 'dual';
    viewport.dataset.layout = dual ? 'dual' : 'pip';
    $('camera-layout-button').setAttribute('aria-pressed', String(dual));
    $('camera-layout-button').textContent = dual ? '画中画' : '双相机并排';
  });
  function update(state, {connected, pending}) {
    if (!initialized && state) {
      activate(state.running ? 'model' : 'manual');
      initialized = true;
    }
    $('workspace-context').textContent = state
      ? `${state.backend} / ${state.task_id} · ${state.robot}` : '等待场景连接';
    $('workspace-stop').disabled = pending || !connected ||
      !(state?.running || state?.motion_busy || state?.pending_request);
    $('workspace-run-state').textContent = !connected ? '服务未连接'
      : state?.pending_request ? '模型推理中' : state?.motion_busy ? '动作执行中'
      : state?.paused ? '实验已暂停' : state?.running ? '实验运行中' : '手动预览 · 不调用模型';
    $('workspace-run-state').dataset.active = String(!!(state?.running || state?.motion_busy));
  }
  activate('manual');
  return {activate, update};
}
