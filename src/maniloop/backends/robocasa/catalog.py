"""Curated RoboCasa task catalog; listing never imports the optional simulator."""
ROBOCASA_REVISION = "4f8a2980def75a55dff96b990745b83540425f09"
ROBOSUITE_REVISION = "5ce6643f3092639d08f7b0f90ed1c6a84f50552c"
ROBOCASA_VERSION = "1.0.1"
MUJOCO_VERSION = "3.3.1"
DEFAULT_LAYOUT = 11
DEFAULT_STYLE = 14
PROFILES = {"debug_rgb128": 128, "llm_rgb512": 512}
CAMERAS = {"external": "robot0_agentview_left", "wrist": "robot0_eye_in_hand"}
TASKS = {
    "OpenDrawer": ("打开抽屉", "Open the indicated drawer.", 750),
    "CloseDrawer": ("关闭抽屉", "Close the open drawer.", 450),
    "OpenCabinet": ("打开柜门", "Open the indicated cabinet.", 1050),
    "CoffeeSetupMug": ("放置咖啡杯", "Place the mug under the coffee machine dispenser.", 600),
}


def validate_task(task):
    if task not in TASKS:
        raise ValueError(f"Unknown RoboCasa task: {task}")
    return TASKS[task]


def validate_scene(layout, style):
    if any(type(x) is not int or x < 1 or x > 60 for x in (layout, style)):
        raise ValueError("RoboCasa layout/style must be integers from 1 to 60")
    return layout, style


def list_tasks():
    return [{"id": key, "display_name": value[0], "instruction": value[1],
             "horizon": value[2], "robot": "panda_omron", "support": "verified", "verification_scope": "interface: layout11/style14/seed0; no model success claim",
             "control_scope": "arm_and_gripper; base and torso hold",
             "default_layout": DEFAULT_LAYOUT, "default_style": DEFAULT_STYLE}
            for key, value in TASKS.items()]
