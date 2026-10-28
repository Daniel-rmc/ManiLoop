import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const source = readFileSync(new URL('../src/maniloop/ui/chatgpt-plan.js', import.meta.url), 'utf8');
const {authorizationURL, createChatGPTPlanControls, connectionModels, defaultReasoningLabel} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const authorized = {accounts: [{id: 'account-a', label: 'Account A', logged_in: true, plan_enabled: true}], active_account_id: 'account-a', pending: false, error: ''};

function fixture(initial = authorized) {
  const nodes = new Map(), calls = [], errors = [], changes = [], opened = [];
  const node = () => ({value: '', children: [], events: {}, rebuilds: 0,
    appendChild(item) { this.children.push(item); },
    replaceChildren() { this.children = []; this.rebuilds++; },
    addEventListener(name, fn) { this.events[name] = fn; }});
  const document = {getElementById(id) { if (!nodes.has(id)) nodes.set(id, node()); return nodes.get(id); }, createElement: node};
  const get = id => document.getElementById('chatgpt-' + id);
  let current = structuredClone(initial), loginURL = 'https://auth.openai.com/api/accounts/authorize?state=offline';
  let popupAllowed = true;
  const window = {
    open(url) {
      if (!popupAllowed) return null;
      const popup = {closed: false, opener: 'original', url,
        location: {replace(value) { popup.url = value; }}, close() { this.closed = true; }};
      opened.push(popup); return popup;
    },
    addEventListener() {}, setTimeout() { return 1; }, clearTimeout() {}
  };
  const request = async (path, body) => {
    calls.push({path, body});
    if (path === '/api/chatgpt/status') return structuredClone(current);
    if (path === '/api/chatgpt/login') { current.pending = true; return {ok: true, authorization_url: loginURL}; }
    if (path === '/api/chatgpt/cancel') { current.pending = false; return {ok: true, pending: false}; }
    if (path === '/api/chatgpt/logout') { current.accounts[0].logged_in = false; return {ok: true}; }
    if (path === '/api/chatgpt/select') { current.active_account_id = body.account_id; return {ok: true}; }
    throw Error('Unexpected route ' + path);
  };
  const controls = createChatGPTPlanControls({request, document, window,
    onChanged: () => changes.push('change'), showError: err => errors.push(err.message), showToast() {}});
  return {controls, get, calls, opened, errors, changes,
    setStatus(value) { current = structuredClone(value); }, setURL(value) { loginURL = value; }, blockPopup() { popupAllowed = false; }};
}

test('only the documented HTTPS authorization endpoint may open', () => {
  assert.match(authorizationURL('https://auth.openai.com/api/accounts/authorize?state=abc'), /state=abc/);
  for (const url of ['javascript:alert(1)', 'http://auth.openai.com/api/accounts/authorize',
    'https://auth.openai.com.evil.invalid/api/accounts/authorize', 'https://auth.openai.com/other',
    'https://user:pass@auth.openai.com/api/accounts/authorize', 'https://auth.openai.com/api/accounts/authorize#x']) {
    assert.throws(() => authorizationURL(url));
  }
});

test('plan catalog excludes stale selections and configured default models', () => {
  assert.deepEqual(connectionModels('chatgpt_plan', ['gpt-6-astra', 'provider-default'], ['account-model', 'account-model'], 'old-account-model'), ['account-model']);
  assert.deepEqual(connectionModels('chatgpt_plan', ['gpt-6-astra'], [], 'old-account-model'), []);
  assert.deepEqual(connectionModels('manual', ['provider-default'], ['listed'], 'custom-id'), ['provider-default', 'listed', 'custom-id']);
});

test('plan auto label states its actual low reasoning setting', () => {
  assert.equal(defaultReasoningLabel('chatgpt_plan'), 'low（套餐直连默认）');
  assert.equal(defaultReasoningLabel('manual'), '模型默认');
});

test('retry uses the retained registration without supplying another account', async () => {
  const f = fixture({...authorized, registration_retry_available: true}); await f.controls.refresh();
  assert.equal(f.get('retry-registration').hidden, false);
  await f.get('retry-registration').events.click();
  assert.deepEqual(f.calls[1], {path: '/api/chatgpt/login', body: {retry_registration: true}});
  assert.equal(f.get('retry-registration').disabled, true);
});

test('retry is unavailable without a retained registration', async () => {
  const f = fixture(); await f.controls.refresh();
  assert.equal(f.get('retry-registration').hidden, true);
  await f.get('retry-registration').events.click();
  assert.equal(f.calls.length, 1);
});

test('login opens an isolated browser window and never triggers model inference', async () => {
  const f = fixture({accounts: [], pending: false}); await f.controls.refresh();
  await f.get('login').events.click();
  assert.equal(f.opened[0].opener, null);
  assert.match(f.opened[0].url, /^https:\/\/auth.openai.com/);
  assert.equal(f.get('login').disabled, true);
  assert.equal(f.get('cancel').hidden, false);
  assert.deepEqual(f.calls.map(x => x.path), ['/api/chatgpt/status', '/api/chatgpt/login']);
  assert.deepEqual(f.calls[1].body, {});
});

test('reauthorization sends only the selected account id', async () => {
  const f = fixture(); await f.controls.refresh();
  await f.get('reauthorize').events.click();
  assert.deepEqual(f.calls[1], {path: '/api/chatgpt/login', body: {account_id: 'account-a'}});
});

test('running sessions lock account changes and authorization', async () => {
  const f = fixture(); await f.controls.refresh(); f.controls.update(true);
  assert.equal(f.get('logout').disabled, true);
  assert.equal(f.get('account').disabled, true);
  const before = f.calls.length;
  await f.get('login').events.click();
  await f.get('logout').events.click();
  assert.equal(f.calls.length, before);
});

test('repeated status refresh preserves the account select and model identity', async () => {
  const f = fixture(); await f.controls.refresh();
  const rebuilds = f.get('account').rebuilds, changes = f.changes.length;
  for (let i = 0; i < 5; i++) { await f.controls.refresh(); f.controls.update(false); }
  assert.equal(f.get('account').rebuilds, rebuilds);
  assert.equal(f.changes.length, changes);
  assert.equal(f.controls.ready(), true);
  f.setStatus({...authorized, accounts: [{...authorized.accounts[0], plan_enabled: false}]});
  await f.controls.refresh();
  assert.equal(f.controls.ready(), false);
  assert.equal(f.changes.length, changes + 1);
});

test('a popup reported closed cannot cancel the pending backend authorization', async () => {
  const f = fixture(); await f.controls.refresh(); await f.get('login').events.click();
  f.opened[0].close(); await f.controls.refresh();
  assert.equal(f.calls.at(-1).path, '/api/chatgpt/status');
  assert.equal(f.calls.some(call => call.path === '/api/chatgpt/cancel'), false);
  assert.equal(f.controls.pending(), true);
  assert.equal(f.get('cancel').hidden, false);
  // The same pending attempt can complete after a cross-origin navigation.
  f.setStatus(authorized); await f.controls.refresh();
  assert.equal(f.controls.ready(), true);
  assert.equal(f.controls.pending(), false);
});

test('an explicit cancel still stops the pending authorization', async () => {
  const f = fixture(); await f.controls.refresh(); await f.get('login').events.click();
  await f.get('cancel').events.click();
  assert.equal(f.calls.some(call => call.path === '/api/chatgpt/cancel'), true);
  assert.equal(f.controls.pending(), false);
});

test('invalid authorization URL closes the popup and cancels server attempt', async () => {
  const f = fixture(); await f.controls.refresh(); f.setURL('https://evil.invalid/');
  await f.get('login').events.click();
  assert.equal(f.opened[0].closed, true);
  assert.equal(f.calls.at(-1).path, '/api/chatgpt/cancel');
  assert.equal(f.errors.length, 1);
});

test('blocked popups never start server authorization', async () => {
  const f = fixture(); f.blockPopup(); await f.get('login').events.click();
  assert.equal(f.calls.length, 0); assert.equal(f.errors.length, 1);
});

test('logout retains account identity while preventing inference', async () => {
  const f = fixture(); await f.controls.refresh(); await f.get('logout').events.click();
  assert.equal(f.controls.ready(), false);
  assert.equal(f.controls.accountId(), 'account-a');
  assert.deepEqual(f.calls.find(x => x.path.endsWith('/logout')).body, {account_id: 'account-a'});
});
