"""Backend contract tests need no LIBERO installation, downloads, graphics or API key."""

import copy
import json
import time
from pathlib import Path
import pytest
from maniloop.backends.libero import environment as adapter
from maniloop.core.actions import Action, ActionChunk
from maniloop.evaluation.benchmark import Experiment, load_suite
from maniloop.representations.sensors import SensorRepresentation
from maniloop.runtime.runner import EpisodeRunner

SENSORS = dict(
    joint_names=[f"joint{i}" for i in range(7)],
    joint_positions=[0.0] * 7,
    joint_velocities=[0.0] * 7,
    tcp_position=[0.0, 0.0, 1.0],
    tcp_rotation_matrix=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    gripper_opening=0.5,
)
DESCRIPTION = dict(
    task="official_test_task",
    instruction="move the bowl",
    suite="libero_spatial",
    backend="libero",
    controller="libero_robosuite_OSC_POSE",
    protocol="test",
    upstream_revision="test",
    controller_config={},
    runtime_dependencies={},
    camera_preprocessing="test",
    task_id=0,
    init_state_id=0,
)


class FakeWorker:
    def __init__(self, *args, **kwargs):
        self.actions = []
        self.calls = []
        self.steps = 0
        self.success = False
        self.closed = False

    def options(self, suite, **kwargs):
        return kwargs

    def call(self, op, **kwargs):
        self.calls.append(op)
        if op == "init":
            return copy.deepcopy(DESCRIPTION)
        if op == "reset":
            self.steps = 0
            return copy.deepcopy(SENSORS)
        if op == "observe":
            return dict(sensors=copy.deepcopy(SENSORS), cameras={}, images={})
        if op == "step":
            self.steps += 1
            self.actions.append(kwargs["action"])
            return dict(
                sensors=copy.deepcopy(SENSORS),
                steps=self.steps,
                terminated=self.success,
            )
        if op == "evaluate":
            return dict(success=self.success, secret_object_pose=[1, 2, 3])
        raise AssertionError(op)

    def close(self):
        self.closed = True


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(adapter, "Worker", FakeWorker)
    value = adapter.LiberoEnvironment(render=False)
    yield value
    value.close()


def test_sensor_packet_excludes_evaluator_and_stays_independent(env):
    assert env.evaluation()["secret_object_pose"] == [1, 2, 3]
    packet, _ = env.observe()
    encoded = SensorRepresentation().encode(packet)
    assert "secret_object_pose" not in json.dumps(encoded)
    assert "success" not in encoded
    assert packet["frame_id"] == "world"
    assert not packet["geometry_queries"]["depth_available"]
    encoded["joint_positions"][0] = 999
    assert env.observe()[0]["joint_positions"][0] == 0
    assert not env.depth_query({})["valid"]


def test_move_units_frame_and_no_hidden_repeat(env):
    assert (
        env.execute(dict(kind="move", delta_position=[0.01, 0, 0], frame="world"))[
            "status"
        ]
        == "accepted"
    )
    assert env.simulation_time == 0
    env.step()
    assert env.worker.actions[-1] == pytest.approx([0.2, 0, 0, 0, 0, 0, -1])
    assert env.simulation_time == 0.05 and not env.busy
    assert (
        env.execute(dict(kind="move", delta_position=[0.06, 0, 0]))["status"]
        == "rejected"
    )
    assert env.execute(dict(kind="move", frame="base"))["status"] == "rejected"
    assert (
        env.execute(dict(kind="move", delta_position=[float("nan"), 0, 0]))["status"]
        == "rejected"
    )


def test_gripper_polarity_and_declared_duration(env):
    assert (
        env.execute(dict(kind="gripper", gripper_opening=0.5))["status"] == "rejected"
    )
    env.execute(dict(kind="gripper", gripper_opening=0))
    env.step(10)
    assert len(env.worker.actions) == 10
    assert all(sample[-1] == 1 for sample in env.worker.actions)
    env.execute(dict(kind="gripper", gripper_opening=1))
    env.step(10)
    assert env.worker.actions[-1][-1] == -1


def test_snapshot_reset_and_cancel(env):
    packet, _ = env.observe()
    assert env.validate_snapshot(packet)[0]
    env.execute(dict(kind="gripper", gripper_opening=0))
    env.hold()
    assert not env.busy and not env.validate_snapshot(packet)[0]
    env.reset(3)
    assert not env.validate_snapshot(packet)[0]
    assert env.simulation_time == 0


def test_native_chunk_timing_and_stop(env):
    packet, _ = env.observe()
    sample = Action("osc_pose", (0.0, 0.0, 0.1, 0.0, 0.0, 0.0, -1.0), frame="world")
    chunk = ActionChunk(packet["observation_id"], (sample, sample), 0.05)
    executor = env.create_chunk_executor(chunk)
    assert executor.tick()["status"] == "accepted"
    assert env.simulation_time == 0
    env.step()
    executor.tick()
    env.step()
    executor.tick()
    assert executor.completed and env.simulation_time == 0.1
    with pytest.raises(ValueError, match="20 Hz"):
        env.create_chunk_executor(ActionChunk(packet["observation_id"], (sample,), 0.1))
    with pytest.raises(ValueError):
        Action("osc_pose", (2.0,) * 7, frame="world").validate()
    with pytest.raises(ValueError):
        Action("osc_pose", (0.0,) * 7).validate()


def test_runner_idle_freezes_and_mock_has_exactly_two_control_steps(env, tmp_path):
    runner = EpisodeRunner(env, output=tmp_path)
    try:
        runner.advance(0.5)
        assert env.simulation_time == 0
        runner.command(
            "start", dict(task=env.instruction, agent="mock_vla", max_steps=3)
        )
        for _ in range(100):
            runner.advance(0.05)
            time.sleep(0.001)
            if not runner.running:
                break
        assert runner.phase == "completed"
        assert len(env.worker.actions) == 2
        manifest = json.loads((runner.log_file.parent / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["policy"]["action_interface"] == "libero_osc_chunk_v1"
    finally:
        runner.close()


def test_official_termination_prevents_next_model_request(env, tmp_path):
    runner = EpisodeRunner(env, output=tmp_path)
    try:
        runner.command(
            "start", dict(task=env.instruction, agent="mock_vla", max_steps=3)
        )
        env.terminated = True
        runner.advance(0.05)
        assert runner.termination_reason == "environment_terminated"
        assert runner.api_calls == 0
    finally:
        runner.close()


def test_libero_experiment_validation_and_matrix(tmp_path):
    Experiment(backend="libero").validate()
    for kwargs in (
        dict(robot="arx5"),
        dict(libero_task_id=-1),
        dict(libero_suite="invented"),
        dict(task="push"),
    ):
        with pytest.raises(ValueError):
            Experiment(backend="libero", **kwargs).validate()
    path = tmp_path / "suite.toml"
    path.write_text(
        '[experiment]\nbackend="libero"\n[matrix]\nlibero_task_id=[0,1]\ninit_state_id=[0,1]\n'
    )
    assert len(load_suite(path)) == 4


def test_missing_runtime_has_installation_guidance(tmp_path):
    from maniloop.backends.libero.transport import Worker

    with pytest.raises(RuntimeError, match="docs/LIBERO.md"):
        Worker(str(tmp_path / "absent-python"), str(tmp_path))


def test_worker_horizon_includes_ten_warmup_steps():
    from types import SimpleNamespace
    import numpy as np
    from maniloop.backends.libero.worker import Runtime

    calls = []
    runtime = Runtime.__new__(Runtime)
    runtime.np = np
    runtime.capture = None
    runtime.steps, runtime.done, runtime.success = 989, False, False
    runtime.sensors = lambda: {}
    runtime.env = SimpleNamespace(
        step=lambda action: (calls.append(action) or {}, 0, False, {}),
        check_success=lambda: False,
    )
    result = runtime.step([0.0] * 7)
    assert result["terminated"] and result["steps"] == 990
    runtime.step([0.0] * 7)
    assert len(calls) == 1


def test_local_policy_restart_resets_existing_profile(env, monkeypatch, tmp_path):
    from maniloop.agents import lerobot

    class FakePolicy:
        metadata = {"repo": "test/local", "family": "smolvla"}

        def __init__(self, **kwargs):
            self.closed = False

        def reset(self, seed):
            self.seed = seed

        def close(self):
            self.closed = True

    monkeypatch.setattr(lerobot, "LeRobotAgent", FakePolicy)
    env.render_enabled = True
    env._description["observation_profile"] = "lerobot_rgb256"
    runner = EpisodeRunner(env, output=tmp_path)
    try:
        runner.command(
            "start", {"agent": "lerobot", "task": "move bowl", "max_steps": 500}
        )
        first = runner.policy
        runner.stop()
        runner.command(
            "start", {"agent": "lerobot", "task": "move bowl", "max_steps": 500}
        )
        assert first.closed
        assert env.worker.calls.count("reset") == 2
        assert env.simulation_time == 0
        assert runner.policy_kind == "lerobot"
    finally:
        runner.close()


def test_target_fixed_goal_timeout_and_cancellation(env):
    import numpy as np
    env.set_llm_control("tcp_target_servo_v2")
    result = env.execute(dict(kind="move", frame="world", delta_position=[0, 0, 0.01]))
    assert result["status"] == "accepted" and env.busy
    env.step()
    # Proprioception reports a 4 mm move: remaining command must shrink, not repeat 10 mm.
    env._sensors["tcp_position"][2] += 0.004
    np.testing.assert_allclose(env._target.sample(env._sensors)[:3], [0, 0, 0.12], atol=1e-8)
    env.step(19)  # fake robot is blocked; budget must end rather than report success
    assert not env.busy and env.feedback["status"] == "timed_out"
    assert env.feedback["control_steps"] == 20
    env.execute(dict(kind="move", delta_position=[0, 0, 0.01]))
    env.hold()
    assert not env.busy and env.feedback["status"] == "interrupted"
    assert env.describe()["target_controller"]["max_steps"] == 20
    assert "target_tracking" in env.observe()[0]["action_limits"]


def test_target_rotation_and_pose_settling():
    import numpy as np
    from maniloop.controllers.target import PoseTarget
    from maniloop.controllers.geometry import rotation_matrix
    sensors = copy.deepcopy(SENSORS)
    target = PoseTarget(sensors, np.array([0, 0, .01]), np.array([0, 0, .1]), -1)
    sensors["tcp_position"] = target.position.tolist()
    sensors["tcp_rotation_matrix"] = rotation_matrix([0, 0, .1]).tolist()
    assert target.update(sensors)["status"] == "executing"  # velocity not settled yet
    assert target.update(sensors)["status"] == "executing"
    result = target.update(sensors)
    assert result["status"] == "reached" and result["position_error_m"] < 1e-9


def test_queued_start_resets_terminated_scene_before_request(env, tmp_path):
    import queue
    runner = EpisodeRunner(env, output=tmp_path)
    try:
        env.terminated = True
        reply = queue.Queue()
        runner.commands.put(("start", dict(task=env.instruction, agent="mock_vla"), reply))
        runner.advance()
        assert reply.get()["ok"] and "reset" in env.worker.calls
        assert not env.terminated and runner.running
    finally:
        runner.close()


def test_diagnostic_has_no_physics_or_action_in_realtime(env, tmp_path):
    from concurrent.futures import Future
    from types import SimpleNamespace
    runner = EpisodeRunner(env, output=tmp_path, timing="realtime")
    try:
        env.terminated = True  # a connection check may inspect an ended scene
        runner.diagnostic_stage = "action"
        runner.policy = SimpleNamespace(last_latency=2.5, last_usage={}, request_options={"timeout_seconds": 120})
        runner.begin_episode("diagnostic", 1)
        runner.future = Future()
        runner.future_token = runner.token
        runner.future.set_result({"stage": "action", "action": {"kind": "move"}, "executed": False})
        runner.advance(1)
        assert runner.phase == "completed" and runner.diagnostic_result["executed"] is False
        assert not env.worker.actions and env.simulation_time == 0
        assert runner.manifest["mode"] == "connection_diagnostic"
    finally:
        runner.close()


def test_manual_motion_after_diagnostic_resumes_physics(env, tmp_path):
    runner = EpisodeRunner(env, output=tmp_path)
    try:
        runner.diagnostic_stage = "text"
        runner.command("manual", {"delta_position": [0,0,.01]})
        runner.advance(.05)
        assert runner.diagnostic_stage is None
        assert len(env.worker.actions) == 1 and env.simulation_time == .05
    finally:
        runner.close()


def test_wide_target_accepts_distant_goal_without_enlarging_native_commands(env):
    import numpy as np
    from maniloop.core.observations import guard_sensor_tree
    env.set_llm_control("tcp_target_servo_v3")
    packet, _ = env.observe()
    guard_sensor_tree(packet)
    assert packet["action_limits"]["translation_max_m"] == 2.5
    assert packet["action_limits"]["rotation_max_rad"] == pytest.approx(np.pi)
    delta, rotation = np.array([.3, .4, 0]), np.array([0, 0, np.pi])
    assert env.execute(dict(kind="move", delta_position=delta, delta_rotation=rotation))["max_control_steps"] == 200
    fixed = env._target.position.copy()
    env.step()
    native = np.array(env.worker.actions[-1])
    assert np.linalg.norm(native[:3]) == pytest.approx(1)
    assert np.linalg.norm(native[3:6]) == pytest.approx(1)
    assert max(abs(native)) <= 1
    assert native[:3] == pytest.approx([.6, .8, 0])
    env._sensors["tcp_position"] = [0.1, 0.2, 1.0]
    env._target.sample(env._sensors)
    np.testing.assert_array_equal(env._target.position, fixed)
    env.step(199)
    assert not env.busy and env.feedback["status"] == "timed_out"
    assert env.feedback["control_steps"] == 200


@pytest.mark.parametrize("delta,rotation", [([2, 2, 0], [0, 0, 0]),
    ([0, 0, 0], [2, 2, 2]), ([float("inf"), 0, 0], [0, 0, 0])])
def test_wide_target_guard_uses_vector_norm_and_finite_values(env, delta, rotation):
    env.set_llm_control("tcp_target_servo_v3")
    assert env.execute(dict(kind="move", delta_position=delta, delta_rotation=rotation))["status"] == "rejected"
    assert not env.busy and not env.worker.actions


def test_wide_target_stops_early_and_preserves_gripper_and_legacy_budgets(env):
    env.set_llm_control("tcp_target_servo_v3")
    env.execute(dict(kind="move", delta_position=[0, 0, 0]))
    env.step(2)
    assert not env.busy and env.feedback["status"] == "reached"
    env.execute(dict(kind="gripper", gripper_opening=1))
    env.step(20)  # fake opening stays 0.5, so opening cannot be complete
    assert not env.busy and env.feedback["status"] == "timed_out"
    assert env.feedback["control_steps"] == 20
    env.execute(dict(kind="move", delta_position=[.1, 0, 0]))
    env.worker.success = True
    env.step(200)
    assert env.terminated and not env.busy and env.feedback["control_steps"] == 1
    env.reset(0)
    env.set_llm_control("tcp_target_servo_v2")
    assert env.describe()["target_controller"]["max_steps"] == 20
    assert env.observe()[0]["action_limits"]["translation_max_m"] == .05
    assert env.execute(dict(kind="move", delta_position=[.1, 0, 0]))["status"] == "rejected"


def test_wide_target_records_distinct_comparison_group_and_execution_feedback(env, tmp_path):
    from maniloop.recording.manifest import describe_run
    from types import SimpleNamespace
    from concurrent.futures import Future
    runner = EpisodeRunner(env, output=tmp_path)
    try:
        runner.policy = SimpleNamespace(request_options={}, last_latency=0., last_usage={})
        env.set_llm_control("tcp_target_servo_v2")
        old = describe_run(runner)
        env.set_llm_control("tcp_target_servo_v3")
        new = describe_run(runner)
        assert old["comparison_group"] != new["comparison_group"]
        assert new["policy"]["action_interface"] == "tcp_target_servo_v3"
        assert new["policy"]["target_command_limits"]["translation_max_m"] == 2.5
        assert new["policy"]["target_controller"]["max_steps"] == 200
        runner.single_step = True
        runner.begin_episode("offline control fixture", 1)
        runner.future = Future()
        runner.future_token = runner.token
        runner.future.set_result(dict(kind="move", delta_position=[.1, 0, 0], delta_rotation=[0, 0, 0],
                                      observation_id=runner.pending_observation["observation_id"]))
        runner.advance(.05)
        assert runner.awaiting_execution and env.busy
        for _ in range(210):
            runner.advance(.05)
            if runner.paused:
                break
        execution = [event for event in runner.events if event["type"] == "execution"]
        assert runner.paused and len(execution) == 1
        assert execution[0]["feedback"]["control_steps"] == 200
        assert execution[0]["feedback"]["status"] == "timed_out"
    finally:
        runner.close()


def test_wide_target_only_valid_for_libero_llm_experiments():
    Experiment(backend="libero", agent="llm_cloud", llm_control="tcp_target_servo_v3").validate()
    for backend, agent in [("mujoco", "llm_cloud"), ("libero", "mock_vla"), ("libero", "lerobot")]:
        with pytest.raises(ValueError, match="LIBERO LLM"):
            Experiment(backend=backend, agent=agent, llm_control="tcp_target_servo_v3").validate()


@pytest.mark.parametrize("backend", ["mujoco", "robosuite", "robocasa"])
def test_invalid_wide_target_backend_rejected_before_replacing_scene(env, tmp_path, monkeypatch, backend):
    from maniloop.runtime import runner as runtime
    monkeypatch.setattr(runtime, "create_environment", lambda **kwargs: pytest.fail("Invalid mode must not create a replacement"))
    runner = EpisodeRunner(env, output=tmp_path)
    try:
        with pytest.raises(ValueError, match="LIBERO"):
            runner.command("configure", {"backend": backend, "llm_control": "tcp_target_servo_v3"})
        assert runner.sim is env and not env.worker.closed
        env.backend = backend
        with pytest.raises(ValueError, match="LIBERO"):
            runner.command("start", {"task": "fixture", "llm_control": "tcp_target_servo_v3"})
        assert runner.policy is None
    finally:
        runner.close()
