"""Fixed-policy batch evaluation with per-episode records and explicit comparison groups."""

from dataclasses import dataclass, asdict
import hashlib
import itertools
import json
import math
from pathlib import Path
import platform
import time
import tomllib
import mujoco
from maniloop import __version__
from maniloop.backends.factory import create_environment
from maniloop.runtime.runner import EpisodeRunner


@dataclass(frozen=True)
class Experiment:
    backend: str = "mujoco"
    libero_suite: str = "libero_spatial"
    libero_task_id: int = 0
    init_state_id: int = 0
    robot: str | None = None
    scene: str = "tabletop_a"
    task: str = "pick_place"
    agent: str = "mock_vla"
    local_model: str = "smolvla-libero"
    device: str = "auto"
    timing: str = "controlled"
    seed: int = 0
    max_calls: int = 30
    max_sim_seconds: float = 120.0
    max_wall_seconds: float = 600.0

    def validate(self):
        if self.backend not in ("mujoco", "libero"):
            raise ValueError("Unknown backend")
        if self.backend == "mujoco":
            if self.robot not in (None, "arx5", "panda") or self.scene not in (
                "tabletop_a",
                "tabletop_b",
            ):
                raise ValueError("Unknown robot or scene")
            if self.task not in ("pick_place", "push"):
                raise ValueError("Unknown task")
        else:
            from maniloop.backends.libero.transport import SUITES

            if self.robot not in (None, "panda") or self.libero_suite not in SUITES:
                raise ValueError("LIBERO requires Panda and an official suite")
            if any(
                type(v) is not int or v < 0
                for v in (self.libero_task_id, self.init_state_id)
            ):
                raise ValueError("LIBERO IDs must be nonnegative integers")
            if self.scene != "tabletop_a" or self.task != "pick_place":
                raise ValueError(
                    "Use libero_suite/libero_task_id for LIBERO, not native scene/task fields"
                )
        if self.agent not in ("llm_cloud", "mock_vla", "lerobot"):
            raise ValueError("Unknown agent")
        if self.agent == "lerobot":
            from maniloop.agents.lerobot.catalog import MODELS

            if (
                self.backend != "libero"
                or self.local_model not in MODELS
                or self.device not in ("auto", "cpu", "mps", "cuda")
            ):
                raise ValueError(
                    "Local checkpoints require LIBERO and a supported model/device"
                )
        if self.timing not in ("controlled", "realtime"):
            raise ValueError("Unknown timing mode")
        if (
            type(self.seed) is not int
            or self.seed < 0
            or type(self.max_calls) is not int
            or not 1 <= self.max_calls <= (1000 if self.agent == "lerobot" else 100)
        ):
            raise ValueError(
                "Seed must be nonnegative; max_calls must be 1–100 (local policy: 1–1000)"
            )
        if any(
            type(x) not in (int, float) or not math.isfinite(x) or x <= 0
            for x in (self.max_sim_seconds, self.max_wall_seconds)
        ):
            raise ValueError("Time budgets must be positive and finite")


def load_suite(path: Path) -> list[Experiment]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if set(data) - {"experiment", "matrix"}:
        raise ValueError("Suite accepts only [experiment] and [matrix]")
    common = data.get("experiment", {})
    matrix = data.get("matrix", {})
    if not matrix or set(matrix) - {
        "backend",
        "libero_suite",
        "libero_task_id",
        "init_state_id",
        "robot",
        "scene",
        "task",
        "seed",
        "agent",
        "local_model",
        "device",
        "timing",
    }:
        raise ValueError(
            "Matrix needs supported robot/scene/task/seed/agent/timing axes"
        )
    if set(common) & set(matrix):
        raise ValueError("A field cannot be both fixed and a matrix axis")
    if any(not isinstance(v, list) or not v for v in matrix.values()):
        raise ValueError("Matrix axes must be nonempty arrays")
    count = math.prod(len(v) for v in matrix.values())
    if count > 1000:
        raise ValueError("Limit a single suite to 1000 episodes")
    cases = [
        Experiment(**common, **dict(zip(matrix, values)))
        for values in itertools.product(*matrix.values())
    ]
    for case in cases:
        case.validate()
    return cases


def run_episode(
    case: Experiment, output: Path, connection: dict | None = None, render=True
):
    case.validate()
    if case.agent in ("llm_cloud", "lerobot") and not render:
        raise ValueError(
            "LLM evaluation requires camera rendering; use OSMesa/EGL on headless Linux"
        )
    sim = create_environment(
        render=render,
        backend=case.backend,
        robot=case.robot,
        scene=case.scene,
        task=case.task,
        libero_suite=case.libero_suite,
        libero_task_id=case.libero_task_id,
        init_state_id=case.init_state_id,
        observation_profile="lerobot_rgb256"
        if case.agent == "lerobot"
        else "debug_rgb128",
    )
    runner = None
    try:
        sim.reset(case.seed)
        runner = EpisodeRunner(sim, timing=case.timing, output=output, benchmark=True)
        runner.seed = case.seed
        runner.sim_budget = case.max_sim_seconds
        runner.wall_budget = case.max_wall_seconds
        runner.command(
            "start",
            {
                **(connection or {}),
                "agent": case.agent,
                "local_model": case.local_model,
                "device": case.device,
                "task": sim.instruction,
                "max_steps": case.max_calls,
            },
        )
        directory = runner.log_file.parent
        manifest = runner.manifest
        group = manifest["comparison_group"]
        manifest["experiment"] = asdict(case)
        (directory / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        while runner.running:
            runner.advance()
            if case.timing == "realtime" or runner.future is not None:
                time.sleep(0.002)
        # A fixed settling window after voluntary done allows the stability criterion to finish.
        # Never extend an exhausted simulation budget.
        if runner.phase == "completed" and sim.backend == "mujoco":
            remaining = max(
                0.0,
                min(
                    1.2,
                    case.max_sim_seconds - (sim.simulation_time - runner.started_sim),
                ),
            )
            sim.step(int(remaining / sim.timestep))
        usage = {}
        for line in runner.log_file.read_text(encoding="utf-8").splitlines():
            for key, value in json.loads(line).get("usage", {}).items():
                if isinstance(value, (int, float)):
                    usage[key] = usage.get(key, 0) + value
        result = {
            "schema_version": 1,
            "comparison_group": group,
            "experiment": asdict(case),
            "phase": runner.phase,
            "error": runner.error,
            "termination_reason": runner.termination_reason,
            "evaluation": sim.evaluation(),
            "environment": sim.describe(),
            "decisions": runner.api_calls,
            "actions": runner.step_count,
            "usage": usage,
            "simulation_seconds": float(sim.simulation_time - runner.started_sim),
            "wall_seconds": time.monotonic() - runner.started_wall,
            "run_directory": str(directory),
            "is_mock": case.agent == "mock_vla",
        }
        if case.agent == "lerobot":
            final_images, _ = sim.render_images()
            for camera, data in final_images.items():
                (directory / f"final-{camera}.png").write_bytes(data)
        (directory / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result
    finally:
        if runner is not None:
            runner.close()
        else:
            sim.close()
