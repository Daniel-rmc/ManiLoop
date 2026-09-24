"""Browser Jev credentials: isolated, memory-only, no real provider requests."""
import json
import time
from concurrent.futures import Future
from pathlib import Path
import pytest
from maniloop.providers.typesafe import TypeSafeClient, normalize_api_key
from maniloop.providers.responses import PolicyError
from maniloop.runtime.runner import EpisodeRunner
from maniloop.backends.robosuite import environment as adapter
from test_robosuite import FakeWorker
from test_jev import answer

KEY = 'synthetic-typesafe-browser-key'


@pytest.fixture
def runner(monkeypatch, tmp_path):
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-openai-only-key')
    monkeypatch.setattr(adapter, 'Worker', FakeWorker)
    env = adapter.RobosuiteEnvironment(render=False)
    value = EpisodeRunner(env, output=tmp_path)
    yield value
    value.running = False
    if value.future is not None and not value.future.done():
        value.future.cancel()
    value.close()

def test_save_clear_never_calls_provider_or_changes_openai(runner, monkeypatch):
    monkeypatch.setattr(TypeSafeClient, '_post', lambda *a: pytest.fail('Unexpected network'))
    clock = runner.sim.simulation_time
    runner.command('typesafe-key', {'typesafe_api_key': '  ' + KEY + '  '})
    runner.publish(render=False)
    assert runner.typesafe_key == KEY
    assert runner.state['typesafe_key_source'] == 'browser'
    assert runner.state['typesafe_browser_key_configured']
    assert KEY not in json.dumps(runner.state)
    assert runner.manual_key == 'synthetic-openai-only-key'
    assert runner.api_calls == 0 and runner.sim.simulation_time == clock
    runner.command('typesafe-key', {'clear': True})
    runner.publish(render=False)
    assert not runner.state['typesafe_key_configured']
    assert runner.manual_key == 'synthetic-openai-only-key'
    assert not runner.typesafe_key and runner.policy is None


@pytest.mark.parametrize('value', [None, False, 123, [], {}, '', '  ', 'x\ny', 'x y', '密钥', 'x'*1001])
def test_invalid_key_keeps_previous_override(runner, value):
    runner.command('typesafe-key', {'typesafe_api_key': KEY})
    with pytest.raises((ValueError, PolicyError)) as error:
        runner.command('typesafe-key', {'typesafe_api_key': value})
    assert runner.typesafe_key == KEY
    assert KEY not in str(error.value)


@pytest.mark.parametrize('payload', [{'api_key': KEY}, {'clear': False},
    {'clear': True, 'typesafe_api_key': KEY}, {'typesafe_api_key': KEY, 'endpoint': 'https://wrong.example'}])
def test_key_endpoint_accepts_only_explicit_typesafe_settings(runner, payload):
    with pytest.raises(ValueError): runner.command('typesafe-key', payload)
    assert not runner.typesafe_key


@pytest.mark.parametrize('state', ['running', 'pending'])
def test_key_changes_blocked_during_requests(runner, state):
    if state == 'running': runner.running = True
    else: runner.future = Future()
    with pytest.raises(ValueError, match='等待'):
        runner.command('typesafe-key', {'typesafe_api_key': KEY})
    assert not runner.typesafe_key


def test_clear_override_restores_environment_and_does_not_edit_it(runner, monkeypatch):
    monkeypatch.setenv('TYPESAFE_API_KEY', 'synthetic-environment-key')
    runner.command('typesafe-key', {'typesafe_api_key': KEY})
    runner.command('typesafe-key', {'clear': True})
    runner.publish(render=False)
    assert runner.state['typesafe_key_source'] == 'environment'
    assert runner.state['typesafe_key_configured']
    assert not runner.state['typesafe_browser_key_configured']
    import os
    assert os.environ['TYPESAFE_API_KEY'] == 'synthetic-environment-key'


def test_typed_key_diagnosis_reuses_memory_and_never_leaks(runner, monkeypatch):
    used = []
    def post(client, payload):
        used.append(client._key)
        request = json.loads(payload)
        assert KEY not in payload.decode()
        return answer(request['questions']['action']['criteria'], 'hold')
    monkeypatch.setattr(TypeSafeClient, '_post', post)
    clock = runner.sim.simulation_time
    for fields in ({'typesafe_api_key': '  '+KEY+'  '}, {}):
        runner.command('diagnose', dict(agent='jev', stage='action', **fields))
        for _ in range(100):
            runner.advance(.05)
            if not runner.running: break
            time.sleep(.002)
        assert runner.phase == 'completed' and not runner.error
        assert runner.diagnostic_result['executed'] is False
        assert runner.sim.simulation_time == clock
        runner.publish(render=False)
        assert KEY not in json.dumps(runner.state)
        for file in runner.log_file.parent.iterdir():
            if file.suffix in {'.json', '.jsonl', '.html'}:
                assert KEY not in file.read_text()
    assert used == [KEY, KEY]
    client = runner.policy.client
    runner.command('typesafe-key', {'clear': True})
    assert not client._key and not runner.typesafe_key and not runner.key
    assert runner.manual_key == 'synthetic-openai-only-key'

def test_missing_key_never_falls_back_to_openai(runner, monkeypatch):
    monkeypatch.setattr(TypeSafeClient, '_post', lambda *a: pytest.fail('Unexpected request'))
    with pytest.raises(PolicyError, match='TypeSafe'):
        runner.command('diagnose', dict(agent='jev', stage='action'))
    assert not runner.typesafe_key and runner.api_calls == 0


def test_environment_key_is_not_cached_as_a_browser_override(runner, monkeypatch):
    monkeypatch.setenv('TYPESAFE_API_KEY', 'synthetic-environment-key')
    runner.command('start', dict(agent='jev', task='Open the gripper.', max_steps=1))
    assert runner.policy.client._key == 'synthetic-environment-key'
    assert not runner.typesafe_key
    runner.publish(render=False)
    assert runner.state['typesafe_key_source'] == 'environment'
    runner.stop()


def test_explicit_invalid_override_cannot_use_stored_key(runner):
    runner.command('typesafe-key', {'typesafe_api_key': KEY})
    with pytest.raises(ValueError, match='文本'):
        runner.command('diagnose', dict(agent='jev', stage='action', typesafe_api_key=42))
    assert runner.api_calls == 0 and runner.typesafe_key == KEY
