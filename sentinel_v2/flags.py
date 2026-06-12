"""v2 feature flag: off by default; nothing v2 runs unless explicitly enabled.

The flag is an environment variable so banked configs, the queue, and every
Phase 1 code path are untouched when it is absent — the night-shift
no-behavior-change guarantee. The 1b launch manifest will set it explicitly;
nothing reads it implicitly except the v2 entry points themselves.
"""
from __future__ import annotations

import os

ENV_VAR = "TRIPWIRE_V2"


def v2_enabled() -> bool:
    return os.environ.get(ENV_VAR, "") == "1"
