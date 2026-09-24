"""Arm-only RoboCasa adapter; the worker expands commands to the full mobile action."""
from collections import deque
import copy
from maniloop.backends.robosuite.environment import RobosuiteEnvironment
from .transport import Worker
from .catalog import DEFAULT_LAYOUT, DEFAULT_STYLE, PROFILES, validate_task, validate_scene


class RobocasaEnvironment(RobosuiteEnvironment):
    backend = "robocasa"
    robot_name = "panda_omron"

    def __init__(self, *, task="OpenDrawer", render=True, python=None, root=None,
                 observation_profile="debug_rgb128", layout=DEFAULT_LAYOUT, style=DEFAULT_STYLE):
        validate_task(task)
        validate_scene(layout, style)
        if observation_profile not in PROFILES:
            raise ValueError("Unknown RoboCasa observation profile")
        self.worker = Worker(python, root)
        self.render_enabled = render
        self._queue = deque()
        self._target = None
        self.llm_control, self._grip, self.epoch = "osc_step", 0.0, 0
        try:
            self._description = self.worker.call("init", task=task, render=render,
                observation_profile=observation_profile, seed=0, layout=layout, style=style)
            self._load_description()
            self._clear_episode()
            self.observe()
        except Exception:
            self.close()
            raise

    def _load_description(self):
        self.scene_name = self._description["scene"]
        self.task_name = self._description["task"]
        self.instruction = self._description["instruction"]

    def _clear_episode(self):
        super()._clear_episode()
        self._grip = 0.0
        self.feedback = {"status": "ready", "message": "RoboCasa episode initialized; base/torso held"}

    def reset(self, seed=0):
        if type(seed) is not int or seed < 0:
            raise ValueError("Seed must be a nonnegative integer")
        result = self.worker.call("reset", seed=seed)
        self._sensors, self._description = result["sensors"], result["description"]
        self._load_description()
        self._clear_episode()

    def observe(self):
        observation, images = super().observe()
        observation["action_limits"].update(
            native_dimension=7, upstream_action_dimension=12,
            action_adapter="world_osc_arm_subset_to_pandaomron_12d_v1",
            base_control=False, torso_control=False,
        )
        execution = ("move captures a fixed world TCP target and tracks it for at most 1 second. "
                     if self.llm_control == "tcp_target_servo_v2" else
                     "move applies a single 20 Hz arm command, not a reached-target guarantee. ")
        observation["robot_description"] = (
            "RoboCasa PandaOmron mobile manipulator, arm-and-gripper-only protocol. "
            "TCP position and orientation are from the same end-effector site in WORLD coordinates. "
            + execution +
            "The worker rotates world deltas into the upstream BASE frame and assembles the full "
            "12-value composite action. Base velocity and torso delta are held at zero; arm mode is -1. "
            "The 7-value osc_pose action is an arm-only adapter, NOT the full upstream action. "
            "Do not request navigation or torso movement. Gripper: 0 closed / 1 open. "
            "RGB-only, no depth queries or object poses. Camera origin is top-left. "
            "Inspect reached/timed_out feedback; completed does not verify a grasp."
        )
        self._snapshot = copy.deepcopy(observation)
        return observation, images

    def depth_query(self, action):
        return {"valid": False, "reason": "RoboCasa RGB-only observations have no depth query",
                "observation_id": action.get("observation_id")}
