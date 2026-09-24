"""RoboCasa wiring and full-action mapping without optional dependencies or model calls."""
import copy
import json
from types import SimpleNamespace
import numpy as np
import pytest
from maniloop.backends.robocasa import environment as adapter
from maniloop.backends.robocasa.catalog import TASKS, list_tasks
from maniloop.backends.robocasa.worker import Runtime
from maniloop.backends.factory import create_environment
from maniloop.evaluation.benchmark import Experiment, load_suite
from maniloop.representations.sensors import SensorRepresentation

SENSORS = dict(joint_names=[f'j{i}' for i in range(7)], joint_positions=[0.0]*7,
    joint_velocities=[0.0]*7, tcp_position=[0.0,0.0,1.0], tcp_rotation_matrix=np.eye(3).tolist(),
    gripper_opening=0.5)


class FakeWorker:
    def __init__(self, *args, **kwargs):
        self.closed, self.steps, self.actions = False, 0, []
        self.description = dict(backend='robocasa', robot='panda_omron', task='OpenDrawer',
            scene='kitchen_11_14', layout=11, style=14, instruction='Open the left drawer.',
            observation_profile='debug_rgb128', protocol='test', controller='upstream',
            control_scope='arm_only', action_adapter='arm7_to_full12', controller_config={},
            runtime_dependencies={}, camera_preprocessing='test', upstream_revision='test',
            upstream_source_sha256='test', robosuite_source='test', robosuite_source_sha256='test')
    def call(self, op, **kwargs):
        if op == 'init':
            return copy.deepcopy(self.description)
        if op == 'reset':
            self.steps = 0
            self.description['instruction'] = f"Open the drawer for seed {kwargs['seed']}."
            return dict(sensors=copy.deepcopy(SENSORS), description=copy.deepcopy(self.description))
        if op == 'observe':
            return dict(sensors=copy.deepcopy(SENSORS), cameras={}, images={})
        if op == 'step':
            self.steps += 1
            self.actions.append(kwargs['action'])
            return dict(sensors=copy.deepcopy(SENSORS), steps=self.steps, terminated=False)
        if op == 'evaluate':
            return dict(success=False, evaluator='robocasa_check_success')
        raise AssertionError(op)
    def close(self):
        self.closed = True


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(adapter, 'Worker', FakeWorker)
    value = adapter.RobocasaEnvironment(render=False)
    yield value
    value.close()


def test_reset_updates_official_language_and_invalidates_snapshot(env):
    before, _ = env.observe()
    env.reset(7)
    assert env.instruction == env.describe()['instruction'] == 'Open the drawer for seed 7.'
    assert not env.validate_snapshot(before, float('inf'))[0]


def test_sensor_boundary_and_arm_subset_description(env):
    packet, _ = env.observe()
    SensorRepresentation().encode(packet)
    assert packet['frame_id'] == 'world'
    assert packet['action_limits']['upstream_action_dimension'] == 12
    assert packet['action_limits']['native_dimension'] == 7
    assert not packet['geometry_queries']['depth_available']
    assert not {'success','object_pose','evaluation'}.intersection(packet)
    assert 'PandaOmron' in packet['robot_description']
    assert not env.depth_query({})['valid']


def test_execute_has_one_clock_and_cancel(env):
    assert env.execute(dict(kind='move', delta_position=[.005,0,0]))['status'] == 'accepted'
    assert env.simulation_time == 0 and not env.worker.actions
    env.step()
    assert env.simulation_time == .05 and env.worker.actions[0][:3] == pytest.approx([.1,0,0])
    packet, _ = env.observe()
    env.execute(dict(kind='gripper',gripper_opening=0))
    env.hold()
    assert not env.busy and not env.validate_snapshot(packet)[0]


@pytest.mark.parametrize('task', TASKS)
def test_catalog_factory_and_batch_validation(task):
    Experiment(backend='robocasa',task=task,robocasa_layout=11,robocasa_style=14).validate()
    assert len(list_tasks()) == 4


@pytest.mark.parametrize('changes', [dict(robot='panda'),dict(robocasa_layout=0),
    dict(robocasa_style=True),dict(agent='lerobot'),dict(record_episode=True)])
def test_unsupported_combinations_are_rejected(changes):
    with pytest.raises(ValueError):
        Experiment(backend='robocasa',task='OpenDrawer',**changes).validate()


def test_full_action_rotates_into_base_and_preserves_other_parts():
    calls = []
    rotation = np.array([[0,-1,0],[1,0,0],[0,0,1]])
    def assemble(parts):
        calls.append(parts)
        return np.r_[parts['right'],parts['right_gripper'],parts['base'],parts['torso'],parts['base_mode']]
    robot = SimpleNamespace(part_controllers={'right':SimpleNamespace(origin_ori=rotation)},
                            create_action_vector=assemble)
    r = Runtime.__new__(Runtime)
    r.np = np
    r.env = SimpleNamespace(robots=[robot],action_spec=(-np.ones(12),np.ones(12)))
    native = r.full_action([.2,0,0,.1,0,0,1])
    assert native.shape == (12,)
    np.testing.assert_allclose(native[:6],[0,-.2,0,0,-.1,0],atol=1e-12)
    np.testing.assert_array_equal(native[7:11],np.zeros(4))
    assert native[6] == 1 and native[11] == -1
    with pytest.raises(ValueError):r.full_action([0]*12)
    with pytest.raises(ValueError):r.full_action([float('nan')]+[0]*6)
