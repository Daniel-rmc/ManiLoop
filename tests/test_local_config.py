"""Credential parsing uses temporary fixtures; no real keys or user files."""
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch
import pytest
from arx5_demo.local_config import ConfigError, MAX_CONFIG_BYTES, discover_configs, load_local_config, load_toml_config, normalize_base_url


def write_json(path, **values):
    path.write_text(json.dumps(values))
    return path


def codex_toml(model='gpt-fixture', token=None):
    return '\n'.join(['model = "'+model+'"','model_provider = "selected"',
                      '[model_providers.selected]','base_url = "https://selected.example/proxy/v1"',
                      'wire_api = "responses"'] + ([f'experimental_bearer_token = "{token}"'] if token else []))


def database(path,key='offline-db-A',model='gpt-fixture'):
    settings={'auth':{'OPENAI_API_KEY':key},'config':codex_toml(model)}
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE providers (name TEXT,app_type TEXT,is_current INTEGER,settings_config TEXT)')
        db.execute('INSERT INTO providers VALUES (?,?,?,?)',('供应商A','codex',1,json.dumps(settings)))
        db.execute('INSERT INTO providers VALUES (?,?,?,?)',('其它应用','claude',1,'not-json'))
    return path


def test_discover_database_then_live_without_loading_credentials(tmp_path,monkeypatch):
    (tmp_path/'.cc-switch').mkdir();(tmp_path/'.cc-switch/cc-switch.db').touch()
    monkeypatch.setenv('HOME',str(tmp_path));monkeypatch.delenv('CODEX_HOME',raising=False);monkeypatch.delenv('ARX_CONFIG_PATH',raising=False)
    with patch.object(Path,'home',return_value=tmp_path):
        items=discover_configs()
    assert items[0]['path']==str(tmp_path/'.cc-switch/cc-switch.db')
    assert any(x['path']==str(tmp_path/'.codex/config.toml') for x in items)


def test_default_environment_path(tmp_path,monkeypatch):
    path=write_json(tmp_path/'api.json',api_key='offline-A',model='gpt-fixture')
    monkeypatch.setenv('ARX_CONFIG_PATH',str(path))
    assert load_local_config().api_key=='offline-A'
    assert discover_configs()[0]['path']==str(path)


def test_codex_pair_and_scoped_token_priority(tmp_path,monkeypatch):
    config=tmp_path/'config.toml';auth=tmp_path/'auth.json'
    config.write_text(codex_toml())
    write_json(auth,OPENAI_API_KEY='offline-auth-key')
    a=load_local_config(str(config))
    assert a.api_key=='offline-auth-key'
    assert a.base_url=='https://selected.example/proxy/v1'
    config.write_text(codex_toml(token='offline-scoped-key'))
    b=load_local_config(str(auth))
    assert b.api_key=='offline-scoped-key' and b.fingerprint!=a.fingerprint
    assert 'offline-scoped-key' not in repr(b)
    assert set(b.public())=={'path','provider','base_url','model','key_configured','models'}
    assert 'offline-scoped-key' not in json.dumps(b.public())
    config.write_text(codex_toml()+'\nenv_key = "FIXTURE_KEY"')
    monkeypatch.setenv('FIXTURE_KEY','offline-env-key')
    assert load_local_config(str(config)).api_key=='offline-env-key'


def test_simple_json_reload_and_custom_endpoint(tmp_path):
    path=write_json(tmp_path/'api.json',api_key='offline-A',base_url='https://a.example/v1',model='gpt-a',models=['gpt-a','gpt-b'])
    a=load_local_config(str(path))
    write_json(path,api_key='offline-B',base_url='https://b.example/custom/v1',model='gpt-b')
    b=load_local_config(str(path))
    assert (b.api_key,b.base_url,b.model)==('offline-B','https://b.example/custom/v1','gpt-b')
    assert a.fingerprint!=b.fingerprint and a.models==('gpt-a','gpt-b')


def test_database_active_row_switch_is_a_single_bundle(tmp_path):
    path=database(tmp_path/'cc-switch.db')
    a=load_local_config(str(path))
    assert a.provider=='供应商A' and a.api_key=='offline-db-A'
    settings={'auth':{'OPENAI_API_KEY':'offline-db-B'},'config':codex_toml('gpt-b').replace('selected.example','second.example')}
    with sqlite3.connect(path) as db:
        db.execute("UPDATE providers SET is_current=0 WHERE app_type='codex'")
        db.execute('INSERT INTO providers VALUES (?,?,?,?)',('供应商B','codex',1,json.dumps(settings)))
    b=load_local_config(str(path))
    assert (b.api_key,b.base_url,b.model,b.provider)==('offline-db-B','https://second.example/proxy/v1','gpt-b','供应商B')
    assert b.fingerprint!=a.fingerprint


def test_database_oauth_or_multiple_current_fails(tmp_path):
    path=database(tmp_path/'cc-switch.db',key=None)
    settings={'auth':{'OPENAI_API_KEY':None,'tokens':{'access_token':'SECRET-OAUTH-TOKEN'}},'config':'model="gpt-fixture"'}
    with sqlite3.connect(path) as db:
        db.execute("UPDATE providers SET settings_config=? WHERE app_type='codex'",(json.dumps(settings),))
    with pytest.raises(ConfigError,match='ChatGPT') as e:load_local_config(str(path))
    assert 'SECRET-OAUTH-TOKEN' not in str(e.value)
    with sqlite3.connect(path) as db:
        db.execute('INSERT INTO providers VALUES (?,?,?,?)',('extra','codex',1,json.dumps(settings)))
    with pytest.raises(ConfigError,match='唯一'):load_local_config(str(path))


@pytest.mark.parametrize('data', ['{"api_key":"SECRET-LEAK", broken}', 'api_key="SECRET-LEAK"\nbroken = ['])
def test_parser_errors_never_contain_input(tmp_path,data):
    path=tmp_path/('config.toml' if data.startswith('api_key=') else 'api.json');path.write_text(data)
    with pytest.raises(ConfigError) as e:load_local_config(str(path))
    assert 'SECRET-LEAK' not in str(e.value)


@pytest.mark.parametrize('url',['https://u:SECRET@a.example/v1','https://a.example/v1?key=SECRET','https://a.example/#SECRET',
                               'http://public.example/v1','file:///tmp/a','https://a.example/v1\\foo','https://a.example:99999/v1'])
def test_bad_endpoints_fail_without_reflecting_secret(url):
    with pytest.raises(ConfigError) as e:normalize_base_url(url)
    assert 'SECRET' not in str(e.value)


def test_local_proxy_and_endpoint_paths():
    assert normalize_base_url(None)=='https://api.openai.com/v1'
    assert normalize_base_url('http://127.0.0.1:15721')=='http://127.0.0.1:15721/v1'
    assert normalize_base_url('https://a.example/router/codex/')=='https://a.example/router/codex'


def test_missing_key_oauth_and_unsupported_wire_api(tmp_path):
    path=write_json(tmp_path/'api.json',tokens={'access_token':'SECRET'},api_key=None)
    with pytest.raises(ConfigError,match='ChatGPT'):load_local_config(str(path))
    write_json(path,api_key='offline',wire_api='chat')
    with pytest.raises(ConfigError,match='Responses'):load_local_config(str(path))
    write_json(path,api_key='')
    with pytest.raises(ConfigError,match='API'):load_local_config(str(path))


def test_toml_separate_key_with_no_auth_and_invalid_sibling_auth(tmp_path):
    path = tmp_path / 'config.toml'
    path.write_text(codex_toml())
    configured = load_local_config(str(path), api_key='  offline-separate  ')
    assert (configured.api_key, configured.base_url, configured.model) == (
        'offline-separate', 'https://selected.example/proxy/v1', 'gpt-fixture')
    (tmp_path / 'auth.json').write_text('invalid irrelevant sibling auth')
    assert load_local_config(str(path), api_key='offline-separate') == configured


@pytest.mark.parametrize('source', ['toml', 'json', 'db', 'env'])
def test_explicit_key_overrides_all_configured_sources(tmp_path, monkeypatch, source):
    if source == 'db':
        path = database(tmp_path / 'cc-switch.db', key='offline-embedded')
    elif source == 'json':
        path = write_json(tmp_path / 'api.json', api_key='offline-embedded',
                          base_url='https://selected.example/proxy/v1')
    else:
        path = tmp_path / 'config.toml'
        if source == 'env':
            monkeypatch.setenv('FIXTURE_KEY', 'offline-embedded')
            path.write_text(codex_toml() + '\nenv_key = "FIXTURE_KEY"')
        else:
            path.write_text(codex_toml(token='offline-embedded'))
    original = load_local_config(str(path), api_key='   ')
    overridden = load_local_config(str(path), api_key='offline-override')
    assert original.api_key == 'offline-embedded'
    assert overridden.api_key == 'offline-override'
    assert overridden.base_url == original.base_url == 'https://selected.example/proxy/v1'
    assert original.fingerprint != overridden.fingerprint
    assert 'offline-override' not in repr(overridden)
    assert 'offline-override' not in json.dumps(overridden.public())


@pytest.mark.parametrize('source', ['toml', 'json', 'db', 'upload'])
def test_preview_without_key_preserves_endpoint(tmp_path, source):
    if source == 'upload':
        preview = load_toml_config(codex_toml(), allow_missing_key=True)
    else:
        if source == 'db':
            path = database(tmp_path / 'cc-switch.db', key=None)
        elif source == 'json':
            path = write_json(tmp_path / 'api.json', base_url='https://selected.example/proxy/v1')
        else:
            path = tmp_path / 'config.toml'
            path.write_text(codex_toml())
        preview = load_local_config(str(path), allow_missing_key=True)
        with pytest.raises(ConfigError, match='API'):
            load_local_config(str(path))
    assert preview.api_key == ''
    assert preview.public()['key_configured'] is False
    assert preview.public()['base_url'] == 'https://selected.example/proxy/v1'
    assert '[已隐藏]' not in json.dumps(preview.public())


def test_uploaded_toml_never_reads_or_writes_local_files(monkeypatch):
    with patch('arx5_demo.local_config._read_stable', side_effect=AssertionError('no disk access')), \
         patch.object(Path, 'open', side_effect=AssertionError('no disk access')):
        config = load_toml_config(codex_toml(token='offline-embedded'),
                                  api_key='offline-upload', name='uploaded.toml')
        assert config.path == 'uploaded.toml'
        assert config.api_key == 'offline-upload'
        assert config.base_url == 'https://selected.example/proxy/v1'
        with pytest.raises(ConfigError, match='API'):
            load_toml_config(codex_toml())
        monkeypatch.setenv('FIXTURE_UPLOAD_KEY', 'offline-env-upload')
        assert load_toml_config(codex_toml() + '\nenv_key = "FIXTURE_UPLOAD_KEY"').api_key == 'offline-env-upload'


@pytest.mark.parametrize('content', [
    'experimental_bearer_token="SECRET-UPLOAD"\nbroken = [',
    '# SECRET-UPLOAD\n' + '字' * (MAX_CONFIG_BYTES // 3 + 1),
    '\ud800 SECRET-UPLOAD',
    b'not-a-text-input SECRET-UPLOAD',
])
def test_uploaded_toml_rejects_invalid_or_oversized_content_without_leak(content):
    with pytest.raises(ConfigError) as exc:
        load_toml_config(content, api_key='SECRET-OVERRIDE')
    assert 'SECRET' not in str(exc.value)


def test_preview_never_accepts_invalid_key_or_endpoint():
    with pytest.raises(ConfigError):
        load_toml_config(codex_toml(), api_key=123, allow_missing_key=True)
    with pytest.raises(ConfigError):
        load_toml_config(codex_toml(token='invalid key'), allow_missing_key=True)
    with pytest.raises(ConfigError) as exc:
        load_toml_config(codex_toml().replace('https://selected.example/proxy/v1',
                                              'https://selected.example/v1?key=SECRET'),
                         api_key='offline-override', allow_missing_key=True)
    assert 'SECRET' not in str(exc.value)
