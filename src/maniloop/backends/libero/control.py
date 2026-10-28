"""LLM target bounds are separate from the pinned upstream OSC command scale."""

import math
from maniloop.controllers.target import TargetSettings


TARGET_MODES = ("tcp_target_servo_v2", "tcp_target_servo_v3")
LLM_CONTROL_MODES = ("osc_step", *TARGET_MODES)

# Pinned robosuite 1.4.0 Panda XML: joint1 origin -> grip_site. The fixed
# base -> joint1 offset cancels between poses. Triangle inequality bounds any
# TCP displacement by 2 * this length, ignoring joint limits and obstacles.
PANDA_CHAIN_LENGTH_M = .316 + .0825 + math.hypot(.0825, .384) + .088 + .1065 + .097
PANDA_DISPLACEMENT_BOUND_M = 2 * PANDA_CHAIN_LENGTH_M


def target_settings(mode, *, gripper=False):
    # 10 s is an explicit engineering deadline (also supported by manual mode),
    # not a guaranteed reach time. Leave every v2/shared-backend setting intact.
    return TargetSettings(max_steps=200 if mode == "tcp_target_servo_v3" and not gripper else 20)


def command_limits(mode):
    return (2.5, math.pi) if mode == "tcp_target_servo_v3" else (.05, .5)


def wide_target_description():
    return {
        "translation_max_m": 2.5,
        "rotation_max_rad": math.pi,
        "bounds_semantics": "invalid_input_guard_not_reachable_workspace",
        "translation_basis": "2 * joint1_to_grip_site_fixed_translation_chain_length",
        "robot_chain_length_m": PANDA_CHAIN_LENGTH_M,
        "geometric_displacement_bound_m": PANDA_DISPLACEMENT_BOUND_M,
        "rotation_basis": "shortest_SO3_rotation_at_most_pi",
        "native_translation_norm_max_m": .05,
        "native_rotation_norm_max_rad": .5,
        "target_timeout_seconds": 10.0,
        "gripper_max_control_steps": 20,
        "gripper_timeout_seconds": 1.0,
        "timeout_basis": "explicit_engineering_deadline_not_reachability_guarantee",
    }
