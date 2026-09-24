"""Real simulation with explicit SYNTHETIC Jev responses; not model evaluation."""
import json
import os
import time
from pathlib import Path
import pytest
from maniloop.backends.factory import create_environment
from maniloop.runtime.runner import EpisodeRunner
from maniloop.providers.typesafe import TypeSafeClient
from test_jev import answer

pytestmark = pytest.mark.skipif(os.environ.get('MANILOOP_TEST_JEV_SIM') != '1',
                               reason='Opt-in actual simulator; Jev HTTP is mocked')


@pytest.mark.parametrize('backend,task', [('robosuite','Lift'), ('libero','pick_place'), ('robocasa','OpenDrawer')])
def test_sequence_executes_once_and_stops_without_extra_request(backend, task, monkeypatch, tmp_path):
    requests = []
    def post(client, payload):
        request = json.loads(payload); requests.append(request)
        command = request['state']['instruction']
        choice = 'tool_rotate_Z_plus' if 'Rotate' in command else 'fixed_translate_Z_plus'
        if 'gripper' in command: choice = 'gripper_open'
        return answer(request['questions']['action']['criteria'], choice)
    monkeypatch.setattr(TypeSafeClient, '_post', post)
    env = create_environment(backend=backend, task=task, observation_profile='debug_rgb128')
    runner = EpisodeRunner(env, output=tmp_path)
    before = env.tcp_position.copy()
    task = 'Move up 10 mm.\nRotate about tool Z by 5 degrees.\nOpen the gripper.'
    try:
        runner.command('start', {'agent': 'jev', 'task': task, 'max_steps': 6,
            'typesafe_api_key': 'fixture-not-real', 'jev_options': {'target_duration_seconds': 3}})
        deadline = time.monotonic() + 80
        while runner.running and time.monotonic() < deadline:
            runner.advance(.05)
            if runner.future is not None: time.sleep(.001)
        assert runner.error == '' and not runner.running, runner.error
        assert runner.termination_reason == 'command_sequence_complete'
        assert len(requests) == runner.api_calls == runner.step_count == 3
        assert env.gripper_opening > .9
        assert env.tcp_position[2] > before[2] + .005
        events = [json.loads(l) for l in runner.log_file.read_text(encoding="utf-8").splitlines()]
        assert len([e for e in events if e['type'] == 'provider_decision']) == 3
        assert 'fixture-not-real' not in runner.log_file.read_text(encoding="utf-8")
        assert runner.manifest['policy']['images_sent_to_policy'] is False
        assert runner.manifest['policy']['request_options']['target_duration_seconds'] == 3
        clock = env.simulation_time
        for _ in range(10): runner.advance(.05)
        assert env.simulation_time == clock
        print(json.dumps({'backend': backend, 'synthetic_jev': True, 'real_simulation': True,
                          'provider_requests': len(requests), 'control_steps': env.evaluation()['control_steps']}))
    finally:
        runner.close()
