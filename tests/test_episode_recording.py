"""Capture integrity, initialization boundary, and human-only export checks."""

import hashlib
import json

import numpy as np
import pytest

from maniloop.backends.libero.episode_capture import EpisodeCapture
from maniloop.evaluation.benchmark import Experiment, run_episode
from maniloop.recording.video import export_video, verify_episode


def score(steps, success=False):
    return {"success": success, "current_success": success, "control_steps": steps,
            "terminated": success, "evaluator": "libero_check_success"}


def capture_fixture(tmp_path, success=False):
    capture = EpisodeCapture(tmp_path / "recording", description={"task_id": 0},
                             seed=0, initial_evaluation=score(0))
    for step in range(3):
        capture.append(step=step, images={name: np.full((32, 32, 3), 80 + step, dtype=np.uint8)
                                          for name in ("external", "wrist")},
                       action=[0.0] * 7 if step else None, sensors={"tcp_position": [0, 0, 1]})
    capture.finish(evaluation=score(2, success), reason="fixture")
    return capture


def test_full_episode_index_and_official_score(tmp_path):
    capture = capture_fixture(tmp_path)
    metadata, frames = verify_episode(capture.directory)
    assert metadata["frame_count"] == metadata["evaluation"]["control_steps"] + 1 == 3
    assert [frame["simulation_time"] for frame in frames] == [0, .05, .10]
    assert all("success" not in frame and "success" not in frame["sensors"] for frame in frames)
    assert metadata["policy_input"] is False and metadata["interpolated"] is False
    with pytest.raises(FileExistsError):
        EpisodeCapture(capture.directory, description={}, seed=0, initial_evaluation=score(0))


def test_tamper_missing_frames_and_action_order_are_rejected(tmp_path):
    capture = capture_fixture(tmp_path)
    raw = capture.index.read_bytes()
    capture.index.write_bytes(raw[:-1] + b" ")
    with pytest.raises(ValueError, match="digest"):
        verify_episode(capture.directory)
    capture.index.write_bytes(raw)
    image = capture.directory / "000001-external.jpg"
    image.write_bytes(image.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="digest"):
        verify_episode(capture.directory)


def test_reordered_frames_rejected_even_with_updated_index_digest(tmp_path):
    capture = capture_fixture(tmp_path)
    frames = capture.index.read_text(encoding="utf-8").splitlines()
    capture.index.write_text("\n".join([frames[0], frames[2], frames[1]]) + "\n", encoding="utf-8")
    metadata = capture.metadata
    metadata["frames_sha256"] = hashlib.sha256(capture.index.read_bytes()).hexdigest()
    (capture.directory / "episode.json").write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="reordered"):
        verify_episode(capture.directory)


def test_capture_rejects_skipped_steps_and_mismatched_terminal_score(tmp_path):
    capture = EpisodeCapture(tmp_path / "recording", description={}, seed=0, initial_evaluation=score(0))
    with pytest.raises(ValueError, match="consecutive"):
        capture.append(step=1, images={}, action=[0] * 7, sensors={})
    with pytest.raises(ValueError, match="counts differ"):
        capture.finish(evaluation=score(2), reason="fixture")


def test_failed_attempt_not_exported_as_success(tmp_path):
    capture = capture_fixture(tmp_path)
    with pytest.raises(ValueError, match="successful demo"):
        export_video(capture.directory)


@pytest.mark.parametrize("settings", [dict(backend="mujoco"),
    dict(backend="libero", timing="realtime"), dict(backend="libero", record_episode=1)])
def test_recording_rejects_unsupported_experiments(settings):
    with pytest.raises(ValueError, match="record|Record"):
        Experiment(**{"record_episode": True, **settings}).validate()


def test_recording_requires_render_before_environment_creation(tmp_path):
    with pytest.raises(ValueError, match="rendering"):
        run_episode(Experiment(backend="libero", record_episode=True), tmp_path, render=False)
