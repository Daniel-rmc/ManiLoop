"""Local JSON RPC for the optional robosuite runtime, without provider credentials."""
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading


class Worker:
    def __init__(self, python=None, root=None, timeout=180):
        base = Path.cwd()
        python = python or os.environ.get("MANILOOP_ROBOSUITE_PYTHON") or str(
            base / ".venv-robosuite" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
        if not Path(python).is_file():
            raise RuntimeError("robosuite runtime missing. Run scripts/setup_robosuite.py; see docs/ROBOSUITE.md")
        root = root or os.environ.get("MANILOOP_ROBOSUITE_ROOT")
        if root and not (Path(root) / "robosuite/__init__.py").is_file():
            raise ValueError("MANILOOP_ROBOSUITE_ROOT must be a robosuite source root")
        self.temp = tempfile.TemporaryDirectory(prefix="maniloop-robosuite-")
        self.log = open(Path(self.temp.name) / "worker.log", "w+", encoding="utf-8")
        allowed = {"PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR",
                   "DISPLAY", "WAYLAND_DISPLAY", "MUJOCO_GL", "PYOPENGL_PLATFORM", "LD_LIBRARY_PATH",
                   "DYLD_LIBRARY_PATH", "CUDA_VISIBLE_DEVICES"}
        env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
        env.update(PYTHONUNBUFFERED="1", NUMBA_CACHE_DIR=str(Path(self.temp.name) / "numba"))
        if root:
            env["PYTHONPATH"] = str(Path(root).resolve())
        try:
            self.process = subprocess.Popen(
                [str(python), "-u", str(Path(__file__).with_name("worker.py"))],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
                text=True, encoding="utf-8", env=env)
        except Exception:
            self.log.close()
            self.temp.cleanup()
            raise
        self.replies = queue.Queue()
        self.timeout, self.sequence, self.closed = timeout, 0, False
        self.lock = threading.Lock()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            while line := self.process.stdout.readline(4 * 1024 * 1024):
                if not line.endswith("\n"):
                    raise RuntimeError("robosuite worker response exceeds limit")
                self.replies.put(json.loads(line))
        except Exception as exc:
            self.replies.put(exc)
        finally:
            self.replies.put(RuntimeError("robosuite worker exited; inspect installation/rendering"))

    def call(self, op, **args):
        if self.closed:
            raise RuntimeError("robosuite worker is closed")
        with self.lock:
            self.sequence += 1
            try:
                self.process.stdin.write(json.dumps(
                    {"id": self.sequence, "op": op, "args": args}, allow_nan=False) + "\n")
                self.process.stdin.flush()
                reply = self.replies.get(timeout=self.timeout)
                if isinstance(reply, Exception):
                    raise reply
                if reply.get("id") != self.sequence:
                    raise RuntimeError("robosuite response ID mismatch")
                if not reply.get("ok"):
                    raise RuntimeError(reply.get("error", "robosuite worker error"))
                return reply["result"]
            except (queue.Empty, BrokenPipeError) as exc:
                self.process.kill()
                self.process.wait()
                raise RuntimeError("robosuite worker failed or timed out; check docs/ROBOSUITE.md") from exc

    def close(self):
        if self.closed:
            return
        try:
            if self.process.poll() is None:
                self.timeout = min(self.timeout, 5)
                try:
                    self.call("close")
                except Exception:
                    pass
        finally:
            self.closed = True
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
