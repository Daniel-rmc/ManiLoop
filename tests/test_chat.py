"""Text workbench tests through the real SDK and local HTTP, without paid calls."""
import json
import threading
from pathlib import Path
from types import SimpleNamespace
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

try:
    import httpx2 as httpx
except ImportError:
    import httpx
import pytest
from openai import OpenAI
from maniloop.providers.chat import ChatService, response_summary
from maniloop.providers.credentials import ConfigError, load_toml_config
from maniloop.providers import credentials
from maniloop.ui.server import handler_for

KEY = "offline-chat-secret"
BASE = {"credential_source": "manual", "api_key": KEY, "base_url": "https://provider.example/v1", "model": "test-model"}
MESSAGES = [{"role": "user", "content": "17 + 25 等于多少？"}]


def response(**changes):
    return {"id": "example-response", "model": "test-model", "status": "completed", "error": None,
            "output": [{"type": "message", "role": "assistant", "status": "completed", "content": [{"type": "output_text", "text": "连接成功，42。"}]}],
            "usage": {"input_tokens": 12, "output_tokens": 6, "total_tokens": 18}, **changes}


@pytest.fixture
def wire(monkeypatch):
    calls=[]
    control={"body": response(), "status": 200}
    def transport(req):
        calls.append(req)
        if "exception" in control: raise control["exception"]
        return httpx.Response(control["status"], json=control["body"])
    def factory(**kwargs):
        assert kwargs['max_retries'] == 0
        assert kwargs['base_url'] == BASE['base_url']
        return OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(transport)))
    monkeypatch.setattr('maniloop.providers.responses.OpenAI',factory)
    monkeypatch.delenv('OPENAI_REASONING_EFFORT',raising=False)
    return calls,control


def send(service=None,**changes):
    return (service or ChatService()).handle('send',{**BASE,"messages":MESSAGES,**changes})


def test_responses_chat_and_multi_turn(wire):
    calls,_=wire
    result=send()
    assert result['complete'] and result['transport_ok']
    assert result['reply']=='连接成功，42。' and result['usage']['total_tokens']==18
    assert calls[0].url.path=='/v1/responses'
    body=json.loads(calls[0].content)
    assert body['input']==MESSAGES and body['store'] is False
    assert 'text' not in body and 'tools' not in body and 'instructions' not in body
    assert 'reasoning' not in body
    history=MESSAGES+[{"role":"assistant","content":result['reply']},{"role":"user","content":"再加一呢？"}]
    send(messages=history,connection_id=result['connection_id'])
    assert json.loads(calls[1].content)['input']==history
    with pytest.raises(ConfigError,match='变化'):
        send(messages=history,connection_id=result['connection_id'],model='another-model')
    assert len(calls)==2


def test_chat_completions_does_not_send_responses_fields(wire):
    calls,control=wire
    control['body']={"id":"chat-test","choices":[{"finish_reason":"stop","message":{"role":"assistant","content":"42"}}],"usage":{"prompt_tokens":3,"completion_tokens":2,"total_tokens":5}}
    result=send(protocol='chat_completions',request_options={"reasoning_effort":"low"})
    assert result['complete'] and result['reply']=='42'
    assert calls[0].url.path=='/v1/chat/completions'
    body=json.loads(calls[0].content)
    assert body['messages']==MESSAGES and body['max_completion_tokens']==4096
    assert body['reasoning_effort']=='low' and 'input' not in body


def test_partial_and_gateway_error_show_evidence_without_success(wire):
    _,control=wire
    control['body']=response(status='incomplete',incomplete_details={'reason':'max_output_tokens'},error={'code':'server_error','message':'failed with '+KEY})
    result=send()
    assert result['reply']=='连接成功，42。' and not result['complete'] and result['transport_ok']
    assert result['status']=='incomplete' and result['incomplete_reason']=='max_output_tokens'
    assert result['error']['code']=='server_error' and KEY not in json.dumps(result)


@pytest.mark.parametrize('status',[400,401,429,500])
def test_http_errors_sanitized_without_retry(wire,status):
    calls,control=wire
    control.update(status=status,body={'error':{'code':'test_error','message':'Bad Bearer '+KEY}})
    result=send()
    assert result['http_status']==status and not result['complete'] and not result['transport_ok']
    assert result['error']['code']=='test_error' and KEY not in json.dumps(result)
    assert len(calls)==1


def test_timeout_unknown_usage_and_no_retry(wire):
    calls,control=wire
    control['exception']=httpx.ReadTimeout('secret '+KEY)
    result=send()
    assert result['category']=='timeout' and result.get('usage') is None
    assert KEY not in json.dumps(result) and len(calls)==1


def test_protocol_mismatch_refusal_and_empty_error_placeholders():
    assert response_summary(response(error={'code':'','message':''},incomplete_details={}), 'responses')['complete']
    r=response_summary({'choices':[]},'responses')
    assert not r['complete'] and 'Chat Completions' in r['protocol_hint']
    r=response_summary(response(output=[{'type':'message','status':'completed','role':'assistant','content':[{'type':'refusal','refusal':'不能回答'}]}]),'responses')
    assert not r['complete'] and r['refusal']=='不能回答'
    assert not response_summary(response(output=[{'type':'reasoning'}]),'responses')['complete']
    assert not response_summary(response(status=None),'responses')['complete']


def test_chat_toml_support_keeps_robot_responses_only(wire):
    toml='model = "test-model"\nmodel_provider = "test"\n[model_providers.test]\nwire_api="chat"\nbase_url="https://provider.example/v1"'
    with pytest.raises(ConfigError,match='Responses'):
        load_toml_config(toml,api_key=KEY)
    result=ChatService().handle('preview',{'credential_source':'upload','config_toml':toml,'api_key':KEY})
    assert result['config']['key_configured'] and KEY not in json.dumps(result)
    assert wire[0]==[]


def test_config_validation_and_busy_do_not_call_provider(wire):
    service=ChatService()
    service.lock.acquire()
    try:
        with pytest.raises(ConfigError,match='正在处理'): send(service)
    finally: service.lock.release()
    for invalid in ([],[{'role':'system','content':'test'}],[{'role':'user','content':''}]):
        with pytest.raises(ConfigError): send(messages=invalid)
    with pytest.raises(ConfigError): send(request_options={'timeout_seconds':0})
    assert wire[0]==[]


def test_chat_routes_without_simulator_and_origin_guard(wire):
    server=ThreadingHTTPServer(('127.0.0.1',0),handler_for())
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    root=f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(root+'/chat') as r: assert 'API 聊天测试' in r.read().decode()
        req=Request(root+'/api/chat/send',data=json.dumps({**BASE,'messages':MESSAGES}).encode(),headers={'Content-Type':'application/json'})
        with urlopen(req) as r: assert json.load(r)['complete']
        req.add_header('Origin','https://untrusted.example')
        with pytest.raises(HTTPError) as error: urlopen(req)
        assert error.value.code==403 and len(wire[0])==1
        with pytest.raises(HTTPError) as error: urlopen(root+'/api/state')
        assert error.value.code==404
    finally:
        server.shutdown();server.server_close();thread.join()


@pytest.mark.parametrize('demo_page', [False, True])
def test_page_options_require_explicit_configuration_discovery(wire, tmp_path, monkeypatch, demo_page):
    """Opening either workbench must not inspect the user's configuration files."""
    config_dir = tmp_path / '.codex'
    config_dir.mkdir()
    config_path = config_dir / 'config.toml'
    auth_path = config_dir / 'auth.json'
    config_path.write_text('model="test-model"\nmodel_provider="test"\n'
                           '[model_providers.test]\nbase_url="https://provider.example/v1"\nwire_api="responses"', encoding='utf-8')
    auth_path.write_text(json.dumps({'OPENAI_API_KEY': KEY}), encoding='utf-8')
    cc_dir = tmp_path / '.cc-switch'
    cc_dir.mkdir()
    settings_path = cc_dir / 'settings.json'
    settings_path.write_text(json.dumps({'codexConfigDir': str(config_dir)}), encoding='utf-8')
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    for name in ('CODEX_HOME', 'ARX_CONFIG_PATH', 'OPENAI_API_KEY', 'OPENAI_BASE_URL'):
        monkeypatch.delenv(name, raising=False)
    reads = []
    read_stable = credentials._read_stable
    def observed_read(paths):
        reads.extend(path for path, _ in paths)
        return read_stable(paths)
    monkeypatch.setattr(credentials, '_read_stable', observed_read)
    demo = SimpleNamespace(manual_base_url=None, default_model='test-model') if demo_page else None
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(demo=demo))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    root = f'http://127.0.0.1:{server.server_port}'
    options_path = '/api/config-options' if demo_page else '/api/chat/options'
    try:
        with urlopen(root + ('/' if demo_page else '/chat')) as r:
            assert r.status == 200
        with urlopen(root + options_path) as r:
            assert json.load(r)['configs'] == []
        assert reads == [] and wire[0] == []
        with urlopen(root + options_path + '?discover=1') as r:
            assert any(item['path'] == str(config_path) for item in json.load(r)['configs'])
        assert reads == [settings_path] and wire[0] == []
        request = Request(root + '/api/chat/preview',
                          data=json.dumps({'credential_source': 'file', 'config_path': str(config_path)}).encode(),
                          headers={'Content-Type': 'application/json'})
        with urlopen(request) as r:
            result = json.load(r)
        assert result['config']['key_configured'] and KEY not in json.dumps(result)
        assert reads == [settings_path, config_path, auth_path] and wire[0] == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
