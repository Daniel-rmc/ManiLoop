"""Offline replay must preserve evidence without making model text executable."""

import base64
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path

import pytest

from PIL import Image

from maniloop.recording.replay import render_replay


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.scripts = []
        self.tags = []
        self.csp = None
        self.in_script = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.tags.append((tag, attributes))
        if tag == "script":
            self.in_script = True
            self.scripts.append([attributes, ""])
        if tag == "meta" and attributes.get("http-equiv") == "Content-Security-Policy":
            self.csp = attributes["content"]

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False

    def handle_data(self, data):
        if self.in_script:
            self.scripts[-1][1] += data

    @property
    def data(self):
        return json.loads(self.scripts[0][1])


def document(**kwargs):
    arguments = {"manifest": {}, "frames": [], "events": [], "summary": {}}
    arguments.update(kwargs)
    html = render_replay(**arguments).decode("utf-8")
    return html, Document(html)


def test_model_html_remains_inert_and_json_round_trips():
    attack = '</script><script src="https://evil.invalid/steal"></script><img onerror="alert(1)"> & \u2028\u2029 __SCRIPT__ __DATA__'
    html, parsed = document(
        manifest={"instruction": attack, "policy": {"model": attack}},
        frames=[{"request_index": 1, "phase": "before", "observation": {"observation_id": attack}, "images": {attack: b"\xff\xd8\xffabc"}}],
        events=[{"request_index": 1, "type": "decision", "action": {"kind": "done", "explanation": attack}}],
        summary={"error": attack, "evaluation": {"success": False}},
    )
    assert len(parsed.scripts) == 2
    assert parsed.scripts[0][0] == {"type": "application/json", "id": "replay-data"}
    assert parsed.scripts[1][0] == {}
    assert "<" not in parsed.scripts[0][1]
    assert parsed.data["summary"]["error"] == attack
    assert parsed.data["provenance"]["instruction"] == attack
    assert parsed.data["events"][0]["action"]["explanation"] == attack
    assert attack in parsed.data["frames"][0]["images"]
    assert not any("onerror" in attrs or "src" in attrs for _, attrs in parsed.tags)
    assert "innerHTML" not in parsed.scripts[1][1]
    assert "仅供人类回看" in html
    assert "该声明不等于独立评分成功" in html


def test_embedded_images_preserve_png_jpeg_and_ignore_active_formats():
    image = Image.new("RGB", (2, 3), (20, 40, 80))
    png, jpeg = io.BytesIO(), io.BytesIO()
    image.save(png, "PNG")
    image.save(jpeg, "JPEG")
    _, parsed = document(frames=[{
        "request_index": 3, "phase": "after", "observation": {"tcp_position": [.1, .2, .3]},
        "images": {"external": png.getvalue(), "wrist": jpeg.getvalue(), "svg": b"<svg onload='alert(1)'/>", "url": "https://evil.invalid/image"},
    }])
    frames = parsed.data["frames"]
    assert frames[0]["request_index"] == 3
    assert frames[0]["phase"] == "after"
    urls = frames[0]["images"]
    assert set(urls) == {"external", "wrist"}
    for key, content, mime in (("external", png.getvalue(), "png"), ("wrist", jpeg.getvalue(), "jpeg")):
        prefix, encoded = urls[key].split(",", 1)
        assert prefix == f"data:image/{mime};base64"
        assert base64.b64decode(encoded) == content


def test_review_projects_public_provenance_and_separates_score():
    secret = "DO-NOT-EXPORT-PRIVATE-METADATA"
    html, parsed = document(
        manifest={
            "instruction": "把碗放入盘子", "credentials": {"key": secret}, "context_mode": "paired",
            "policy": {
                "model": "gpt-6-astra", "context_mode": "paired", "endpoint": secret,
                "request_options": {"transport": "codex_exec_chatgpt_v1", "reasoning_effort": "low", "max_output_tokens": 4096, "config_path": secret},
            },
        },
        frames=[{"request_index": 2, "phase": "final", "observation": {"tcp_position": [.1, .2, .3], "evaluation": {"success": True}, "object_position": [9, 9, 9], "private_config": secret}, "images": {}}],
        events=[{
            "request_index": 2, "type": "execution", "feedback": {"status": "reached", "position_error_m": .001, "evaluation": {"success": True}, "api_key": secret},
            "credentials": secret,
        }],
        summary={"api_calls": 2, "step_count": 1, "termination_reason": "decision_budget", "error": "", "evaluation": {"success": False, "evaluator": "libero_check_success", "control_steps": 20, "credentials": secret}, "api_key": secret},
    )
    data = parsed.data
    assert secret not in html
    assert data["evaluation"] == {"success": False, "evaluator": "libero_check_success", "control_steps": 20}
    assert "evaluation" not in data["summary"]
    assert data["frames"][0]["observation"] == {"tcp_position": [.1, .2, .3]}
    assert data["events"][0]["feedback"] == {"status": "reached", "position_error_m": .001}
    assert data["provenance"]["policy"]["context_mode"] == "paired"
    assert data["provenance"]["policy"]["request_options"]["transport"] == "codex_exec_chatgpt_v1"
    assert data["summary"]["api_calls"] == 2


def test_empty_replay_has_working_data_and_strict_offline_script_policy():
    _, parsed = document()
    assert parsed.data["frames"] == []
    assert parsed.data["events"] == []
    assert parsed.data["evaluation"] == {}
    script = parsed.scripts[1][1]
    digest = base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii")
    assert f"script-src 'sha256-{digest}'" in parsed.csp
    assert "connect-src 'none'" in parsed.csp
    assert "default-src 'none'" in parsed.csp
    assert "img-src data:" in parsed.csp
    assert "if (!frame)" in script
    assert not any(tag in {"iframe", "object", "embed", "link"} for tag, _ in parsed.tags)


def test_events_use_explicit_request_association_and_do_not_mutate_inputs():
    frames = [
        {"request_index": 1, "phase": "before", "observation": {"observation_id": "obs-1"}, "images": {}},
        {"request_index": 1, "phase": "after", "observation": {"observation_id": "obs-2"}, "images": {}},
        {"request_index": 2, "phase": "final", "observation": {"observation_id": "obs-3"}, "images": {}},
    ]
    events = [
        {"type": "decision", "request_index": 1, "action": {"kind": "move", "delta_position": [0, 0, .02]}},
        {"type": "execution", "request_index": 1, "feedback": {"status": "reached"}},
        {"type": "info", "message": "运行结束"},
        {"type": "decision", "request_index": 2, "action": {"kind": "done"}},
    ]
    original = json.dumps([frames, events], ensure_ascii=False)
    _, parsed = document(frames=frames, events=events)
    assert [f["request_index"] for f in parsed.data["frames"]] == [1, 1, 2]
    assert "request_index" not in parsed.data["events"][2]
    assert "event.request_index === frame.request_index" in parsed.scripts[1][1]
    assert json.dumps([frames, events], ensure_ascii=False) == original


def generated_replays(tmp_path):
    for name, value in [('20260916-120000-12345678', b'first'), ('20260916-130000-abcdef01', b'latest')]:
        folder = tmp_path / name
        folder.mkdir()
        (folder / 'replay.html').write_bytes(value)
    unrelated = tmp_path / 'private-config'
    unrelated.mkdir()
    (unrelated / 'replay.html').write_bytes(b'not a generated run')
    return unrelated


def test_restore_latest_generated_replay(tmp_path):
    from maniloop.recording.replay import load_latest_replay
    assert load_latest_replay(tmp_path / 'missing') == b''
    generated_replays(tmp_path)
    assert load_latest_replay(tmp_path) == b'latest'


@pytest.mark.parametrize('linked_entry', ['run', 'replay'])
def test_restore_latest_generated_replay_rejects_symlink_metadata(tmp_path, monkeypatch, linked_entry):
    from maniloop.recording.replay import load_latest_replay
    generated_replays(tmp_path)
    candidate = tmp_path / '20260916-140000-00000000'
    candidate.mkdir()
    (candidate / 'replay.html').write_bytes(b'must not read linked content')
    linked_path = candidate if linked_entry == 'run' else candidate / 'replay.html'
    is_symlink = Path.is_symlink
    # Exercise both guards even on Windows accounts without symlink privileges.
    monkeypatch.setattr(Path, 'is_symlink', lambda path: path == linked_path or is_symlink(path))
    assert load_latest_replay(tmp_path) == b'latest'


def test_restore_latest_generated_replay_without_following_real_links(tmp_path):
    from maniloop.recording.replay import load_latest_replay
    unrelated = generated_replays(tmp_path)
    try:
        (tmp_path / '20260916-140000-00000000').symlink_to(unrelated, target_is_directory=True)
    except OSError as error:
        if getattr(error, 'winerror', None) == 1314:
            pytest.skip('This Windows account lacks the privilege to create real symlinks')
        raise
    assert load_latest_replay(tmp_path) == b'latest'
