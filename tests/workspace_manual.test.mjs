// Pure frontend input tests. Node is used for tests only, never by the app.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const source = readFileSync(new URL('../src/maniloop/ui/manual-control.js', import.meta.url), 'utf8');
const {buildPoseCommand, radians, syncControlMode, actionLimitsDescription} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
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

function controlDOM(value = 'tcp_target_servo_v2') {
  const writes = [], record = (id, initial) => {
    const node = {};
    for (const [key, initialValue] of Object.entries(initial)) {
      let value = initialValue;
      Object.defineProperty(node, key, {get: () => value, set(next) { writes.push({id, key, value: next}); value = next; }});
    }
    return node;
  };
  const control = record('control', {value});
  const v3 = record('v3', {value: 'tcp_target_servo_v3', disabled: true});
  control.options = [{value: 'tcp_target_servo_v2'}, v3, {value: 'osc_step'}];
  return {control, v3, note: record('note', {textContent: ''}), writes};
}

test('server-started LIBERO v3 restores selection and explains target versus native scales', () => {
  const {control, v3, note} = controlDOM();
  syncControlMode(control, note, 'libero', 'tcp_target_servo_v3');
  assert.equal(control.value, 'tcp_target_servo_v3');
  assert.equal(v3.disabled, false);
  for (const value of ['2.5 m / 180°', '200', '10 秒', '20 Hz', '5 cm / 0.5 rad', '2 ms', '夹爪命令仍最多 20 步']) assert.ok(note.textContent.includes(value));
});

test('non-LIBERO backends disable v3 and safely fall back without changing old modes', () => {
  for (const backend of ['mujoco', 'robosuite', 'robocasa']) {
    const {control, v3, note} = controlDOM('tcp_target_servo_v3');
    syncControlMode(control, note, backend);
    assert.equal(control.value, 'tcp_target_servo_v2');
    assert.equal(v3.disabled, true);
    syncControlMode(control, note, backend, 'osc_step');
    assert.equal(control.value, 'osc_step');
    syncControlMode(control, note, backend, 'tcp_target_servo_v2');
    assert.equal(control.value, 'tcp_target_servo_v2');
  }
});

test('unchanged control refresh preserves selection without rebuilding the native menu', () => {
  const {control, note, writes} = controlDOM();
  syncControlMode(control, note, 'libero', 'tcp_target_servo_v3');
  writes.length = 0;
  for (let i = 0; i < 100; i++) syncControlMode(control, note, 'libero');
  assert.deepEqual(writes, []);
  syncControlMode(control, note, 'libero', 'tcp_target_servo_v2');
  assert.equal(control.value, 'tcp_target_servo_v2');
  assert.match(note.textContent, /最长 1 秒/);
});

test('manual v3 validates advertised planning bounds, preserving the independent duration', () => {
  const wide = {...state, backend: 'libero', environment: {llm_control: 'tcp_target_servo_v3'},
    observation: {action_limits: {translation_max_m: 2.5, rotation_max_rad: Math.PI}}};
  const command = buildPoseCommand([0.4,0,0], [0,0,Math.PI], 'fixed', 3, wide);
  assert.equal(command.delta_position[0], 0.4);
  assert.equal(command.target_duration_seconds, 3);
  assert.throws(() => buildPoseCommand([2.51,0,0], [0,0,0], 'fixed', 3, wide));
  assert.throws(() => buildPoseCommand([0,0,0], [0,0,Math.PI + 0.01], 'fixed', 3, wide));
  const label = actionLimitsDescription(wide);
  assert.match(label, /规划目标向量上限：平移 2500 mm · 旋转 180.0°/);
  assert.match(label, /原生控制：20 Hz，每步尺度 50 mm \/ 0.5 rad/);
  assert.match(actionLimitsDescription(state), /单步向量上限：平移 50 mm/);
});
