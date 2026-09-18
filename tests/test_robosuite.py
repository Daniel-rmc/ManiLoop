"""Backend contract tests need no robosuite installation, downloads, graphics or API key."""

import copy
import json
import time
from pathlib import Path
import pytest
from maniloop.backends.robosuite import environment as adapter
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
    task="Lift",
    scene="robosuite_tabletop",
    robot="panda",
    upstream_source_sha256="test",
    controller_overrides={"input_ref_frame": "world"},
    instruction="Lift the cube.",
    observation_profile="debug_rgb128",
    backend="robosuite",
    controller="robosuite_robosuite_OSC_POSE",
    protocol="test",
    upstream_revision="test",
    controller_config={},
    runtime_dependencies={},
    camera_preprocessing="test",
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
    value = adapter.RobosuiteEnvironment(render=False)
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
        assert manifest["policy"]["action_interface"] == "robosuite_osc_chunk_v1"
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


def test_task_catalog_and_experiment_validation(tmp_path):
    from maniloop.backends.robosuite.catalog import list_tasks
    expected = {'Lift', 'Stack', 'PickPlaceCan', 'Door', 'NutAssemblySquare'}
    assert {item['id'] for item in list_tasks()} == expected
    for task in expected:
        Experiment(backend='robosuite', task=task).validate()
    for kwargs in (dict(task='invented'), dict(task='Lift', robot='arx5'),
                   dict(task='Lift', agent='lerobot'), dict(task='Lift', record_episode=True)):
        with pytest.raises(ValueError):
            Experiment(backend='robosuite', **kwargs).validate()
    path = tmp_path / 'suite.toml'
    path.write_text('[experiment]\nbackend="robosuite"\n[matrix]\ntask=["Lift","Stack"]\nseed=[0,1]\n')
    assert len(load_suite(path)) == 4


def test_missing_runtime_has_installation_guidance(tmp_path):
    from maniloop.backends.robosuite.transport import Worker
    with pytest.raises(RuntimeError, match='docs/ROBOSUITE.md'):
        Worker(python=str(tmp_path / 'missing-python'))


def test_invalid_task_and_profile_fail_before_starting_worker():
    with pytest.raises(ValueError, match='Unknown robosuite task'):
        adapter.RobosuiteEnvironment(task='not_a_task')
    with pytest.raises(ValueError, match='observation profile'):
        adapter.RobosuiteEnvironment(task='Lift', observation_profile='lerobot_rgb256')


def test_worker_horizon_and_success_stop_without_extra_step():
    from types import SimpleNamespace
    import numpy as np
    from maniloop.backends.robosuite.worker import Runtime
    calls = []
    runtime = Runtime.__new__(Runtime)
    runtime.np = np
    runtime.sensors = lambda: {}
    runtime.steps, runtime.done, runtime.success = 999, False, False
    runtime.env = SimpleNamespace(
        robots=[SimpleNamespace(create_action_vector=lambda parts: np.r_[parts['right'], parts['right_gripper']])],
        step=lambda action: (calls.append(action) or {}, 0, False, {}),
        _check_success=lambda: False)
    result = runtime.step([0.0] * 7)
    assert result['terminated'] and result['steps'] == 1000
    runtime.step([0.0] * 7)
    assert len(calls) == 1
    runtime.steps, runtime.done = 0, False
    runtime.env._check_success = lambda: True
    assert runtime.step([0.0] * 7)['terminated']
    assert runtime.success
    runtime.step([0.0] * 7)
    assert len(calls) == 2
