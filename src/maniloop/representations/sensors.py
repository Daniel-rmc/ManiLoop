"""Fail closed at the shared policy boundary; no privileged observation mode."""

from copy import deepcopy
from maniloop.core.observations import PUBLIC_OBSERVATION_FIELDS, guard_sensor_tree


class SensorRepresentation:
    name = "rgbd_proprio_v1"

    def encode(self, observation: dict) -> dict:
        unknown = set(observation) - PUBLIC_OBSERVATION_FIELDS
        if unknown:
            raise ValueError(f"Unexpected policy observation fields: {sorted(unknown)}")
        guard_sensor_tree(observation)
        return deepcopy(observation)
