"""Convert human TCP jogs into the existing fixed-frame pose contract.

This adapter uses only current robot proprioception. It does not change the
policy action protocol, select joint targets, or access task/object state.
"""
from copy import deepcopy
import math
import numpy as np


def _vector(value, name):
    if (not isinstance(value, (list, tuple)) or len(value) != 3
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError(f"{name} 必须是三个有限数值")
    return np.asarray(value, dtype=float)


def prepare_manual_move(payload: dict, observation: dict) -> dict:
    """Capture the tool frame once, then delegate to the unchanged controller."""
    action = deepcopy(payload)
    reference = action.pop("reference_frame", "fixed")
    if reference not in ("fixed", "tool"):
        raise ValueError("手动参考系必须是 fixed 或 tool")
    frame = observation.get("frame_id")
    if frame not in ("world", "base"):
        raise ValueError("当前后端没有声明可用的固定坐标系")
    if action.get("frame", frame) != frame:
        raise ValueError("动作 frame 必须与后端一致；末端轴请使用 reference_frame=tool")
    position = _vector(action.get("delta_position", [0, 0, 0]), "平移增量")
    rotation = _vector(action.get("delta_rotation", [0, 0, 0]), "旋转向量")
    if reference == "tool":
        matrix = np.asarray(observation.get("tcp_rotation_matrix"), dtype=float)
        if (matrix.shape != (3, 3) or not np.isfinite(matrix).all()
                or not np.allclose(matrix.T @ matrix, np.eye(3), atol=1e-5)
                or not math.isclose(float(np.linalg.det(matrix)), 1.0, abs_tol=1e-5)):
            raise ValueError("当前 TCP 姿态无效，不能转换末端坐标轴")
        # Exp(R v) R = R Exp(v): right-multiplying a tool-frame rotation
        # is exactly equivalent to the fixed-frame vector passed downstream.
        position, rotation = matrix @ position, matrix @ rotation
    limits = observation.get("action_limits", {})
    for vector, key, label in ((position, "translation_max_m", "平移"),
                               (rotation, "rotation_max_rad", "旋转")):
        limit = limits.get(key)
        if type(limit) not in (int, float) or not math.isfinite(limit) or limit <= 0:
            raise ValueError(f"当前后端未声明有效的{label}步长上限")
        if np.linalg.norm(vector) > limit + 1e-9:
            raise ValueError(f"{label}增量超过当前后端单步上限；请减小增量")
    action.update(kind="move", frame=frame,
                  delta_position=position.tolist(), delta_rotation=rotation.tolist())
    return action


def manual_control_steps(seconds, timestep):
    """Manual-only target budget; it never changes the model action budget."""
    if (type(seconds) not in (int, float) or not math.isfinite(seconds)
            or not .05 <= seconds <= 10):
        raise ValueError("手动目标跟踪时限须为 0.05 至 10 秒")
    if type(timestep) not in (int, float) or not math.isfinite(timestep) or timestep <= 0:
        raise ValueError("后端控制步长无效")
    return max(1, math.ceil(seconds / timestep - 1e-9))
