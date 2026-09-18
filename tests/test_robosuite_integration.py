"""Opt-in real robosuite checks; no model API or learned policy required."""
import io
import os
import numpy as np
from PIL import Image
import pytest
from maniloop.backends.robosuite import RobosuiteEnvironment
from maniloop.backends.robosuite.catalog import TASKS
from maniloop.representations.sensors import SensorRepresentation
from maniloop.controllers.geometry import rotation_matrix, rotation_vector

pytestmark = pytest.mark.skipif(os.environ.get('MANILOOP_TEST_ROBOSUITE') != '1',
                               reason='Optional robosuite runtime and graphics required')


@pytest.fixture(scope='module')
def env():
    value = RobosuiteEnvironment(task='Lift')
    yield value
    value.close()


@pytest.mark.parametrize('task', TASKS)
def test_task_reset_render_native_step_and_official_evaluator(task):
    value = RobosuiteEnvironment(task=task)
    try:
        value.reset(7)
        first, images = value.observe()
        SensorRepresentation().encode(first)
        assert set(images) == {'external', 'wrist'}
        for data in images.values():
            rgb = np.array(Image.open(io.BytesIO(data)))
            assert rgb.shape == (128, 128, 3) and rgb.std() > 10
        assert not {'success', 'object-state', 'contacts'}.intersection(first)
        assert value.describe()['tcp_orientation_source'] == 'robot0_eef_quat_site'
        assert value.describe()['controller_overrides'] == {'input_ref_frame': 'world'}
        value.reset(7)
        again, again_images = value.observe()
        np.testing.assert_allclose(first['tcp_position'], again['tcp_position'], atol=1e-7)
        np.testing.assert_allclose(first['joint_positions'], again['joint_positions'], atol=1e-7)
        assert images == again_images
        result = value.execute(dict(kind='move', frame='world', delta_position=[0, 0, .005]))
        assert result['status'] == 'accepted' and value.simulation_time == 0
        value.step()
        assert value.simulation_time == .05
        score = value.evaluation()
        assert score['evaluator'] == 'robosuite_check_success'
        assert score['control_steps'] == 1 and not score['success']
    finally:
        value.close()
        value.close()


@pytest.mark.parametrize('delta,rotation', [([0,0,.01],[0,0,0]), ([.01,0,0],[0,0,0]),
                                           ([0,-.01,0],[0,0,0]), ([0,0,0],[0,0,.1])])
def test_actual_target_execution(env, delta, rotation):
    env.reset(0)
    env.set_llm_control('tcp_target_servo_v2')
    before, _ = env.observe()
    target = np.array(before['tcp_position']) + delta
    target_rotation = rotation_matrix(rotation) @ np.array(before['tcp_rotation_matrix'])
    assert env.execute(dict(kind='move', frame='world', delta_position=delta,
                            delta_rotation=rotation))['status'] == 'accepted'
    for _ in range(20):
        if not env.busy:
            break
        env.step()
    after, _ = env.observe()
    assert env.feedback['status'] == 'reached', env.feedback
    assert np.linalg.norm(np.array(after['tcp_position']) - target) < .002
    assert np.linalg.norm(rotation_vector(target_rotation @ np.array(after['tcp_rotation_matrix']).T)) < .02


def test_gripper_holding_and_cancel(env):
    env.reset(0)
    env.set_llm_control('tcp_target_servo_v2')
    before = env.tcp_position.copy()
    for opening in (1, 0):
        assert env.execute(dict(kind='gripper', gripper_opening=opening))['status'] == 'accepted'
        for _ in range(20):
            if not env.busy:
                break
            env.step()
        assert env.feedback['status'] == 'completed', env.feedback
        assert np.linalg.norm(env.tcp_position - before) < .002
        assert env.gripper_opening > .9 if opening else env.gripper_opening < .1
    snapshot, _ = env.observe()
    env.execute(dict(kind='move', frame='world', delta_position=[0, 0, .01]))
    clock = env.simulation_time
    env.hold()
    assert not env.busy and env.simulation_time == clock
    assert not env.validate_snapshot(snapshot)[0]


def test_rgb512_and_single_clock(env):
    other = RobosuiteEnvironment(task='Lift', observation_profile='llm_rgb512')
    try:
        observation, images = other.observe()
        for data in images.values():
            assert Image.open(io.BytesIO(data)).size == (512, 512)
        assert other.simulation_time == 0
        assert observation['frame_id'] == 'world'
        other.render_images()
        other.evaluation()
        assert other.simulation_time == 0
    finally:
        other.close()


def test_demo_paired_single_step_on_real_robosuite(tmp_path):
    """Actual sensor/servo/UI-runner path with a fixture policy, never GPT."""
    import time
    from copy import deepcopy
    from maniloop.runtime.runner import EpisodeRunner
    from maniloop.core.observations import guard_sensor_tree

    class FixturePolicy:
        last_latency = 0.0
        last_usage = {}
        request_options = {'transport': 'offline_fixture'}
        def __init__(self): self.requests = []
        def decide(self, task, observation, images, history, geometry):
            self.requests.append(deepcopy((observation, images, history)))
            return dict(observation_id=observation['observation_id'], kind='move',
                        delta_position=[0, 0, .005], delta_rotation=[0, 0, 0],
                        gripper_opening=0, camera='', pixel=[0, 0], explanation='offline fixture')

    env = RobosuiteEnvironment(task="Lift", observation_profile='llm_rgb512')
    env.set_llm_control('tcp_target_servo_v2')
    runner = EpisodeRunner(env, model='offline-fixture', output=tmp_path)
    try:
        policy = runner.policy = FixturePolicy()
        runner.context_mode = 'paired'
        runner.single_step = True
        runner.begin_episode('offline integration motion only', 2)
        for expected in (1, 2):
            if expected == 2: runner.command('step', {})
            for _ in range(3000):
                runner.advance(.05)
                if runner.paused: break
                time.sleep(.001)
            assert runner.paused and runner.api_calls == expected and not env.busy
        current, images, history = policy.requests[1]
        assert set(images) == {'external', 'wrist', 'previous/external', 'previous/wrist'}
        assert all(Image.open(io.BytesIO(data)).size == (512, 512) for data in images.values())
        transition = history[-1]['transition']
        assert transition['feedback']['status'] in {'reached', 'timed_out'}
        assert transition['after']['tcp_position'][2] > transition['before']['tcp_position'][2]
        guard_sensor_tree([current, history])
        frozen = env.simulation_time
        runner.advance(1)
        assert env.simulation_time == frozen
        assert runner.replay_html and (runner.log_file.parent / 'review-summary.json').exists()
    finally:
        runner.close()


def test_snapshot_does_not_reuse_cached_camera_buffers():
    import subprocess
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    python = os.environ.get('MANILOOP_ROBOSUITE_PYTHON') or str(
        root / '.venv-robosuite' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python'))
    code = '''
import sys, base64, io
import numpy as np
from PIL import Image
sys.path.insert(0, sys.argv[1])
from worker import Runtime
r = Runtime(dict(task='Lift', render=True, seed=0))
try:
    for camera in ('agentview', 'robot0_eye_in_hand'):
        r.obs[camera + '_image'][:] = 0
    before = r.env.sim.data.time
    packet = r.observe()
    for label, camera in [('external', 'agentview'), ('wrist', 'robot0_eye_in_hand')]:
        decoded = np.array(Image.open(io.BytesIO(base64.b64decode(packet['images'][label]))))
        current = r.env.sim.render(height=128, width=128, camera_name=camera)[::-1]
        assert np.mean(np.abs(decoded.astype(float) - current)) < 4
    assert r.env.sim.data.time == before
finally:
    r.close()
'''
    result = subprocess.run([python, '-c', code, str(root / 'src/maniloop/backends/robosuite')],
                            cwd=root, text=True, capture_output=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
