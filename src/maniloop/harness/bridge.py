"""Plan cursor state machine: advance, retry, rewind, or replan.

The bridge owns the slow-loop decision after each executed chunk: L0 rules
(timeout, stall) first, then the executor's L1 self-report, and only a claimed
completion triggers the L2 VLM confirm. Reflection is bounded by attempt,
replan and rewind budgets from the shared limits.
"""

from __future__ import annotations

from .memory import MemoryManager
from .planner import Planner
from .reflector import Reflector
from .types import (
    DEFAULT_LIMITS,
    BridgeStepOutcome,
    PhaseStatus,
    ReflectionResult,
    SubTask,
    VerifyResult,
)
from .verifier import ProgressGate, Verifier


class PlanBridge:
    def __init__(
        self,
        memory: MemoryManager,
        planner: Planner,
        verifier: Verifier,
        reflector: Reflector,
        limits: dict | None = None,
    ):
        self.memory = memory
        self.planner = planner
        self.verifier = verifier
        self.reflector = reflector
        self.limits = {**DEFAULT_LIMITS, **(limits or {})}
        self._pending_status: PhaseStatus = "working"
        self._pending_note = ""

    # ------------------------------------------------------------------ plan
    def set_plan(self, plan: list[SubTask]) -> None:
        self.memory.set_plan(plan)
        self._pending_status = "working"

    def current_subtask(self) -> SubTask | None:
        return self.memory.current_subtask()

    def progress_label(self) -> str:
        state = self.memory.state
        total = len(state.current_plan)
        return f"{min(state.plan_index + 1, total)}/{total}" if total else "0/0"

    def note_execution(self, subtask: SubTask, action: dict, phase_status: str) -> None:
        """L1: file the executor's self-report; judged on the next decide()."""
        if phase_status in ("working", "done", "stuck"):
            self._pending_status = phase_status
        else:
            self._pending_status = "working"
        self.memory.record_execution(
            subtask,
            str(action.get("kind", "?")),
            str(action.get("explanation", "")),
            self._pending_status,
        )

    # ---------------------------------------------------------------- review
    def review(
        self,
        *,
        observation: dict,
        images: dict[str, bytes],
        elapsed_s: float,
        gate: ProgressGate,
        scene: dict,
    ) -> BridgeStepOutcome:
        subtask = self.memory.current_subtask()
        if subtask is None:
            return self._outcome(None, None, episode_done=True, notice="计划已全部完成")

        verify = self._judge(subtask, images=images, elapsed_s=elapsed_s, gate=gate)
        if verify.completion == "running":
            return self._outcome(verify, None)

        attempt = self.memory.increment_attempt(subtask.subtask_id)
        self.memory.record_verification(subtask, verify, attempt=attempt)

        if verify.completion == "success":
            if not verify.prior_phase_intact:
                return self._rewind(verify)
            self.memory.advance()
            self._pending_status = "working"
            following = self.memory.current_subtask()
            return self._outcome(
                verify,
                None,
                advanced=True,
                episode_done=following is None,
                current=following,
                notice=f"子任务完成（{verify.source}）：{verify.evidence[:120]}",
                phase_restarted=True,
            )

        # fail / timeout -> independent reflection, bounded by budgets.
        reflection = self.reflector.reflect(
            subtask, verify, self.memory.export_for_reflector()
        )
        if (
            reflection.recovery == "retry"
            and attempt >= self.limits["max_attempts_per_subtask"]
        ):
            reflection = ReflectionResult(
                diagnosis=reflection.diagnosis + "；重试次数用尽",
                recovery="replan",
                parameter_updates=reflection.parameter_updates,
            )
        self.memory.record_error(subtask, verify, reflection, attempt)
        return self._recover(subtask, verify, reflection, scene)

    # ----------------------------------------------------------------- parts
    def _judge(
        self,
        subtask: SubTask,
        *,
        images: dict[str, bytes],
        elapsed_s: float,
        gate: ProgressGate,
    ) -> VerifyResult:
        """L0 rules -> L1 self-report -> L2 VLM confirm, cheapest first."""
        if elapsed_s > subtask.timeout_s:
            return VerifyResult(
                completion="timeout",
                confidence=1.0,
                evidence=f"子任务超时 {elapsed_s:.0f}s > 预算 {subtask.timeout_s:.0f}s",
                source="rule",
            )
        if gate.stalled:
            return VerifyResult(
                completion="fail",
                confidence=0.6,
                evidence=f"连续 {self.limits['stall_window']} 次决策无可见运动进展",
                source="rule",
            )
        status = self._pending_status
        self._pending_status = "working"
        if status == "working":
            return VerifyResult(
                completion="running", confidence=1.0, evidence="执行器仍在推进", source="self_report"
            )
        if status == "stuck":
            return VerifyResult(
                completion="fail",
                confidence=0.7,
                evidence="执行器报告当前子任务无法继续",
                source="self_report",
            )
        # status == "done": the only moment that spends an L2 VLM confirm.
        return self.verifier.confirm(
            subtask, images, self.memory.export_for_verifier()
        )

    def _rewind(self, verify: VerifyResult) -> BridgeStepOutcome:
        if self.memory.state.rewind_count >= self.limits["max_rewinds"]:
            return self._outcome(
                verify,
                None,
                aborted=True,
                notice="先前阶段被推翻且回退次数已用尽，中止",
            )
        self.memory.revoke_last()
        self._pending_status = "working"
        return self._outcome(
            verify,
            None,
            current=self.memory.current_subtask(),
            notice=f"先前阶段被视觉证据推翻，回退重做：{verify.evidence[:120]}",
            phase_restarted=True,
        )

    def _recover(
        self,
        subtask: SubTask,
        verify: VerifyResult,
        reflection: ReflectionResult,
        scene: dict,
    ) -> BridgeStepOutcome:
        if reflection.recovery in ("retry", "adjust-param"):
            if reflection.recovery == "adjust-param" and reflection.parameter_updates:
                subtask.skill_params.update(reflection.parameter_updates)
            self._pending_status = "working"
            return self._outcome(
                verify,
                reflection,
                current=subtask,
                notice=f"{reflection.recovery}：{reflection.diagnosis[:120]}",
                phase_restarted=True,
            )
        # replan
        state = self.memory.state
        if state.replan_count >= self.limits["max_replans"]:
            return self._outcome(
                verify,
                reflection,
                aborted=True,
                notice=f"重规划次数已用尽，中止：{reflection.diagnosis[:120]}",
            )
        suffix = self.planner.replan(
            state.current_goal, scene, self.memory.export_for_planner()
        )
        state.replan_count += 1
        self.memory.set_plan(suffix, keep_prefix=True)
        self._pending_status = "working"
        return self._outcome(
            verify,
            reflection,
            replanned=True,
            current=self.memory.current_subtask(),
            notice=f"已重规划剩余步骤：{reflection.diagnosis[:120]}",
            phase_restarted=True,
        )

    def _outcome(
        self,
        verify: VerifyResult | None,
        reflection: ReflectionResult | None,
        *,
        episode_done: bool = False,
        aborted: bool = False,
        replanned: bool = False,
        advanced: bool = False,
        current: SubTask | None = None,
        notice: str = "",
        phase_restarted: bool = False,
    ) -> BridgeStepOutcome:
        if current is None and not (episode_done or aborted):
            current = self.memory.current_subtask()
        return BridgeStepOutcome(
            verify=verify,
            reflection=reflection,
            episode_done=episode_done,
            aborted=aborted,
            replanned=replanned,
            advanced=advanced,
            current_subtask=current,
            notice=notice,
            phase_restarted=phase_restarted,
        )
