"""Reuse inference dependencies AND reviewed checkpoints; never install in shared paths."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import pytest


@pytest.fixture
def installation(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location('vla_setup_test',
        Path(__file__).resolve().parents[1] / 'scripts/setup_vla.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    dev, other = tmp_path / 'dev', tmp_path / 'original'
    dev.mkdir(); other.mkdir()
    venv, store = other / '.venv-vla', other / '.runtime/models'
    python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    python.parent.mkdir(parents=True); python.write_text('fixture, never executed')
    versions = {'python': [3, 12], 'dependencies': {'lerobot':'0.4.4', 'torch':'2.10.0',
        'torchvision':'0.25.0', 'transformers':'4.57.6', 'numpy':'2.2.6', 'huggingface-hub':'0.35.3'}}
    monkeypatch.setattr(module, 'ROOT', dev)
    monkeypatch.setattr(module.subprocess, 'check_output', lambda *a, **kw: json.dumps(versions))
    for name, entry in module.CATALOG['MODELS'].items():
        folder = store / name; folder.mkdir(parents=True)
        (folder / 'maniloop_source.json').write_text(json.dumps(entry))
        (folder / 'config.json').write_text(json.dumps({'type':entry['family']}))
        for f in ('model.safetensors','normalizer.safetensors'):
            (folder / f).write_bytes(b'fixture, never loaded')
        for f in ('policy_preprocessor.json','policy_postprocessor.json'):
            (folder / f).write_text(json.dumps({'steps':[{'state_file':'normalizer.safetensors'}]}))
    tokenizer = store / 'smolvlm-tokenizer'; tokenizer.mkdir()
    for f in ('config.json','tokenizer.json','tokenizer_config.json'):
        (tokenizer / f).write_text('{}')
    return module, dev, other, venv, store, versions


@pytest.fixture
def links_supported(tmp_path):
    target = tmp_path / 'target'; target.mkdir()
    link = tmp_path / 'link'
    try: link.symlink_to(target, target_is_directory=True)
    except OSError: pytest.skip('This OS account cannot create directory links')
    else: link.unlink()


def test_reuse_links_runtime_and_models_without_uv_or_install(installation, monkeypatch, links_supported):
    m, dev, other, venv, store, _ = installation
    monkeypatch.setattr(sys, 'argv', ['setup_vla.py', '--reuse-from', str(other),
        '--models', 'smolvla-libero','act-libero','diffusion-libero'])
    monkeypatch.setattr(m.shutil, 'which', lambda *a: None)
    monkeypatch.setattr(m, 'run', lambda *a, **kw: pytest.fail('Unexpected installation'))
    m.main(); m.main()
    for path, target in ((dev/'.venv-vla', venv), (dev/'.runtime/models',store)):
        assert path.is_symlink() and path.resolve() == target
        assert not os.path.isabs(os.readlink(path))
    assert (store/'smolvla-libero/model.safetensors').read_bytes() == b'fixture, never loaded'

@pytest.mark.parametrize('filename', ['smolvla-libero/model.safetensors',
    'smolvla-libero/config.json', 'smolvla-libero/normalizer.safetensors',
    'smolvla-libero/policy_preprocessor.json', 'smolvlm-tokenizer/tokenizer.json'])
def test_missing_component_preserves_both_destinations(installation, filename):
    m, dev, other, _, store, _ = installation
    (store / filename).unlink()
    with pytest.raises(SystemExit): m.reuse_runtime(other, ['smolvla-libero'])
    assert not os.path.lexists(dev/'.venv-vla') and not os.path.lexists(dev/'.runtime/models')


@pytest.mark.parametrize('component', ['version','python','provenance','family','state_path'])
def test_incompatible_installation_is_rejected(installation, component):
    m, dev, other, _, store, versions = installation
    p = store / 'smolvla-libero'
    if component == 'version': versions['dependencies']['torch'] = '9.0'
    elif component == 'python': versions['python'] = [3, 10]
    elif component == 'provenance': (p/'maniloop_source.json').write_text('{}')
    elif component == 'family': (p/'config.json').write_text('{"type":"act"}')
    else: (p/'policy_preprocessor.json').write_text('{"steps":[{"state_file":"../escape"}]}')
    with pytest.raises(SystemExit): m.reuse_runtime(other, ['smolvla-libero'])
    assert not os.path.lexists(dev/'.venv-vla')


def test_reuse_act_does_not_require_smol_tokenizer(installation, links_supported):
    m, _, other, _, store, _ = installation
    (store/'smolvlm-tokenizer/tokenizer.json').unlink()
    m.reuse_runtime(other, ['act-libero'])

@pytest.mark.parametrize('kind', ['directory','broken_link'])
def test_conflicting_model_store_never_creates_runtime_link(installation, links_supported, kind):
    m, dev, other, _, _, _ = installation
    conflict=dev/'.runtime/models'; conflict.parent.mkdir()
    if kind=='directory': conflict.mkdir()
    else: conflict.symlink_to(dev/'missing', target_is_directory=True)
    with pytest.raises(SystemExit, match='Preserving existing path'):
        m.reuse_runtime(other, ['smolvla-libero'])
    assert os.path.lexists(conflict) and not os.path.lexists(dev/'.venv-vla')


@pytest.mark.parametrize('path', ['.venv-vla','.runtime/models','.runtime/models/smolvla-libero'])
def test_ordinary_install_never_writes_to_shared_targets(installation, monkeypatch, links_supported, path):
    m, dev, _, venv, _, _ = installation
    destination=dev/path; destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(venv, target_is_directory=True)
    monkeypatch.setattr(sys, 'argv', ['setup_vla.py'])
    with pytest.raises(SystemExit, match='refusing to modify'): m.main()


def test_partial_creation_failure_removes_only_new_links(installation, monkeypatch, links_supported):
    m, dev, other, _, _, _ = installation
    real=Path.symlink_to
    def fail(path, target, **kw):
        if path.name=='models': raise OSError('fixture failure')
        return real(path,target,**kw)
    monkeypatch.setattr(Path,'symlink_to',fail)
    with pytest.raises(SystemExit, match='Directory links unavailable'): m.reuse_runtime(other,['smolvla-libero'])
    assert not os.path.lexists(dev/'.venv-vla')
