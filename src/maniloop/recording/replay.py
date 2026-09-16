"""Self-contained human review artifact; never used to construct policy input."""

import base64
import hashlib
import json
import math
from pathlib import Path
import re

from maniloop.core.observations import FEEDBACK_FIELDS, PAIR_SENSOR_FIELDS


def load_latest_replay(output):
    """Restore the most recent generated review when the local UI restarts."""
    root = Path(output)
    if not root.is_dir():
        return b""
    for run in sorted(root.iterdir(), reverse=True):
        if not re.fullmatch(r"\d{8}-\d{6}-[0-9a-f]{8}", run.name) or run.is_symlink() or not run.is_dir():
            continue
        path = run / "replay.html"
        if path.is_file() and not path.is_symlink() and path.stat().st_size <= 64 * 1024 * 1024:
            return path.read_bytes()
    return b""


_POLICY_FIELDS = {
    "kind", "model", "representation", "controller", "action_interface", "timing",
    "memory", "context_mode", "max_decisions", "max_sim_seconds", "max_wall_seconds",
    "diagnostic_stage", "implementation_sha256", "execution_cadence", "initial_cadence",
    "feedback_protocol", "human_pause_budget",
}
_REQUEST_FIELDS = {
    "timeout_seconds", "reasoning_effort", "max_output_tokens", "transport",
    "policy_retries", "transport_retries", "ephemeral", "agent_tools", "output_limit", "output_limit_chars", "cli_version",
}
_ACTION_FIELDS = {
    "observation_id", "kind", "delta_position", "delta_rotation", "gripper_opening",
    "pixel", "camera", "explanation", "interval_seconds", "frame", "actions",
}
_SUMMARY_FIELDS = {
    "api_calls", "step_count", "termination_reason", "error", "paused", "phase",
    "diagnostic_stage", "human_pause_used",
}
_EVALUATION_FIELDS = {
    "success", "current_success", "native_success", "evaluator", "control_steps",
    "terminated", "score", "elapsed_seconds", "distance_to_target", "stable_steps",
    "in_target", "stable", "released", "task", "lifted", "invalid_lift", "criterion",
}
_SECRET_FIELDS = {
    "api_key", "key", "token", "access_token", "refresh_token", "password", "secret",
    "authorization", "credentials", "config_path", "private_config", "base_url", "endpoint",
}


def _json_value(value):
    """Copy JSON values only; metadata objects cannot leak through repr/default=str."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        return value if math.isfinite(value) else None
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _json_value(item)
            for key, item in value.items()
            if isinstance(key, str) and key.lower() not in _SECRET_FIELDS
        }
    return None


def _select(value, fields):
    if not isinstance(value, dict):
        return {}
    return {key: _json_value(item) for key, item in value.items() if key in fields}


def _image_url(data):
    if not isinstance(data, bytes):
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    else:
        # In particular SVG and supplied URLs are not active image content here.
        return None
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def render_replay(*, manifest: dict, frames: list[dict], events: list[dict], summary: dict) -> bytes:
    """Render the supplied sensor frames and independent score for offline review.

    Input order is the timeline order. Events are associated only by their explicit
    request_index; unindexed events remain visible in the complete event log.
    This function reads no files, environment variables, or authentication state.
    """
    policy = manifest.get("policy", {})
    provenance = _select(manifest, {
        "version", "mode", "robot", "scene", "task", "seed", "instruction",
        "comparison_group", "source_sha256", "context_mode",
    })
    provenance["policy"] = _select(policy, _POLICY_FIELDS)
    provenance["policy"]["request_options"] = _select(
        policy.get("request_options", {}) if isinstance(policy, dict) else {}, _REQUEST_FIELDS,
    )
    safe_frames = []
    for frame in frames:
        observation = _select(frame.get("observation", {}), PAIR_SENSOR_FIELDS)
        images = {}
        for camera, content in frame.get("images", {}).items():
            if isinstance(camera, str) and (url := _image_url(content)):
                images[camera] = url
        safe_frames.append({
            "request_index": frame.get("request_index") if type(frame.get("request_index")) is int else None,
            "phase": frame.get("phase") if frame.get("phase") in {"before", "after", "final"} else "before",
            "observation": observation,
            "images": images,
        })
    safe_events = []
    for event in events:
        entry = _select(event, {"time", "type", "message", "request_index", "latency_seconds", "category", "http_status"})
        if "action" in event:
            entry["action"] = _select(event["action"], _ACTION_FIELDS)
        if "feedback" in event:
            entry["feedback"] = _select(event["feedback"], FEEDBACK_FIELDS)
        safe_events.append(entry)
    data = {
        "provenance": provenance,
        "frames": safe_frames,
        "events": safe_events,
        "summary": _select(summary, _SUMMARY_FIELDS),
        "evaluation": _select(summary.get("evaluation", {}), _EVALUATION_FIELDS),
    }
    # JSON lives in a non-executable script element. Escape HTML delimiters before
    # embedding so a model explanation cannot close that element or inject markup.
    encoded = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    for char, escaped in (("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e"), ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        encoded = encoded.replace(char, escaped)
    script_hash = base64.b64encode(hashlib.sha256(_SCRIPT.encode("utf-8")).digest()).decode("ascii")
    return _HTML.replace("__SCRIPT_HASH__", script_hash).replace("__SCRIPT__", _SCRIPT).replace("__DATA__", encoded).encode("utf-8")


_SCRIPT = r"""
'use strict';
const data = JSON.parse(document.getElementById('replay-data').textContent);
const $ = id => document.getElementById(id);
const pretty = value => JSON.stringify(value, null, 2);
const text = (id, value) => { $(id).textContent = value; };
const summary = data.summary;
const policy = data.provenance.policy || {};
text('task', data.provenance.instruction || data.provenance.task || '未记录任务描述');
text('model', policy.model || policy.kind || '未记录模型');
text('calls', summary.api_calls ?? '—');
text('steps', summary.step_count ?? '—');
text('termination', summary.termination_reason || (summary.paused ? 'paused' : summary.phase) || '未记录');
text('summary', pretty(summary));
text('provenance', pretty(data.provenance));
text('events', pretty(data.events));
text('evaluation', pretty(data.evaluation));
const success = data.evaluation.success;
text('score', success === true ? '独立评分：成功' : success === false ? '独立评分：未成功' : '独立评分：未提供');
$('score').classList.add(success === true ? 'success' : success === false ? 'failure' : 'unknown');
const done = data.events.filter(event => event.action?.kind === 'done');
text('declaration', done.length ? '模型曾声明 done。该声明不等于独立评分成功。' : '未记录模型 done 声明。');
if (summary.error) { text('error', summary.error); $('error').hidden = false; }
const frames = data.frames;
let index = Math.max(0, frames.length - 1);
$('slider').max = Math.max(0, frames.length - 1);
function draw() {
  const frame = frames[index];
  $('slider').value = index;
  $('slider').disabled = frames.length < 2;
  $('previous').disabled = !frames.length || index === 0;
  $('next').disabled = !frames.length || index === frames.length - 1;
  $('images').replaceChildren();
  if (!frame) {
    text('position', '没有保存相机帧');
    text('sensors', '{}'); text('decision', '没有关联的决策'); text('feedback', '没有关联的执行反馈');
    const empty = document.createElement('p');
    empty.className = 'empty'; empty.textContent = '本次运行尚无图像，诊断与错误仍可在下方查看。';
    $('images').append(empty); return;
  }
  const phase = {before:'决策前', after:'执行后', final:'末帧'}[frame.phase];
  text('position', `${index + 1} / ${frames.length} · 请求 ${frame.request_index ?? '—'} · ${phase}`);
  text('sensors', pretty(frame.observation));
  const matches = frame.request_index === null ? [] : data.events.filter(event => event.request_index === frame.request_index);
  const decisions = matches.filter(event => event.action).map(event => ({action:event.action, latency_seconds:event.latency_seconds}));
  const feedback = matches.filter(event => event.feedback).map(event => ({type:event.type, feedback:event.feedback}));
  text('decision', decisions.length ? pretty(decisions) : '没有关联的决策');
  text('feedback', feedback.length ? pretty(feedback) : '没有关联的执行反馈');
  for (const [camera, source] of Object.entries(frame.images)) {
    const figure = document.createElement('figure');
    const image = document.createElement('img'); image.src = source; image.alt = camera;
    const caption = document.createElement('figcaption'); caption.textContent = camera;
    figure.append(image, caption); $('images').append(figure);
  }
  if (!Object.keys(frame.images).length) {
    const empty = document.createElement('p'); empty.className = 'empty'; empty.textContent = '此帧没有保存 PNG / JPEG 图像。'; $('images').append(empty);
  }
}
$('previous').addEventListener('click', () => { index = Math.max(0, index - 1); draw(); });
$('next').addEventListener('click', () => { index = Math.min(frames.length - 1, index + 1); draw(); });
$('slider').addEventListener('input', event => { index = Number(event.target.value); draw(); });
document.addEventListener('keydown', event => {
  if (event.target.tagName === 'INPUT') return;
  if (event.key === 'ArrowLeft') { index = Math.max(0, index - 1); draw(); }
  if (event.key === 'ArrowRight' && frames.length) { index = Math.min(frames.length - 1, index + 1); draw(); }
});
draw();
"""

_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'sha256-__SCRIPT_HASH__'; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>ManiLoop · 操作回看</title>
<style>
:root{color-scheme:light;--ink:#202d35;--muted:#62727c;--line:#dce4e8;--blue:#245f78;--paper:#fff}
*{box-sizing:border-box}body{margin:0;background:#f3f6f7;color:var(--ink);font:15px/1.55 system-ui,-apple-system,sans-serif}
main{max-width:1240px;margin:auto;padding:32px 24px 64px}header{margin-bottom:22px}.eyebrow{font-size:12px;letter-spacing:2px;color:var(--blue);font-weight:700}h1{font-size:30px;margin:8px 0}h2{font-size:17px;margin:0 0 12px}h3{font-size:14px;margin:0 0 10px}p{margin:8px 0}.muted{color:var(--muted)}
.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:20px 0}.card,.panel{border:1px solid var(--line);border-radius:12px;background:var(--paper);padding:18px}.card small{display:block;color:var(--muted)}.card strong{display:block;margin-top:7px;font-size:18px;overflow-wrap:anywhere}
.audit{border-left:5px solid #b0803d;background:#fffaf1}.audit p{font-size:13px}.success{color:#287247}.failure{color:#9b502c}.unknown{color:var(--muted)}
.timeline{display:flex;align-items:center;gap:12px;margin:18px 0 12px}.timeline input{flex:1;min-width:40px;accent-color:var(--blue)}button{padding:9px 15px;border:1px solid var(--line);border-radius:8px;background:white;color:var(--ink);cursor:pointer}button:disabled{opacity:.35;cursor:default}button:focus-visible,input:focus-visible{outline:3px solid #8bbfd4;outline-offset:2px}
.images{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}figure{margin:0;background:#19252c;border-radius:10px;overflow:hidden}figure img{width:100%;max-height:480px;object-fit:contain;display:block}figcaption{color:#dbe8ef;padding:9px 14px;font-size:12px}.empty{padding:48px;text-align:center;color:var(--muted);background:white;border:1px dashed var(--line);border-radius:10px}
.columns{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:16px}.panel{margin-top:14px}.columns .panel{margin:0}pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.65 ui-monospace,SFMono-Regular,monospace;max-height:360px;overflow:auto}details summary{cursor:pointer;font-weight:600}details pre{margin-top:12px}.error{padding:15px;background:#fff0ee;border:1px solid #e6bcb5;color:#952e27;border-radius:10px;white-space:pre-wrap;overflow-wrap:anywhere}footer{margin-top:20px;font-size:12px;color:var(--muted)}
@media(max-width:720px){main{padding:20px 14px 40px}.cards{grid-template-columns:1fr 1fr}.columns{grid-template-columns:1fr}h1{font-size:25px}.timeline{gap:8px}button{padding:8px 10px}}
</style></head><body><main>
<header><div class="eyebrow">MANILOOP / EPISODE REVIEW</div><h1>操作回看</h1><p id="task"></p><p class="muted">静态运行快照 · 保存时刻之后的变化不包含在本页 · 可离线打开</p></header>
<section class="cards" aria-label="运行摘要"><div class="card"><small>模型</small><strong id="model"></strong></div><div class="card"><small>决策／诊断调用</small><strong id="calls"></strong></div><div class="card"><small>执行计数</small><strong id="steps"></strong></div><div class="card"><small>终止／当前状态</small><strong id="termination"></strong></div></section>
<section class="panel audit"><h2 id="score">独立评分</h2><p><strong>仅供人类回看：评分与策略输入隔离。</strong>本页包含独立评估，不能作为模型的相机输入或上下文。</p><p id="declaration"></p><details><summary>查看独立评分字段</summary><pre id="evaluation"></pre></details></section>
<p class="error" id="error" hidden></p>
<nav class="timeline" aria-label="相机时间轴"><button id="previous" type="button">← 上一帧</button><input id="slider" aria-label="选择记录帧" type="range" min="0" max="0" value="0" step="1"><button id="next" type="button">下一帧 →</button></nav><p class="muted" id="position" aria-live="polite"></p><section class="images" id="images" aria-label="传感器图像"></section>
<div class="columns"><section class="panel"><h2>模型动作／声明</h2><pre id="decision"></pre></section><section class="panel"><h2>执行器反馈</h2><pre id="feedback"></pre></section></div>
<details class="panel"><summary>此帧机器人本体观测</summary><pre id="sensors"></pre></details><details class="panel"><summary>运行状态与预算终止</summary><pre id="summary"></pre></details><details class="panel"><summary>模型、请求选项与上下文协议</summary><pre id="provenance"></pre></details><details class="panel"><summary>完整事件记录</summary><pre id="events"></pre></details>
<footer>回看不会调用模型、推进仿真或访问网络。帧间跳转展示已记录的观测，不插值重建物理轨迹。</footer>
<noscript><p class="error">请允许本地 JavaScript 以查看时间轴；所有数据和图像均包含在此文件中。</p></noscript>
</main><script type="application/json" id="replay-data">__DATA__</script><script>__SCRIPT__</script></body></html>
"""
