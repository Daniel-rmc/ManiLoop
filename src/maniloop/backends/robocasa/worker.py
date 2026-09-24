"""RoboCasa physics worker. Only sensors/actions cross RPC; evaluation stays separate."""
import contextlib
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import base64
import io

if __package__:
    from .catalog import (CAMERAS, PROFILES, TASKS, ROBOCASA_REVISION,
                          ROBOCASA_VERSION, MUJOCO_VERSION, validate_task, validate_scene)
else:
    from catalog import (CAMERAS, PROFILES, TASKS, ROBOCASA_REVISION,
                         ROBOCASA_VERSION, MUJOCO_VERSION, validate_task, validate_scene)


def source_digest(root):
    digest = hashlib.sha256()
    for path in sorted(root.rglob('*.py')):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


class Runtime:
    def __init__(self, options):
        import numpy as np
        import robocasa
        import robosuite
        from robosuite.controllers import load_composite_controller_config
        self.np, self.robosuite, self.env = np, robosuite, None
        self.task = options.get('task', 'OpenDrawer')
        _, _, self.horizon = validate_task(self.task)
        self.layout, self.style = validate_scene(options.get('layout', 11), options.get('style', 14))
        self.profile = options.get('observation_profile', 'debug_rgb128')
        if self.profile not in PROFILES:
            raise ValueError('Unknown RoboCasa observation profile')
        self.render = bool(options.get('render', True))
        self.size, self.image_format = PROFILES[self.profile], 'JPEG'
        dependencies = {name: importlib.metadata.version(name) for name in
                        ('robocasa', 'robosuite', 'mujoco', 'numpy', 'Pillow', 'numba', 'scipy')}
        if (dependencies['robocasa'] != ROBOCASA_VERSION or dependencies['mujoco'] != MUJOCO_VERSION
                or dependencies['robosuite'] != '1.5.2' or dependencies['numpy'] != '2.2.5'):
            raise RuntimeError('Use scripts/setup_robocasa.py to install the pinned separate runtime')
        import inspect
        from robosuite.environments.manipulation.manipulation_env import ManipulationEnv
        if 'load_model_on_init' not in inspect.signature(ManipulationEnv.__init__).parameters:
            raise RuntimeError('RoboCasa needs the pinned robosuite source, not the PyPI 1.5.2 wheel')
        for package, expected in ((robocasa, ROBOCASA_REVISION),
                                  (robosuite, '5ce6643f3092639d08f7b0f90ed1c6a84f50552c')):
            marker = Path(package.__file__).resolve().parents[1] / '.maniloop-source.json'
            if not marker.is_file() or json.loads(marker.read_text()).get('revision') != expected:
                raise RuntimeError('Missing pinned source metadata; run scripts/setup_robocasa.py')
        self.config = load_composite_controller_config(robot='PandaOmron')
        # Keep the upstream base-frame controller; transform the command, not its gains.
        self.kwargs = dict(env_name=self.task, robots='PandaOmron', controller_configs=self.config,
            renderer='mujoco', has_renderer=False, has_offscreen_renderer=self.render,
            use_camera_obs=self.render, use_object_obs=False, camera_names=list(CAMERAS.values()),
            camera_heights=self.size, camera_widths=self.size, camera_depths=False,
            control_freq=20, horizon=self.horizon, ignore_done=False,
            layout_ids=[self.layout], style_ids=[self.style], randomize_cameras=False,
            generative_textures=None)
        self.description = dict(
            backend='robocasa', robot='panda_omron', task=self.task,
            scene=f'kitchen_{self.layout}_{self.style}', layout=self.layout, style=self.style,
            controller='robocasa_PandaOmron_HYBRID_MOBILE_BASE', controller_config=self.config,
            controller_overrides={}, protocol=f'maniloop_robocasa_{self.profile}_arm_subset_v1',
            observation_profile=self.profile, evaluator='robocasa_check_success',
            upstream_revision=ROBOCASA_REVISION, runtime_dependencies=dependencies,
            upstream_source_sha256=source_digest(Path(robocasa.__file__).parent),
            robosuite_source='5ce6643f3092639d08f7b0f90ed1c6a84f50552c', robosuite_source_sha256=source_digest(Path(robosuite.__file__).parent),
            renderer='mujoco', render_lifecycle='destroy_before_hard_reset_v1',
            camera_mapping=dict(CAMERAS), tcp_orientation_source='robot0_eef_quat_site',
            camera_preprocessing=f'{self.size}x{self.size}; snapshot render; vertical flip; JPEG quality 90; RGB',
            native_action='Full 12-dimensional PandaOmron composite; base-frame arm, base/torso and mode',
            action_adapter='world_osc_arm_subset_to_pandaomron_12d_v1',
            control_scope='arm_and_gripper; zero base velocity, zero torso delta, arm mode -1',
            control_timestep=0.05, horizon=self.horizon, max_episode_control_steps=self.horizon,
            stop_on_first_success=True, paper_comparable=False,
        )
        try:
            self.reset(options.get('seed', 0))
        except Exception:
            self.close()
            raise

    def reset(self, seed):
        if type(seed) is not int or seed < 0:
            raise ValueError('Seed must be a nonnegative integer')
        self.close()
        self.seed = seed
        self.env = self.robosuite.make(**self.kwargs, seed=seed)
        self.obs = self.env.reset()
        robot = self.env.robots[0]
        parts = robot.composite_controller._action_split_indexes
        expected_dims = {'right': 6, 'right_gripper': 1, 'base': 3, 'torso': 1}
        if (self.env.action_dim != 12 or set(parts) != set(expected_dims)
                or any(b-a != expected_dims[k] for k,(a,b) in parts.items())):
            raise RuntimeError('Unsupported PandaOmron composite action layout')
        arm = robot.part_controllers['right']
        torso = robot.part_controllers['torso']
        if arm.input_ref_frame != 'base' or arm.input_type != 'delta':
            raise RuntimeError('Expected the upstream base-frame delta OSC controller')
        if getattr(torso, 'input_type', None) != 'delta':
            raise RuntimeError('Zero torso hold requires the upstream delta joint-position controller')
        if not self.np.allclose(arm.output_max, [.05]*3+[.5]*3):
            raise RuntimeError('Unexpected upstream arm action scaling')
        meta = self.env.get_ep_meta()
        self.instruction = meta.get('lang')
        if not isinstance(self.instruction, str) or not self.instruction:
            raise RuntimeError('No language instruction in the upstream episode metadata')
        self.description.update(instruction=self.instruction, seed=seed,
            actual_layout=int(self.env.layout_id), actual_style=int(self.env.style_id),
            physics_timestep=float(self.env.sim.model.opt.timestep),
            action_parts={k:list(v) for k,v in parts.items()}, native_action_dimension=12)
        self.steps, self.done, self.success = 0, False, bool(self.env._check_success())
        return {'sensors': self.sensors(), 'description': self.description}

    def full_action(self, action):
        """Expand a world-frame arm command; never truncate an upstream action."""
        a = self.np.asarray(action, dtype=float)
        if a.shape != (7,) or not self.np.isfinite(a).all() or (self.np.abs(a)>1).any():
            raise ValueError('Expected seven normalized world-frame arm/hand values')
        robot = self.env.robots[0]
        arm = robot.part_controllers['right']
        rotation = self.np.asarray(arm.origin_ori, dtype=float)
        if rotation.shape != (3,3) or not self.np.isfinite(rotation).all():
            raise RuntimeError('Upstream controller origin orientation is unavailable')
        parts = {'right': self.np.r_[rotation.T @ a[:3], rotation.T @ a[3:6]],
                 'right_gripper': a[6:], 'base': self.np.zeros(3),
                 'torso': self.np.zeros(1), 'base_mode': -1}
        native = robot.create_action_vector(parts)
        low, high = self.env.action_spec
        if native.shape != (12,) or (native < low-1e-10).any() or (native > high+1e-10).any():
            raise ValueError('Transformed command exceeds upstream composite action bounds')
        return native

    def step(self, action):
        native = self.full_action(action)
        if not self.done:
            self.obs, _, done, _ = self.env.step(native)
            self.steps += 1
            self.success |= bool(self.env._check_success())
            self.done = bool(done) or self.success or self.steps >= self.horizon
        return {'sensors': self.sensors(), 'steps': self.steps, 'terminated': self.done}

    def evaluation(self):
        return {'success': self.success, 'current_success': bool(self.env._check_success()),
                'evaluator': 'robocasa_check_success', 'control_steps': self.steps,
                'terminated': self.done, 'seed': self.seed,
                'stop_reason': 'success' if self.success else 'horizon' if self.done else None}

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
