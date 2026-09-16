"""Bounded pose tracking from robot proprioception, without task or object state."""

from dataclasses import asdict, dataclass
import numpy as np
from .geometry import rotation_matrix, rotation_vector


@dataclass(frozen=True)
class TargetSettings:
    max_steps: int = 20
    position_tolerance_m: float = 0.002
    rotation_tolerance_rad: float = 0.02
    linear_speed_tolerance_m_s: float = 0.01
    angular_speed_tolerance_rad_s: float = 0.1
    stable_steps: int = 2
    gripper_speed_tolerance_s: float = 0.1


class PoseTarget:
    """Capture the target once; produce bounded deltas relative to current sensors."""

    def __init__(self, sensors, position_delta, rotation_delta, grip, *, gripper=False):
        self.settings = TargetSettings()
        self.start = np.array(sensors["tcp_position"], dtype=float)
        self.previous_position = self.start.copy()
        self.previous_rotation = np.array(sensors["tcp_rotation_matrix"], dtype=float)
        self.position = self.start + position_delta
        self.rotation = rotation_matrix(rotation_delta) @ self.previous_rotation
        self.previous_opening = float(sensors["gripper_opening"])
        self.grip = grip
        self.gripper = gripper
        self.steps = self.stable = 0
        self.finished = False

    @staticmethod
    def bounded(vector, limit):
        norm = np.linalg.norm(vector)
        return vector * min(1.0, limit / max(norm, 1e-12))

    def sample(self, sensors):
        position = np.array(sensors["tcp_position"])
        rotation = np.array(sensors["tcp_rotation_matrix"])
        dp = self.bounded(self.position - position, 0.05) / 0.05
        dr = self.bounded(rotation_vector(self.rotation @ rotation.T), 0.5) / 0.5
        return [*dp.tolist(), *dr.tolist(), self.grip]

    def update(self, sensors, interval=0.05, interrupted=False):
        self.steps += 1
        position = np.array(sensors["tcp_position"])
        rotation = np.array(sensors["tcp_rotation_matrix"])
        distance = float(np.linalg.norm(self.position - position))
        angle = float(np.linalg.norm(rotation_vector(self.rotation @ rotation.T)))
        speed = float(np.linalg.norm(position - self.previous_position) / interval)
        angular_speed = float(np.linalg.norm(rotation_vector(rotation @ self.previous_rotation.T)) / interval)
        self.previous_position, self.previous_rotation = position, rotation
        opening = float(sensors["gripper_opening"])
        gripper_speed = abs(opening - self.previous_opening) / interval
        self.previous_opening = opening
        s = self.settings
        settled = (distance <= s.position_tolerance_m and angle <= s.rotation_tolerance_rad
                   and speed <= s.linear_speed_tolerance_m_s and angular_speed <= s.angular_speed_tolerance_rad_s)
        if self.gripper:
            settled = settled and gripper_speed <= s.gripper_speed_tolerance_s
            # Closing may stop against an object; opening must reach the open range.
            settled = settled and (self.grip > 0 or opening >= 0.9)
        self.stable = self.stable + 1 if settled else 0
        reached = self.stable >= s.stable_steps and self.steps >= (10 if self.gripper else 2)
        self.finished = interrupted or reached or self.steps >= s.max_steps
        status = "interrupted" if interrupted else ("reached" if reached else "timed_out")
        if not self.finished:
            status = "executing"
        if reached and self.gripper:
            status = "completed"
        return {"status": status, "message": "Gripper settled; grasp is not verified" if status == "completed" else f"TCP target {status}",
                "actual_delta_position": (position - self.start).tolist(),
                "position_error_m": distance, "rotation_error_rad": angle,
                "linear_speed_m_s": speed, "angular_speed_rad_s": angular_speed,
                "control_steps": self.steps, "gripper_opening": opening, "gripper_speed_s": gripper_speed}

    @staticmethod
    def description():
        return asdict(TargetSettings())
