// Pure frontend input tests. Node is used for tests only, never by the app.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const source = readFileSync(new URL('../src/maniloop/ui/manual-control.js', import.meta.url), 'utf8');
const {buildPoseCommand, radians} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const state = {
  manual_control: {protocol: 'tcp_jog_fixed_tool_v1', adjustable_target_duration: true},
  observation: {action_limits: {translation_max_m: 0.05, rotation_max_rad: 0.5}}
};

test('SI command preserves input and leaves frame conversion to the server', () => {
  const p = [0.003, 0, 0], r = [0, 0, radians(5)];
  const command = buildPoseCommand(p, r, 'tool', 3, state);
  assert.deepEqual(command, {kind: 'move', delta_position: p, delta_rotation: r,
    reference_frame: 'tool', target_duration_seconds: 3});
  command.delta_position[0] = 1;
  assert.equal(p[0], 0.003);
});

test('invalid and oversized vectors are rejected, not clipped', () => {
  for (const [p, r] of [ [[0.06,0,0],[0,0,0]], [[0,0,0],[0.4,0.4,0]],
    [[NaN,0,0],[0,0,0]], [[0,0],[0,0,0]], [[true,0,0],[0,0,0]],
    [[0,0,0],[Infinity,0,0]], [[0,0,0],['0',0,0]] ]) {
    assert.throws(() => buildPoseCommand(p, r, 'fixed', 3, state));
  }
});

test('missing limits and invalid frame fail before submission', () => {
  assert.throws(() => buildPoseCommand([0,0,0], [0,0,0], 'camera', 3, state));
  assert.throws(() => buildPoseCommand([0,0,0], [0,0,0], 'fixed', 3,
    {...state, observation: {}}));
});

test('manual duration validates independently of the motion vector', () => {
  for (const value of [0, -1, 11, '3', null, NaN, Infinity, true]) {
    assert.throws(() => buildPoseCommand([0,0,0], [0,0,0], 'fixed', value, state));
  }
  assert.equal(buildPoseCommand([0,0,0], [0,0,0], 'fixed', 10, state).target_duration_seconds, 10);
});

test('legacy capability cannot silently execute tool or rotation commands', () => {
  const legacy = {...state, manual_control: {}};
  assert.throws(() => buildPoseCommand([0,0,0], [0,0,0.1], 'fixed', 3, legacy));
  assert.throws(() => buildPoseCommand([0.01,0,0], [0,0,0], 'tool', 3, legacy));
  const command = buildPoseCommand([0.01,0,0], [0,0,0], 'fixed', undefined, legacy);
  assert.equal('target_duration_seconds' in command, false);
});

// A select's native popup must not be rebuilt by background status polling.
const {createManualControls} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
function manualDOM() {
  const nodes = new Map(), writes = [];
  function element(id) {
    const values = {textContent: '', disabled: false, value: '0'};
    const node = {id, dataset: {}, events: {},
      addEventListener(name, callback) { this.events[name] = callback; },
      hasAttribute(name) { return name === 'data-rotation-axis' && id === 'rotation-button'; },
      checkValidity() { return true; }, focus() {}};
    for (const key of Object.keys(values)) Object.defineProperty(node, key, {
      get: () => values[key],
      set(value) { writes.push({id, key, value}); values[key] = value; }
    });
    return node;
  }
  const get = id => { if (!nodes.has(id)) nodes.set(id, element(id)); return nodes.get(id); };
  get('manual-reference').options = [element('fixed-option'), element('tool-option')];
  get('manual-reference').value = 'fixed';
  const buttons = ['move-button', 'rotation-button', 'manual-pose-submit', 'open-gripper', 'close-gripper'].map(get);
  const document = {getElementById: get, querySelectorAll(selector) {
    return selector === '.manual-button' ? buttons : selector.includes('#manual-pose-submit')
      ? [get('rotation-button'), get('manual-pose-submit')] : [get('move-button'), get('rotation-button')];
  }};
  return {document, get, writes, menuWrites: () => writes.filter(w => ['manual-reference', 'fixed-option', 'tool-option'].includes(w.id))};
}

test('repeated polling never mutates the open reference menu or resets the choice', t => {
  const dom = manualDOM(), prior = globalThis.document;
  globalThis.document = dom.document;
  t.after(() => { globalThis.document = prior; });
  let current = {...state, backend: 'robosuite'};
  const controls = createManualControls({getState: () => current,
    perform: () => { throw new Error('Unexpected request'); }, showError: error => { throw error; }});
  controls.update(current, false);
  dom.get('manual-reference').value = 'tool';
  dom.get('manual-reference').events.change();
  dom.writes.length = 0;
  for (let i = 0; i < 100; i++) controls.update({...current, api_calls: i}, false);
  assert.deepEqual(dom.menuWrites(), []);
  assert.equal(dom.get('manual-reference').value, 'tool');
  controls.update(current, true);
  assert.equal(dom.get('manual-reference').disabled, true);
  dom.writes.length = 0;
  controls.update(current, true);
  assert.deepEqual(dom.menuWrites(), []);
  controls.update(current, false);
  current = {...current, backend: 'mujoco'};
  controls.update(current, false);
  assert.equal(dom.get('manual-reference').options[0].textContent, '固定轴（基座）');
  assert.equal(dom.get('manual-reference').value, 'tool');
  dom.writes.length = 0;
  controls.update(current, false);
  assert.deepEqual(dom.menuWrites(), []);
});

test('legacy capability stays disabled without briefly enabling on each poll', t => {
  const dom = manualDOM(), prior = globalThis.document;
  globalThis.document = dom.document;
  t.after(() => { globalThis.document = prior; });
  const legacy = {...state, manual_control: {}, backend: 'libero'};
  const controls = createManualControls({getState: () => legacy, perform() {}, showError() {}});
  controls.update(legacy, false);
  assert.equal(dom.get('manual-reference').disabled, true);
  assert.equal(dom.get('manual-reference').value, 'fixed');
  dom.writes.length = 0;
  controls.update(legacy, false);
  assert.deepEqual(dom.menuWrites(), []);
});
