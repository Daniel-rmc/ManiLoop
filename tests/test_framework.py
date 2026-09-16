"""Cross-embodiment physics and runtime contracts; no network or trained model."""

from concurrent.futures import Future
from dataclasses import replace
import json
import time
import numpy as np
import pytest
from maniloop.core.actions import Action, ActionChunk
from maniloop.runtime.chunks import ChunkExecutor
from maniloop.runtime.runner import EpisodeRunner
from maniloop.simulation.environment import RobotSim
from maniloop.representations.sensors import SensorRepresentation
from maniloop.evaluation.benchmark import Experiment, load_suite, run_episode


def move_to(sim, target):
    for _ in range(70):
        delta = np.array(target) - sim.tcp_position
        if np.linalg.norm(delta) < 0.002:
            return
        delta *= min(1, 0.035 / np.linalg.norm(delta))
        result = sim.execute({"kind": "move", "delta_position": delta.tolist()})
        assert result["status"] == "accepted", result
        for _ in range(150):
            sim.step(20)
            if sim.settled:
                break
    pytest.fail("Controller did not converge")


@pytest.mark.parametrize("robot", ["arx5", "panda"])
@pytest.mark.parametrize("scene", ["tabletop_a", "tabletop_b"])
@pytest.mark.parametrize("task", ["pick_place", "push"])
def test_contact_tasks_across_embodiments(robot, scene, task):
    sim = RobotSim(render=False, robot=robot, scene=scene, task=task)
    try:
        p, t = np.array(sim.layout.object_position), np.array(
            sim.layout.target_position
        )
        # Known test-fixture coordinates are confined to this physics test.
        if task == "pick_place":
            move_to(sim, [*p[:2], 0.16])
            move_to(sim, [*p[:2], 0.021])
            sim.execute({"kind": "gripper", "gripper_opening": 0})
            sim.step(700)
            move_to(sim, [*p[:2], 0.15])
            assert sim.data.body("red_cube").xpos[2] > 0.10
            move_to(sim, [*t[:2], 0.15])
            move_to(sim, [*t[:2], 0.025])
            sim.execute({"kind": "gripper", "gripper_opening": 1})
            sim.step(700)
            move_to(sim, [*t[:2], 0.15])
        else:
            direction = t[:2] - p[:2]
            direction /= np.linalg.norm(direction)
            start, end = p[:2] - 0.052 * direction, t[:2] - 0.022 * direction
            move_to(sim, [*start, 0.16])
            sim.execute({"kind": "gripper", "gripper_opening": 0})
            sim.step(700)
            move_to(sim, [*start, 0.021])
            move_to(sim, [*end, 0.021])
            move_to(sim, [*end, 0.15])
        sim.step(800)
        assert sim.evaluation()["success"], sim.evaluation()
        # Scoring is a read-only snapshot, independent of UI refresh frequency.
        assert sim.evaluation() == sim.evaluation()
    finally:
        sim.close()


@pytest.mark.parametrize("robot", ["arx5", "panda"])
def test_reset_encoders_and_sensor_boundary(robot):
    sim = RobotSim(render=False, robot=robot)
    try:
        assert len(sim.observe()[0]["joint_positions"]) == (6 if robot == "arx5" else 7)
        assert sim.gripper_opening > 0.98
        sim.reset(31)
        first = sim.data.qpos.copy()
        sim.step(10)
        sim.reset(31)
        np.testing.assert_allclose(sim.data.qpos, first, atol=1e-12)
        sim.reset(32)
        assert not np.array_equal(first, sim.data.qpos)
        observation, _ = sim.observe()
        packet = SensorRepresentation().encode(observation)
        assert set(packet).isdisjoint(
            {"object_pose", "contacts", "success", "evaluation", "target_center"}
        )
        with pytest.raises(ValueError):
            SensorRepresentation().encode({**observation, "object_pose": [1, 2, 3]})
        packet["joint_positions"][0] = 100
        assert observation["joint_positions"][0] != 100
    finally:
        sim.close()


@pytest.mark.parametrize("timing", ["controlled", "realtime"])
def test_inference_clock_and_stale_response_cancellation(timing):
    sim = RobotSim(render=False)
    runner = EpisodeRunner(sim, timing=timing)
    try:
        runner.running = True
        runner.future = Future()
        runner.future_token = runner.token
        runner._last_wall = time.monotonic() - 0.04
        before = float(sim.data.time)
        runner.advance(0.04)
        assert (sim.data.time > before) == (timing == "realtime")
        runner.stop()
        runner.future.set_result({"kind": "done"})
        runner.advance()
        assert runner.phase == "stopped"
    finally:
        runner.close()


def test_chunk_cadence_and_invalid_joint_names():
    sim = RobotSim(render=False)
    try:
        obs, _ = sim.observe()
        q, names = tuple(obs["joint_positions"]), tuple(obs["joint_names"])
        action = Action("joint_position", (q[0] + 0.003, *q[1:]), joint_names=names)
        chunk = ChunkExecutor(
            sim, ActionChunk(obs["observation_id"], (action, action), 0.1)
        )
        times = []
        for _ in range(120):
            result = chunk.tick()
            if result and result["status"] == "accepted":
                times.append(result["simulation_time"])
            sim.step()
        assert len(times) == 2 and times[1] - times[0] == pytest.approx(0.1)
        assert chunk.completed
        invalid = ChunkExecutor(
            sim,
            ActionChunk(
                obs["observation_id"],
                (replace(action, joint_names=tuple(reversed(names))),),
            ),
        )
        controls = sim.data.ctrl.copy()
        assert invalid.tick()["status"] == "rejected"
        assert invalid.completed
        # Rejection holds measured arm positions, preserving gripper targets.
        np.testing.assert_array_equal(
            sim.data.ctrl[sim.gripper_act], controls[sim.gripper_act]
        )
    finally:
        sim.close()


@pytest.mark.parametrize(
    "chunk",
    [
        ActionChunk("", (Action("wait"),)),
        ActionChunk("o", (Action("wait"),), float("nan")),
        ActionChunk(
            "o", (Action("joint_position", (float("nan"),), joint_names=("joint1",)),)
        ),
        ActionChunk("o", (Action("gripper", gripper=2),)),
        ActionChunk("o", (Action("tcp_delta", (0.1, 0.2)),)),
    ],
)
def test_invalid_chunks_fail_closed(chunk):
    with pytest.raises(ValueError):
        chunk.validate()


def test_mock_episode_recording_and_grouping(tmp_path):
    result = run_episode(Experiment(robot="panda"), tmp_path, render=False)
    assert result["phase"] == "completed" and result["is_mock"]
    assert not result["evaluation"]["success"]
    assert result["decisions"] == 2 and result["actions"] == 2
    manifest = json.loads(
        (
            __import__("pathlib").Path(result["run_directory"]) / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["policy"]["memory"] == "reset_per_episode"
    assert manifest["robot_revision"]
    assert manifest["policy"]["endpoint"] is None
    assert (
        len(load_suite(__import__("pathlib").Path("examples/offline-suite.toml"))) == 8
    )


def test_budget_stops_an_outstanding_request():
    sim = RobotSim(render=False)
    runner = EpisodeRunner(sim)
    try:
        runner.running = True
        runner.started_wall = time.monotonic() - 2
        runner.wall_budget = 1
        runner.future = Future()
        runner.future_token = runner.token
        runner.advance()
        assert not runner.running and runner.phase == "stopped"
        runner.future.set_result({"kind": "done"})
        runner.advance()
        assert runner.phase == "stopped"
    finally:
        runner.close()


def test_stop_cancels_remaining_chunk_samples():
    sim = RobotSim(render=False)
    runner = EpisodeRunner(sim)
    try:
        obs, _ = sim.observe()
        q, names = tuple(obs["joint_positions"]), tuple(obs["joint_names"])
        runner.chunk = ChunkExecutor(
            sim,
            ActionChunk(
                obs["observation_id"],
                (
                    Action("joint_position", (q[0] + 0.003, *q[1:]), joint_names=names),
                    Action("joint_position", (q[0] + 0.006, *q[1:]), joint_names=names),
                ),
            ),
        )
        runner.chunk.tick()
        runner.running = True
        runner.stop()
        held = sim.data.ctrl.copy()
        runner.advance(0.3)
        assert runner.chunk is None and runner.phase == "stopped"
        np.testing.assert_array_equal(sim.data.ctrl, held)
    finally:
        runner.close()


def test_benchmark_provider_switch_aborts_before_new_request(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    import maniloop.runtime.runner as module

    config = tmp_path / "provider.json"
    config.write_text(json.dumps({"api_key": "synthetic-one", "model": "test-model"}))
    factory = MagicMock()
    monkeypatch.setattr(module, "GPTPolicy", factory)
    sim = RobotSim(render=False)
    runner = EpisodeRunner(sim, benchmark=True, output=tmp_path / "results")
    try:
        runner.command(
            "start",
            {"task": "test", "credential_source": "file", "config_path": str(config)},
        )
        config.write_text(
            json.dumps({"api_key": "synthetic-two", "model": "test-model"})
        )
        runner.tick()
        assert runner.phase == "error" and not runner.running
        assert runner.api_calls == 0 and factory.call_count == 1
        assert "配置发生变化" in runner.error
        assert "synthetic-" not in runner.log_file.read_text(encoding="utf-8")
    finally:
        runner.close()


def test_cloud_failure_summary_preserves_unknown_usage(tmp_path, monkeypatch):
    import maniloop.evaluation.benchmark as batch
    import maniloop.runtime.runner as runtime
    from maniloop.providers.responses import PolicyError

    class TimeoutPolicy:
        last_latency = 4.0
        last_usage = {}
        request_options = {"timeout_seconds":120, "reasoning_effort":"low"}
        def __init__(self, **kwargs):
            pass
        def decide(self, *args):
            raise PolicyError("timed out", category="timeout")

    monkeypatch.setattr(runtime, "GPTPolicy", TimeoutPolicy)
    monkeypatch.setattr(batch, "create_environment", lambda **kwargs: RobotSim(render=False))
    result = run_episode(Experiment(agent="llm_cloud", max_calls=1), tmp_path,
                         connection={"credential_source":"manual", "api_key":"offline-fixture"})
    assert result["phase"] == "error" and result["decisions"] == 1
    assert result["usage"] is None and result["usage_complete"] is False
    assert result["actions"] == 0
