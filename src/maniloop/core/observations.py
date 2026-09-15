"""Allowed sensor-packet fields shared by all policy families."""

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
