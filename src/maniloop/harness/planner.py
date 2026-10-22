"""Planner role: goal -> linear list of semantic subtasks, plus replanning."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .types import SubTask
from .vlm import HarnessVLM, HarnessVLMError

PLAN_INSTRUCTIONS = """You are the high-level planner of a robot manipulation system.
Decompose the goal into a short linear sequence of semantic subtasks.

Rules:
- Each subtask ends at a visually checkable state change (an object grasped,
  placed, a door opened), never at a low-level motion like "move 3 cm".
- 2 to 6 subtasks for typical tabletop tasks. Do not over-decompose.
- The executor is a vision-language policy that receives your instruction
  verbatim and controls the arm step by step; write instructions it can ground
  directly from camera images (name objects by color/shape/position).
- postconditions list what must be visibly true when the subtask completes;
  a verifier that only sees camera images will judge exactly these.
- timeout_s is the wall-clock budget for this subtask (60-300).
- Reply with JSON only: {"subtasks": [{"subtask_id": "s1", "instruction":
  "...", "postconditions": ["..."], "timeout_s": 120}]}."""

REPLAN_INSTRUCTIONS = """You are the high-level planner of a robot manipulation system.
The previous plan failed partway. The completed prefix is preserved; write a
REPLACEMENT SUFFIX for the remaining work only.

Rules:
- Do not repeat any completed instruction; the suffix continues from the
  current scene state shown in the images.
- Same granularity and output contract as an initial plan; subtask ids must be
  fresh (r1_s1, r1_s2, ...), 1 to 5 subtasks.
- Reply with JSON only: {"subtasks": [...]}."""


class Planner(ABC):
    @abstractmethod
    def plan(self, goal: str, scene: dict, context: dict) -> list[SubTask]:
        raise NotImplementedError

    def replan(self, goal: str, scene: dict, context: dict) -> list[SubTask]:
        return self.plan(goal, scene, context)


class SingleTaskPlanner(Planner):
    """Offline envelope: the whole goal as one subtask (degraded but safe)."""

    def plan(self, goal: str, scene: dict, context: dict) -> list[SubTask]:
        del scene, context
        return [
            SubTask(
                subtask_id="s1",
                instruction=goal,
                postconditions=["The goal is visibly achieved"],
                timeout_s=600.0,
            )
        ]


def _parse_subtasks(data: dict, *, id_prefix: str = "s") -> list[SubTask]:
    raw = data.get("subtasks")
    if not isinstance(raw, list):
        raise HarnessVLMError("planner: 响应缺少 subtasks 列表")
    subtasks: list[SubTask] = []
    for i, item in enumerate(raw[:8]):
        if not isinstance(item, dict):
            continue
        instruction = item.get("instruction")
        if not isinstance(instruction, str) or not instruction.strip():
            continue
        postconditions = item.get("postconditions")
        if not isinstance(postconditions, list):
            postconditions = [str(postconditions)] if postconditions else []
        try:
            timeout_s = float(item.get("timeout_s", 120.0))
        except (TypeError, ValueError):
            timeout_s = 120.0
        timeout_s = min(max(timeout_s, 30.0), 600.0)
        subtasks.append(
            SubTask(
                subtask_id=str(item.get("subtask_id") or f"{id_prefix}{i + 1}")[:40],
                instruction=instruction.strip()[:300],
                postconditions=[str(p)[:200] for p in postconditions[:4]],
                timeout_s=timeout_s,
            )
        )
    if not subtasks:
        raise HarnessVLMError("planner: 未解析出任何有效子任务")
    return subtasks


class VLMPlanner(Planner):
    def __init__(self, vlm: HarnessVLM, fallback: Planner | None = None):
        self.vlm = vlm
        self.fallback = fallback or SingleTaskPlanner()

    def plan(self, goal: str, scene: dict, context: dict) -> list[SubTask]:
        try:
            data = self.vlm.query_json(
                PLAN_INSTRUCTIONS, {"goal": goal, "scene": scene, "memory": context}
            )
            return _parse_subtasks(data)
        except HarnessVLMError:
            return self.fallback.plan(goal, scene, context)

    def replan(self, goal: str, scene: dict, context: dict) -> list[SubTask]:
        try:
            data = self.vlm.query_json(
                REPLAN_INSTRUCTIONS,
                {"goal": goal, "scene": scene, "memory": context},
            )
            return _parse_subtasks(data, id_prefix=f"r{context.get('replans_so_far', 0) + 1}_s")
        except HarnessVLMError:
            return self.fallback.plan(goal, scene, context)
