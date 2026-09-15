"""Task lifecycle and privileged scoring, never provided to a policy."""

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class TabletopLayout:
    name: str
    object_position: tuple[float, float, float]
    target_position: tuple[float, float, float]


LAYOUTS = {
    "tabletop_a": TabletopLayout("tabletop_a", (0.30, -0.06, 0.015), (0.31, 0.10, 0)),
    "tabletop_b": TabletopLayout("tabletop_b", (0.34, 0.04, 0.015), (0.30, -0.12, 0)),
}


class ManipulationTask:
    def __init__(self, name: str, layout: TabletopLayout):
        if name not in ("pick_place", "push"):
            raise ValueError("Unknown task")
        self.name = name
        self.layout = layout
        self.reset()

    @property
    def instruction(self):
        return (
            "把红色方块抓起来，放到绿色目标区域，再松开夹爪。"
            if self.name == "pick_place"
            else "沿桌面推动红色方块到绿色目标区域，不要把方块抬离桌面，完成后让夹爪离开方块。"
        )

    def reset(self):
        self.since = None
        self.lifted = False
        self.invalid_lift = False
        self.result = {
            "success": False,
            "in_target": False,
            "stable": False,
            "released": False,
            "task": self.name,
        }

    def update(self, env):
        # Only the evaluator accesses object pose/velocity. Policies receive no result.
        obj = env.model.body("red_cube").id
        pos = env.data.xpos[obj]
        gid = env.model.geom("red_cube_geom").id
        extent = np.abs(env.data.xmat[obj].reshape(3, 3)) @ env.model.geom_size[gid]
        in_region = bool(
            np.all(
                np.abs(pos[:2] - np.array(self.layout.target_position[:2])) + extent[:2]
                < 0.045
            )
        )
        dof = env.model.jnt_dofadr[env.model.joint("cube_free").id]
        stable = bool(np.linalg.norm(env.data.qvel[dof : dof + 6]) < 0.035)
        supported = bool(abs(pos[2] - extent[2]) < 0.005)
        self.lifted |= bool(pos[2] > 0.065)
        self.invalid_lift |= bool(pos[2] - extent[2] > 0.015)
        away = bool(np.linalg.norm(pos - env.tcp_position) > 0.055)
        released = away and (
            env.gripper_opening > 0.65 if self.name == "pick_place" else True
        )
        task_condition = (
            self.lifted if self.name == "pick_place" else not self.invalid_lift
        )
        candidate = in_region and stable and supported and released and task_condition
        if candidate and self.since is None:
            self.since = float(env.data.time)
        if not candidate:
            self.since = None
        success = bool(self.since is not None and env.data.time - self.since >= 1.0)
        self.result = {
            "success": success,
            "in_target": in_region,
            "stable": stable,
            "released": released,
            "task": self.name,
            "lifted": self.lifted,
            "invalid_lift": self.invalid_lift if self.name == "push" else False,
            "criterion": "目标区域内稳定1秒；抓放须先抬起再释放，推物不得抬离桌面",
        }

    def evaluate(self):
        return dict(self.result)
