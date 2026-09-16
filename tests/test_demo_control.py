"""Demo cadence and sensor evidence tests: fake policy, real MuJoCo, no network."""
from concurrent.futures import Future
from copy import deepcopy
import json
import time
import pytest
from maniloop.runtime.runner import EpisodeRunner
from maniloop.core.observations import guard_sensor_tree
from arx5_demo.sim import RobotSim


class Policy:
    last_latency = .1
    last_usage = {}
    request_options = {}
    def __init__(self):
        self.requests = []
        self.cancelled = False
    def reset(self, seed):
        self.cancelled = False
    def cancel(self):
        self.cancelled = True
    def decide(self, task, observation, images, history, geometry):
        self.requests.append(deepcopy((observation, images, history, geometry)))
        return dict(observation_id=observation['observation_id'], kind='move',
                    delta_position=[0, 0, .002], delta_rotation=[0, 0, 0],
                    gripper_opening=0, camera='', pixel=[0, 0], explanation='test step')


@pytest.fixture
def demo(tmp_path):
    sim = RobotSim(render=False)
    runner = EpisodeRunner(sim, output=tmp_path)
    runner.policy = Policy()
    runner.single_step = True
    runner.context_mode = 'paired'
    runner.begin_episode('test', 3)
    yield runner
    runner.close()


def advance_until(demo, condition):
    for _ in range(3000):
        demo.advance(.02)
        if condition():
            return
        time.sleep(.0001)
    pytest.fail(f'did not reach expected state: {demo.phase}')


def test_single_step_waits_for_completion_freezes_then_pairs(demo):
    advance_until(demo, lambda: demo.paused)
    assert demo.api_calls == 1 and demo.step_count == 1
    assert not demo.sim.busy
    frozen = demo.sim.simulation_time
    for _ in range(20):
        demo.advance(.2)
    assert demo.sim.simulation_time == frozen and demo.api_calls == 1
    assert demo.replay_html and (demo.log_file.parent / 'replay.html').exists()
    # Independent scoring is present in the human artifact only.
    assert 'evaluation' in json.loads((demo.log_file.parent / 'review-summary.json').read_text(encoding='utf-8'))
    demo.command('step', {})
    advance_until(demo, lambda: demo.paused)
    assert demo.api_calls == 2 and demo.step_count == 2
    request = demo.policy.requests[1]
    transition = request[2][-1]['transition']
    assert transition['protocol'] == 'sensor_transition_v1'
    assert transition['before']['observation_id'] != request[0]['observation_id']
    assert transition['feedback']['status'] != 'accepted'
    guard_sensor_tree(request)
    assert 'evaluation' not in json.dumps(request)
    assert demo.history[0]['feedback']['status'] != 'accepted'
    demo.command('resume', {})
    advance_until(demo, lambda: not demo.running)
    assert demo.api_calls == 3 and demo.termination_reason == 'decision_budget'


def test_pause_during_inflight_allows_one_action_and_no_second_request(demo):
    demo.single_step = False
    demo.future = Future()
    demo.future_token = demo.token
    demo.api_calls = 1
    demo.command('pause', {})
    demo.advance()
    assert demo.pause_requested and not demo.paused
    packet = demo.pending_observation
    action = demo.policy.decide('test', packet, {}, [], [])
    demo.future.set_result(action)
    advance_until(demo, lambda: demo.paused)
    assert demo.api_calls == 1 and demo.step_count == 1


def test_stop_cancels_process_and_discards_late_action(demo):
    policy = demo.policy
    demo.future = Future()
    demo.future_token = demo.token
    demo.stop()
    assert policy.cancelled
    demo.future.set_result(policy.decide('test', demo.pending_observation, {}, [], []))
    demo.tick()
    assert not demo.running and demo.step_count == 0


@pytest.mark.parametrize('payload', [
    {'history': [{'feedback': {'status': 'completed', 'success': True}}]},
    {'transition': {'after': {'object_pose': [1, 2, 3]}}},
    {'last_feedback': {'status': 'done', 'extra': {'native_success': True}}},
    {'geometry': [{'score': 1}]},
])
def test_nested_privileged_feedback_rejected(payload):
    with pytest.raises(ValueError):
        guard_sensor_tree(payload)


@pytest.mark.parametrize('command', ['reset', 'configure', 'stop'])
def test_ended_review_is_not_overwritten_by_next_scene(demo, monkeypatch, command):
    demo.running = False
    demo.phase = 'completed'
    demo.termination_reason = 'model_done'
    demo.update_review()
    directory = demo.log_file.parent
    original_summary = (directory / 'review-summary.json').read_bytes()
    original_replay = (directory / 'replay.html').read_bytes()
    if command == 'configure':
        monkeypatch.setattr('maniloop.runtime.runner.create_environment', lambda **_: RobotSim(render=False))
    demo.command(command, {'seed': 4})
    demo.advance()
    assert (directory / 'review-summary.json').read_bytes() == original_summary
    assert (directory / 'replay.html').read_bytes() == original_replay


def test_single_step_discard_due_to_config_change_still_pauses(demo, monkeypatch):
    demo.credential_source = 'file'
    monkeypatch.setattr(demo, 'refresh_local_connection', lambda: True)
    demo.api_calls = 1
    demo.future_token = demo.token
    demo.future = Future()
    demo.future.set_result({})
    demo.tick()
    demo.tick()
    assert demo.paused and demo.api_calls == 1 and not demo.policy.requests


def test_single_step_done_clears_pending_pause(demo):
    action = demo.policy.decide('test', demo.pending_observation, {}, [], [])
    action.update(kind='done', delta_position=[0, 0, 0])
    demo.future_token = demo.token
    demo.future = Future()
    demo.future.set_result(action)
    demo.tick()
    assert not demo.running and demo.phase == 'completed'
    assert not demo.paused and not demo.pause_requested


def test_review_does_not_invalidate_depth_followup(demo):
    import numpy as np
    observation, images = demo.sim.observe()
    demo.pending_observation, demo.request_images = observation, images
    demo.sim._snapshot['depth'] = np.full((480, 640), .6)
    result = demo.sim.depth_query({'observation_id': observation['observation_id'],
                                 'camera': 'external', 'pixel': [320, 240]})
    assert result['valid']
    demo.geometry = [result]
    demo.paused = True
    demo.phase = 'paused'
    demo.update_review()
    assert demo.sim.validate_snapshot(observation)[0]
    demo.command('step', {})
    demo.tick()
    demo.future.result(timeout=5)
    assert demo.policy.requests[0][3] == [result]
