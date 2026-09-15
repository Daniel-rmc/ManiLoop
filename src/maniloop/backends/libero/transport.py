"""A bounded local JSON transport, independent of cloud provider configuration."""

import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading

REVISION = "8f1084e3132a39270c3a13ebe37270a43ece2a01"
SUITES = ("libero_spatial", "libero_object", "libero_goal", "libero_90", "libero_10")


class Worker:
    def __init__(self, python=None, root=None, timeout=180):
        base = Path.cwd()
        python = (
            python
            or os.environ.get("MANILOOP_LIBERO_PYTHON")
            or str(
                base
                / ".venv-libero"
                / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            )
        )
        self.root = Path(
            root or os.environ.get("MANILOOP_LIBERO_ROOT") or base / ".external/LIBERO"
        ).resolve()
        if (
            not Path(python).is_file()
            or not (self.root / "libero/libero/assets").is_dir()
        ):
            raise RuntimeError(
                "LIBERO runtime is missing. Follow docs/LIBERO.md; set MANILOOP_LIBERO_PYTHON and MANILOOP_LIBERO_ROOT if installed elsewhere."
            )
        try:
            revision = subprocess.check_output(
                ["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True
            ).strip()
            dirty = subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.root),
                    "diff",
                    "--quiet",
                    "HEAD",
                    "--",
                    "libero",
                ],
                check=False,
            ).returncode
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(
                "LIBERO source must be the Git checkout installed by scripts/setup_libero.py"
            ) from exc
        if revision != REVISION or dirty:
            raise RuntimeError(
                "LIBERO source revision differs or tracked task code is modified; reinstall the pinned source"
            )
        self.temp = tempfile.TemporaryDirectory(prefix="maniloop-libero-")
        self.log = open(Path(self.temp.name) / "worker.log", "w+", encoding="utf-8")
        # Do not inherit API keys, provider settings or Python paths from the controller process.
        allowed = {
            "PATH",
            "HOME",
            "USERPROFILE",
            "SYSTEMROOT",
            "WINDIR",
            "TEMP",
            "TMP",
            "TMPDIR",
            "DISPLAY",
            "WAYLAND_DISPLAY",
            "MUJOCO_GL",
            "PYOPENGL_PLATFORM",
            "LD_LIBRARY_PATH",
            "DYLD_LIBRARY_PATH",
            "CUDA_VISIBLE_DEVICES",
        }
        env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
        env.update(
            PYTHONPATH=str(self.root),
            PYTHONUNBUFFERED="1",
            NUMBA_CACHE_DIR=str(Path(self.temp.name) / "numba"),
        )
        self.process = subprocess.Popen(
            [str(python), "-u", str(Path(__file__).with_name("worker.py"))],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.log,
            text=True,
            encoding="utf-8",
            env=env,
        )
        self.replies = queue.Queue()
        self.timeout = timeout
        self.sequence = 0
        self.lock = threading.Lock()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            while line := self.process.stdout.readline(4 * 1024 * 1024):
                if not line.endswith("\n"):
                    raise RuntimeError("LIBERO worker response exceeds limit")
                self.replies.put(json.loads(line))
        except Exception as exc:
            self.replies.put(exc)
        finally:
            self.replies.put(RuntimeError("LIBERO worker exited"))

    def call(self, op, **args):
        with self.lock:
            self.sequence += 1
            try:
                self.process.stdin.write(
                    json.dumps(
                        {"id": self.sequence, "op": op, "args": args}, allow_nan=False
                    )
                    + "\n"
                )
                self.process.stdin.flush()
                response = self.replies.get(timeout=self.timeout)
                if isinstance(response, Exception):
                    raise response
                if response.get("id") != self.sequence:
                    raise RuntimeError("LIBERO response ID mismatch")
                if not response.get("ok"):
                    raise RuntimeError(response.get("error", "LIBERO worker error"))
                return response["result"]
            except (queue.Empty, BrokenPipeError) as exc:
                self.process.kill()
                raise RuntimeError(
                    "LIBERO worker failed or timed out; check runtime dependencies and rendering configuration in docs/LIBERO.md"
                ) from exc

    def options(self, suite, **kwargs):
        return dict(
            root=str(self.root),
            config=self.temp.name,
            revision=REVISION,
            suite=suite,
            **kwargs,
        )

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.process.stdin.close()
        self.process.stdout.close()
        self.log.close()
        self.temp.cleanup()


def list_tasks(suite="libero_spatial", python=None, root=None):
    worker = Worker(python, root)
    try:
        return worker.call("list", **worker.options(suite))
    finally:
        worker.close()
