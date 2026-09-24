"""Workspace assets are local, packaged, and allowlisted; no API calls."""
from html.parser import HTMLParser
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
import threading
import tomllib
import pytest
from maniloop.ui.server import handler_for, ROOT, WORKSPACE_ASSETS


@pytest.fixture
def http():
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(SimpleNamespace(), SimpleNamespace()))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
    try:
        yield connection
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize('path', tuple(WORKSPACE_ASSETS))
def test_local_static_asset_has_correct_mime_and_no_cache(http, path):
    http.request('GET', path)
    response = http.getresponse()
    filename, mime = WORKSPACE_ASSETS[path]
    assert response.status == 200
    assert response.getheader('Content-Type') == mime
    assert response.getheader('Cache-Control') == 'no-store'
    assert response.getheader('X-Content-Type-Options') == 'nosniff'
    assert response.read() == (ROOT / 'ui' / filename).read_bytes()


@pytest.mark.parametrize('path', ['/ui/server.py', '/ui/../server.py',
    '/ui/%2e%2e/providers/credentials.py', '/ui/missing.js'])
def test_arbitrary_files_are_not_served(http, path):
    http.request('GET', path)
    response = http.getresponse()
    assert response.status == 404
    response.read()


def test_assets_keep_local_origin_protection(http):
    http.request('GET', '/ui/workspace.js', headers={'Origin': 'https://untrusted.example'})
    response = http.getresponse()
    assert response.status == 403
    response.read()


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
    def handle_starttag(self, tag, attrs):
        self.items.append((tag, dict(attrs)))


def test_workspace_entry_point_and_unique_control_ids(http):
    http.request('GET', '/')
    response = http.getresponse()
    assert response.status == 200
    html = response.read().decode()
    parser = Elements(); parser.feed(html)
    ids = [attrs['id'] for _, attrs in parser.items if 'id' in attrs]
    assert len(ids) == len(set(ids))
    controls = {attrs.get('id'): attrs for _, attrs in parser.items}
    for mode in ('manual', 'model', 'environment'):
        assert controls[f'tab-{mode}']['aria-controls'] == f'workspace-{mode}'
    assert 'hidden' not in controls['workspace-manual']
    assert all('hidden' in controls[f'workspace-{m}'] for m in ('model', 'environment'))
    assert {'workspace-stop', 'manual-zero', 'manual-duration', 'config-toml', 'config-api-key'} <= set(ids)
    scripts = [a for tag, a in parser.items if tag == 'script']
    assert scripts == [{'type': 'module', 'src': '/ui/workspace.js'}]
    assert html.encode() == (ROOT / 'ui/workspace.html').read_bytes()


def test_package_includes_modular_workspace():
    project = Path(__file__).resolve().parents[1]
    config = tomllib.loads((project / 'pyproject.toml').read_text())
    patterns = config['tool']['setuptools']['package-data']['maniloop']
    assert {'ui/*.html', 'ui/*.js', 'ui/*.css'} <= set(patterns)


@pytest.mark.parametrize('extension', ['.js', '.css'])
def test_source_fingerprint_covers_workspace_assets(tmp_path, monkeypatch, extension):
    from maniloop.recording import manifest
    root = tmp_path / 'maniloop'
    (root / 'recording').mkdir(parents=True)
    (root / 'ui').mkdir()
    monkeypatch.setattr(manifest, '__file__', str(root / 'recording/manifest.py'))
    path = root / 'ui' / ('module' + extension)
    path.write_text('first')
    before = manifest.source_digest()
    path.write_text('changed')
    assert manifest.source_digest() != before
