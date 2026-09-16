"""Allowed sensor-packet fields shared by all policy families."""

from copy import deepcopy

FORBIDDEN_SENSOR_FIELDS = frozenset({
    "evaluation", "evaluator", "success", "native_success", "current_success",
    "reward", "score", "object-state", "object_state", "object_pose", "object_poses",
    "object_position", "object_positions", "target_center", "target_position",
    "contacts", "contact_truth", "ground_truth", "simulator", "fault_label",
})

FEEDBACK_FIELDS = frozenset({
    "status", "message", "kind", "sample", "simulation_time", "control_steps",
    "max_control_steps", "actual_delta_position", "actual_tcp_position", "target_tcp_position",
    "position_error_m", "rotation_error_rad", "linear_speed_m_s", "angular_speed_rad_s",
    "gripper_opening", "gripper_speed_s",
})

PAIR_SENSOR_FIELDS = frozenset({
    "observation_id", "simulation_time", "frame_id", "tcp_position", "tcp_rotation_matrix",
    "tcp_quaternion_xyzw", "gripper_opening", "joint_positions", "joint_velocities",
})


def guard_sensor_tree(value):
    """Reject privileged fields anywhere, including future nested history entries."""
    if isinstance(value, dict):
        if any(not isinstance(key, str) or key.lower() in FORBIDDEN_SENSOR_FIELDS for key in value):
            raise ValueError("Privileged or invalid field in sensor payload")
        for key, child in value.items():
            if key in {"feedback", "last_feedback"}:
                if not isinstance(child, dict) or set(child) - FEEDBACK_FIELDS:
                    raise ValueError("Unsupported execution feedback fields")
            guard_sensor_tree(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            guard_sensor_tree(child)


def paired_sensors(observation):
    guard_sensor_tree(observation)
    return deepcopy({key: value for key, value in observation.items() if key in PAIR_SENSOR_FIELDS})

PUBLIC_OBSERVATION_FIELDS = frozenset(
    {
        "execution_mode",
        "joint_names",
        "observation_id",
        "timestamp_monotonic",
        "simulation_time",
        "frame_id",
        "tcp_position",
        "tcp_rotation_matrix",
        "tcp_quaternion_xyzw",
        "gripper_joint_positions",
        "joint_positions",
        "joint_velocities",
        "gripper_opening",
        "cameras",
        "action_limits",
        "last_feedback",
        "robot_description",
        "geometry_queries",
        "task",
    }
)
