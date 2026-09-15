"""Compatibility import; new code lives in maniloop.simulation.environment."""

import sys
from maniloop.simulation import environment as implementation

sys.modules[__name__] = implementation
