"""Embodiment metadata. Sensor joint ranges and actuator command ranges differ."""

from dataclasses import dataclass
from pathlib import Path
import json

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "robots"


@dataclass(frozen=True)
class RobotSpec:
    name: str
    model_path: Path
    config: dict

    @property
    def joint_names(self):
        return tuple(self.config["joint_names"])


def robot_spec(name: str) -> RobotSpec:
    if name == "arx5":
        config = json.loads((ASSETS / "arx5/robot_config.json").read_text())
        config["home_q"] = config["home_arm_qpos_rad"]
        config["gripper_sensor_ranges"] = [[0, 0.044], [0, 0.044]]
        return RobotSpec(name, ASSETS / "arx5/scene.xml", config)
    if name == "panda":
        config = {
            "upstream_revision": "8161bba264d7fa7c99ca301e91e7fb44737676ad",
            "joint_names": [f"joint{i}" for i in range(1, 8)],
            "actuator_names": [f"actuator{i}" for i in range(1, 8)],
            "gripper_actuator_names": ["actuator8"],
            "gripper_ctrl_ranges": [[0, 255]],
            "gripper_joint_names": ["finger_joint1", "finger_joint2"],
            "gripper_sensor_ranges": [[0, 0.04], [0, 0.04]],
            "home_q": [0, -0.785, 0, -2.356, 0, 1.571, 0.785],
            "tcp_site": "tcp",
            "base_body": "link0",
            "object_joint": "cube_free",
            "object_body": "red_cube",
            "workspace_min": [0.10, -0.4, 0.012],
            "workspace_max": [0.70, 0.4, 0.70],
            "robot_description": "Franka Panda, 7 arm joints and parallel gripper. TCP is between fingertips; local +Z toward fingertips. Base/world coincide; metres/radians. Joint position actions use named joints in radians. Gripper 0 closed, 1 open (80 mm). External RGB-D and wrist RGB cameras.",
        }
        return RobotSpec(name, ASSETS / "panda/panda.xml", config)
    raise ValueError(f"Unknown robot: {name}; choose arx5 or panda")
