"""Offline feedback provenance checks using small, fully hashed recordings.

The image payloads are deliberately synthetic: the auditor checks bytes and
sensor provenance, and must neither render a simulator nor invoke a policy.
"""

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

from maniloop.research.feedback_audit import audit_run, write_audit


def _json(path, value):
    path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")


def _jsonl(path, values):
    path.write_text("".join(json.dumps(value, allow_nan=False) + "\n" for value in values),
                    encoding="utf-8")


def _score(step, success=False):
    return {"success": success, "current_success": success, "control_steps": step,
            "terminated": success, "evaluator": "libero_check_success"}


def _sensor(position):
    return {"tcp_position": list(position), "tcp_quaternion_xyzw": [0, 0, 0, 1],
            "tcp_rotation_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            "joint_positions": [0.0] * 7, "joint_velocities": [0.0] * 7,
            "gripper_opening": 0.5}


def _snapshot(run):
    return {str(path.relative_to(run)): path.read_bytes()
            for path in run.rglob("*") if path.is_file()}


def _run_fixture(tmp_path, *, kind="move", accepted=True, feedback=True,
                 success=False, reported_error=None, name="run"):
    """One policy decision, initialization and one native control step."""
    run = tmp_path / name
    run.mkdir()
    recording = run / "recording"
    recording.mkdir()
    start = [0.1, 0.2, 0.3]
    actual = [0.01, 0.02, 0.0] if accepted else [0.0, 0.0, 0.0]
    requested = [0.03, 0.04, 0.0] if kind == "move" else [0.0, 0.0, 0.0]
    end = [a + b for a, b in zip(start, actual)]
    before = {**_sensor(start), "observation_id": "obs-before", "frame_id": "world",
              "simulation_time": 0.0}
    after = {**_sensor(end), "observation_id": "obs-after", "frame_id": "world",
             "simulation_time": 0.05}
    frames = []
    for step, sensors in enumerate((_sensor(start), _sensor(end))):
        images = {}
        for camera in ("external", "wrist"):
            filename = f"{step:06d}-{camera}.jpg"
            payload = b"\xff\xd8\xff" + f"synthetic-{step}-{camera}".encode() + b"\xff\xd9"
            (recording / filename).write_bytes(payload)
            images[camera] = {"file": filename, "sha256": hashlib.sha256(payload).hexdigest()}
            if step == 0:
                (run / f"001-{camera}.jpg").write_bytes(payload)
        frames.append({"control_step": step, "simulation_time": step * 0.05,
                       "action": [0.0] * 7 if step else None,
                       "sensors": sensors, "images": images})
    _jsonl(recording / "frames.jsonl", frames)
    evaluation = _score(1, success)
    _json(recording / "episode.json", {
        "format": "maniloop_control_step_recording_v1", "interpolated": False,
        "policy_input": False, "frame_count": 2, "control_timestep": 0.05,
        "initial_evaluation": _score(0), "evaluation": evaluation,
        "frames_sha256": hashlib.sha256((recording / "frames.jsonl").read_bytes()).hexdigest(),
        "termination_reason": "environment_terminated" if success else "decision_budget",
    })
    _json(run / "manifest.json", {
        "schema_version": 1, "backend": "libero", "seed": 0,
        "policy": {"context_mode": "paired", "action_interface": "tcp_target_servo_v2",
                   "timing": "controlled"},
    })
    _json(run / "result.json", {
        "schema_version": 1, "decisions": 1, "actions": 1,
        "termination_reason": "environment_terminated" if success else "decision_budget",
        "evaluation": evaluation,
    })
    _json(run / "001-observation.json", {**before, "last_feedback": {"status": "ready"}})
    _json(run / "001-context.json", {
        "context_mode": "paired", "history": [], "image_labels": ["external", "wrist"],
    })
    action = {"observation_id": "obs-before", "kind": kind,
              "delta_position": requested, "delta_rotation": [0.0] * 3,
              "gripper_opening": 0.0}
    residual = math.dist(requested, actual)
    completed = {
        "status": "reached" if kind == "move" else "completed",
        "kind": kind, "control_steps": 1, "actual_delta_position": actual,
        "position_error_m": residual if reported_error is None else reported_error,
    }
    rejected = {"status": "rejected", "message": "Synthetic bound rejection"}
    events = [
        {"type": "request", "message": "Request 1"},
        {"type": "decision", "request_index": 1, "action": action},
        {"type": "accepted" if accepted else "rejected", "request_index": 1,
         "feedback": {"status": "accepted"} if accepted else rejected},
    ]
    if feedback:
        if accepted:
            events.append({"type": "execution", "request_index": 1, "feedback": completed})
        events.append({"type": "transition", "request_index": 1, "transition": {
            "protocol": "sensor_transition_v1", "request_index": 1,
            "before": before, "after": after, "action": action,
            "feedback": completed if accepted else rejected,
        }})
    _jsonl(run / "events.jsonl", events)
    return run


def _row(report):
    assert len(report["rows"]) == 1
    assert report["rows"][0]["request_index"] == 1
    return report["rows"][0]


def test_residual_uses_vector_difference_and_preserves_source_files(tmp_path):
    run = _run_fixture(tmp_path)
    original = _snapshot(run)
    report = audit_run(run)
    row = _row(report)
    assert report["policy_input"] is False
    assert row["accepted"] is True
    assert row["kind"] == "move"
    assert row["feedback_source"] == "transition"
    assert row["feedback_status"] == "reached"
    assert row["endpoint_source"] == "recorded_feedback"
    assert row["requested_translation_m"] == pytest.approx(0.05)
    assert row["actual_translation_m"] == pytest.approx(math.hypot(0.01, 0.02))
    assert row["residual_recomputed_m"] == pytest.approx(math.hypot(0.02, 0.02))
    assert row["residual_reported_m"] == pytest.approx(row["residual_recomputed_m"])
    assert row["residual_difference_m"] == pytest.approx(0.0, abs=1e-12)
    assert row["native_start_step"] == 0
    assert row["native_end_step"] == 1
    assert report["summary"]["requests"] == report["summary"]["decisions"] == 1
    assert report["summary"]["accepted_actions"] == 1
    assert report["summary"]["execution_events"] == 1
    assert report["summary"]["transition_events"] == 1
    assert report["evaluation"]["success"] is False
    assert _snapshot(run) == original


def test_reported_residual_is_not_silently_substituted_for_recomputed_value(tmp_path):
    report = audit_run(_run_fixture(tmp_path, reported_error=0.5))
    row = _row(report)
    residual = math.hypot(0.02, 0.02)
    assert row["residual_recomputed_m"] == pytest.approx(residual)
    assert row["residual_reported_m"] == 0.5
    assert abs(row["residual_difference_m"]) == pytest.approx(0.5 - residual)
    assert row["flags"]


def test_gripper_residual_measures_arm_drift_against_zero_translation(tmp_path):
    run = _run_fixture(tmp_path, kind="gripper")
    # Gripper commands hold the arm; unused movement fields cannot create a
    # translation target even if a serialized response retained nonzero values.
    events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
    events[1]["action"]["delta_position"] = [0.03, 0.04, 0.0]
    events[-1]["transition"]["action"]["delta_position"] = [0.03, 0.04, 0.0]
    _jsonl(run / "events.jsonl", events)
    row = _row(audit_run(run))
    assert row["requested_translation_m"] == 0.0
    assert row["actual_translation_m"] == pytest.approx(math.hypot(0.01, 0.02))
    assert row["residual_recomputed_m"] == pytest.approx(row["actual_translation_m"])
    assert row["feedback_status"] == "completed"


def test_execution_only_feedback_remains_a_distinct_source(tmp_path):
    run = _run_fixture(tmp_path)
    events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
    _jsonl(run / "events.jsonl", [event for event in events if event["type"] != "transition"])
    report = audit_run(run)
    row = _row(report)
    assert row["feedback_source"] == "execution"
    assert row["endpoint_source"] == "recorded_feedback"
    assert row["native_end_step"] == 1
    assert row["residual_recomputed_m"] == pytest.approx(math.hypot(0.02, 0.02))
    assert report["summary"]["transition_events"] == 0


def test_terminal_native_endpoint_does_not_invent_completed_feedback(tmp_path):
    report = audit_run(_run_fixture(tmp_path, feedback=False, success=True))
    row = _row(report)
    assert row["accepted"] is True
    assert row["feedback_source"] == "none"
    assert row["feedback_status"] is None
    assert row["endpoint_source"] == "terminal_native_frame"
    assert row["native_start_step"] == 0
    assert row["native_end_step"] == 1
    assert row["residual_recomputed_m"] == pytest.approx(math.hypot(0.02, 0.02))
    assert row["residual_reported_m"] is None
    assert report["summary"]["execution_events"] == 0
    assert report["summary"]["transition_events"] == 0
    assert report["evaluation"]["success"] is True


def test_missing_feedback_without_native_termination_is_not_silently_reconstructed(tmp_path):
    report = audit_run(_run_fixture(tmp_path, feedback=False, success=False))
    row = _row(report)
    assert row["endpoint_source"] == "none"
    assert row["feedback_status"] is None
    assert row["actual_translation_m"] is None
    assert row["residual_recomputed_m"] is None
    assert row["native_end_step"] is None
    assert "missing_execution_feedback" in row["flags"]
    assert report["summary"]["terminal_reconstructions"] == 0


def test_rejection_followed_by_transition_does_not_count_as_execution(tmp_path):
    run = _run_fixture(tmp_path, accepted=False)
    events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
    events.append({"type": "rejected", "message": "Stale observation without request index"})
    _jsonl(run / "events.jsonl", events)
    report = audit_run(run)
    row = _row(report)
    assert row["accepted"] is False
    assert report["summary"]["accepted_actions"] == 0
    assert report["summary"]["execution_events"] == 0
    assert report["summary"]["transition_events"] == 1
    assert report["summary"]["unindexed_rejections"] == 1
    assert row["endpoint_source"] == "none"
    assert row["residual_recomputed_m"] is None


def test_evaluator_fields_remain_outside_all_rows(tmp_path):
    report = audit_run(_run_fixture(tmp_path, success=True))

    def assert_sensor_only(value):
        if isinstance(value, dict):
            for key, child in value.items():
                assert key not in {"evaluation", "evaluator", "success", "current_success",
                                   "native_success", "object_position", "object_pose", "reward"}
                assert_sensor_only(child)
        elif isinstance(value, list):
            for child in value:
                assert_sensor_only(child)

    assert report["evaluation"]["success"] is True
    assert_sensor_only(report["rows"])


@pytest.mark.parametrize("suffix", ["observation", "context"])
def test_missing_sensor_file_is_diagnosed_without_modifying_evidence(tmp_path, suffix):
    run = _run_fixture(tmp_path)
    (run / f"001-{suffix}.json").unlink()
    original = _snapshot(run)
    report = audit_run(run)
    assert f"missing_{suffix}" in _row(report)["flags"]
    assert report["summary"]["flags"][f"missing_{suffix}"] == 1
    assert _snapshot(run) == original


@pytest.mark.parametrize("mismatch, expected_flag", [
    ("observation_id", "action_observation_mismatch"),
    ("tcp_position", "request_native_alignment_unverified"),
])
def test_mismatched_request_sensor_evidence_is_not_marked_aligned(tmp_path, mismatch, expected_flag):
    run = _run_fixture(tmp_path)
    path = run / "001-observation.json"
    observation = json.loads(path.read_text())
    observation[mismatch] = "different-observation" if mismatch == "observation_id" else [9, 8, 7]
    _json(path, observation)
    report = audit_run(run)
    row = _row(report)
    assert expected_flag in row["flags"]
    if mismatch == "tcp_position":
        assert row["native_start_step"] is None
        assert row["native_end_step"] is None


@pytest.mark.parametrize("suffix", ["observation", "context"])
@pytest.mark.parametrize("forbidden", ["object_pose", "evaluation"])
def test_privileged_fields_in_policy_inputs_are_flagged_and_not_copied(tmp_path, suffix, forbidden):
    run = _run_fixture(tmp_path)
    path = run / f"001-{suffix}.json"
    value = json.loads(path.read_text())
    value["nested"] = {forbidden: {"private_marker": "must-not-be-exported"}}
    _json(path, value)
    original = _snapshot(run)
    report = audit_run(run)
    row = _row(report)
    assert f"forbidden_or_unsupported_{suffix}_fields" in row["flags"]
    assert "must-not-be-exported" not in json.dumps(report)
    assert forbidden not in row
    assert _snapshot(run) == original


def _add_second_request_with_feedback(run):
    event_path = run / "events.jsonl"
    events = [json.loads(line) for line in event_path.read_text().splitlines()]
    transition = deepcopy(events[-1]["transition"])
    after = transition["after"]
    completed = transition["feedback"]
    _json(run / "002-observation.json", {**after, "last_feedback": completed})
    _json(run / "002-context.json", {"context_mode": "paired", "history": [
        {"action": transition["action"], "feedback": completed},
        {"transition": transition},
    ], "image_labels": ["external", "wrist", "previous/external", "previous/wrist"]})
    for camera in ("external", "wrist"):
        (run / f"002-{camera}.jpg").write_bytes((run / "recording" / f"000001-{camera}.jpg").read_bytes())
    events.extend([
        {"type": "request", "message": "Request 2"},
        {"type": "decision", "request_index": 2,
         "action": {"observation_id": after["observation_id"], "kind": "done"}},
    ])
    _jsonl(event_path, events)
    result = json.loads((run / "result.json").read_text())
    result["decisions"] = 2
    _json(run / "result.json", result)


def test_feedback_occurrences_count_policy_payload_copies_not_execution_events(tmp_path):
    run = _run_fixture(tmp_path)
    _add_second_request_with_feedback(run)
    report = audit_run(run)
    first, second = report["rows"]
    assert first["request_index"] == 1 and second["request_index"] == 2
    assert first["feedback_occurrences"] == 0
    assert second["feedback_occurrences"] == 3
    assert second["latest_residual_occurrences"] == 3
    assert second["history_actions"] == second["history_transitions"] == 1
    assert second["accepted"] is False
    assert second["feedback_source"] == "none"
    assert second["feedback_status"] is None
    assert report["summary"]["accepted_actions"] == 1
    assert report["summary"]["execution_events"] == report["summary"]["transition_events"] == 1


def test_transition_before_sensor_tampering_is_detected_even_with_same_id(tmp_path):
    run = _run_fixture(tmp_path)
    path = run / "events.jsonl"
    events = [json.loads(line) for line in path.read_text().splitlines()]
    before = events[-1]["transition"]["before"]
    before["tcp_position"][0] += 0.2
    assert before["observation_id"] == "obs-before"
    _jsonl(path, events)
    original = _snapshot(run)
    report = audit_run(run)
    row = _row(report)
    assert "transition_before_sensor_mismatch" in row["flags"]
    assert "transition_observation_mismatch" not in row["flags"]
    assert report["summary"]["flags"]["transition_before_sensor_mismatch"] == 1
    assert _snapshot(run) == original


def test_context_action_feedback_must_match_the_recorded_prior_action(tmp_path):
    run = _run_fixture(tmp_path)
    _add_second_request_with_feedback(run)
    path = run / "002-context.json"
    context = json.loads(path.read_text())
    context["history"][0]["feedback"]["position_error_m"] = 0.8
    _json(path, context)
    original = _snapshot(run)
    report = audit_run(run)
    first, second = report["rows"]
    assert "context_action_feedback_mismatch" not in first["flags"]
    assert "context_action_feedback_mismatch" in second["flags"]
    assert "context_transition_mismatch" not in second["flags"]
    assert report["summary"]["flags"]["context_action_feedback_mismatch"] == 1
    assert _snapshot(run) == original


@pytest.mark.parametrize("mismatch", ["future_request", "changed_transition"])
def test_context_transition_must_be_an_unchanged_completed_prior_transition(tmp_path, mismatch):
    run = _run_fixture(tmp_path)
    _add_second_request_with_feedback(run)
    path = run / "002-context.json"
    context = json.loads(path.read_text())
    transition = context["history"][1]["transition"]
    if mismatch == "future_request":
        transition["request_index"] = 3
    else:
        transition["after"]["tcp_position"][1] += 0.2
    _json(path, context)
    original = _snapshot(run)
    report = audit_run(run)
    first, second = report["rows"]
    assert "context_transition_mismatch" not in first["flags"]
    assert "context_transition_mismatch" in second["flags"]
    assert "context_action_feedback_mismatch" not in second["flags"]
    assert report["summary"]["flags"]["context_transition_mismatch"] == 1
    assert _snapshot(run) == original


@pytest.mark.parametrize("target", ["recording/frames.jsonl", "recording/000001-wrist.jpg"])
def test_native_recording_digest_tampering_is_rejected(tmp_path, target):
    run = _run_fixture(tmp_path)
    path = run / target
    path.write_bytes(path.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="digest"):
        audit_run(run)


@pytest.mark.parametrize("existing", ["file", "nonempty_directory", "empty_directory"])
def test_write_audit_refuses_overwrite_and_preserves_every_source(tmp_path, existing):
    run = _run_fixture(tmp_path)
    original = _snapshot(run)
    output = tmp_path / "audit"
    if existing == "file":
        output.write_bytes(b"must survive")
        survivor = output
    else:
        output.mkdir()
        survivor = output / "keep.txt" if existing == "nonempty_directory" else None
        if survivor:
            survivor.write_bytes(b"must survive")
    with pytest.raises((FileExistsError, ValueError)):
        write_audit([run], output)
    if survivor:
        assert survivor.read_bytes() == b"must survive"
    else:
        assert list(output.iterdir()) == []
    assert _snapshot(run) == original


def test_write_audit_exports_new_artifacts_outside_immutable_sources(tmp_path):
    run = _run_fixture(tmp_path)
    original = _snapshot(run)
    output = tmp_path / "audit"
    report = write_audit([run], output)
    assert report["policy_input"] is False
    assert len(report["runs"]) == 1
    assert json.loads((output / "audit.json").read_text()) == report
    assert (output / "requests.csv").is_file()
    assert _snapshot(run) == original
    with pytest.raises(ValueError, match="outside"):
        write_audit([run], run / "not-allowed")
    assert _snapshot(run) == original


def test_cli_exports_synthetic_episode_without_model_or_simulation(tmp_path):
    run = _run_fixture(tmp_path)
    original = _snapshot(run)
    output = tmp_path / "cli-audit"
    completed = subprocess.run(
        [sys.executable, "-m", "maniloop.research.feedback_audit", str(run), "--output", str(output)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    notice = json.loads(completed.stdout)
    assert notice["policy_input"] is False
    assert notice["runs"] == notice["requests"] == 1
    assert (output / "audit.json").is_file()
    assert _snapshot(run) == original
