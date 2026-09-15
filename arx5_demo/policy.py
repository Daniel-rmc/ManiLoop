"""Compatibility import; new code lives in maniloop.providers.responses."""

import sys
from maniloop.providers import responses as implementation

sys.modules[__name__] = implementation
