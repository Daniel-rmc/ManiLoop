"""Install pinned RoboCasa simulation sources and an isolated Python 3.11 runtime."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ('robocasa', 'robocasa/robocasa', '4f8a2980def75a55dff96b990745b83540425f09', 'tar.gz'),
    ('robocasa-robosuite', 'ARISE-Initiative/robosuite', '5ce6643f3092639d08f7b0f90ed1c6a84f50552c', 'zip'),
)


def run(*args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def source_install(name, repo, revision, suffix):
    target = ROOT / '.external' / name
    marker = target / '.maniloop-source.json'
    if target.exists():
        if not marker.is_file() or json.loads(marker.read_text()).get('revision') != revision:
            raise RuntimeError(f'Existing {target.name} has no matching source marker; preserve it before reinstalling')
        return target
    target.parent.mkdir(exist_ok=True)
    cache = ROOT / '.runtime/robocasa-sources'
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / f'{name}-{revision}.{suffix}'
    kind = 'tar.gz' if suffix == 'tar.gz' else 'zip'
    url = f'https://codeload.github.com/{repo}/{kind}/{revision}'
    print(f'Downloading pinned source: {repo}@{revision}', flush=True)
    partial = archive.with_name(archive.name + '.part')
    with urllib.request.urlopen(url, timeout=90) as response, partial.open('wb') as output:
        while chunk := response.read(1024*1024):
            output.write(chunk)
    partial.replace(archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(dir=target.parent) as temporary:
        temp = Path(temporary)
        if suffix == 'tar.gz':
            with tarfile.open(archive) as data:
                data.extractall(temp, filter='data')
        else:
            with zipfile.ZipFile(archive) as data:
                for member in data.infolist():
                    if not (temp / member.filename).resolve().is_relative_to(temp.resolve()):
                        raise ValueError('Unsafe archive path')
                    if (member.external_attr >> 16) & 0o170000 == 0o120000:
                        raise ValueError('Source archive symlinks are not supported')
                data.extractall(temp)
        candidates = [p for p in temp.iterdir() if p.is_dir() and (p / 'setup.py').is_file()]
        if len(candidates) != 1:
            raise RuntimeError('Unexpected source archive layout')
        candidates[0].rename(target)
    marker.write_text(json.dumps({'repository': repo, 'revision': revision,
                                  'archive_sha256': digest}, indent=2))
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uv', default='uv', help='Path to the uv executable')
    parser.add_argument('--download-assets', action='store_true',
                        help='Download the official asset groups required by the default scenes')
    args = parser.parse_args()
    if not shutil.which(args.uv):
        raise SystemExit('Install uv or supply --uv /path/to/uv')
    sources = [source_install(*spec) for spec in SOURCES]
    env = dict(os.environ, UV_PYTHON_INSTALL_DIR=str(ROOT / '.runtime/python'))
    venv = ROOT / '.venv-robocasa'
    python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        run(args.uv, 'python', 'install', '3.11', '--no-bin', '--no-registry', env=env)
        managed = subprocess.check_output([args.uv, 'python', 'find', '3.11', '--managed-python',
            '--no-project', '--resolve-links'], env=env, text=True).strip()
        if not Path(managed).is_relative_to(ROOT / '.runtime/python'):
            raise RuntimeError('Expected project-managed Python; other environments preserved')
        run(args.uv, 'venv', '--no-project', '--python', managed, venv, env=env)
    version = subprocess.check_output([str(python), '-c',
        "import sys;print('%s.%s'%sys.version_info[:2])"], text=True).strip()
    if version != '3.11':
        raise RuntimeError('Existing .venv-robocasa must be Python 3.11; not replacing it')
    run(args.uv, 'pip', 'install', '--python', python, '-r', ROOT / 'requirements/robocasa.txt')
    # Upstream setup includes training frameworks; this worker needs simulation only.
    run(args.uv, 'pip', 'install', '--python', python, '--no-deps', '-e', sources[1], '-e', sources[0])
    run(python, '-c', "import robocasa,robosuite,mujoco,inspect;"
        "from robosuite.environments.manipulation.manipulation_env import ManipulationEnv;"
        "assert 'load_model_on_init' in inspect.signature(ManipulationEnv.__init__).parameters;"
        "print('Simulation imports OK:',robocasa.__version__,robosuite.__version__,mujoco.__version__)")
    snapshot = ROOT / '.runtime/robocasa-packages.txt'
    snapshot.write_text(subprocess.check_output(
        [args.uv, 'pip', 'freeze', '--python', str(python)], text=True), encoding='utf-8')
    print('Simulation-only profile: upstream training extras (lerobot/tianshou) are not installed.')
    if args.download_assets:
        print('Official textures (including style-referenced generative textures) and default object assets will be downloaded/extracted under .external/robocasa; no demonstrations or weights.')
        run(sys.executable, ROOT / 'scripts/download_robocasa_assets.py')
    print('Next: python -m maniloop smoke --backend robocasa --task OpenDrawer')


if __name__ == '__main__':
    main()
