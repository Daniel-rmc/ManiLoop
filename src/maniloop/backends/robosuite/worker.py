"""Isolated robosuite process: sensor-only observations and separate evaluator RPC."""
import base64
import contextlib
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import sys

if __package__:
    from .catalog import CAMERAS, PROFILES, ROBOSUITE_VERSION, MUJOCO_VERSION, validate_task
else:
    from catalog import CAMERAS, PROFILES, ROBOSUITE_VERSION, MUJOCO_VERSION, validate_task


class Runtime:
    def __init__(self, options):
        import numpy as np
        import robosuite
        from robosuite.controllers import load_composite_controller_config
        self.np, self.robosuite, self.env = np, robosuite, None
        self.task = options.get("task", "Lift")
        _, self.instruction = validate_task(self.task)
        self.render = bool(options.get("render", True))
        self.profile = options.get("observation_profile", "debug_rgb128")
        if self.profile not in PROFILES:
            raise ValueError("Unknown robosuite observation profile")
        self.size, self.image_format = PROFILES[self.profile], "JPEG"
        dependencies = {name: importlib.metadata.version(name)
                        for name in ("robosuite", "mujoco", "numpy", "Pillow", "numba", "scipy")}
        if dependencies["robosuite"] != ROBOSUITE_VERSION or dependencies["mujoco"] != MUJOCO_VERSION:
            raise RuntimeError("Use the pinned robosuite runtime installed by scripts/setup_robosuite.py")
        if robosuite.__version__ != ROBOSUITE_VERSION:
            raise RuntimeError("Imported robosuite source differs from the pinned release")
        self.config = load_composite_controller_config(robot="Panda")
        # Explicit integration protocol, not an upstream-default claim.
        self.config["body_parts"]["right"]["input_ref_frame"] = "world"
        # In robosuite 1.5.2 only renderer="mujoco" frees the existing MjSim
        # before a hard reset replaces it. The mjviewer default can leave an
        # old offscreen context for GC to destroy while the NEW context is
        # current, deleting that new context's GL resources. No viewer is used.
        self.kwargs = dict(env_name=self.task, robots="Panda", controller_configs=self.config,
                           renderer="mujoco",
                           has_renderer=False, has_offscreen_renderer=self.render,
                           use_camera_obs=self.render, use_object_obs=False,
                           camera_names=list(CAMERAS.values()), camera_heights=self.size,
                           camera_widths=self.size, control_freq=20, horizon=1000,
                           ignore_done=False, reward_shaping=False)
        digest = hashlib.sha256()
        source = Path(robosuite.__file__).parent
        for path in sorted(source.rglob("*.py")):
            digest.update(str(path.relative_to(source)).encode())
            digest.update(path.read_bytes())
        self.description = {
            "backend": "robosuite", "robot": "panda", "scene": "robosuite_tabletop",
            "task": self.task, "instruction": self.instruction,
            "controller": "robosuite_1_5_Panda_OSC_POSE_world",
            "controller_config": self.config, "controller_overrides": {"input_ref_frame": "world"},
            "protocol": f"maniloop_robosuite_{self.profile}_v1",
            "observation_profile": self.profile, "evaluator": "robosuite_check_success",
            "renderer": "mujoco", "render_lifecycle": "destroy_before_hard_reset_v1",
            "upstream_revision": f"pypi:{ROBOSUITE_VERSION}",
            "upstream_source_sha256": digest.hexdigest(), "runtime_dependencies": dependencies,
            "camera_preprocessing": f"{self.size}x{self.size}; snapshot render; vertical flip; JPEG quality 90; RGB",
            "camera_mapping": dict(CAMERAS), "tcp_orientation_source": "robot0_eef_quat_site",
            "native_action": "7 normalized OSC_POSE values; world frame; -1 open / +1 close",
            "llm_action_adapter": "one OSC step per move; 10 steps per gripper; fixed target mode optional",
            "control_timestep": 0.05, "horizon": 1000, "warmup_steps": 0,
            "max_episode_control_steps": 1000, "stop_on_first_success": True,
            "paper_comparable": False,
        }
        try:
            self.reset(options.get("seed", 0))
        except Exception:
            self.close()
            raise

    def reset(self, seed):
        if type(seed) is not int or seed < 0:
            raise ValueError("Seed must be a nonnegative integer")
        self.close()
        self.seed = seed
        self.env = self.robosuite.make(**self.kwargs, seed=seed)
        self.obs = self.env.reset()
        robot = self.env.robots[0]
        splits = robot.composite_controller._action_split_indexes
        if dict(splits) != {"right": (0, 6), "right_gripper": (6, 7)}:
            raise RuntimeError("Unexpected Panda composite action layout")
        low, high = self.env.action_spec
        if self.env.action_dim != 7 or not self.np.all(low == -1) or not self.np.all(high == 1):
            raise RuntimeError("Unexpected Panda action bounds")
        self.description["action_parts"] = {key: list(value) for key, value in splits.items()}
        self.description["physics_timestep"] = float(self.env.sim.model.opt.timestep)
        self.steps, self.done = 0, False
        self.success = bool(self.env._check_success())
        return self.sensors()

    def step(self, action):
        action = self.np.asarray(action, dtype=float)
        if action.shape != (7,) or not self.np.isfinite(action).all() or (self.np.abs(action) > 1).any():
            raise ValueError("Expected seven finite normalized OSC values in [-1, 1]")
        if not self.done:
            native = self.env.robots[0].create_action_vector(
                {"right": action[:6], "right_gripper": action[6:]})
            self.obs, _, done, _ = self.env.step(native)
            self.steps += 1
            self.success |= bool(self.env._check_success())
            self.done = bool(done) or self.success or self.steps >= 1000
        return {"sensors": self.sensors(), "steps": self.steps, "terminated": self.done}

    def evaluation(self):
        return {"success": self.success, "current_success": bool(self.env._check_success()),
                "evaluator": "robosuite_check_success", "control_steps": self.steps,
                "terminated": self.done, "seed": self.seed,
                "stop_reason": "success" if self.success else "horizon" if self.done else None}

    def close(self):
        if self.env is not None:
            self.env.close()
            self.env = None

    def sensors(self):
        from robosuite.utils.transform_utils import quat2mat

        obs = self.obs
        return {
            "joint_names": list(self.env.robots[0].robot_model.joints),
            "joint_positions": obs["robot0_joint_pos"].tolist(),
            "joint_velocities": obs["robot0_joint_vel"].tolist(),
            "tcp_position": obs["robot0_eef_pos"].tolist(),
            "tcp_quaternion_xyzw": obs["robot0_eef_quat_site"].tolist(),
            "gripper_joint_positions": obs["robot0_gripper_qpos"].tolist(),
            "tcp_rotation_matrix": quat2mat(obs["robot0_eef_quat_site"]).tolist(),
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
                # Snapshot rendering must not depend on cached observable image buffers.
                # Rendering reads the current state but does not advance physics.
                rgb = self.env.sim.render(height=self.size, width=self.size, camera_name=native)
                Image.fromarray(rgb[::-1].copy()).save(
                    stream,
                    self.image_format,
                    **({"quality": 90} if self.image_format == "JPEG" else {}),
                )
                images[label] = base64.b64encode(stream.getvalue()).decode("ascii")
        return {"sensors": self.sensors(), "cameras": cameras, "images": images}



def main():
    wire, runtime = sys.stdout, None
    for line in sys.stdin:
        request = {}
        try:
            request = json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                op, args = request["op"], request.get("args", {})
                if op == "init":
                    if runtime is not None:
                        raise ValueError("Worker already initialized")
                    runtime = Runtime(args)
                    result = runtime.description
                elif op == "close":
                    if runtime is not None:
                        runtime.close()
                    result = None
                elif runtime is None:
                    raise ValueError("Initialize the runtime first")
                elif op == "reset":
                    result = runtime.reset(args["seed"])
                elif op == "observe":
                    result = runtime.observe()
                elif op == "step":
                    result = runtime.step(args["action"])
                elif op == "evaluate":
                    result = runtime.evaluation()
                else:
                    raise ValueError("Unknown worker operation")
            response = {"id": request["id"], "ok": True, "result": result}
        except Exception as exc:
            import traceback
            traceback.print_exc(file=sys.stderr)
            response = {"id": request.get("id"), "ok": False,
                        "error": f"{type(exc).__name__}: {exc}"}
        wire.write(json.dumps(response, allow_nan=False) + "\n")
        wire.flush()
        if request.get("op") == "close":
            break
    if runtime is not None:
        with contextlib.redirect_stdout(sys.stderr):
            runtime.close()


if __name__ == "__main__":
    main()
