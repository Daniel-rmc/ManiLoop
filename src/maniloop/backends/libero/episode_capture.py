"""Human-only, bounded episode capture using already rendered control-step RGB.

This module also runs in the isolated LIBERO interpreter. It does not import
ManiLoop, call the simulator, inspect authentication, or create policy inputs.
"""

import hashlib
import json
from pathlib import Path


class EpisodeCapture:
    def __init__(self, directory, *, description, seed, initial_evaluation):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=False)
        self.index = self.directory / "frames.jsonl"
        self.index.touch()
        self.count = 0
        self.finished = False
        self.metadata = {
            "format": "maniloop_control_step_recording_v1",
            "description": description,
            "seed": seed,
            "initial_evaluation": initial_evaluation,
            "control_timestep": 0.05,
            "capture": "initial observation after official warmup, then every actual native control step",
            "playback": "simulation time; model inference and human pause wall time omitted",
            "interpolated": False,
            "policy_input": False,
        }

    def append(self, *, step, images, action, sensors):
        from PIL import Image

        if self.finished or step != self.count or not 0 <= step <= 990:
            raise ValueError("Recording requires consecutive control steps 0..990")
        if set(images) != {"external", "wrist"}:
            raise ValueError("Recording requires both real RGB cameras")
        files = {}
        for camera, pixels in images.items():
            name = f"{step:06d}-{camera}.jpg"
            path = self.directory / name
            Image.fromarray(pixels).save(path, "JPEG", quality=90)
            files[camera] = {"file": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        entry = {"control_step": step, "simulation_time": step * 0.05,
                 "action": action, "sensors": sensors, "images": files}
        with self.index.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, allow_nan=False, separators=(",", ":")) + "\n")
        self.count += 1

    def finish(self, *, evaluation, reason):
        if not self.finished:
            if not self.count or evaluation["control_steps"] != self.count - 1:
                raise ValueError("Recording and evaluator control-step counts differ")
            self.metadata.update(
                frame_count=self.count, evaluation=evaluation, termination_reason=reason,
                frames_sha256=hashlib.sha256(self.index.read_bytes()).hexdigest(),
            )
            (self.directory / "episode.json").write_text(
                json.dumps(self.metadata, indent=2, allow_nan=False), encoding="utf-8"
            )
            self.finished = True
        return dict(self.metadata)
