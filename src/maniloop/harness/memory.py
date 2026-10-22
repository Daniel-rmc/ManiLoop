"""Episode memory for the harness: one fact source, per-role minimal views."""

from __future__ import annotations

from .types import (
    ErrorRecord,
    ExecutionRecord,
    MemoryState,
    ReflectionResult,
    SubTask,
    VerifyResult,
)


class MemoryManager:
    def __init__(self, history_window: int = 12):
        self.state = MemoryState()
        self.history_window = history_window

    def begin(self, goal: str) -> None:
        self.state.current_goal = goal

    def set_plan(self, plan: list[SubTask], *, keep_prefix: bool = False) -> None:
        if keep_prefix:
            prefix = self.state.current_plan[: self.state.plan_index]
            taken = {s.subtask_id for s in prefix}
            suffix = []
            for item in plan:
                # Attempt counters key on subtask_id, so suffix ids must not
                # collide with the preserved prefix (fallback planners reuse
                # plain ids like "s1").
                base, serial, candidate = item.subtask_id, 2, item.subtask_id
                while candidate in taken:
                    candidate = f"{base}~{serial}"
                    serial += 1
                if candidate != item.subtask_id:
                    item = SubTask(
                        subtask_id=candidate,
                        instruction=item.instruction,
                        postconditions=item.postconditions,
                        timeout_s=item.timeout_s,
                        skill_params=item.skill_params,
                    )
                taken.add(candidate)
                suffix.append(item)
            self.state.current_plan = prefix + suffix
        else:
            self.state.current_plan = list(plan)
            self.state.plan_index = 0
            self.state.completed_steps = []

    def current_subtask(self) -> SubTask | None:
        plan = self.state.current_plan
        if 0 <= self.state.plan_index < len(plan):
            return plan[self.state.plan_index]
        return None

    def advance(self) -> SubTask | None:
        current = self.current_subtask()
        if current is not None:
            self.state.completed_steps.append(current.subtask_id)
            self.state.attempt_counter.pop(current.subtask_id, None)
        self.state.plan_index += 1
        return self.current_subtask()

    def revoke_last(self) -> None:
        """Rewind the cursor one phase; the revoked phase must be redone."""
        if self.state.completed_steps:
            self.state.completed_steps.pop()
        self.state.plan_index = max(0, self.state.plan_index - 1)
        self.state.rewind_count += 1

    def increment_attempt(self, subtask_id: str) -> int:
        count = self.state.attempt_counter.get(subtask_id, 0) + 1
        self.state.attempt_counter[subtask_id] = count
        return count

    def attempts(self, subtask_id: str) -> int:
        return self.state.attempt_counter.get(subtask_id, 0)

    def record_execution(
        self, subtask: SubTask, action_kind: str, explanation: str, phase_status: str
    ) -> None:
        self.state.episodic_history.append(
            ExecutionRecord(
                subtask_id=subtask.subtask_id,
                instruction=subtask.instruction,
                action_kind=action_kind,
                explanation=explanation[:400],
                phase_status=phase_status,
            )
        )
        del self.state.episodic_history[: -self.history_window]

    def record_verification(
        self, subtask: SubTask, verify: VerifyResult, *, attempt: int
    ) -> None:
        self.state.evidence_chain.append(
            {
                "subtask_id": subtask.subtask_id,
                "attempt": attempt,
                "completion": verify.completion,
                "confidence": round(verify.confidence, 3),
                "source": verify.source,
                "evidence": verify.evidence[:400],
            }
        )

    def record_error(
        self, subtask: SubTask, verify: VerifyResult, reflection: ReflectionResult, attempt: int
    ) -> None:
        self.state.error_register.append(
            ErrorRecord(
                subtask_id=subtask.subtask_id,
                attempt_idx=attempt,
                completion=verify.completion,
                diagnosis=reflection.diagnosis[:400],
                recovery=reflection.recovery,
            )
        )

    def export_for_planner(self) -> dict:
        state = self.state
        return {
            "goal": state.current_goal,
            "completed": [
                {"id": s.subtask_id, "instruction": s.instruction}
                for s in state.current_plan[: state.plan_index]
            ],
            "recent_errors": [vars(e) for e in state.error_register[-4:]],
            "recent_history": [vars(r) for r in state.episodic_history[-6:]],
            "replans_so_far": state.replan_count,
        }

    def export_for_verifier(self) -> dict:
        state = self.state
        current = self.current_subtask()
        return {
            "goal": state.current_goal,
            "current_subtask": (
                {
                    "id": current.subtask_id,
                    "instruction": current.instruction,
                    "postconditions": current.postconditions,
                }
                if current
                else None
            ),
            "completed_instructions": [
                s.instruction for s in state.current_plan[: state.plan_index]
            ],
            "attempt": self.attempts(current.subtask_id) if current else 0,
        }

    def export_for_reflector(self) -> dict:
        state = self.state
        current = self.current_subtask()
        return {
            "goal": state.current_goal,
            "current_subtask": (
                {
                    "id": current.subtask_id,
                    "instruction": current.instruction,
                    "postconditions": current.postconditions,
                    "skill_params": current.skill_params,
                }
                if current
                else None
            ),
            "attempt": self.attempts(current.subtask_id) if current else 0,
            "recent_errors": [vars(e) for e in state.error_register[-4:]],
            "remaining_instructions": [
                s.instruction for s in state.current_plan[state.plan_index + 1 :]
            ],
            "replans_so_far": state.replan_count,
        }

    def snapshot(self) -> dict:
        state = self.state
        current = self.current_subtask()
        return {
            "goal": state.current_goal,
            "plan": [
                {
                    "id": s.subtask_id,
                    "instruction": s.instruction,
                    "status": (
                        "done"
                        if i < state.plan_index
                        else "active" if i == state.plan_index else "pending"
                    ),
                }
                for i, s in enumerate(state.current_plan)
            ],
            "current": current.subtask_id if current else None,
            "replans": state.replan_count,
            "rewinds": state.rewind_count,
            "errors": len(state.error_register),
            "evidence": state.evidence_chain[-6:],
        }
