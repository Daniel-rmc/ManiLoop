"""Bounded position controller: IK, joint limits and known-fixture collision checks."""

import numpy as np
import mujoco
from .geometry import rotation_matrix, rotation_vector


class PositionController:
    def __init__(self, environment):
        self.env = environment

    def _ik(self, position, rotation):
        self.env.scratch.qpos[:] = self.env.data.qpos
        q = self.env.data.qpos[self.env.qidx].copy()
        jacp = np.zeros((3, self.env.model.nv))
        jacr = np.zeros((3, self.env.model.nv))
        for _ in range(160):
            self.env.scratch.qpos[self.env.qidx] = q
            mujoco.mj_forward(self.env.model, self.env.scratch)
            current = self.env.scratch.site_xmat[self.env.tcp].reshape(3, 3)
            ep = position - self.env.scratch.site_xpos[self.env.tcp]
            er = rotation_vector(rotation @ current.T)
            if np.linalg.norm(ep) < 0.0015 and np.linalg.norm(er) < 0.035:
                return q
            mujoco.mj_jacSite(
                self.env.model, self.env.scratch, jacp, jacr, self.env.tcp
            )
            jac = np.vstack((jacp[:, self.env.didx], 0.25 * jacr[:, self.env.didx]))
            error = np.r_[ep, 0.25 * er]
            dq = jac.T @ np.linalg.solve(jac @ jac.T + 0.00008 * np.eye(6), error)
            dq = np.clip(dq, -0.12, 0.12)
            q += dq
            for j, jid in enumerate(self.env.arm_joints):
                if self.env.model.jnt_limited[jid]:
                    lo, hi = self.env.model.jnt_range[jid]
                    q[j] = np.clip(q[j], lo + 0.005, hi - 0.005)
        return None

    def _path_collision(self, target_q):
        # Known fixture/self checks only; no object pose is read or supplied to policy.
        static_names = self.env.config.get("protected_geoms", ["table", "floor"])
        protected = {
            self.env.model.geom(name).id
            for name in static_names
            if mujoco.mj_name2id(self.env.model, mujoco.mjtObj.mjOBJ_GEOM, name) >= 0
        }
        robot_bodies = set()
        root = self.env.model.body(self.env.config.get("base_body", "base_link")).id
        for bid in range(1, self.env.model.nbody):
            parent = bid
            while parent > 0:
                if parent == root:
                    robot_bodies.add(bid)
                    break
                parent = self.env.model.body_parentid[parent]
        self.env.scratch.qpos[:] = self.env.data.qpos
        for f in np.linspace(0.05, 1, 20):
            self.env.scratch.qpos[self.env.qidx] = self.env.data.qpos[
                self.env.qidx
            ] + f * (target_q - self.env.data.qpos[self.env.qidx])
            mujoco.mj_forward(self.env.model, self.env.scratch)
            for c in self.env.scratch.contact:
                b1, b2 = (
                    self.env.model.geom_bodyid[c.geom1],
                    self.env.model.geom_bodyid[c.geom2],
                )
                if c.dist < -0.0015 and (
                    (b1 in robot_bodies and b1 != root and c.geom2 in protected)
                    or (b2 in robot_bodies and b2 != root and c.geom1 in protected)
                ):
                    return "预测轨迹会与已知桌面或地面碰撞"
                if (
                    c.dist < -0.003
                    and b1 in robot_bodies
                    and b2 in robot_bodies
                    and b1 != b2
                ):
                    if (
                        self.env.model.body_parentid[b1] != b2
                        and self.env.model.body_parentid[b2] != b1
                    ):
                        return "预测轨迹存在机械臂自碰撞"
        return None

    def execute(self, action):
        kind = action.get("kind", "move")
        if self.env.busy:
            return {"status": "rejected", "message": "上一个动作仍在执行"}
        try:
            p = np.asarray(action.get("delta_position", [0, 0, 0]), dtype=float)
            r = np.asarray(action.get("delta_rotation", [0, 0, 0]), dtype=float)
            opening = float(action.get("gripper_opening", self.env.gripper_opening))
            if (
                p.shape != (3,)
                or r.shape != (3,)
                or not np.all(np.isfinite(np.r_[p, r, opening]))
            ):
                raise ValueError("动作包含无效数值")
            if not 0 <= opening <= 1:
                raise ValueError("夹爪开度必须在0至1之间")
            if (
                np.linalg.norm(p) > self.env.translation_limit + 1e-9
                or np.linalg.norm(r) > self.env.rotation_limit + 1e-9
            ):
                raise ValueError("动作超过单步位移或旋转上限")
            if kind not in ["move", "joint_position", "gripper", "wait"]:
                raise ValueError("不支持的执行动作")
            if kind == "gripper":
                self.env.set_gripper(opening)
                self.env._settle_until = self.env.data.time + 0.65
            elif kind == "wait":
                self.env._settle_until = self.env.data.time + 0.4
            else:
                if kind == "joint_position":
                    if tuple(action.get("joint_names", ())) != tuple(
                        self.env.config["joint_names"]
                    ):
                        raise ValueError("关节名称或顺序与当前机器人不符")
                    target_q = np.asarray(
                        action.get("joint_positions", []), dtype=float
                    )
                    if target_q.shape != self.env.qidx.shape or not np.all(
                        np.isfinite(target_q)
                    ):
                        raise ValueError("关节目标维度或数值无效")
                    for value, jid in zip(target_q, self.env.arm_joints):
                        lo, hi = self.env.model.jnt_range[jid]
                        if not lo <= value <= hi:
                            raise ValueError("关节目标超出限位")
                    self.env.scratch.qpos[:] = self.env.data.qpos
                    self.env.scratch.qpos[self.env.qidx] = target_q
                    mujoco.mj_forward(self.env.model, self.env.scratch)
                    position = self.env.scratch.site_xpos[self.env.tcp].copy()
                else:
                    position = self.env.tcp_position + p
                    target_q = self._ik(
                        position, rotation_matrix(r) @ self.env.tcp_rotation
                    )
                    if target_q is None:
                        raise ValueError("该末端目标在当前姿态下不可达（IK未收敛）")
                if np.any(position < self.env.workspace_min) or np.any(
                    position > self.env.workspace_max
                ):
                    raise ValueError("目标末端位置超出工作空间")
                reason = self._path_collision(target_q)
                if reason:
                    raise ValueError(reason)
                duration = max(
                    0.45,
                    float(np.max(np.abs(target_q - self.env.data.qpos[self.env.qidx])))
                    / 0.4,
                    float(np.linalg.norm(p)) / 0.06,
                    float(np.linalg.norm(r)) / 0.5,
                )
                self.env.trajectory = {
                    "q0": self.env.data.qpos[self.env.qidx].copy(),
                    "q1": target_q,
                    "target": position,
                    "start": float(self.env.data.time),
                    "duration": duration,
                }
            if kind == "joint_position" and "gripper_opening" in action:
                self.env.set_gripper(opening)
            self.env.feedback = {
                "status": "accepted",
                "message": "动作已接受",
                "kind": kind,
            }
        except (ValueError, TypeError) as exc:
            self.env.feedback = {"status": "rejected", "message": str(exc)}
        return dict(self.env.feedback)
