"""Policy boundary and timing tests without optional PyTorch/model dependencies."""

import base64
from unittest.mock import patch
import pytest
from maniloop.agents.lerobot.agent import LeRobotAgent
from maniloop.evaluation.benchmark import Experiment, load_suite
from maniloop.core.observations import PUBLIC_OBSERVATION_FIELDS


def test_sensor_allowlist_and_single_control_tick():
    agent = LeRobotAgent.__new__(LeRobotAgent)
    observation = {
        "observation_id": "test",
        "action_limits": {"native_action": "osc_pose"},
        "tcp_position": [0, 0, 1],
        "tcp_quaternion_xyzw": [0, 0, 0, 1],
        "gripper_joint_positions": [0.04, -0.04],
        "object_truth": {"red_cube": [1, 2, 3]},
        "evaluation": {"success": True},
    }
    with patch.object(
        agent,
        "call",
        return_value={
            "action": [0, 0, 0, 0, 0, 0, -1],
            "usage": {"model_inferences": 1},
        },
    ) as call:
        chunk = agent.decide(
            "task",
            observation,
            {"external": b"rgb1", "wrist": b"rgb2"},
            [{"secret": "history"}],
            [{"secret": "geometry"}],
        )
    args = call.call_args.kwargs
    assert set(args) == {"task", "sensors", "images"}
    assert set(args["sensors"]) == {
        "tcp_position",
        "tcp_quaternion_xyzw",
        "gripper_joint_positions",
    }
    assert base64.b64decode(args["images"]["wrist"]) == b"rgb2"
    assert chunk.interval_seconds == 0.05 and len(chunk.actions) == 1
    assert agent.last_usage["model_inferences"] == 1


def test_local_policy_requires_compatible_backend_and_render_protocol():
    with pytest.raises(ValueError, match="LIBERO"):
        Experiment(agent="lerobot").validate()
    Experiment(backend="libero", agent="lerobot", max_calls=500).validate()
    with pytest.raises(ValueError):
        Experiment(agent="llm_cloud", max_calls=500).validate()
    with pytest.raises(ValueError):
        Experiment(backend="libero", agent="lerobot", local_model="pi05").validate()
    assert {
        "tcp_quaternion_xyzw",
        "gripper_joint_positions",
    } <= PUBLIC_OBSERVATION_FIELDS


def test_model_matrix(tmp_path):
    suite = tmp_path / "suite.toml"
    suite.write_text(
        '[experiment]\nbackend="libero"\nagent="lerobot"\nmax_calls=500\n[matrix]\nlocal_model=["smolvla-libero", "act-libero", "diffusion-libero"]\n'
    )
    assert len(load_suite(suite)) == 3
