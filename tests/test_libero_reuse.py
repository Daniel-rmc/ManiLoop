"""Explicit worktree runtime reuse: no downloads, credentials, or dependency writes."""
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import pytest


@pytest.fixture
def installer(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location('libero_setup_test',
        Path(__file__).resolve().parents[1] / 'scripts/setup_libero.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    current, other = tmp_path / 'dev', tmp_path / 'main'
    current.mkdir(); other.mkdir()
    venv = other / '.venv-libero'; venv.mkdir()
    python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    python.parent.mkdir(); python.write_text('fixture: never executed')
    source = other / '.external/LIBERO'
    (source / 'libero/libero/assets').mkdir(parents=True)
    monkeypatch.setattr(module, 'ROOT', current)
    return module, current, other, venv, source


def mock_validation(monkeypatch, module, *, revision=None, dirty=0, versions='3.10\n2.3.7\n1.4.0\n'):
    def output(command, **kwargs):
        return (module.REVISION if revision is None else revision) if command[0] == 'git' else versions
    monkeypatch.setattr(module.subprocess, 'check_output', output)
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=dirty))


def test_explicit_reuse_is_idempotent_and_never_installs(installer, monkeypatch, links_supported):
    m, current, other, venv, source = installer
    mock_validation(monkeypatch, m)
    m.reuse_runtime(other)
    m.reuse_runtime(other)
    for link, target in [(current / '.venv-libero', venv), (current / '.external/LIBERO', source)]:
        assert link.is_symlink() and link.resolve() == target
        assert not os.path.isabs(os.readlink(link))
    assert (venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')).read_text() == 'fixture: never executed'


@pytest.mark.parametrize('kind', ['directory', 'file', 'broken_link'])
def test_conflicting_second_path_preserves_everything(installer, monkeypatch, kind, request):
    if kind == 'broken_link': request.getfixturevalue('links_supported')
    m, current, other, _, _ = installer
    mock_validation(monkeypatch, m)
    conflict = current / '.external/LIBERO'; conflict.parent.mkdir()
    if kind == 'directory': conflict.mkdir()
    elif kind == 'file': conflict.write_text('keep')
    else: conflict.symlink_to(current / 'missing', target_is_directory=True)
    with pytest.raises(SystemExit, match='Preserving existing path'):
        m.reuse_runtime(other)
    assert os.path.lexists(conflict)
    assert not os.path.lexists(current / '.venv-libero')


def test_same_checkout_is_rejected(installer):
    m, current, *_ = installer
    with pytest.raises(SystemExit, match='another checkout'): m.reuse_runtime(current)


@pytest.mark.parametrize('changes', [dict(revision='wrong'), dict(dirty=1),
    dict(versions='3.12\n2.3.7\n1.4.0\n'), dict(versions='3.10\n3.3.7\n1.5.2\n')])
def test_invalid_installation_never_creates_links(installer, monkeypatch, changes):
    m, current, other, _, _ = installer
    mock_validation(monkeypatch, m, **changes)
    with pytest.raises(SystemExit): m.reuse_runtime(other)
    assert not os.path.lexists(current / '.venv-libero')
    assert not os.path.lexists(current / '.external/LIBERO')


def test_missing_installation_never_downloads(installer):
    m, current, other, _, _ = installer
    with pytest.raises(SystemExit, match='no complete LIBERO'):
        m.reuse_runtime(other / 'absent')
    assert list(current.iterdir()) == []


def test_ordinary_install_refuses_to_modify_shared_runtime(installer, monkeypatch, links_supported):
    m, current, _, venv, _ = installer
    (current / '.venv-libero').symlink_to(venv, target_is_directory=True)
    monkeypatch.setattr(m.sys, 'argv', ['setup_libero.py'])
    with pytest.raises(SystemExit, match='refusing to modify'):
        m.main()


def test_partial_link_failure_rolls_back_only_new_links(installer, monkeypatch, links_supported):
    m, current, other, _, _ = installer
    mock_validation(monkeypatch, m)
    real_symlink = Path.symlink_to
    def symlink(path, target, **kwargs):
        if path.name == 'LIBERO': raise OSError('fixture failure')
        return real_symlink(path, target, **kwargs)
    monkeypatch.setattr(Path, 'symlink_to', symlink)
    with pytest.raises(SystemExit, match='Directory links unavailable'):
        m.reuse_runtime(other)
    assert not os.path.lexists(current / '.venv-libero')
    assert not os.path.lexists(current / '.external/LIBERO')


def test_reuse_does_not_require_uv_or_invoke_pip(installer, monkeypatch, links_supported):
    m, _, other, _, _ = installer
    mock_validation(monkeypatch, m)
    monkeypatch.setattr(m.sys, 'argv', ['setup_libero.py', '--reuse-from', str(other)])
    monkeypatch.setattr(m.shutil, 'which', lambda *a: None)
    monkeypatch.setattr(m, 'run', lambda *a, **kw: pytest.fail('Unexpected install'))
    m.main()


@pytest.fixture
def links_supported(tmp_path):
    target = tmp_path / 'link-probe-target'; target.mkdir()
    link = tmp_path / 'link-probe'
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip('OS does not permit directory symlinks for this test account')
    else:
        link.unlink()
