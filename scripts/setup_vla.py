"""Install isolated LeRobot inference and download reviewed immutable checkpoints."""

import argparse
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements/vla.txt"
CATALOG = runpy.run_path(str(ROOT / "src/maniloop/agents/lerobot/catalog.py"))


def run(*args, **kwargs):
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def _required_file(path):
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"Missing or empty local model file: {path.name}; see docs/VLA.md")


def _model_json(path):
    _required_file(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise SystemExit(f"Invalid local model metadata: {path.name}; nothing changed") from exc


def validate_reusable_runtime(directory, models):
    """Validate one explicitly selected installation; never import or download a model."""
    directory = Path(directory).expanduser().resolve()
    venv, root = directory / ".venv-vla", directory / ".runtime/models"
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file() or not root.is_dir():
        raise SystemExit("Selected checkout has no complete local policy runtime; see docs/VLA.md")
    if not models or any(name not in CATALOG["MODELS"] for name in models):
        raise SystemExit("Choose reviewed local model names with --models")
    import re
    expected = dict(re.findall(r"(?m)^([\w.-]+)(?:\[[^]]+\])?==([^\s#]+)",
                              REQUIREMENTS.read_text(encoding="utf-8")))
    if not expected:
        raise SystemExit("Pinned inference requirements are missing; nothing changed")
    code = ("import sys,json; from importlib.metadata import version; "
            "print(json.dumps({'python':list(sys.version_info[:2]),'dependencies':"
            f"{{name:version(name) for name in {list(expected)!r}}}" + "}))")
    try:
        actual = json.loads(subprocess.check_output([str(python), "-I", "-c", code],
                                                  text=True, timeout=20))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise SystemExit("Cannot validate existing inference dependencies; nothing changed") from exc
    if not isinstance(actual, dict) or actual.get("python") != [3, 12] or actual.get("dependencies") != expected:
        raise SystemExit("Inference Python/dependencies differ from requirements/vla.txt; nothing changed")
    for name in models:
        path = root / name
        if _model_json(path / "maniloop_source.json") != CATALOG["MODELS"][name]:
            raise SystemExit(f"Checkpoint source metadata differs for {name}; nothing changed")
        configuration = _model_json(path / "config.json")
        if not isinstance(configuration, dict) or configuration.get("type") != CATALOG["MODELS"][name]["family"]:
            raise SystemExit(f"Checkpoint family differs for {name}; nothing changed")
        _required_file(path / "model.safetensors")
        for filename in ("policy_preprocessor.json", "policy_postprocessor.json"):
            config = _model_json(path / filename)
            if not isinstance(config, dict) or not isinstance(config.get("steps"), list):
                raise SystemExit(f"Invalid processor configuration for {name}")
            for step in config["steps"]:
                if not isinstance(step, dict):
                    raise SystemExit(f"Invalid processor step for {name}")
                state = step.get("state_file")
                if state is not None:
                    if not isinstance(state, str) or Path(state).name != state or state in ("", ".", ".."):
                        raise SystemExit(f"Invalid processor state filename for {name}")
                    _required_file(path / state)
    if "smolvla-libero" in models:
        for name in ("config.json", "tokenizer.json", "tokenizer_config.json"):
            _model_json(root / "smolvlm-tokenizer" / name)
    return venv.resolve(), root.resolve()


def reuse_runtime(directory, models):
    """Link an existing runtime and model store without writing to either target."""
    directory = Path(directory).expanduser().resolve()
    if directory == ROOT.resolve():
        raise SystemExit("--reuse-from must name another checkout")
    venv, models_root = validate_reusable_runtime(directory, models)
    if (ROOT / ".runtime").is_symlink():
        raise SystemExit("Preserving shared .runtime directory; use explicit environment variables")
    pairs = [(ROOT / ".venv-vla", venv), (ROOT / ".runtime/models", models_root)]
    pending = []
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
        raise SystemExit("Directory links unavailable; use MANILOOP_VLA_PYTHON and MANILOOP_MODELS_ROOT (docs/VLA.md)") from exc
    print("Inference runtime and model files linked. No downloads or dependency changes.")
    print("File/dependency checks passed; run a local inference smoke test to verify model execution.")


def ensure_private_install_paths(models):
    """Never let an ordinary install upgrade shared dependencies or model targets."""
    paths = [ROOT / ".venv-vla", ROOT / ".runtime", ROOT / ".runtime/models"]
    paths.extend(ROOT / ".runtime/models" / name for name in [*models, "smolvlm-tokenizer"])
    if any(path.is_symlink() for path in paths):
        raise SystemExit("Shared VLA paths detected: revalidate with --reuse-from; refusing to modify another checkout's dependencies or models")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", default="uv")
    parser.add_argument(
        "--models",
        nargs="+",
        choices=list(CATALOG["MODELS"]),
        default=["smolvla-libero"],
    )
    parser.add_argument("--reuse-from", type=Path, help="Reuse a verified inference runtime and model store in another checkout")
    args = parser.parse_args()
    if args.reuse_from is not None:
        reuse_runtime(args.reuse_from, args.models)
        return
    ensure_private_install_paths(args.models)
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
