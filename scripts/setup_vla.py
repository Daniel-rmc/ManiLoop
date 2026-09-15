"""Install isolated LeRobot inference and download reviewed immutable checkpoints."""

import argparse
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CATALOG = runpy.run_path(str(ROOT / "src/maniloop/agents/lerobot/catalog.py"))


def run(*args, **kwargs):
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", default="uv")
    parser.add_argument(
        "--models",
        nargs="+",
        choices=list(CATALOG["MODELS"]),
        default=["smolvla-libero"],
    )
    args = parser.parse_args()
    if not shutil.which(args.uv):
        raise SystemExit("Install uv first: python -m pip install uv")
    env = dict(
        os.environ,
        UV_PYTHON_INSTALL_DIR=str(ROOT / ".runtime/python"),
        HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
    )
    venv = ROOT / ".venv-vla"
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        run(args.uv, "python", "install", "3.12", "--no-bin", "--no-registry", env=env)
        managed = subprocess.check_output(
            [
                args.uv,
                "python",
                "find",
                "3.12",
                "--managed-python",
                "--no-project",
                "--resolve-links",
            ],
            text=True,
            env=env,
        ).strip()
        if not Path(managed).is_relative_to(ROOT / ".runtime/python"):
            raise SystemExit("Expected project-managed Python")
        run(args.uv, "venv", "--no-project", "--python", managed, venv, env=env)
    run(
        args.uv,
        "pip",
        "install",
        "--python",
        python,
        "-r",
        ROOT / "requirements/vla.txt",
    )
    hf = venv / ("Scripts/hf.exe" if os.name == "nt" else "bin/hf")
    models_root = ROOT / ".runtime/models"
    for name in args.models:
        item = CATALOG["MODELS"][name]
        destination = models_root / name
        run(
            hf,
            "download",
            item["repo"],
            "--revision",
            item["revision"],
            "--local-dir",
            destination,
            env=env,
        )
        (destination / "maniloop_source.json").write_text(
            json.dumps(item, indent=2) + "\n"
        )
    if "smolvla-libero" in args.models:
        item = CATALOG["TOKENIZER"]
        run(
            hf,
            "download",
            item["repo"],
            "--revision",
            item["revision"],
            "--include",
            "*.json",
            "*.txt",
            "--local-dir",
            models_root / "smolvlm-tokenizer",
            env=env,
        )
    print("Local models ready. See docs/VLA.md for LIBERO inference commands.")


if __name__ == "__main__":
    main()
