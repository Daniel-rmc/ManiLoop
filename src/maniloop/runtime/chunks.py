"""Execute short policy chunks at simulation-time sample boundaries."""

import numpy as np
import mujoco
from maniloop.core.actions import ActionChunk
from maniloop.controllers.geometry import rotation_matrix


class ChunkExecutor:
    def __init__(self, env, chunk: ActionChunk):
        chunk.validate()
        self.env, self.chunk = env, chunk
        self.index = 0
        self.next_time = float(env.data.time)
        self.completed = False

    def tick(self):
        env = self.env
        if self.completed or env.data.time + 1e-9 < self.next_time:
            return None
        if self.index == len(self.chunk.actions):
            self.completed = True
            env._settle_until = env.data.time + 0.25
            return {"status": "completed", "message": "动作块已执行，等待停稳"}
        action = self.chunk.actions[self.index]
        dt = self.chunk.interval_seconds
        try:
            if action.kind == "joint_position":
                if action.joint_names != tuple(env.config["joint_names"]):
                    raise ValueError("Chunk joint names/order do not match the robot")
                q = np.asarray(action.values)
            elif action.kind == "tcp_delta":
                if (
                    np.linalg.norm(action.values) > 0.06 * dt + 1e-9
                    or np.linalg.norm(action.rotation) > 0.5 * dt + 1e-9
                ):
                    raise ValueError("Chunk TCP sample exceeds controller speed limit")
                q = env.controller._ik(
                    env.tcp_position + np.array(action.values),
                    rotation_matrix(action.rotation) @ env.tcp_rotation,
                )
                if q is None:
                    raise ValueError("Chunk target IK did not converge")
            else:
                q = None
            if q is not None:
                if np.max(np.abs(q - env.data.qpos[env.qidx])) > 0.4 * dt + 1e-9:
                    raise ValueError(
                        "Chunk joint sample exceeds controller speed limit"
                    )
                for value, jid in zip(q, env.arm_joints):
                    lo, hi = env.model.jnt_range[jid]
                    if not lo <= value <= hi:
                        raise ValueError("Chunk target exceeds joint limits")
                env.scratch.qpos[:] = env.data.qpos
                env.scratch.qpos[env.qidx] = q
                mujoco.mj_forward(env.model, env.scratch)
                p = env.scratch.site_xpos[env.tcp]
                if np.any(p < env.workspace_min) or np.any(p > env.workspace_max):
                    raise ValueError("Chunk TCP target exceeds workspace")
                reason = env.controller._path_collision(q)
                if reason:
                    raise ValueError(reason)
                env.data.ctrl[env.arm_act] = q
            if action.gripper is not None:
                env.set_gripper(action.gripper)
            self.index += 1
            self.next_time += dt
            env.feedback = {
                "status": "accepted",
                "message": "动作块采样已执行",
                "sample": self.index,
                "simulation_time": float(env.data.time),
            }
        except (ValueError, TypeError) as exc:
            env.hold()
            self.completed = True
            env.feedback = {
                "status": "rejected",
                "message": str(exc),
                "sample": self.index + 1,
            }
        return dict(env.feedback)
