"""Opt-in real RoboCasa scene/control checks. Never calls a model provider."""
import io
import json
import os
from pathlib import Path
import subprocess
import numpy as np
from PIL import Image
import pytest
from maniloop.backends.robocasa import RobocasaEnvironment
from maniloop.backends.robocasa.catalog import TASKS
from maniloop.representations.sensors import SensorRepresentation

pytestmark = pytest.mark.skipif(os.environ.get('MANILOOP_TEST_ROBOCASA') != '1',
                               reason='Optional RoboCasa runtime/assets/rendering required')


@pytest.mark.parametrize('task', TASKS)
def test_task_scene_language_sensor_action_reset(task, tmp_path):
    env = RobocasaEnvironment(task=task, layout=11, style=14)
    try:
        first, images = env.observe()
        SensorRepresentation().encode(first)
        assert set(images) == {'external','wrist'}
        for name, raw in images.items():
            rgb = np.array(Image.open(io.BytesIO(raw)))
            assert rgb.shape == (128,128,3) and rgb.std() > 10
            (tmp_path / f'{task}-{name}.jpg').write_bytes(raw)
        description = env.describe()
        assert description['native_action_dimension'] == 12
        assert description['controller_config']['body_parts']['right']['input_ref_frame'] == 'base'
        assert env.instruction and env.simulation_time == 0
        env.set_llm_control('tcp_target_servo_v2')
        assert env.execute(dict(kind='move',delta_position=[0,0,.005]))['status'] == 'accepted'
        for _ in range(20):
            if not env.busy:
                break
            env.step()
        after, _ = env.observe()
        assert np.isfinite(after['tcp_position']).all()
        assert after['tcp_position'][2] > first['tcp_position'][2]
        assert env.evaluation()['evaluator'] == 'robocasa_check_success'
        previous = after
        env.reset(0)
        assert not env.validate_snapshot(previous, float('inf'))[0]
        reset, _ = env.observe()
        np.testing.assert_allclose(reset['tcp_position'], first['tcp_position'], atol=1e-7)
        assert env.simulation_time == 0
        (tmp_path / f'{task}-description.json').write_text(json.dumps(env.describe(),indent=2))
    finally:
        env.close()
        env.close()


@pytest.mark.parametrize('delta,rotation', [([.005,0,0],[0,0,0]),([0,.005,0],[0,0,0]),
                                           ([0,0,0],[0,0,.05])])
def test_world_targets_with_rotated_mobile_base(delta,rotation):
    from maniloop.controllers.geometry import rotation_matrix,rotation_vector
    env = RobocasaEnvironment(task='OpenDrawer')
    try:
        env.set_llm_control('tcp_target_servo_v2')
        before,_=env.observe()
        goal=np.array(before['tcp_position'])+delta
        orientation=rotation_matrix(rotation)@np.array(before['tcp_rotation_matrix'])
        assert env.execute(dict(kind='move',delta_position=delta,delta_rotation=rotation))['status']=='accepted'
        while env.busy:
            env.step()
        after,_=env.observe()
        assert np.linalg.norm(np.array(after['tcp_position'])-goal)<.002,env.feedback
        assert np.linalg.norm(rotation_vector(orientation@np.array(after['tcp_rotation_matrix']).T))<.02
        assert env.feedback['status']=='reached',env.feedback
    finally:
        env.close()


def test_reset_gc_and_full_action_hold_parts(tmp_path):
    root=Path(__file__).resolve().parents[1]
    python=os.environ.get('MANILOOP_ROBOCASA_PYTHON') or str(root/'.venv-robocasa/bin/python')
    code='''
import gc,sys,json,base64
import numpy as np
sys.path.insert(0,sys.argv[1])
from worker import Runtime
r=Runtime(dict(task='OpenDrawer',render=True,observation_profile='llm_rgb512',layout=11,style=14))
try:
    for i in range(2):
        if i:r.reset(0)
        before=r.observe()
        qpos=r.env.sim.data.qpos.copy()
        qvel=r.env.sim.data.qvel.copy()
        clock=r.env.sim.data.time
        gc.collect()
        after=r.observe()
        assert before['images']==after['images'],'GC changed a frozen snapshot'
        assert before['images']['external']!=before['images']['wrist']
        np.testing.assert_array_equal(qpos,r.env.sim.data.qpos)
        np.testing.assert_array_equal(qvel,r.env.sim.data.qvel)
        assert clock==r.env.sim.data.time
        logical=np.array([.1,0,0,0,.1,0,1])
        rotation=r.env.robots[0].part_controllers['right'].origin_ori.copy()
        a=r.full_action(logical)
        np.testing.assert_allclose(a[:3],rotation.T@logical[:3])
        np.testing.assert_allclose(a[3:6],rotation.T@logical[3:6])
        np.testing.assert_array_equal(a[7:11],np.zeros(4))
        assert a[-1]==-1 and a[6]==1 and len(a)==12
        r.step([0,0,.1,0,0,0,0])
        moved=r.observe()
        assert r.steps==1
        gc.collect()
        assert moved['images']==r.observe()['images']
finally:r.close()
'''
    result=subprocess.run([python,'-c',code,str(root/'src/maniloop/backends/robocasa')],
                          cwd=root,capture_output=True,text=True,timeout=180)
    (tmp_path/'gc-output.txt').write_text(result.stdout+result.stderr)
    assert result.returncode==0,result.stdout+result.stderr


def test_demo_paired_single_step_on_real_robocasa(tmp_path):
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

    env = RobocasaEnvironment(task="OpenDrawer", observation_profile='llm_rgb512')
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
