"""Opt-in real upstream checks: MANILOOP_TEST_LIBERO=1; no cloud API calls."""

import io
import os
import numpy as np
from PIL import Image
import pytest
from maniloop.backends.libero import LiberoEnvironment
from maniloop.backends.libero.transport import list_tasks, SUITES

pytestmark = pytest.mark.skipif(
    os.environ.get("MANILOOP_TEST_LIBERO") != "1",
    reason="Optional LIBERO runtime and graphics required",
)


@pytest.fixture(scope="module")
def official():
    env = LiberoEnvironment()
    yield env
    env.close()


def test_official_reset_images_native_motion_and_scoring(official):
    official.reset(7)
    before, images = official.observe()
    assert set(images) == {"external", "wrist"}
    for value in images.values():
        rgb = np.asarray(Image.open(io.BytesIO(value)))
        assert rgb.shape == (128, 128, 3) and rgb.std() > 10
    official.reset(7)
    again, _ = official.observe()
    np.testing.assert_allclose(
        before["joint_positions"], again["joint_positions"], atol=1e-7
    )
    np.testing.assert_allclose(before["tcp_position"], again["tcp_position"], atol=1e-7)
    for _ in range(10):
        result = official.execute(
            dict(kind="move", frame="world", delta_position=[0, 0, 0.005])
        )
        assert result["status"] == "accepted"
        official.step()
    after, _ = official.observe()
    assert after["tcp_position"][2] > again["tcp_position"][2] + 0.005
    assert official.simulation_time == 0.5
    evaluation = official.evaluation()
    assert (
        evaluation["evaluator"] == "libero_check_success" and not evaluation["success"]
    )
    assert "success" not in after and "object-state" not in after
    assert official.describe()["paper_comparable"] is False


@pytest.mark.parametrize("suite", SUITES)
def test_official_task_catalog(suite):
    tasks = list_tasks(suite)
    assert len(tasks) == (90 if suite == "libero_90" else 10)
    assert all(task["id"] == i and task["instruction"] for i, task in enumerate(tasks))


def test_learned_policy_observation_profile():
    with_profile = LiberoEnvironment(observation_profile="lerobot_rgb256")
    try:
        packet, images = with_profile.observe()
        assert len(packet["tcp_quaternion_xyzw"]) == 4
        assert len(packet["gripper_joint_positions"]) == 2
        assert with_profile.describe()["observation_profile"] == "lerobot_rgb256"
        for data in images.values():
            assert data.startswith(b"\x89PNG")
            assert Image.open(io.BytesIO(data)).size == (256, 256)
        assert not {"object-state", "success", "contacts"}.intersection(packet)
    finally:
        with_profile.close()


@pytest.mark.parametrize("delta,rotation", [([0,0,.01],[0,0,0]),([.01,0,0],[0,0,0]),
    ([0,-.01,0],[0,0,0]),([0,0,0],[0,0,.1])])
def test_real_target_pose_execution(official, delta, rotation):
    from maniloop.controllers.geometry import rotation_matrix, rotation_vector
    official.reset(0)
    official.set_llm_control("tcp_target_servo_v2")
    before, _ = official.observe()
    start = np.array(before['tcp_position'])
    target_rotation = rotation_matrix(rotation) @ np.array(before['tcp_rotation_matrix'])
    assert official.execute(dict(kind='move', frame='world', delta_position=delta, delta_rotation=rotation))['status'] == 'accepted'
    while official.busy:
        official.step()
    after, _ = official.observe()
    assert official.feedback['status'] == 'reached', official.feedback
    assert np.linalg.norm(np.array(after['tcp_position']) - start - delta) < .002
    assert np.linalg.norm(rotation_vector(target_rotation @ np.array(after['tcp_rotation_matrix']).T)) < .02
    assert official.feedback['control_steps'] <= 20
    official.set_llm_control("osc_step")


def test_llm_rgb512_profile():
    env = LiberoEnvironment(observation_profile='llm_rgb512')
    try:
        packet, images = env.observe()
        assert env.describe()['protocol'] == 'maniloop_libero_llm_rgb512_v2'
        assert packet['cameras']['external']['width'] == 512
        assert all(Image.open(io.BytesIO(data)).size == (512,512) for data in images.values())
        assert 'success' not in packet and 'object-state' not in packet
    finally:
        env.close()


def test_target_gripper_hold_close_and_open(official):
    official.set_llm_control("tcp_target_servo_v2")
    official.reset(0)
    packet, _ = official.observe()
    opening = official.gripper_opening
    official.execute(dict(kind="move", delta_position=[0,0,.01]))
    while official.busy:
        official.step()
    assert abs(official.gripper_opening - opening) < .02
    position = official.tcp_position.copy()
    for target in (0,1):
        official.execute(dict(kind="gripper", gripper_opening=target))
        while official.busy:
            official.step()
        assert official.feedback["status"] == "completed", official.feedback
        assert np.linalg.norm(official.tcp_position - position) < .002
        assert (official.gripper_opening < .1 if target == 0 else official.gripper_opening > .9)
    official.set_llm_control("osc_step")


def test_demo_paired_single_step_on_real_libero(tmp_path):
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

    env = LiberoEnvironment(observation_profile='llm_rgb512')
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
