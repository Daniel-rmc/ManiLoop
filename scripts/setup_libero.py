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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", default="uv", help="Path to uv executable")
    args = parser.parse_args()
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
