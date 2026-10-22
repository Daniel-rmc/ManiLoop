"""Reflector role: independent failure diagnosis, separate from the verifier."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .types import ReflectionResult, SubTask, VerifyResult
from .vlm import HarnessVLM, HarnessVLMError

REFLECT_INSTRUCTIONS = """You are the failure diagnostician of a robot manipulation system.
A subtask failed or timed out. Diagnose the likely cause and choose one
recovery:
- retry: same subtask again (transient miss, e.g. grasp slipped).
- adjust-param: same subtask with corrected skill_params (e.g. a wrong target
  description); put the corrections in parameter_updates.
- replan: the remaining plan is wrong or the scene changed; replace it.

You did not verify the failure yourself, so stay factual: what deviated, what
is the cheapest plausible fix. Reply with JSON only:
{"diagnosis": "...", "recovery": "retry|adjust-param|replan",
 "parameter_updates": {...}}."""


class Reflector(ABC):
    @abstractmethod
    def reflect(
        self, subtask: SubTask, verify: VerifyResult, context: dict
    ) -> ReflectionResult:
        raise NotImplementedError


class RuleReflector(Reflector):
    def reflect(
        self, subtask: SubTask, verify: VerifyResult, context: dict
    ) -> ReflectionResult:
        attempt = int(context.get("attempt", 1))
        if verify.completion == "timeout":
            return ReflectionResult(
                diagnosis="subtask exceeded its time budget without completion",
                recovery="replan" if attempt >= 2 else "retry",
            )
        if verify.source == "self_report":
            return ReflectionResult(
                diagnosis="executor reported it cannot make progress",
                recovery="replan" if attempt >= 2 else "retry",
            )
        return ReflectionResult(
            diagnosis=f"postcondition not satisfied ({verify.evidence[:120]})",
            recovery="retry" if attempt < 2 else "replan",
        )


class VLMReflector(Reflector):
    def __init__(self, vlm: HarnessVLM, fallback: Reflector | None = None):
        self.vlm = vlm
        self.fallback = fallback or RuleReflector()

    def reflect(
        self, subtask: SubTask, verify: VerifyResult, context: dict
    ) -> ReflectionResult:
        payload = {
            "subtask": {
                "instruction": subtask.instruction,
                "postconditions": subtask.postconditions,
                "skill_params": subtask.skill_params,
            },
            "verification": {
                "completion": verify.completion,
                "evidence": verify.evidence,
                "source": verify.source,
            },
            "memory": context,
        }
        try:
            data = self.vlm.query_json(REFLECT_INSTRUCTIONS, payload)
        except HarnessVLMError:
            return self.fallback.reflect(subtask, verify, context)
        recovery = data.get("recovery")
        if recovery not in ("retry", "adjust-param", "replan"):
            return self.fallback.reflect(subtask, verify, context)
        updates = data.get("parameter_updates")
        return ReflectionResult(
            diagnosis=str(data.get("diagnosis") or "no diagnosis")[:400],
            recovery=recovery,
            parameter_updates=updates if isinstance(updates, dict) else {},
        )
