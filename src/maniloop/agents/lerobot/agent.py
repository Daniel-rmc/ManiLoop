"""Sensor-only local policy adapter. No simulator handles or scoring data cross IPC."""

import base64
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
from maniloop.core.actions import Action, ActionChunk
from .catalog import MODELS


class LeRobotAgent:
    def __init__(
        self,
        model="smolvla-libero",
        device="auto",
        python=None,
        models_root=None,
        timeout=300,
    ):
        if model not in MODELS or device not in ("auto", "cpu", "mps", "cuda"):
            raise ValueError("Unknown local model or device")
        base = Path.cwd()
        python = (
            python
            or os.environ.get("MANILOOP_VLA_PYTHON")
            or base
            / ".venv-vla"
            / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        )
        root = Path(
            models_root
            or os.environ.get("MANILOOP_MODELS_ROOT")
            or base / ".runtime/models"
        ).resolve()
        if (
            not Path(python).is_file()
            or not (root / model / "model.safetensors").is_file()
        ):
            raise RuntimeError(
                "Local model runtime is missing. Run scripts/setup_vla.py; see docs/VLA.md"
            )
        self.log = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
        allowed = {
            "PATH",
            "HOME",
            "USERPROFILE",
            "SYSTEMROOT",
            "WINDIR",
            "TEMP",
            "TMP",
            "TMPDIR",
            "CUDA_VISIBLE_DEVICES",
        }
        env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
        env.update(
            HF_HUB_OFFLINE="1",
            TRANSFORMERS_OFFLINE="1",
            HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
            TOKENIZERS_PARALLELISM="false",
            PYTHONUNBUFFERED="1",
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
        self.lock = threading.Lock()
        self.timeout, self.sequence = timeout, 0
        self.last_usage, self.last_latency = {}, 0.0
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.metadata = self.call(
                "init", model=model, root=str(root), device=device
            )
        except Exception:
            self.close()
            raise

    def _read(self):
        try:
            while line := self.process.stdout.readline(1024 * 1024):
                if not line.endswith("\n"):
                    raise RuntimeError("Policy response exceeds limit")
                self.replies.put(json.loads(line))
        except Exception as exc:
            self.replies.put(exc)
        finally:
            self.replies.put(RuntimeError("Local policy process exited"))

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
                    raise RuntimeError("Policy response ID mismatch")
                if not response.get("ok"):
                    raise RuntimeError(response.get("error", "Local inference failed"))
                return response["result"]
            except (queue.Empty, BrokenPipeError) as exc:
                self.process.kill()
                raise RuntimeError(
                    "Local inference timed out or exited; try CPU or inspect docs/VLA.md"
                ) from exc

    def reset(self, seed=0):
        self.call("reset", seed=seed)
        self.last_usage, self.last_latency = {}, 0.0

    def decide(self, task, observation, images, history, geometry_results):
        if observation["action_limits"].get("native_action") != "osc_pose":
            raise ValueError(
                "These checkpoints require the official LIBERO Panda OSC environment"
            )
        started = time.monotonic()
        # Explicit allowlist: even future public packet additions cannot leak to this worker.
        sensor = {
            key: observation[key]
            for key in (
                "tcp_position",
                "tcp_quaternion_xyzw",
                "gripper_joint_positions",
            )
        }
        result = self.call(
            "act",
            task=task,
            sensors=sensor,
            images={
                key: base64.b64encode(images[key]).decode("ascii")
                for key in ("external", "wrist")
            },
        )
        self.last_latency = time.monotonic() - started
        self.last_usage = result["usage"]
        action = Action("osc_pose", tuple(result["action"]), frame="world")
        # LeRobot owns its chunk queue. A fresh observation arrives on every 20 Hz control step,
        # including cached-action steps, which preserves Diffusion's two-frame observation history.
        return ActionChunk(
            observation["observation_id"], (action,), interval_seconds=0.05
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
