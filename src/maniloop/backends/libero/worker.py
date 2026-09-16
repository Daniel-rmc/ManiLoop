"""Isolated Python 3.10 LIBERO process. JSON on stdout; upstream diagnostics on stderr.

Run this file directly, never import ManiLoop or its provider credentials here.
Only explicit sensor fields cross the observation boundary. Scoring is a separate RPC.
"""

import base64
import contextlib
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import sys

if __package__:
    from .episode_capture import EpisodeCapture
else:
    from episode_capture import EpisodeCapture

CAMERAS = {"external": "agentview", "wrist": "robot0_eye_in_hand"}
SUITES = ("libero_spatial", "libero_object", "libero_goal", "libero_90", "libero_10")


def prepare(root, config):
    root = Path(root).resolve() / "libero" / "libero"
    config = Path(config)
    config.mkdir(parents=True, exist_ok=True)
    datasets = config / "datasets"
    datasets.mkdir(exist_ok=True)
    (config / "config.yaml").write_text(
        json.dumps(
            {
                "benchmark_root": str(root),
                "bddl_files": str(root / "bddl_files"),
                "init_states": str(root / "init_files"),
                "assets": str(root / "assets"),
                "datasets": str(datasets),
            }
        )
    )
    os.environ["LIBERO_CONFIG_PATH"] = str(config)
    if sys.platform == "darwin":
        # MuJoCo 2.3.7's unused CGL loader has an incorrect macOS framework path.
        # Robosuite owns its GLFW context, so avoid importing MuJoCo's separate context.
        previous = os.environ.get("MUJOCO_GL")
        os.environ["MUJOCO_GL"] = "disable"
        try:
            import mujoco
        finally:
            if previous is None:
                os.environ.pop("MUJOCO_GL", None)
            else:
                os.environ["MUJOCO_GL"] = previous


def suite_for(name):
    if name not in SUITES:
        raise ValueError("Unsupported official LIBERO suite")
    from libero.libero import benchmark

    return benchmark.get_benchmark_dict()[name](task_order_index=0)


class Runtime:
    def __init__(self, options):
        import numpy as np
        import robosuite
        from libero.libero.envs.env_wrapper import OffScreenRenderEnv, ControlEnv

        self.np = np
        self.suite = suite_for(options["suite"])
        self.task_id = options["task_id"]
        self.init_id = options["init_state_id"]
        if not 0 <= self.task_id < self.suite.get_num_tasks():
            raise ValueError("LIBERO task ID out of range")
        self.task = self.suite.get_task(self.task_id)
        self.states = self.suite.get_task_init_states(self.task_id)
        if not 0 <= self.init_id < len(self.states):
            raise ValueError("LIBERO initialization ID out of range")
        self.render = options["render"]
        profile = options.get("observation_profile", "debug_rgb128")
        if profile not in ("debug_rgb128", "lerobot_rgb256", "llm_rgb512"):
            raise ValueError("Unknown observation profile")
        self.size = {"debug_rgb128": 128, "lerobot_rgb256": 256, "llm_rgb512": 512}[profile]
        self.image_format = "PNG" if self.size == 256 else "JPEG"
        bddl = self.suite.get_task_bddl_file_path(self.task_id)
        cls = OffScreenRenderEnv if self.render else ControlEnv
        self.env = cls(
            bddl_file_name=bddl,
            robots=["Panda"],
            controller="OSC_POSE",
            use_camera_obs=self.render,
            has_offscreen_renderer=self.render,
            camera_heights=self.size,
            camera_widths=self.size,
            camera_depths=False,
            control_freq=20,
            horizon=1000,
            ignore_done=False,
        )
        config = robosuite.load_controller_config(default_controller="OSC_POSE")
        root = Path(options["root"]) / "libero" / "libero"
        init_file = (
            root / "init_files" / self.task.problem_folder / self.task.init_states_file
        )
        self.description = {
            "backend": "libero",
            "robot": "panda",
            "scene": options["suite"],
            "task": self.task.name,
            "instruction": self.task.language,
            "suite": options["suite"],
            "task_id": self.task_id,
            "init_state_id": self.init_id,
            "initialization_count": len(self.states),
            "task_order_index": 0,
            "upstream_revision": options["revision"],
            "bddl_sha256": hashlib.sha256(Path(bddl).read_bytes()).hexdigest(),
            "initial_states_sha256": hashlib.sha256(init_file.read_bytes()).hexdigest(),
            "controller": "libero_robosuite_OSC_POSE",
            "controller_config": config,
            "protocol": {"debug_rgb128": "maniloop_libero_rgb_proprio_v1",
                         "lerobot_rgb256": "maniloop_libero_lerobot_v1",
                         "llm_rgb512": "maniloop_libero_llm_rgb512_v2"}[profile],
            "observation_profile": profile,
            "evaluator": "libero_check_success",
            "physics_timestep": float(self.env.sim.model.opt.timestep),
            "control_timestep": 0.05,
            "horizon": 1000,
            "warmup_steps": 10,
            "max_episode_control_steps": 990,
            "runtime_dependencies": {
                name: importlib.metadata.version(name)
                for name in ("robosuite", "mujoco", "numpy", "torch", "bddl")
            },
            "camera_preprocessing": f"{self.size}x{self.size}; vertical flip to top-left origin; {self.image_format}"
            + (" quality 90" if self.image_format == "JPEG" else " lossless"),
            "native_action": "7 normalized OSC_POSE values, world frame; -1 opens gripper, +1 closes",
            "llm_action_adapter": "one OSC step per move; 10 steps per gripper; 1 zero-arm step per wait",
            "paper_comparable": False,
        }
        self.capture = None
        self.reset(options.get("seed", 0))

    def reset(self, seed):
        self.finish_recording("reset")
        self.seed = seed
        self.env.seed(seed)
        self.env.reset()
        self.obs = self.env.set_init_state(self.states[self.init_id])
        # Official README stabilization convention; not counted in episode budget.
        for _ in range(10):
            self.obs, _, _, _ = self.env.step([0.0] * 7)
        self.steps = 0
        self.done = False
        self.success = bool(self.env.check_success())
        return self.sensors()

    def start_recording(self, directory):
        if not self.render or self.steps != 0 or self.done:
            raise ValueError("Recording must begin at the rendered official episode initialization")
        if self.capture is not None:
            raise ValueError("An episode recording is already active")
        # The worker records native OSC samples, not the parent adapter's
        # move/gripper semantics. The run manifest owns that high-level mode.
        recording_description = dict(self.description)
        recording_description.pop("llm_action_adapter", None)
        self.capture = EpisodeCapture(directory, description=recording_description,
                                      seed=self.seed, initial_evaluation=self.evaluation())
        self.capture_frame(None)
        return {"recording": True, "frame_count": self.capture.count}

    def capture_frame(self, action):
        if self.capture is not None:
            images = {label: self.obs[native + "_image"][::-1].copy() for label, native in CAMERAS.items()}
            self.capture.append(step=self.steps, images=images, action=action, sensors=self.sensors())

    def finish_recording(self, reason="episode_end"):
        if self.capture is None:
            return None
        result = self.capture.finish(evaluation=self.evaluation(), reason=reason)
        self.capture = None
        return result

    def sensors(self):
        from robosuite.utils.transform_utils import quat2mat

        obs = self.obs
        return {
            "joint_names": list(self.env.robots[0].robot_model.joints),
            "joint_positions": obs["robot0_joint_pos"].tolist(),
            "joint_velocities": obs["robot0_joint_vel"].tolist(),
            "tcp_position": obs["robot0_eef_pos"].tolist(),
            "tcp_quaternion_xyzw": obs["robot0_eef_quat"].tolist(),
            "gripper_joint_positions": obs["robot0_gripper_qpos"].tolist(),
            "tcp_rotation_matrix": quat2mat(obs["robot0_eef_quat"]).tolist(),
            "gripper_opening": float(
                self.np.clip(self.np.abs(obs["robot0_gripper_qpos"]).sum() / 0.08, 0, 1)
            ),
        }

    def observe(self):
        from PIL import Image
        from robosuite.utils.camera_utils import (
            get_camera_intrinsic_matrix,
            get_camera_extrinsic_matrix,
        )

        cameras, images = {}, {}
        for label, native in CAMERAS.items():
            cameras[label] = {
                "width": self.size,
                "height": self.size,
                "depth_available": False,
                "intrinsics": get_camera_intrinsic_matrix(
                    self.env.sim, native, self.size, self.size
                ).tolist(),
                "camera_to_world": get_camera_extrinsic_matrix(
                    self.env.sim, native
                ).tolist(),
                "frame": "world",
                "pixel_origin": "top_left",
            }
            if self.render:
                stream = io.BytesIO()
                Image.fromarray(self.obs[native + "_image"][::-1].copy()).save(
                    stream,
                    self.image_format,
                    **({"quality": 90} if self.image_format == "JPEG" else {}),
                )
                images[label] = base64.b64encode(stream.getvalue()).decode("ascii")
        return {"sensors": self.sensors(), "cameras": cameras, "images": images}

    def step(self, action):
        action = self.np.asarray(action, dtype=float)
        if (
            action.shape != (7,)
            or not self.np.isfinite(action).all()
            or (self.np.abs(action) > 1).any()
        ):
            raise ValueError(
                "Native OSC action must contain seven finite values in [-1, 1]"
            )
        if not self.done:
            self.obs, _, done, _ = self.env.step(action)
            self.steps += 1
            self.success |= bool(self.env.check_success())
            self.done = bool(done) or self.success or self.steps >= 990
            self.capture_frame(action.tolist())
        return {"sensors": self.sensors(), "steps": self.steps, "terminated": self.done}

    def evaluation(self):
        return {
            "success": self.success,
            "current_success": bool(self.env.check_success()),
            "evaluator": "libero_check_success",
            "control_steps": self.steps,
            "terminated": self.done,
        }


def main():
    wire = sys.stdout
    runtime = None
    for line in sys.stdin:
        request = {}
        try:
            request = json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                op, args = request["op"], request.get("args", {})
                if op in ("init", "list"):
                    prepare(args["root"], args["config"])
                if op == "init":
                    runtime = Runtime(args)
                    result = runtime.description
                elif op == "list":
                    suite = suite_for(args["suite"])
                    result = [
                        {
                            "id": i,
                            "name": suite.get_task(i).name,
                            "instruction": suite.get_task(i).language,
                        }
                        for i in range(suite.get_num_tasks())
                    ]
                elif op == "reset":
                    result = runtime.reset(args["seed"])
                elif op == "observe":
                    result = runtime.observe()
                elif op == "step":
                    result = runtime.step(args["action"])
                elif op == "evaluate":
                    result = runtime.evaluation()
                elif op == "start_recording":
                    result = runtime.start_recording(args["directory"])
                elif op == "finish_recording":
                    result = runtime.finish_recording(args.get("reason", "episode_end"))
                elif op == "close":
                    if runtime:
                        runtime.finish_recording("environment_closed")
                        runtime.env.close()
                    result = None
                else:
                    raise ValueError("Unknown worker operation")
            response = {"id": request["id"], "ok": True, "result": result}
        except Exception as exc:
            import traceback

            traceback.print_exc(file=sys.stderr)
            response = {
                "id": request.get("id"),
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        wire.write(json.dumps(response, allow_nan=False) + "\n")
        wire.flush()
        if request.get("op") == "close":
            break


if __name__ == "__main__":
    main()
