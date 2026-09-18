"""Dependency-free task catalog; availability is not a model-success claim."""
ROBOSUITE_VERSION = "1.5.2"
MUJOCO_VERSION = "3.3.7"
CAMERAS = {"external": "agentview", "wrist": "robot0_eye_in_hand"}
PROFILES = {"debug_rgb128": 128, "llm_rgb512": 512}
TASKS = {
    "Lift": ("抓起方块", "Lift the cube off the table."),
    "Stack": ("堆叠方块", "Stack the red cube on the green cube and release it."),
    "PickPlaceCan": ("易拉罐分类放置", "Pick up the can and place it in its target bin."),
    "Door": ("打开门", "Open the door using its handle."),
    "NutAssemblySquare": ("方形螺母装配", "Place the square nut onto its matching peg."),
}


def list_tasks():
    return [{"id": name, "backend": "robosuite", "upstream_env": name,
             "display_name": details[0], "instruction": details[1],
             "robot": "panda", "controller": "OSC_POSE_world_v1",
             "support": "experimental", "camera_mapping": dict(CAMERAS)}
            for name, details in TASKS.items()]


def validate_task(task):
    if task not in TASKS:
        raise ValueError(f"Unknown robosuite task {task!r}; choose: {', '.join(TASKS)}")
    return TASKS[task]
