"""Install optional, pinned LIBERO runtime without changing ManiLoop dependencies."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
# Keep installation independent of the main package's optional runtime imports.
import runpy

REVISION = runpy.run_path(str(ROOT / "src/maniloop/backends/libero/transport.py"))[
    "REVISION"
]


def run(*args, **kwargs):
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def validate_reusable_runtime(directory):
    """Check an explicitly selected installation without importing the simulator."""
    directory = Path(directory).expanduser().resolve()
    venv = directory / ".venv-libero"
    source = directory / ".external" / "LIBERO"
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file() or not (source / "libero/libero/assets").is_dir():
        raise SystemExit("Selected directory has no complete LIBERO runtime; see docs/LIBERO.md")
    try:
        revision = subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"], text=True, timeout=10).strip()
        dirty = subprocess.run(["git", "-C", str(source), "diff", "--quiet", "HEAD", "--", "libero"],
                               check=False, timeout=10).returncode
        versions = subprocess.check_output([str(python), "-c",
            "import sys; from importlib.metadata import version; "
            "print('%s.%s' % sys.version_info[:2]); "
            "print(version('mujoco')); print(version('robosuite'))"],
            text=True, timeout=15).splitlines()
    except (OSError, subprocess.SubprocessError) as exc:
        raise SystemExit("Unable to validate the existing LIBERO installation; nothing changed") from exc
    if revision != REVISION or dirty:
        raise SystemExit("Selected LIBERO source differs from the pinned revision; nothing changed")
    if versions != ["3.10", "2.3.7", "1.4.0"]:
        raise SystemExit("Reuse requires Python 3.10 / MuJoCo 2.3.7 / robosuite 1.4.0; nothing changed")
    return venv.resolve(), source.resolve()

def reuse_runtime(directory):
    """Create local directory links only; never install into the shared environment."""
    directory = Path(directory).expanduser().resolve()
    if directory == ROOT.resolve():
        raise SystemExit("--reuse-from must name another checkout")
    venv, source = validate_reusable_runtime(directory)
    pairs = [(ROOT / ".venv-libero", venv), (ROOT / ".external/LIBERO", source)]
    pending = []
    # Check BOTH destinations before creating either link. Preserve broken links too.
    for destination, target in pairs:
        if os.path.lexists(destination):
            if not destination.is_symlink() or destination.resolve() != target:
                raise SystemExit(f"Preserving existing path: {destination}; no links created")
        else:
            pending.append((destination, target))
    created = []
    try:
        for destination, target in pending:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.symlink_to(os.path.relpath(target, destination.parent), target_is_directory=True)
            created.append(destination)
    except OSError as exc:
        for destination in reversed(created):
            destination.unlink()  # Only links created by this invocation.
        raise SystemExit("Directory links unavailable; use MANILOOP_LIBERO_PYTHON and MANILOOP_LIBERO_ROOT (docs/LIBERO.md)") from exc
    print("LIBERO runtime linked and validated. No downloads or dependency changes.")
    print("Source checkout must remain available. Next: python -m maniloop list --backend libero")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", default="uv", help="Path to uv executable")
    parser.add_argument("--reuse-from", type=Path,
                        help="Reuse a verified installation in another checkout without downloading")
    args = parser.parse_args()
    if args.reuse_from is not None:
        reuse_runtime(args.reuse_from)
        return
    if (ROOT / ".venv-libero").is_symlink() or (ROOT / ".external/LIBERO").is_symlink():
        raise SystemExit("Shared LIBERO paths detected: revalidate with --reuse-from; refusing to modify another checkout's dependencies")
    if not shutil.which(args.uv) or not shutil.which("git"):
        raise SystemExit("Install Git and uv first: python -m pip install uv")
    source = ROOT / ".external" / "LIBERO"
    source.parent.mkdir(exist_ok=True)
    if not source.exists():
        run(
            "git",
            "clone",
            "https://github.com/Lifelong-Robot-Learning/LIBERO.git",
            source,
        )
        run("git", "-C", source, "checkout", "--detach", REVISION)
    else:
        revision = subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
        ).strip()
        dirty = subprocess.check_output(
            ["git", "-C", str(source), "status", "--porcelain", "--untracked-files=no"],
            text=True,
        ).strip()
        if revision != REVISION or dirty:
            raise SystemExit(
                "Existing .external/LIBERO differs; preserve your work and use a clean pinned checkout before retrying."
            )
    env = dict(os.environ, UV_PYTHON_INSTALL_DIR=str(ROOT / ".runtime" / "python"))
    venv = ROOT / ".venv-libero"
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        run(args.uv, "python", "install", "3.10", "--no-bin", "--no-registry", env=env)
        managed = subprocess.check_output(
            [args.uv, "python", "find", "3.10", "--managed-python", "--no-project", "--resolve-links"],
            text=True, env=env,
        ).strip()
        if not Path(managed).is_relative_to(ROOT / ".runtime" / "python"):
            raise SystemExit("Expected the project-managed Python; check uv Python selection settings.")
        run(args.uv, "venv", "--no-project", "--python", managed, venv, env=env)
    version = subprocess.check_output(
        [str(python), "-c", "import sys; print('%s.%s' % sys.version_info[:2])"],
        text=True,
    ).strip()
    if version != "3.10":
        raise SystemExit(
            ".venv-libero must use Python 3.10; existing environment was left unchanged."
        )
    run(
        args.uv,
        "pip",
        "install",
        "--python",
        python,
        "-r",
        ROOT / "requirements/libero.txt",
        "-e",
        source,
    )
    print("LIBERO installed. Next: python -m maniloop smoke --backend libero")


if __name__ == "__main__":
    main()
