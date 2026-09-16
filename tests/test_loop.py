"""Exercise the actual runtime with a fake policy; never makes a paid API request."""
from concurrent.futures import Future
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import numpy as np
import pytest
import arx5_demo.app as app
from arx5_demo.local_config import ConfigError
from arx5_demo.sim import RobotSim
from arx5_demo.app import Demo

class ImmediatePool:
    def submit(self,fn,*args):
        f=Future()
        try:f.set_result(fn(*args))
        except Exception as exc:f.set_exception(exc)
        return f

class FakePolicy:
    last_usage={};last_latency=.1
    def __init__(self):self.count=0
    def decide(self,task,observation,images,history,geometry):
        self.count+=1
        return {'observation_id':observation['observation_id'],
                'kind':'move' if self.count==1 else 'done',
                'delta_position':[0,0,-.01] if self.count==1 else [0,0,0],
                'delta_rotation':[0,0,0],'gripper_opening':0,'camera':'','pixel':[0,0],
                'explanation':'离线测试动作'}


def test_runtime_observes_moves_reobserves_and_finishes():
    sim=RobotSim(render=False)
    demo=Demo(sim)
    demo.pool.shutdown();demo.pool=ImmediatePool()
    demo.policy=FakePolicy();demo.running=True;demo.task='离线测试';demo.next_request=0
    before=sim.tcp_position
    demo.tick()
    old_id=demo.pending_observation['observation_id']
    assert demo.future is not None
    sim.step(20)  # physical time progresses during an outstanding API call
    demo.tick()
    assert sim.busy and demo.step_count==1
    sim.step(1000);demo.next_request=0
    demo.tick()
    assert demo.pending_observation['observation_id']!=old_id
    demo.tick()
    assert demo.phase=='completed' and not demo.running
    np.testing.assert_allclose(sim.tcp_position,before+[0,0,-.01],atol=.002)
    sim.close()


def test_stop_discards_inflight_response_even_when_it_fails():
    sim=RobotSim(render=False);demo=Demo(sim)
    demo.pool.shutdown()
    demo.running=True;demo.future=Future();demo.future_token=demo.token
    demo.stop()
    held=sim.data.ctrl.copy()
    demo.future.set_exception(RuntimeError('stale API error'))
    demo.tick()
    assert demo.phase=='stopped' and not demo.running
    np.testing.assert_array_equal(sim.data.ctrl,held)
    sim.close()


def test_missing_key_and_out_of_range_calls_fail_before_network():
    with patch.dict('os.environ',{},clear=True):
        sim=RobotSim(render=False);demo=Demo(sim)
        try:
            demo.command('start',{'task':'test'})
        except ValueError as e:
            assert 'OPENAI_API_KEY' in str(e)
        else:raise AssertionError('Should reject without key')
        assert demo.future is None
        demo.pool.shutdown();sim.close()


def test_file_switch_discards_old_reply_and_reloads_key_endpoint_model(tmp_path,monkeypatch):
    import json
    from unittest.mock import MagicMock
    import arx5_demo.app as app
    path=tmp_path/'profile.json'
    def config(key,url,model):
        path.write_text(json.dumps({'api_key':key,'base_url':url,'model':model}))
    config('offline-key-A','https://a.example/v1','gpt-a')
    clients=[]
    def factory(**kwargs):
        p=MagicMock();p.last_latency=.1;p.last_usage={};p.options=kwargs
        clients.append(p);return p
    monkeypatch.setattr(app,'GPTPolicy',factory)
    monkeypatch.setattr(app,'ROOT',tmp_path)
    sim=RobotSim(render=False);demo=Demo(sim)
    demo.pool.shutdown();demo.pool=ImmediatePool()
    demo.command('start',{'credential_source':'file','config_path':str(path),'model':'','task':'test','max_steps':2})
    demo.future=Future();demo.future_token=demo.token
    demo.future.set_exception(RuntimeError('old provider failed'))
    config('offline-key-B','https://b.example/v1','gpt-b')
    demo.tick()
    assert demo.running and demo.phase=='observing' and demo.last_action is None
    assert clients[-1].options=={'model':'gpt-b','api_key':'offline-key-B','base_url':'https://b.example/v1'}
    demo.publish(render=False)
    serialized=json.dumps(demo.state)
    assert 'offline-key-' not in serialized and 'fingerprint' not in serialized
    assert demo.credentials['base_url']=='https://b.example/v1'
    assert demo.credentials['model']=='gpt-b'
    assert not sim.busy
    sim.close()


def test_model_override_survives_profile_switch_and_invalid_config_stops(tmp_path,monkeypatch):
    import json
    from unittest.mock import MagicMock
    import arx5_demo.app as app
    path=tmp_path/'profile.json'
    path.write_text(json.dumps({'api_key':'offline-A','model':'from-file'}))
    monkeypatch.setattr(app,'GPTPolicy',MagicMock())
    monkeypatch.setattr(app,'ROOT',tmp_path)
    sim=RobotSim(render=False);demo=Demo(sim)
    demo.command('start',{'credential_source':'file','config_path':str(path),'model':'explicit-model','task':'test'})
    path.write_text(json.dumps({'api_key':'offline-B','model':'changed-file'}))
    assert demo.refresh_local_connection()
    assert demo.model=='explicit-model'
    path.write_text('{"api_key":"SECRET", invalid')
    demo.tick()
    assert not demo.running and demo.phase=='error'
    assert 'SECRET' not in demo.error
    demo.pool.shutdown();sim.close()


@pytest.fixture
def configured_demo(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setattr(app, 'ROOT', tmp_path)
    factory = MagicMock()
    monkeypatch.setattr(app, 'GPTPolicy', factory)
    sim = RobotSim(render=False)
    demo = Demo(sim)
    try:
        yield demo, factory
    finally:
        demo.pool.shutdown()
        sim.close()


def uploaded_profile(endpoint='https://selected.example/proxy/v1', token=None):
    config = '\n'.join([
        'model="gpt-upload"',
        'model_provider="selected"',
        '[model_providers.selected]',
        f'base_url="{endpoint}"',
        'wire_api="responses"',
    ])
    if token:
        config += f'\nexperimental_bearer_token="{token}"'
    return config


def test_uploaded_toml_and_separate_key_resolve_and_start(configured_demo, tmp_path, monkeypatch):
    demo, factory = configured_demo
    monkeypatch.setattr(app, 'load_local_config', MagicMock(side_effect=AssertionError('upload must not read files')))
    payload = {
        'credential_source': 'upload', 'config_toml': uploaded_profile(token='offline-embedded'),
        'config_name': 'my-provider.toml', 'api_key': 'offline-separate',
        'model': '', 'task': '下降一厘米', 'max_steps': 2,
    }
    resolved = demo.resolve_connection(payload)
    assert (resolved.api_key, resolved.base_url, resolved.model) == (
        'offline-separate', 'https://selected.example/proxy/v1', 'gpt-upload')
    preview = demo.connection_request('config-preview', payload)
    assert preview['config']['key_configured'] is True
    factory.assert_not_called()
    demo.command('start', payload)
    factory.assert_called_once_with(model='gpt-upload', api_key='offline-separate',
                                    base_url='https://selected.example/proxy/v1')
    assert demo.running and demo.credential_source == 'upload'
    assert demo.config_path is None and demo.config_key_override is None
    assert demo.future is None and demo.api_calls == 0
    demo.publish(render=False)
    exposed = json.dumps({'preview': preview, 'state': demo.state, 'events': demo.events})
    assert 'offline-separate' not in exposed and 'offline-embedded' not in exposed
    assert 'config_toml' not in exposed
    assert not list(tmp_path.rglob('*.toml'))
    assert 'offline-separate' not in demo.log_file.read_text(encoding="utf-8")


@pytest.mark.parametrize('source', ['upload', 'file'])
def test_keyless_config_preview_succeeds_but_start_rejects(configured_demo, tmp_path, source):
    demo, factory = configured_demo
    payload = {'credential_source': source, 'task': '测试', 'api_key': ''}
    if source == 'file':
        path = tmp_path / 'keyless.toml'
        path.write_text(uploaded_profile())
        payload['config_path'] = str(path)
    else:
        payload['config_toml'] = uploaded_profile()
    preview = demo.connection_request('config-preview', payload)
    assert preview['ok'] is True
    assert preview['config']['base_url'] == 'https://selected.example/proxy/v1'
    assert preview['config']['model'] == 'gpt-upload'
    assert preview['config']['key_configured'] is False
    with pytest.raises(ConfigError, match='API'):
        demo.command('start', payload)
    factory.assert_not_called()
    assert not demo.running and demo.future is None and demo.log_file is None


@pytest.mark.parametrize('response_pending', [False, True])
def test_file_override_endpoint_switch_stops_before_creating_client(configured_demo, tmp_path, response_pending):
    demo, factory = configured_demo
    path = tmp_path / 'bound.toml'
    path.write_text(uploaded_profile())
    demo.command('start', {
        'credential_source': 'file', 'config_path': str(path), 'api_key': 'offline-bound-key',
        'task': '测试地址切换', 'max_steps': 2,
    })
    old_policy = demo.policy
    old_controls = demo.sim.data.ctrl.copy()
    if response_pending:
        demo.future = Future()
        demo.future_token = demo.token
        demo.future.set_exception(RuntimeError('discard old response'))
    path.write_text(uploaded_profile(endpoint='https://changed.example/v1', token='offline-other-key'))
    demo.tick()
    assert factory.call_count == 1
    assert demo.policy is old_policy
    assert not demo.running and demo.phase == 'error'
    assert 'API 地址' in demo.error
    assert demo.api_calls == 0 and demo.step_count == 0
    # hold() deliberately waits 150 ms for settling; busy is true during that
    # interval even though no trajectory or new command has been scheduled.
    assert demo.sim.trajectory is None and demo.sim._pending_target is None
    np.testing.assert_array_equal(demo.sim.data.ctrl[demo.sim.arm_act],
                                  demo.sim.data.qpos[demo.sim.qidx])
    np.testing.assert_array_equal(demo.sim.data.ctrl[demo.sim.gripper_act],
                                  old_controls[demo.sim.gripper_act])
    demo.publish(render=False)
    exposed = json.dumps(demo.state) + demo.log_file.read_text(encoding="utf-8")
    assert 'offline-bound-key' not in exposed and 'offline-other-key' not in exposed


def test_uploaded_key_is_redacted_from_runtime_failure_state_and_events(configured_demo):
    demo, factory = configured_demo
    demo.command('start', {
        'credential_source': 'upload', 'config_toml': uploaded_profile(),
        'api_key': 'offline-sensitive-upload', 'task': '测试失败反馈',
    })
    demo.future = Future()
    demo.future_token = demo.token
    demo.future.set_exception(RuntimeError('rejected credential offline-sensitive-upload'))
    demo.tick()
    assert not demo.running and demo.phase == 'error'
    assert '[REDACTED]' in demo.error
    assert factory.call_count == 1
    demo.publish(render=False)
    exposed = json.dumps(demo.state) + json.dumps(demo.events) + demo.log_file.read_text(encoding="utf-8")
    assert 'offline-sensitive-upload' not in exposed


def test_timeout_latency_and_category_are_recorded(configured_demo):
    from maniloop.providers.responses import PolicyError
    demo, _ = configured_demo
    demo.command('start', {'credential_source':'upload', 'config_toml':uploaded_profile(),
                          'api_key':'offline-key', 'task':'test'})
    demo.policy.last_latency = 47.25
    demo.policy.last_usage = {}
    demo.future = Future()
    demo.future_token = demo.token
    demo.future.set_exception(PolicyError('request timed out', category='timeout'))
    demo.tick()
    demo.publish(render=False)
    assert demo.state['api_latency'] == 47.25
    event = json.loads(demo.log_file.read_text(encoding='utf-8').splitlines()[-1])
    assert event['category'] == 'timeout' and event['latency_seconds'] == 47.25
    assert event['usage'] is None and demo.step_count == 0
