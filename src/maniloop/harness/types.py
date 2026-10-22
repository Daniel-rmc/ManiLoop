"""Contracts for the layered harness: plan, verify, reflect, remember.

Abstracted from the Goal2Skill upper brain (robomme custom_high_level) and
trimmed to the portable core: no task-specific plan templates, no local model
backends, no oracle state. Every role reads the same memory through its own
minimal view.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Completion = Literal["success", "running", "fail", "timeout"]
RecoveryType = Literal["retry", "adjust-param", "replan"]
PhaseStatus = Literal["working", "done", "stuck"]

# Hard bounds that keep the slow loop from cycling forever.
DEFAULT_LIMITS = {
    "max_attempts_per_subtask": 3,
    "max_replans": 2,
    "max_rewinds": 1,
    # L0 progress gate: this many consecutive decide() calls without visible
    # motion marks the subtask stalled, no API call needed.
    "stall_window": 6,
    "stall_translation_m": 0.002,
    "stall_gripper_delta": 0.02,
}


@dataclass
class SubTask:
    """One semantic phase; granularity matches a visually checkable event."""

    subtask_id: str
    instruction: str
    postconditions: list[str] = field(default_factory=list)
    timeout_s: float = 120.0
    skill_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerifyResult:
    completion: Completion
    confidence: float
    evidence: str
    # False only when an already-completed phase was visibly undone again.
    prior_phase_intact: bool = True
    # rule | self_report | vlm -- where this verdict came from.
    source: str = "rule"


@dataclass
class ReflectionResult:
    diagnosis: str
    recovery: RecoveryType
    parameter_updates: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionRecord:
    subtask_id: str
    instruction: str
    action_kind: str
    explanation: str
    phase_status: str


@dataclass
class ErrorRecord:
    subtask_id: str
    attempt_idx: int
    completion: str
    diagnosis: str
    recovery: str


@dataclass
class MemoryState:
    current_goal: str = ""
    current_plan: list[SubTask] = field(default_factory=list)
    plan_index: int = 0
    completed_steps: list[str] = field(default_factory=list)
    episodic_history: list[ExecutionRecord] = field(default_factory=list)
    error_register: list[ErrorRecord] = field(default_factory=list)
    attempt_counter: dict[str, int] = field(default_factory=dict)
    evidence_chain: list[dict[str, Any]] = field(default_factory=list)
    replan_count: int = 0
    rewind_count: int = 0


@dataclass
class BridgeStepOutcome:
    verify: VerifyResult | None
    reflection: ReflectionResult | None
    episode_done: bool
    aborted: bool
    replanned: bool
    advanced: bool
    current_subtask: SubTask | None
    notice: str = ""
    # True whenever the active phase (re)starts with a fresh budget: advanced,
    # retried, adjusted, replanned or rewound. Only a plain "running" leaves
    # the phase clock untouched.
    phase_restarted: bool = False
