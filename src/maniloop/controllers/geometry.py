import math
import numpy as np
import mujoco


def rotation_vector(matrix):
    quat = np.zeros(4)
    mujoco.mju_mat2Quat(quat, np.asarray(matrix).reshape(9))
    if quat[0] < 0:
        quat *= -1
    length = np.linalg.norm(quat[1:])
    return (
        np.zeros(3)
        if length < 1e-10
        else quat[1:] / length * (2 * math.atan2(length, quat[0]))
    )


def rotation_matrix(vector):
    vector = np.asarray(vector, dtype=float)
    theta = np.linalg.norm(vector)
    if theta < 1e-10:
        return np.eye(3)
    quat = np.r_[math.cos(theta / 2), vector / theta * math.sin(theta / 2)]
    result = np.zeros(9)
    mujoco.mju_quat2Mat(result, quat)
    return result.reshape(3, 3)
