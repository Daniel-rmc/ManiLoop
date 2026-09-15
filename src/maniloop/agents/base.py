"""Agents receive sensor packets, not a MuJoCo environment or evaluator."""

from typing import Protocol
from maniloop.core.actions import ActionChunk


class Agent(Protocol):
    last_usage: dict
    last_latency: float

    def reset(self, seed: int = 0) -> None: ...
    def decide(
        self,
        task: str,
        observation: dict,
        images: dict[str, bytes],
        history: list[dict],
        geometry_results: list[dict],
    ) -> dict | ActionChunk: ...
