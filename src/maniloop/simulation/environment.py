"""MuJoCo adapter. Only observation() is public to the policy; evaluation is separate."""

from __future__ import annotations
import io
import json
import math
import time
import uuid
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image

from maniloop.robots.specs import robot_spec
from maniloop.tasks.tabletop import LAYOUTS, ManipulationTask
from maniloop.simulation.scenes import scene_xml
from maniloop.controllers.position import PositionController
from maniloop.controllers.geometry import rotation_vector, rotation_matrix

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "robots" / "arx5"


class MuJoCoEnvironment:
    width, height = 640, 480
    translation_limit = 0.04
    rotation_limit = 0.20

    def __init__(
        self, render=True, robot="arx5", scene="tabletop_a", task="pick_place"
    ):
        self.robot = robot_spec(robot)
        self.layout = LAYOUTS[scene]
        self.task = ManipulationTask(task, self.layout)
        self.config = dict(self.robot.config)
        self.config["target_center"] = list(self.layout.target_position)
        self.model = mujoco.MjModel.from_xml_string(scene_xml(self.robot, self.layout))
        self.data = mujoco.MjData(self.model)
        self.scratch = mujoco.MjData(self.model)
        self.arm_joints = [
            self.model.joint(name).id for name in self.config["joint_names"]
        ]
        self.qidx = np.array([self.model.jnt_qposadr[i] for i in self.arm_joints])
        self.didx = np.array([self.model.jnt_dofadr[i] for i in self.arm_joints])
        self.arm_act = np.array(
            [self.model.actuator(name).id for name in self.config["actuator_names"]]
        )
        self.gripper_act = [
            self.model.actuator(name).id
            for name in self.config["gripper_actuator_names"]
        ]
        self.tcp = self.model.site(self.config.get("tcp_site", "tcp")).id
        self.workspace_min = np.array(
            self.config.get("workspace_min", [0.08, -0.35, 0.015])
        )
        self.workspace_max = np.array(
            self.config.get("workspace_max", [0.55, 0.35, 0.60])
        )
        self.scene_option = mujoco.MjvOption()
        self.scene_option.geomgroup[3] = 0
        self.scene_option.sitegroup[4] = 0
        self.renderer = (
            mujoco.Renderer(self.model, height=self.height, width=self.width)
            if render
            else None
        )
        self.epoch = 0
        self.sequence = 0
        self.feedback = {"status": "initialized"}
        self.trajectory = None
        self._pending_target = None
        self._settle_until = 0.0
        self._success_since = None
        self._snapshot = None
        self.controller = PositionController(self)
        self.reset(0)

    backend = "mujoco"
    terminated = False

    @property
    def timestep(self):
        return float(self.model.opt.timestep)

    @property
    def simulation_time(self):
        return float(self.data.time)

    @property
    def render_enabled(self):
        return self.renderer is not None

    @property
    def robot_name(self):
        return self.robot.name

    @property
    def scene_name(self):
        return self.layout.name

    @property
    def task_name(self):
        return self.task.name

    @property
    def instruction(self):
        return self.task.instruction

    def create_chunk_executor(self, chunk):
        from maniloop.runtime.chunks import ChunkExecutor

        return ChunkExecutor(self, chunk)

    def describe(self):
        return {
            "backend": self.backend,
            "robot": self.robot_name,
            "scene": self.scene_name,
            "task": self.task_name,
            "robot_revision": self.config.get("upstream_revision"),
            "robot_configuration": self.config,
            "layout": {
                "initial_object_position": self.layout.object_position,
                "target_position": self.layout.target_position,
            },
            "evaluator": "tabletop_v1",
            "controller": "position_v1",
            "protocol": "maniloop_tabletop_v1",
            "simulation_timestep": self.timestep,
            "controller_limits": {
                "joint_speed_rad_s": 0.4,
                "tcp_speed_m_s": 0.06,
                "rotation_speed_rad_s": 0.5,
                "chunk_min_interval_s": 0.02,
                "chunk_max_interval_s": 1.0,
                "chunk_max_samples": 64,
            },
        }

    def reset(self, seed=0):
        self.epoch += 1
        self.sequence = 0
        mujoco.mj_resetData(self.model, self.data)
        if self.model.nkey:
            mujoco.mj_resetDataKeyframe(self.model, self.data, 0)
        else:
            self.data.qpos[self.qidx] = self.config["home_q"]
            self.data.ctrl[self.arm_act] = self.data.qpos[self.qidx]
        # Only initialization and independent evaluation may use object state.
        rng = np.random.default_rng(seed)
        if seed:
            obj = self.model.joint(self.config.get("object_joint", "object_joint"))
            self.data.qpos[obj.qposadr[0] : obj.qposadr[0] + 2] += rng.uniform(
                -0.025, 0.025, 2
            )
        self.data.ctrl[self.arm_act] = self.data.qpos[self.qidx]
        self.set_gripper(1.0)
        mujoco.mj_forward(self.model, self.data)
        for _ in range(round(0.5 / self.model.opt.timestep)):
            mujoco.mj_step(self.model, self.data)
        self.trajectory = None
        self._pending_target = None
        self._settle_until = self.data.time
        self.feedback = {"status": "initialized", "message": "场景已初始化"}
        self._success_since = None
        self._snapshot = None
        self.task.reset()
        self.task.update(self)

    @property
    def tcp_position(self):
        return self.data.site_xpos[self.tcp].copy()

    @property
    def tcp_rotation(self):
        return self.data.site_xmat[self.tcp].reshape(3, 3).copy()

    @property
    def gripper_opening(self):
        # Read finger joint encoders, independent of joint/tendon actuator units.
        vals = []
        for name, (closed, opened) in zip(
            self.config["gripper_joint_names"], self.config["gripper_sensor_ranges"]
        ):
            q = self.data.qpos[self.model.joint(name).qposadr[0]]
            vals.append((q - closed) / (opened - closed))
        return float(np.clip(np.mean(vals), 0, 1))

    def set_gripper(self, opening):
        for aid, (closed, opened) in zip(
            self.gripper_act, self.config["gripper_ctrl_ranges"]
        ):
            self.data.ctrl[aid] = closed + float(opening) * (opened - closed)

    def hold(self):
        self.trajectory = None
        self._pending_target = None
        self.data.ctrl[self.arm_act] = self.data.qpos[self.qidx]
        self._settle_until = self.data.time + 0.15
        self.epoch += 1
        self._snapshot = None

    @property
    def busy(self):
        return (
            self.trajectory is not None
            or self._pending_target is not None
            or self.data.time < self._settle_until
        )

    @property
    def settled(self):
        return not self.busy and np.max(np.abs(self.data.qvel[self.didx])) < 0.08

    def step(self, count=1):
        for _ in range(count):
            if self.trajectory:
                t = self.trajectory
                f = min(1.0, (self.data.time - t["start"]) / t["duration"])
                blend = f * f * (3 - 2 * f)
                self.data.ctrl[self.arm_act] = t["q0"] + blend * (t["q1"] - t["q0"])
                if f >= 1:
                    self.trajectory = None
                    self._settle_until = self.data.time + 0.25
                    self._pending_target = t["target"].copy()
            mujoco.mj_step(self.model, self.data)
            self.task.update(self)
        if self._pending_target is not None and self.data.time >= self._settle_until:
            stable = np.max(np.abs(self.data.qvel[self.didx])) < 0.08
            expired = self.data.time > self._settle_until + 2.0
            if stable or expired:
                error = float(np.linalg.norm(self.tcp_position - self._pending_target))
                reached = stable and error < 0.008
                self.feedback = {
                    "status": "completed" if reached else "failed",
                    "message": (
                        "动作已完成并停稳"
                        if reached
                        else "执行未达到目标，请根据新观测重新决策"
                    ),
                    "actual_tcp_position": self.tcp_position.tolist(),
                    "target_tcp_position": self._pending_target.tolist(),
                    "position_error_m": error,
                }
                self._pending_target = None
        if not np.all(np.isfinite(self.data.qpos)):
            raise RuntimeError("仿真状态出现非有限数值，请重置场景")

    def _camera(self, name):
        cid = self.model.camera(name).id
        fy = self.height / (2 * math.tan(math.radians(self.model.cam_fovy[cid]) / 2))
        return {
            "width": self.width,
            "height": self.height,
            "intrinsics": {
                "fx": fy,
                "fy": fy,
                "cx": (self.width - 1) / 2,
                "cy": (self.height - 1) / 2,
            },
            "position_in_base": self.data.cam_xpos[cid].tolist(),
            "rotation_in_base": self.data.cam_xmat[cid].reshape(3, 3).tolist(),
            "depth_available": name == "external",
            "optical_convention": "MuJoCo camera +x right, +y up, looks along -z; image v increases down",
        }

    def render_images(self, with_depth=False):
        if self.renderer is None:
            return {}, None
        images, depth = {}, None
        for name in ["external", "wrist"]:
            self.renderer.disable_depth_rendering()
            self.renderer.update_scene(
                self.data, camera=name, scene_option=self.scene_option
            )
            rgb = self.renderer.render().copy()
            buf = io.BytesIO()
            Image.fromarray(rgb).save(buf, format="JPEG", quality=88)
            images[name] = buf.getvalue()
            if with_depth and name == "external":
                self.renderer.enable_depth_rendering()
                self.renderer.update_scene(
                    self.data, camera=name, scene_option=self.scene_option
                )
                depth = self.renderer.render().copy()
                self.renderer.disable_depth_rendering()
        return images, depth

    def observe(self):
        self.sequence += 1
        observation = {
            "observation_id": f"{self.epoch}:{self.sequence}:{uuid.uuid4().hex[:8]}",
            "timestamp_monotonic": time.monotonic(),
            "simulation_time": float(self.data.time),
            "frame_id": "base",
            "tcp_position": self.tcp_position.tolist(),
            "tcp_rotation_matrix": self.tcp_rotation.tolist(),
            "joint_names": list(self.config["joint_names"]),
            "joint_positions": self.data.qpos[self.qidx].tolist(),
            "joint_velocities": self.data.qvel[self.didx].tolist(),
            "gripper_opening": self.gripper_opening,
            "cameras": {name: self._camera(name) for name in ["external", "wrist"]},
            "action_limits": {
                "translation_max_m": self.translation_limit,
                "rotation_max_rad": self.rotation_limit,
                "workspace_xyz_min": self.workspace_min.tolist(),
                "workspace_xyz_max": self.workspace_max.tolist(),
            },
            "last_feedback": dict(self.feedback),
            "robot_description": self.config.get(
                "robot_description",
                "ARX X5, six-axis arm, parallel gripper. TCP is the center between fingertips. Base frame coincides with world; metres and radians. delta_rotation is a base-frame rotation vector, left-multiplied onto the observed TCP rotation. gripper_opening is 0 closed, 1 fully open. Images are 640x480; query_depth pixels are integer [u,v].",
            ),
        }
        images, depth = self.render_images(with_depth=True)
        self._snapshot = {"observation": observation, "images": images, "depth": depth}
        return observation, images

    def depth_query(self, action):
        if (
            self._snapshot is None
            or action.get("observation_id")
            != self._snapshot["observation"]["observation_id"]
        ):
            return {"valid": False, "reason": "observation_id mismatch"}
        if action.get("camera") != "external":
            return {"valid": False, "reason": "Only external has a depth sensor"}
        u, v = action.get("pixel", [-1, -1])
        if not all(
            isinstance(a, int) and not isinstance(a, bool) for a in [u, v]
        ) or not (0 <= u < self.width and 0 <= v < self.height):
            return {"valid": False, "reason": "Pixel outside image"}
        depth = self._snapshot["depth"]
        if depth is None:
            return {"valid": False, "reason": "Depth unavailable"}
        patch = depth[max(0, v - 1) : v + 2, max(0, u - 1) : u + 2]
        vals = patch[np.isfinite(patch) & (patch > 0.02) & (patch < 2.0)]
        if not len(vals):
            return {"valid": False, "reason": "No valid depth in 3x3 neighbourhood"}
        z = float(np.median(vals))
        camera = self._snapshot["observation"]["cameras"]["external"]
        k = camera["intrinsics"]
        point = np.array(
            [(u - k["cx"]) * z / k["fx"], -(v - k["cy"]) * z / k["fy"], -z]
        )
        world = (
            np.array(camera["position_in_base"])
            + np.array(camera["rotation_in_base"]) @ point
        )
        return {
            "valid": True,
            "observation_id": action["observation_id"],
            "camera": "external",
            "pixel": [u, v],
            "depth_m": z,
            "position_in_base": world.tolist(),
            "depth_spread_m": float(np.std(vals)),
            "source": "simulated calibrated RGB-D depth, median 3x3 pixels; surface point, not object center",
        }

    def validate_snapshot(self, observation, max_age=60.0):
        if (
            not self._snapshot
            or observation["observation_id"]
            != self._snapshot["observation"]["observation_id"]
        ):
            return False, "观测已被重置或替换"
        if time.monotonic() - observation["timestamp_monotonic"] > max_age:
            return False, "观测已过期"
        if np.linalg.norm(self.tcp_position - observation["tcp_position"]) > 0.008:
            return False, "等待期间末端位置已变化，需要重新观察"
        if (
            np.max(np.abs(self.data.qpos[self.qidx] - observation["joint_positions"]))
            > 0.05
        ):
            return False, "等待期间关节状态已变化，需要重新观察"
        return True, ""

    def _ik(self, position, rotation):
        return self.controller._ik(position, rotation)

    def _path_collision(self, target_q):
        return self.controller._path_collision(target_q)

    def execute(self, action):
        return self.controller.execute(action)

    def evaluation(self):
        return self.task.evaluate()

    def close(self):
        if self.renderer:
            self.renderer.close()


RobotSim = MuJoCoEnvironment  # Compatibility with the original demo.
