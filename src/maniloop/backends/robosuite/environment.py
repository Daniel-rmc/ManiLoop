"""Panda robosuite adapter with explicitly configured world-frame OSC control."""

import base64
from collections import deque
import copy
import math
import time
import uuid
import numpy as np
from maniloop.controllers.target import PoseTarget
from .transport import Worker
from .catalog import PROFILES, validate_task


class RobosuiteEnvironment:
    backend = "robosuite"
    robot_name = "panda"
    timestep = 0.05
    pause_when_idle = True

    def __init__(self, *, task="Lift", render=True, python=None, root=None,
                 observation_profile="debug_rgb128"):
        validate_task(task)
        if observation_profile not in PROFILES:
            raise ValueError("Unknown robosuite observation profile")
        self.worker = Worker(python, root)
        self.render_enabled = render
        self._queue = deque()
        self._target = None
        self.llm_control = "osc_step"
        self._grip = -1.0
        self.epoch = 0
        try:
            self._description = self.worker.call("init", task=task, render=render,
                                                observation_profile=observation_profile, seed=0)
            self.scene_name = self._description["scene"]
            self.task_name = self._description["task"]
            self.instruction = self._description["instruction"]
            self._clear_episode()
            self.observe()
        except Exception:
            self.close()
            raise

    def _clear_episode(self):
        self.epoch += 1
        self.simulation_time = 0.0
        self.terminated = False
        self._queue.clear()
        self._target = None
        self._grip = 0.0 if self.llm_control == "tcp_target_servo_v2" else -1.0
        self.feedback = {
            "status": "ready",
            "message": "Upstream robosuite initialization loaded",
        }
        self._snapshot = None

    @property
    def busy(self):
        return bool(self._queue) or self._target is not None

    @property
    def settled(self):
        return not self.busy

    @property
    def tcp_position(self):
        return np.array(self._sensors["tcp_position"])

    @property
    def gripper_opening(self):
        return self._sensors["gripper_opening"]

    def reset(self, seed=0):
        if type(seed) is not int or seed < 0:
            raise ValueError("Seed must be nonnegative")
        self._sensors = self.worker.call("reset", seed=seed)
        self._clear_episode()

    def set_llm_control(self, mode):
        if mode not in ("osc_step", "tcp_target_servo_v2") or self.busy:
            raise ValueError("Unknown control mode or action still executing")
        self.llm_control = mode
        if self.simulation_time == 0:
            # Zero initial gripper input preserves the upstream initial actuator target.
            self._grip = 0.0 if mode == "tcp_target_servo_v2" else -1.0

    def describe(self):
        result = copy.deepcopy(self._description)
        result["llm_control"] = self.llm_control
        if self.llm_control == "tcp_target_servo_v2":
            result["target_controller"] = PoseTarget.description()
            result["llm_action_adapter"] = "Fixed TCP target; proprioceptive OSC feedback up to 20 control steps; no object state"
        return result

    def observe(self):
        result = self.worker.call("observe")
        self._sensors = result["sensors"]
        observation = {
            **self._sensors,
            "observation_id": f"{self.epoch}:{uuid.uuid4().hex}",
            "timestamp_monotonic": time.monotonic(),
            "simulation_time": self.simulation_time,
            "frame_id": "world",
            "cameras": result["cameras"],
            "action_limits": {
                "translation_max_m": 0.05,
                "rotation_max_rad": 0.5,
                "native_action": "osc_pose",
                "native_dimension": 7,
                "native_range": [-1.0, 1.0],
                "control_interval_seconds": 0.05,
            },
            "geometry_queries": {"depth_available": False},
            "last_feedback": copy.deepcopy(self.feedback),
            "robot_description": "robosuite Panda with parallel gripper. World-frame OSC_POSE control. "
            "TCP state is robot0_eef_pos/eef_quat_site from consistent site kinematics. RGB cameras only; no depth queries. "
            "move applies one 20 Hz OSC command, bounded by translation/rotation norm; it is not a reached target guarantee. "
            "gripper_opening accepts 0 (close) or 1 (open), each for 10 control steps. "
            "Native osc_pose chunks contain 7 normalized values: world xyz/rotation delta, then -1 open / +1 close. "
            "Images use top-left pixel origin, camera_to_world is OpenCV camera coordinates.",
        }
        if self.llm_control == "tcp_target_servo_v2":
            observation["action_limits"]["target_tracking"] = PoseTarget.description()
            observation["robot_description"] = (
                "robosuite Panda, world frame, RGB sensors only. move captures one fixed TCP pose target "
                "from the current pose plus your delta, then uses proprioceptive feedback at 20 Hz "
                "for up to 1 second. Rotation is Exp(world rotation vector) @ current rotation. "
                "Inspect reached/timed_out/interrupted feedback and actual displacement; accepted is not reached. "
                "Gripper accepts only 0 closed or 1 open and holds arm pose; completed does not prove a grasp. "
                "No object poses or success feedback are available. Camera pixels have top-left origin."
            )
        self._snapshot = copy.deepcopy(observation)
        return observation, {
            k: base64.b64decode(v) for k, v in result["images"].items()
        }

    def render_images(self):
        result = self.worker.call("observe")
        self._sensors = result["sensors"]
        return {k: base64.b64decode(v) for k, v in result["images"].items()}, None

    def validate_snapshot(self, observation, max_age=60):
        if (
            self._snapshot is None
            or observation.get("observation_id") != self._snapshot["observation_id"]
        ):
            return False, "Observation belongs to an old reset or decision（观测版本已失效，不是时间超限）"
        age = time.monotonic() - self._snapshot["timestamp_monotonic"]
        if age > max_age:
            return False, f"Observation expired（观测已等待 {age:.1f} 秒，时间上限 {max_age:g} 秒）"
        return True, "valid"

    def depth_query(self, action):
        return {
            "valid": False,
            "reason": "robosuite RGB-only protocol has no depth sensor",
            "observation_id": action.get("observation_id"),
        }

    def execute(self, action):
        try:
            if self.terminated or self.busy:
                raise ValueError("Environment terminated or action still executing")
            kind = action["kind"]
            native = np.array([0.0] * 6 + [self._grip])
            count = 1
            if kind == "move":
                if action.get("frame", "world") != "world":
                    raise ValueError("robosuite TCP commands require world frame")
                pos = np.asarray(action.get("delta_position", [0, 0, 0]), dtype=float)
                rot = np.asarray(action.get("delta_rotation", [0, 0, 0]), dtype=float)
                if (
                    pos.shape != (3,)
                    or rot.shape != (3,)
                    or not np.isfinite(pos).all()
                    or not np.isfinite(rot).all()
                ):
                    raise ValueError("Expected finite xyz and rotation vectors")
                if (
                    np.linalg.norm(pos) > 0.05 + 1e-12
                    or np.linalg.norm(rot) > 0.5 + 1e-12
                ):
                    raise ValueError("Move exceeds .05 m / .5 rad per-step limits")
                native[:3], native[3:6] = pos / 0.05, rot / 0.5
            elif kind == "gripper":
                opening = action.get("gripper_opening")
                if type(opening) not in (int, float) or opening not in (0, 1):
                    raise ValueError("robosuite gripper accepts 0 closed or 1 open")
                native[6] = 1.0 - 2.0 * opening
                count = 10
            elif kind != "wait":
                raise ValueError(
                    "robosuite supports move/gripper/wait or native osc_pose chunks"
                )
            self._grip = float(native[6])
            if self.llm_control == "tcp_target_servo_v2" and kind in ("move", "gripper"):
                self._target = PoseTarget(
                    self._sensors, pos if kind == "move" else np.zeros(3),
                    rot if kind == "move" else np.zeros(3), self._grip,
                    gripper=kind == "gripper",
                )
                self.feedback = {"status": "accepted", "message": "Tracking fixed TCP target from proprioception", "max_control_steps": 20}
                return dict(self.feedback)
            self._queue.extend(native.tolist() for _ in range(count))
            self.feedback = {
                "status": "accepted",
                "message": "Queued native OSC command",
                "control_steps": count,
            }
        except (ValueError, TypeError, KeyError) as exc:
            self.feedback = {"status": "rejected", "message": str(exc)}
        return dict(self.feedback)

    def execute_manual(self, action, *, max_control_steps):
        """Explicit human-only budget; policy execute() keeps its original limit."""
        from dataclasses import replace
        if type(max_control_steps) is not int or not 1 <= max_control_steps <= 200:
            raise ValueError("Manual target budget must be 1–200 control steps")
        result = self.execute(action)
        if result["status"] == "accepted" and self._target is not None:
            self._target.settings = replace(self._target.settings, max_steps=max_control_steps)
            self.feedback["max_control_steps"] = max_control_steps
            result = dict(self.feedback)
        return result

    def stage_native(self, action):
        action.validate()
        if (
            action.kind != "osc_pose"
            or action.frame != "world"
            or self.busy
            or self.terminated
        ):
            raise ValueError(
                "Native robosuite chunks require available world-frame OSC control"
            )
        self._grip = action.values[-1]
        self._queue.append(list(action.values))

    def step(self, count=1):
        for _ in range(count):
            if self.terminated:
                break
            action = (self._target.sample(self._sensors) if self._target is not None else
                      self._queue.popleft() if self._queue else [0.0] * 6 + [self._grip])
            result = self.worker.call("step", action=action)
            self._sensors = result["sensors"]
            self.simulation_time = result["steps"] * self.timestep
            self.terminated = result["terminated"]
            if self._target is not None:
                self.feedback = self._target.update(self._sensors, self.timestep, self.terminated)
                if self._target.finished:
                    self._target = None
            if self.terminated:
                self._queue.clear()

    def hold(self):
        if self._target is not None:
            self.feedback = {**self.feedback, "status": "interrupted", "message": "Target cancelled; no remaining samples"}
        self._target = None
        self._queue.clear()
        self._snapshot = None

    def create_chunk_executor(self, chunk):
        return RobosuiteChunkExecutor(self, chunk)

    def evaluation(self):
        return self.worker.call("evaluate")

    def close(self):
        self.worker.close()


class RobosuiteChunkExecutor:
    """One sample per native control tick, with no hidden repeats or extra physics steps."""

    def __init__(self, env, chunk):
        chunk.validate()
        if not math.isclose(chunk.interval_seconds, env.timestep, abs_tol=1e-9):
            raise ValueError("robosuite native chunks must run at 20 Hz (interval .05 s)")
        for action in chunk.actions:
            if action.kind != "osc_pose" or action.frame != "world":
                raise ValueError(
                    "robosuite chunks require normalized world-frame osc_pose samples"
                )
        self.env, self.chunk, self.index = env, chunk, 0
        self.completed = False

    def tick(self):
        if self.index == len(self.chunk.actions):
            self.completed = True
            return None
        self.env.stage_native(self.chunk.actions[self.index])
        self.index += 1
        return {
            "status": "accepted",
            "message": "Native OSC sample staged",
            "sample": self.index,
        }
