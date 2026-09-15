"""Policy output contract. Physical SI actions and explicitly normalized native OSC actions."""

from dataclasses import dataclass
from typing import Literal
import math


@dataclass(frozen=True)
class Action:
    kind: Literal["tcp_delta", "joint_position", "gripper", "wait", "osc_pose"]
    values: tuple[float, ...] = ()
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    gripper: float | None = None
    joint_names: tuple[str, ...] = ()
    frame: str = "base"

    def validate(self):
        if self.kind not in (
            "tcp_delta",
            "joint_position",
            "gripper",
            "wait",
            "osc_pose",
        ) or self.frame not in ("base", "world"):
            raise ValueError("Unsupported action kind or frame")
        numbers = (
            *self.values,
            *self.rotation,
            *(() if self.gripper is None else (self.gripper,)),
        )
        if any(type(x) not in (float, int) or not math.isfinite(x) for x in numbers):
            raise ValueError("Action values must be finite numbers")
        if self.kind == "osc_pose" and (
            len(self.values) != 7
            or any(abs(x) > 1 for x in self.values)
            or self.frame != "world"
            or self.gripper is not None
        ):
            raise ValueError(
                "OSC action requires seven normalized [-1, 1] world-frame values"
            )
        if len(self.rotation) != 3 or (
            self.kind == "tcp_delta" and len(self.values) != 3
        ):
            raise ValueError(
                "TCP action requires three translation and rotation values"
            )
        if self.gripper is not None and not 0 <= self.gripper <= 1:
            raise ValueError("Gripper must be between zero and one")
        if self.kind == "gripper" and self.gripper is None:
            raise ValueError("Gripper opening is required")
        if self.kind == "joint_position" and (
            not self.values
            or len(self.values) != len(self.joint_names)
            or len(set(self.joint_names)) != len(self.joint_names)
        ):
            raise ValueError("Joint values require explicit unique ordered joint names")
        if self.kind != "tcp_delta" and any(self.rotation):
            raise ValueError("Only a TCP action may contain rotation")
        if self.kind != "joint_position" and self.joint_names:
            raise ValueError("Only joint actions may specify joint names")
        if any(type(name) is not str or not name for name in self.joint_names):
            raise ValueError("Joint names must be nonempty strings")
        if self.kind in ("gripper", "wait") and self.values:
            raise ValueError("This action cannot contain motion targets")

    @classmethod
    def from_legacy(cls, value, frame="base"):
        kind = value["kind"]
        if kind == "move":
            return cls(
                "tcp_delta",
                tuple(value.get("delta_position", (0, 0, 0))),
                tuple(value.get("delta_rotation", (0, 0, 0))),
                frame=frame,
            )
        if kind == "joint_position":
            return cls(
                "joint_position",
                tuple(value["joint_positions"]),
                joint_names=tuple(value["joint_names"]),
                gripper=value.get("gripper_opening"),
            )
        if kind == "gripper":
            return cls("gripper", gripper=value["gripper_opening"])
        if kind == "wait":
            return cls("wait")
        raise ValueError("Not an executable action")

    def legacy(self):
        self.validate()
        return {
            "kind": {
                "tcp_delta": "move",
                "joint_position": "joint_position",
                "gripper": "gripper",
                "wait": "wait",
            }[self.kind],
            "delta_position": (
                list(self.values) if self.kind == "tcp_delta" else [0, 0, 0]
            ),
            "delta_rotation": list(self.rotation),
            "frame": self.frame,
            **({"gripper_opening": self.gripper} if self.gripper is not None else {}),
            "joint_positions": list(self.values),
            "joint_names": list(self.joint_names),
        }


@dataclass(frozen=True)
class ActionChunk:
    observation_id: str
    actions: tuple[Action, ...]
    interval_seconds: float = 0.1

    def validate(self):
        if (
            type(self.observation_id) is not str
            or not self.observation_id
            or not 1 <= len(self.actions) <= 64
        ):
            raise ValueError("A chunk needs an observation ID and 1–64 actions")
        if (
            type(self.interval_seconds) not in (int, float)
            or not math.isfinite(self.interval_seconds)
            or not 0.02 <= self.interval_seconds <= 1.0
        ):
            raise ValueError("Chunk interval must be 0.02–1 simulation seconds")
        for action in self.actions:
            action.validate()
