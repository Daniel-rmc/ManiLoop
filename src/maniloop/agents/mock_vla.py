"""Offline action-chunk adapter test. This is not a trained VLA policy."""

from maniloop.core.actions import Action, ActionChunk


class MockVLAAgent:
    last_latency = 0.0
    last_usage = {}

    def __init__(self):
        self.reset()

    def reset(self, seed=0):
        self.calls = 0

    def decide(self, task, observation, images, history, geometry_results):
        self.calls += 1
        if self.calls > 1:
            return {
                "kind": "done",
                "observation_id": observation["observation_id"],
                "explanation": "Mock VLA adapter finished; no learned task capability claimed.",
            }
        if observation["action_limits"].get("native_action") == "osc_pose":
            return ActionChunk(
                observation["observation_id"],
                tuple(
                    Action(
                        "osc_pose", (0.0, 0.0, 0.1, 0.0, 0.0, 0.0, -1.0), frame="world"
                    )
                    for _ in range(2)
                ),
                interval_seconds=0.05,
            )
        q = tuple(observation["joint_positions"])
        names = tuple(observation["joint_names"])
        # Small encoder-relative targets validate dimensions, cadence and feedback.
        samples = tuple(
            Action("joint_position", (q[0] + offset, *q[1:]), joint_names=names)
            for offset in (0.003, 0.006)
        )
        return ActionChunk(observation["observation_id"], samples, interval_seconds=0.1)
