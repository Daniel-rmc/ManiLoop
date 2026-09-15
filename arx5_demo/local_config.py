"""Compatibility import; new code lives in maniloop.providers.credentials."""

import sys
from maniloop.providers import credentials as implementation

sys.modules[__name__] = implementation
