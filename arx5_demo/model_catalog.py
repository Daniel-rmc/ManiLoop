"""Compatibility import; new code lives in maniloop.providers.catalog."""

import sys
from maniloop.providers import catalog as implementation

sys.modules[__name__] = implementation
