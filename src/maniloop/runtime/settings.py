"""Runtime limits shared by the workspace and CLI; no credentials or model calls."""
import math


DEFAULT_OBSERVATION_MAX_AGE_SECONDS = 60.0


def validate_observation_max_age(value):
    """Zero disables only the realtime wall-clock age limit, not snapshot identity."""
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("观测有效期必须为非负有限秒数；0 表示不限制时间")
    return float(value)


def effective_observation_max_age(timing, configured):
    """Controlled inference freezes physics, so waiting alone cannot age the scene."""
    if timing == "controlled" or configured == 0:
        return float("inf")
    return configured
