"""Opt-in real simulator capture; no model requests or pretrained policies."""

import os

import numpy as np
import pytest

from maniloop.backends.libero import LiberoEnvironment
from maniloop.recording.video import verify_episode

pytestmark = pytest.mark.skipif(os.environ.get("MANILOOP_TEST_LIBERO") != "1",
                                reason="Optional LIBERO runtime and graphics required")


def test_every_native_step_is_recorded_without_changing_trajectory(tmp_path):
    env = LiberoEnvironment()
    trajectories = []
    try:
        for recording in (False, True):
            env.reset(0)
            if recording:
                assert env.start_recording(tmp_path / "recording")["frame_count"] == 1
            trajectory = []
            for _ in range(8):
                env.execute({"kind": "move", "delta_position": [0, 0, .001]})
                env.step()
                packet, _ = env.observe()
                assert "success" not in packet and "recording" not in packet
                trajectory.append(packet["joint_positions"] + packet["tcp_position"])
            trajectories.append(trajectory)
            if recording:
                score = env.evaluation()
                result = env.finish_recording("integration_test")
                assert result["evaluation"] == score
                metadata, frames = verify_episode(tmp_path / "recording")
                assert metadata["frame_count"] == 9 and len(frames) == 9
                assert metadata["evaluation"]["control_steps"] == 8
                with pytest.raises(ValueError, match="Reset"):
                    env.start_recording(tmp_path / "late")
        np.testing.assert_array_equal(trajectories[0], trajectories[1])
    finally:
        env.close()
