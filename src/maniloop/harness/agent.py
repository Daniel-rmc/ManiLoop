"""HarnessAgent: the layered upper brain as a standard ManiLoop agent.

Wraps any executor implementing the Agent protocol (today: the cloud LLM
agent). The slow loop plans the goal into semantic subtasks, gates progress
with L0 motion rules and the executor's L1 self-report, confirms claimed
completions with an L2 VLM check, and recovers through bounded reflection.
The runner only sees decide() -> action, so no runner loop changes are needed.
"""

from __future__ import annotations

import re
import time

from .bridge import PlanBridge
from .memory import MemoryManager
from .planner import SingleTaskPlanner, VLMPlanner
from .reflector import RuleReflector, VLMReflector
from .router import RoleRouter
from .types import DEFAULT_LIMITS
from .verifier import ProgressGate, RuleVerifier, VLMVerifier
from .vlm import HarnessVLM

_PHASE_RE = re.compile(r"PHASE:\s*(working|done|stuck)", re.IGNORECASE)


def _scene_summary(observation: dict) -> dict:
    return {
        "tcp_position": observation.get("tcp_position"),
        "gripper_opening": observation.get("gripper_opening"),
        "cameras": list((observation.get("cameras") or {}).keys())
        if isinstance(observation.get("cameras"), dict)
        else observation.get("cameras"),
        "robot_description": str(observation.get("robot_description") or "")[:400],
        "action_limits": observation.get("action_limits"),
    }


def _subtask_prompt(subtask, goal: str, progress: str) -> str:
    postconditions = "; ".join(subtask.postconditions) or subtask.instruction
    prompt = (
        f"{subtask.instruction}\n\n"
        f"[Harness protocol] Overall goal: {goal}\n"
        f"This is subtask {progress} decomposed from the goal; complete ONLY "
        f"this subtask, then stop moving.\n"
        f"Done when ALL hold: {postconditions}.\n"
        f"End your explanation with exactly one status line:\n"
        f"PHASE: working | done | stuck\n"
        f"- working: still executing this subtask\n"
        f"- done: the postconditions are visibly satisfied\n"
        f"- stuck: you cannot make progress toward them"
    )
    if subtask.skill_params:
        import json

        prompt += f"\nParameters: {json.dumps(subtask.skill_params, ensure_ascii=False)}"
    return prompt


def _split_phase_status(explanation: str) -> tuple[str, str]:
    match = _PHASE_RE.search(explanation or "")
    if not match:
        return "working", explanation
    cleaned = (explanation[: match.start()] + explanation[match.end() :]).strip()
    return match.group(1).lower(), cleaned


class HarnessAgent:
    def __init__(self, executor, *, roles: dict | None = None, limits: dict | None = None):
        self.executor = executor
        provider = executor.provider  # LLMAgent -> GPTPolicy (owns client+model)
        self.router = RoleRouter(provider.model, roles)
        self.limits = {**DEFAULT_LIMITS, **(limits or {})}
        self._vlms = {
            role: HarnessVLM(provider.client, self.router.model_for(role))
            for role in ("planner", "verifier", "reflector")
        }
        planner = VLMPlanner(self._vlms["planner"], fallback=SingleTaskPlanner())
        verifier = VLMVerifier(self._vlms["verifier"], fallback=RuleVerifier())
        reflector = VLMReflector(self._vlms["reflector"], fallback=RuleReflector())
        self._roles = (planner, verifier, reflector)
        self.memory = MemoryManager()
        self.bridge = PlanBridge(self.memory, planner, verifier, reflector, self.limits)
        self.gate = ProgressGate(
            window=int(self.limits["stall_window"]),
            translation_m=float(self.limits["stall_translation_m"]),
            gripper_delta=float(self.limits["stall_gripper_delta"]),
        )
        self._planned = False
        self._phase_started = 0.0
        self.last_usage: dict = {}
        self.last_latency = 0.0
        self.last_decision: dict | None = None

    # ------------------------------------------------------ Agent protocol
    @property
    def request_options(self):
        return self.executor.request_options

    @property
    def last_response_id(self):
        return self.executor.last_response_id

    def reset(self, seed: int = 0) -> None:
        self.executor.reset(seed)
        self.memory = MemoryManager()
        planner, verifier, reflector = self._roles
        self.bridge = PlanBridge(self.memory, planner, verifier, reflector, self.limits)
        self.gate.reset()
        self._planned = False
        self._phase_started = 0.0
        self.last_usage = {}
        self.last_latency = 0.0
        self.last_decision = None

    def decide(self, task, observation, images, history, geometry_results):
        started = time.monotonic()
        try:
            if not self._planned:
                self.memory.begin(task)
                plan = self.bridge.planner.plan(
                    task, _scene_summary(observation), self.memory.export_for_planner()
                )
                self.bridge.set_plan(plan)
                self._planned = True
                self._phase_started = started
            else:
                outcome = self.bridge.review(
                    observation=observation,
                    images=images,
                    elapsed_s=started - self._phase_started,
                    gate=self.gate,
                    scene=_scene_summary(observation),
                )
                if outcome.phase_restarted:
                    self._phase_started = started
                    self.gate.reset()
                if outcome.episode_done or outcome.aborted:
                    return self._terminal_action(
                        observation,
                        outcome.notice or "分层控制结束",
                    )
            subtask = self.bridge.current_subtask()
            if subtask is None:
                return self._terminal_action(observation, "计划已全部完成")
            action = self.executor.decide(
                _subtask_prompt(subtask, task, self.bridge.progress_label()),
                observation,
                images,
                history,
                geometry_results,
            )
            status, explanation = _split_phase_status(str(action.get("explanation", "")))
            action["explanation"] = (
                f"[Harness {self.bridge.progress_label()} · {subtask.instruction[:40]}] "
                f"{explanation}"
            )
            self.bridge.note_execution(subtask, action, status)
            self.gate.update(observation)
            return action
        finally:
            self.last_latency = time.monotonic() - started
            self.last_usage = self._merged_usage()
            self.last_decision = self.memory.snapshot()

    def close(self) -> None:
        # The role VLMs share the executor's client; closing the executor
        # closes the transport for everyone. Mirror the runner's close_policy
        # fallback: not every executor exposes close() itself.
        close = getattr(self.executor, "close", None)
        if callable(close):
            close()
            return
        client = getattr(self.executor, "client", None)
        if client is not None:
            client.close()

    # ----------------------------------------------------------------- parts
    def _terminal_action(self, observation: dict, message: str) -> dict:
        gripper = observation.get("gripper_opening")
        return {
            "observation_id": observation["observation_id"],
            "kind": "done",
            "delta_position": [0.0, 0.0, 0.0],
            "delta_rotation": [0.0, 0.0, 0.0],
            "gripper_opening": float(gripper) if type(gripper) in (int, float) else 1.0,
            "pixel": [0, 0],
            "camera": "",
            "explanation": f"[Harness] {message}",
        }

    def _merged_usage(self) -> dict:
        merged: dict[str, int] = {}
        sources = [self.executor.last_usage] + [vlm.last_usage for vlm in self._vlms.values()]
        for usage in sources:
            for key, count in (usage or {}).items():
                if type(count) is int:
                    merged[key] = merged.get(key, 0) + count
        return merged
