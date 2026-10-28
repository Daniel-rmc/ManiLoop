// Account controls share the local backend; credentials never enter browser storage.
export function authorizationURL(value) {
  const url = new URL(value);
  if (url.origin !== 'https://auth.openai.com' || url.pathname !== '/api/accounts/authorize'
      || url.username || url.password || url.hash) throw new Error('授权地址无效；未打开登录窗口。');
  return url.href;
}

export function connectionModels(source, configuredModels, fetchedModels, selected) {
  const candidates = source === 'chatgpt_plan' ? fetchedModels : [...configuredModels, ...fetchedModels, selected];
  return [...new Set(candidates.filter(model => typeof model === 'string' && model && model !== '__custom__'))];
}

export function defaultReasoningLabel(source) {
  return source === 'chatgpt_plan' ? 'low（套餐直连默认）' : '模型默认';
}

export function createChatGPTPlanControls({request, onChanged, showError, showToast,
  document = globalThis.document, window = globalThis.window}) {
  const get = id => document.getElementById(id);
  const account = get('chatgpt-account');
  const login = get('chatgpt-login'), again = get('chatgpt-reauthorize');
  const retry = get('chatgpt-retry-registration');
  const logout = get('chatgpt-logout'), cancel = get('chatgpt-cancel');
  const status = get('chatgpt-status');
  let data = {accounts: [], active_account_id: null, pending: false, error: ''};
  let locked = false, busy = false, polling = false, timer = null, popup = null;
  let fingerprint = '', modelIdentity = '';
  const active = () => data.accounts.find(item => item.id === data.active_account_id);
  const ready = () => !!(active()?.logged_in && active()?.plan_enabled);
  function render() {
    const next = JSON.stringify([data.accounts, data.active_account_id]);
    // Status polling must not continually rebuild an open account select.
    if (next !== fingerprint) {
      fingerprint = next;
      account.replaceChildren();
      const empty = document.createElement('option');
      empty.value = ''; empty.textContent = '选择已保存的 ChatGPT 账号'; account.appendChild(empty);
      for (const item of data.accounts) {
        const option = document.createElement('option'); option.value = item.id;
        option.textContent = item.label + (item.logged_in ? item.plan_enabled ? '' : ' · 未启用套餐授权' : ' · 已退出');
        account.appendChild(option);
      }
      account.value = data.active_account_id || '';
    }
    status.textContent = data.pending ? '请在授权窗口完成登录；完成后此处会自动更新。若已关闭窗口，可点击「取消授权」后重新开始。'
      : data.error || (ready() ? '已授权 · 使用 ChatGPT 套餐直连；模型可用性需通过诊断验证。'
        : active()?.logged_in ? '已登录，但未授予套餐使用权限。请重新授权后再诊断。'
          : '尚未连接。授权仅用于此 ManiLoop 安装，与 Codex CLI 登录独立。');
    account.disabled = locked || busy || data.pending;
    login.disabled = locked || busy || data.pending;
    again.disabled = locked || busy || data.pending || !active();
    retry.hidden = !data.registration_retry_available;
    retry.disabled = locked || busy || data.pending || !data.registration_retry_available;
    logout.disabled = locked || busy || data.pending || !active()?.logged_in;
    cancel.hidden = !data.pending;
    cancel.disabled = locked || busy || !data.pending;
    const identity = JSON.stringify([data.active_account_id, ready()]);
    if (identity !== modelIdentity) { modelIdentity = identity; onChanged(); }
  }
  function schedule() {
    if (timer !== null) window.clearTimeout(timer);
    timer = data.pending ? window.setTimeout(() => refresh(), 1000) : null;
  }
  async function refresh({quiet = false} = {}) {
    if (polling) return;
    polling = true;
    try {
      const result = await request('/api/chatgpt/status');
      data = {...result, accounts: Array.isArray(result.accounts) ? result.accounts : []};
      // Cross-origin opener isolation and embedded browsers can report a live
      // authorization window as closed. Only the backend callback/expiry or an
      // explicit cancel may end the attempt; never infer cancellation here.
      render();
    } catch (error) { if (!quiet) showError(error); }
    finally { polling = false; schedule(); }
  }
  async function authenticate(accountId, retryRegistration = false) {
    if (locked || busy || data.pending) return;
    if (retryRegistration && !data.registration_retry_available) return;
    // Open synchronously in the click handler to avoid popup blockers.
    popup = window.open('about:blank', '_blank');
    if (!popup) { showError(new Error('浏览器阻止了授权窗口，请允许此本地页面打开弹窗后重试。')); return; }
    popup.opener = null;
    busy = true; render();
    try {
      const body = retryRegistration ? {retry_registration: true} : accountId ? {account_id: accountId} : {};
      const result = await request('/api/chatgpt/login', body);
      popup.location.replace(authorizationURL(result.authorization_url));
      data = {...data, pending: true, error: ''};
    } catch (error) {
      popup.close(); popup = null;
      // A rejected or malformed URL must not leave a live authorization attempt.
      try { await request('/api/chatgpt/cancel', {}); } catch (_) { /* backend expires pending attempts */ }
      showError(error);
    } finally { busy = false; render(); schedule(); }
  }
  async function change(path, body, message) {
    if (locked || busy || (data.pending && path !== 'cancel')) return;
    busy = true; render();
    try {
      const result = await request('/api/chatgpt/' + path, body);
      if (path === 'cancel' && popup) { popup.close(); popup = null; }
      if (result.warning) showToast(result.warning); else if (message) showToast(message);
      await refresh();
    } catch (error) { showError(error); await refresh({quiet: true}); }
    finally { busy = false; render(); }
  }
  login.addEventListener('click', () => authenticate(null));
  again.addEventListener('click', () => authenticate(data.active_account_id));
  retry.addEventListener('click', () => authenticate(null, true));
  logout.addEventListener('click', () => change('logout', {account_id: data.active_account_id}, '已退出此 ManiLoop 账号连接。'));
  cancel.addEventListener('click', () => change('cancel', {}, '已取消本次授权。'));
  account.addEventListener('change', () => {
    if (!account.value) { account.value = data.active_account_id || ''; return; }
    change('select', {account_id: account.value}, '已切换 ChatGPT 账号，请重新读取模型列表。');
  });
  window.addEventListener('pagehide', () => { if (timer !== null) window.clearTimeout(timer); });
  return {refresh, ready, accountId: () => data.active_account_id,
    update(value) { locked = value; render(); }, pending: () => busy || data.pending};
}
