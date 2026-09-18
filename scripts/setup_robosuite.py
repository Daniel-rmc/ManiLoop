"""Install the optional robosuite worker without modifying existing environments."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", default="uv", help="Path to uv executable")
    args = parser.parse_args()
    if not shutil.which(args.uv):
        raise SystemExit("Install uv first: python -m pip install uv")
    env = dict(os.environ, UV_PYTHON_INSTALL_DIR=str(ROOT / ".runtime/python"))
    venv = ROOT / ".venv-robosuite"
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        run(args.uv, "python", "install", "3.11", "--no-bin", "--no-registry", env=env)
        managed = subprocess.check_output(
            [args.uv, "python", "find", "3.11", "--managed-python", "--no-project", "--resolve-links"],
            text=True, env=env,
        ).strip()
        if not Path(managed).is_relative_to(ROOT / ".runtime/python"):
            raise SystemExit("Expected the project-managed Python; existing files preserved.")
        run(args.uv, "venv", "--no-project", "--python", managed, venv, env=env)
    version = subprocess.check_output(
        [str(python), "-c", "import sys; print('%s.%s' % sys.version_info[:2])"], text=True,
    ).strip()
    if version != "3.11":
        raise SystemExit(".venv-robosuite must use Python 3.11; existing environment unchanged.")
    run(args.uv, "pip", "install", "--python", python, "-r", ROOT / "requirements/robosuite.txt")
    run(args.uv, "pip", "check", "--python", python)
    snapshot = ROOT / ".runtime/robosuite-packages.txt"
    snapshot.parent.mkdir(exist_ok=True)
    snapshot.write_text(subprocess.check_output(
        [args.uv, "pip", "freeze", "--python", str(python)], text=True,
    ), encoding="utf-8")
    print(f"Worker: {python}\nInstalled versions: {snapshot}")
    print("Next: python -m maniloop smoke --backend robosuite --task Lift")


if __name__ == "__main__":
    main()
