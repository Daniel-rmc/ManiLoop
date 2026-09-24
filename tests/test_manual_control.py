"""Human jog conversion and routing; no network or model calls."""
from copy import deepcopy
import math
import numpy as np
import pytest
from maniloop.controllers.manual import prepare_manual_move
from maniloop.controllers.geometry import rotation_matrix


def observation(frame="world"):
    return dict(frame_id=frame,
                tcp_rotation_matrix=rotation_matrix([0, math.pi / 2, 0]).tolist(),
                action_limits=dict(translation_max_m=.05, rotation_max_rad=.5))


@pytest.mark.parametrize("frame", ["world", "base"])
@pytest.mark.parametrize("reference", ["fixed", "tool"])
def test_pose_mapping(frame, reference):
    obs = observation(frame)
    payload = dict(delta_position=[.003, -.002, .001], delta_rotation=[.02, .03, .04],
                   reference_frame=reference)
    original = deepcopy(payload)
    action = prepare_manual_move(payload, obs)
    r = np.array(obs['tcp_rotation_matrix'])
    transform = r if reference == 'tool' else np.eye(3)
    np.testing.assert_allclose(action['delta_position'], transform @ payload['delta_position'])
    np.testing.assert_allclose(action['delta_rotation'], transform @ payload['delta_rotation'])
    assert action['frame'] == frame and action['kind'] == 'move'
    assert payload == original and 'reference_frame' not in action
    expected = r @ rotation_matrix(payload['delta_rotation']) if reference == 'tool' else rotation_matrix(payload['delta_rotation']) @ r
    np.testing.assert_allclose(rotation_matrix(action['delta_rotation']) @ r, expected, atol=1e-10)


def test_tool_z_is_not_world_z_for_a_tilted_tool():
    action = prepare_manual_move(dict(delta_rotation=[0, 0, .1], reference_frame='tool'), observation())
    np.testing.assert_allclose(action['delta_rotation'], [.1, 0, 0], atol=1e-12)
    assert action['delta_position'] == [0, 0, 0]


@pytest.mark.parametrize('payload', [
    dict(delta_rotation=[True, 0, 0]), dict(delta_rotation=[float('nan'), 0, 0]),
    dict(delta_rotation=[0, 0]), dict(delta_position=['1', 0, 0]),
    dict(delta_rotation=[.4, .4, 0]), dict(delta_position=[.06, 0, 0]),
    dict(reference_frame='camera'), dict(frame='base'),
])
def test_invalid_input_fails_before_control(payload):
    with pytest.raises(ValueError):
        prepare_manual_move(payload, observation())


def test_tool_transform_requires_a_real_rotation():
    for matrix in (None, [[1, 0], [0, 1]], np.zeros((3, 3)), np.diag([1, 1, -1])):
        obs = observation(); obs['tcp_rotation_matrix'] = matrix
        with pytest.raises(ValueError):
            prepare_manual_move(dict(reference_frame='tool'), obs)


def test_runner_uses_fresh_tool_axes_and_preserves_gripper_path():
    from types import SimpleNamespace
    from unittest.mock import Mock
    from maniloop.runtime.runner import EpisodeRunner
    runner = EpisodeRunner.__new__(EpisodeRunner)
    runner.running, runner.future, runner.chunk = False, None, None
    runner.event = Mock()
    runner.sim = SimpleNamespace(busy=False, timestep=.05, observe=Mock(return_value=(observation(), {})),
        execute=Mock(return_value={'status': 'accepted', 'message': 'test'}))
    runner.command('manual', dict(delta_rotation=[0, 0, .1], reference_frame='tool'))
    runner.sim.observe.assert_called_once()
    resolved = runner.sim.execute.call_args.args[0]
    np.testing.assert_allclose(resolved['delta_rotation'], [.1, 0, 0], atol=1e-12)
    assert runner.event.call_args.kwargs['resolved_action'] == resolved
    runner.command('manual', dict(kind='gripper', gripper_opening=1))
    assert runner.sim.observe.call_count == 1
    assert runner.sim.execute.call_args.args[0] == dict(kind='gripper', gripper_opening=1)
    runner.sim.busy = True
    with pytest.raises(ValueError):
        runner.command('manual', dict(delta_rotation=[0, 0, .1]))
    assert runner.sim.observe.call_count == 1 and runner.sim.execute.call_count == 2


@pytest.mark.parametrize('reference', ['fixed', 'tool'])
def test_builtin_panda_rotates_without_a_model(reference, tmp_path):
    from maniloop.backends.factory import create_environment
    from maniloop.controllers.geometry import rotation_vector
    from maniloop.runtime.runner import EpisodeRunner
    env = create_environment(backend='mujoco', robot='panda', render=False)
    runner = EpisodeRunner(env, output=tmp_path)
    try:
        before, _ = env.observe()
        r = np.array(before['tcp_rotation_matrix']); delta = [0, 0, math.radians(5)]
        runner.command('manual', dict(delta_rotation=delta, reference_frame=reference))
        assert env.feedback['status'] == 'accepted'
        for _ in range(1500):
            if not env.busy and env.settled:
                break
            runner.advance(.01)
        after, _ = env.observe()
        target = r @ rotation_matrix(delta) if reference == 'tool' else rotation_matrix(delta) @ r
        assert np.linalg.norm(rotation_vector(target @ np.array(after['tcp_rotation_matrix']).T)) < .005
        assert np.linalg.norm(np.array(after['tcp_position']) - before['tcp_position']) < .001
        assert runner.api_calls == 0
    finally:
        runner.close()


@pytest.mark.parametrize('backend', ['robosuite', 'libero'])
def test_manual_budget_does_not_change_policy_budget(monkeypatch, backend):
    import importlib
    from test_robosuite import FakeWorker as RSWorker
    from test_libero import FakeWorker as LWorker
    module = importlib.import_module(f'maniloop.backends.{backend}.environment')
    monkeypatch.setattr(module, 'Worker', RSWorker if backend == 'robosuite' else LWorker)
    cls = module.RobosuiteEnvironment if backend == 'robosuite' else module.LiberoEnvironment
    env = cls(render=False)
    try:
        env.set_llm_control('tcp_target_servo_v2')
        action = dict(kind='move', delta_rotation=[0, 0, .1])
        env.execute_manual(action, max_control_steps=60)
        assert env._target.settings.max_steps == 60
        assert env.feedback['max_control_steps'] == 60
        env.hold()
        env.execute(action)
        assert env._target.settings.max_steps == 20
        assert env.describe()['target_controller']['max_steps'] == 20
    finally:
        env.close()


@pytest.mark.parametrize('value', [True, None, 0, -1, 11, '3', float('nan'), float('inf')])
def test_manual_target_time_validation(value):
    from maniloop.controllers.manual import manual_control_steps
    with pytest.raises(ValueError):
        manual_control_steps(value, .05)


def test_manual_target_time_uses_control_steps():
    from maniloop.controllers.manual import manual_control_steps
    assert manual_control_steps(3, .05) == 60
    assert manual_control_steps(.125, .05) == 3
