"""Verifier role and the zero-cost L0 progress gate.

Verification is layered so the expensive VLM confirm (L2) runs only at a
claimed subtask boundary: L0 rules watch motion feedback every step for free,
L1 is the executor's own status line parsed from its reply, and L2 confirms a
claimed completion from the camera image.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import math

from .types import SubTask, VerifyResult
from .vlm import HarnessVLM, HarnessVLMError

VERIFY_INSTRUCTIONS = """You are the execution verifier of a robot manipulation system.
Judge ONLY from the camera image whether the current subtask is complete.
The executor claims it finished; confirm or reject that claim.

Rules:
- Check every postcondition against what is visible; name what you see.
- completion is "success" only if ALL postconditions are visibly satisfied.
- prior_phase_intact is false only if an earlier completed result (listed in
  memory) was visibly undone, e.g. a placed object fell or was dropped.
- Reply with JSON only: {"completion": "success|fail", "confidence": 0.0-1.0,
  "evidence": "what the image shows", "prior_phase_intact": true}."""


class ProgressGate:
    """L0: marks a subtask stalled after a window of motion-free decisions."""

    def __init__(
        self,
        window: int = 6,
        translation_m: float = 0.002,
        gripper_delta: float = 0.02,
    ):
        self.window = window
        self.translation_m = translation_m
        self.gripper_delta = gripper_delta
        self._motion: list[float] = []
        self._last_gripper: float | None = None

    def reset(self) -> None:
        self._motion = []
        self._last_gripper = None

    def update(self, observation: dict) -> None:
        feedback = observation.get("last_feedback")
        if not isinstance(feedback, dict) or feedback.get("status") not in (
            "accepted",
            "completed",
        ):
            return
        motion = 0.0
        delta = feedback.get("actual_delta_position")
        if isinstance(delta, (list, tuple)) and len(delta) == 3:
            try:
                motion += math.sqrt(sum(float(d) ** 2 for d in delta))
            except (TypeError, ValueError):
                pass
        gripper = feedback.get("gripper_opening")
        if type(gripper) in (int, float):
            if self._last_gripper is not None:
                motion += abs(float(gripper) - self._last_gripper)
            self._last_gripper = float(gripper)
        self._motion.append(motion)
        del self._motion[: -self.window]

    @property
    def stalled(self) -> bool:
        return (
            len(self._motion) >= self.window
            and max(self._motion) < self.translation_m + self.gripper_delta
        )


class Verifier(ABC):
    @abstractmethod
    def confirm(
        self, subtask: SubTask, images: dict[str, bytes], context: dict
    ) -> VerifyResult:
        raise NotImplementedError


class RuleVerifier(Verifier):
    """Degraded L2: trust the executor's claim, at low confidence."""

    def confirm(
        self, subtask: SubTask, images: dict[str, bytes], context: dict
    ) -> VerifyResult:
        del images, context
        return VerifyResult(
            completion="success",
            confidence=0.4,
            evidence="VLM 确认不可用，采信执行器自报完成",
            source="self_report",
        )


class VLMVerifier(Verifier):
    def __init__(self, vlm: HarnessVLM, fallback: Verifier | None = None):
        self.vlm = vlm
        self.fallback = fallback or RuleVerifier()

    def confirm(
        self, subtask: SubTask, images: dict[str, bytes], context: dict
    ) -> VerifyResult:
        try:
            data = self.vlm.query_json(
                VERIFY_INSTRUCTIONS,
                {
                    "subtask": {
                        "instruction": subtask.instruction,
                        "postconditions": subtask.postconditions,
                    },
                    "memory": context,
                },
                images=images,
            )
        except HarnessVLMError:
            return self.fallback.confirm(subtask, images, context)
        completion = data.get("completion")
        if completion not in ("success", "fail"):
            return self.fallback.confirm(subtask, images, context)
        try:
            confidence = min(max(float(data.get("confidence", 0.5)), 0.0), 1.0)
        except (TypeError, ValueError):
            confidence = 0.5
        return VerifyResult(
            completion=completion,
            confidence=confidence,
            evidence=str(data.get("evidence") or "")[:400],
            prior_phase_intact=data.get("prior_phase_intact") is not False,
            source="vlm",
        )
