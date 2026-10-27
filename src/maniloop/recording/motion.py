"""Live episode motion video for the in-process MuJoCo backend.

The runner's physics loop hands immutable MjData snapshots to a worker thread
at a fixed simulation-time cadence. The worker owns its offscreen context and
streams composited dual-camera frames to ffmpeg, so recording never slows
physics or inference. Controlled timing freezes physics during API calls, and
paused/diagnostic periods never reach the physics loop; request latency
therefore never appears in the video.
"""

from __future__ import annotations

import hashlib
import json
import math
import queue
import shutil
import subprocess
import threading
from pathlib import Path

import mujoco
from PIL import Image, ImageDraw

CAMERAS = ("external", "wrist")
_MAX_ERRORS = 5


class MotionRecorder:
    """Dual-camera MP4 of everything physics actually did, nothing it did not."""

    def __init__(
        self,
        sim,
        run_dir,
        *,
        fps: int = 20,
        panel: int = 320,
        ffmpeg: str | None = None,
        max_frames: int = 20 * 7200,
    ):
        if getattr(sim, "backend", None) != "mujoco":
            raise ValueError("MotionRecorder supports only the in-process mujoco backend")
        for name in CAMERAS:
            sim.model.camera(name)  # Raises early when a scene lacks the cameras.
        if type(fps) is not int or not 1 <= fps <= 60:
            raise ValueError("fps must be an integer from 1 to 60")
        binary = ffmpeg or shutil.which("ffmpeg")
        if not binary or not Path(binary).is_file():
            raise ValueError("ffmpeg was not found; motion video requires the ffmpeg executable")
        self._model = sim.model
        self._scene_option = getattr(sim, "scene_option", None)
        self._fps = fps
        self._panel = panel
        self._interval = 1.0 / fps
        self._next_due = None
        self._max_frames = max_frames
        self._queue: queue.Queue = queue.Queue(maxsize=8)
        self._dropped = 0
        self._captured = 0
        self._errors = 0
        self._last_sim_time = -math.inf
        self._disabled = False
        self._finalized = False
        self._thread = threading.Thread(
            target=self._work, name="motion-recorder", daemon=True
        )
        canvas = (2 * panel, panel + 56)
        self._canvas = canvas
        run_dir = Path(run_dir)
        self._partial = run_dir / "motion.partial.mp4"
        self._destination = run_dir / "motion.mp4"
        self._process = subprocess.Popen(
            [
                str(binary), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "rawvideo", "-pixel_format", "rgb24",
                "-video_size", f"{canvas[0]}x{canvas[1]}",
                "-framerate", str(fps), "-i", "pipe:0",
                "-an", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(self._partial),
            ],
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._thread.start()

    def tick(self, sim) -> None:
        """Physics-loop hook: snapshot state at the simulation-time cadence.

        Runs in the physics thread; rendering happens in the worker. A short
        blocking put throttles headless runs to encoder speed instead of
        dropping motion; only sustained overload drops a snapshot.
        """
        if self._disabled or self._finalized or self._captured >= self._max_frames:
            return
        sim_time = float(sim.data.time)
        if self._next_due is None:
            self._next_due = sim_time
        if sim_time + 1e-9 < self._next_due:
            return
        self._next_due += self._interval
        snapshot = mujoco.MjData(self._model)
        mujoco.mj_copyData(snapshot, self._model, sim.data)
        try:
            self._queue.put((snapshot, sim_time), timeout=1.0)
        except queue.Full:
            self._dropped += 1

    def _work(self) -> None:
        renderer = None
        while True:
            item = self._queue.get()
            if item is None:
                return
            data, sim_time = item
            try:
                if renderer is None:
                    # The OSMesa/EGL context is thread-local; create it here.
                    renderer = mujoco.Renderer(
                        self._model, height=self._panel, width=self._panel
                    )
                canvas = Image.new("RGB", self._canvas, "#111b24")
                for offset, camera in enumerate(CAMERAS):
                    renderer.update_scene(
                        data, camera=camera, scene_option=self._scene_option
                    )
                    rgb = renderer.render()
                    canvas.paste(
                        Image.fromarray(rgb).convert("RGB"),
                        (offset * self._panel, 28),
                    )
                draw = ImageDraw.Draw(canvas)
                draw.text((10, 8), "EXTERNAL CAMERA", fill="white")
                draw.text((self._panel + 10, 8), "WRIST CAMERA", fill="white")
                draw.text(
                    (10, self._panel + 36),
                    f"simulation {sim_time:.2f}s | {self._fps} fps | motion only (API latency excluded)",
                    fill="white",
                )
                self._process.stdin.write(canvas.tobytes())
                self._captured += 1
                self._last_sim_time = sim_time
            except (BrokenPipeError, OSError, ValueError):
                self._disabled = True
                return
            except Exception:
                self._errors += 1
                if self._errors >= _MAX_ERRORS:
                    self._disabled = True
                    return

    def finalize(self) -> dict | None:
        """Flush the encoder once; returns stats for the run log, or None."""
        if self._finalized:
            return None
        self._finalized = True
        # Drain any queued snapshot, then stop the worker.
        try:
            self._queue.put(None, timeout=2)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put(None, timeout=2)
            except queue.Full:
                self._disabled = True
        self._thread.join(timeout=30)
        if self._process.stdin and not self._process.stdin.closed:
            try:
                self._process.stdin.close()
            except (BrokenPipeError, OSError):
                pass
        try:
            error = self._process.stderr.read().decode("utf-8", errors="replace")
        except (OSError, ValueError):
            error = ""
        try:
            returncode = self._process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()
            returncode = -1
        stats = {
            "frames": self._captured,
            "dropped": self._dropped,
            "fps": self._fps,
            "panel": self._panel,
            "simulation_span_seconds": (
                round(self._last_sim_time, 3) if self._captured else 0.0
            ),
        }
        ok = (
            returncode == 0
            and self._captured > 0
            and self._partial.is_file()
            and self._partial.stat().st_size > 0
        )
        if ok:
            self._partial.replace(self._destination)
            stats["video"] = self._destination.name
            stats["video_sha256"] = hashlib.sha256(
                self._destination.read_bytes()
            ).hexdigest()
            stats["video_bytes"] = self._destination.stat().st_size
        else:
            self._partial.unlink(missing_ok=True)
            stats["video"] = None
            if error.strip():
                stats["encoder_error"] = error.strip()[:300]
        (self._destination.parent / "motion.json").write_text(
            json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return stats

    def abort(self) -> None:
        """Kill the encoder without producing a video (runner teardown)."""
        if self._finalized:
            return
        self._finalized = True
        self._disabled = True
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        if self._process.poll() is None:
            try:
                self._process.stdin.close()
            except (BrokenPipeError, OSError):
                pass
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        self._partial.unlink(missing_ok=True)
