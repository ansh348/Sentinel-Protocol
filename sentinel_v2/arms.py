"""Phase 1b arm designations (pre-commitment P3; prereg_1b.md §1 item 2).

The two-tier (no-judge) configuration is the designated PRIMARY arm; the
rebuilt-judge configuration is EXPLORATORY only; no post-selection — the
confirmatory claim attaches to the two-tier arm regardless of outcomes.

System-id strings are PROVISIONAL (flagged in the night-shift report for
author confirmation): they appear nowhere outside this module tonight —
deliberately NOT registered in conductor.systems.SYSTEMS, so no run can be
launched against them until the author wires the arms in the morning
sessions.
"""
from __future__ import annotations

from sentinel_v2.flags import v2_enabled

# PROVISIONAL ids, pending author confirmation at arm wiring time.
TWO_TIER = "V2"
REBUILT_JUDGE = "V2J"

# P3, in ink before any battery result: primary is fixed here, not chosen later.
PRIMARY_ARM = TWO_TIER
EXPLORATORY_ARMS = (REBUILT_JUDGE,)


def resolve_arm(arm_id: str):
    """Stub wiring point for the 1b launch manifest. Raises by design:
    the arm implementations are judgment-layer work (corroboration wiring,
    cadence semantics, judge logic) and are NOT built by the night shift."""
    if not v2_enabled():
        raise RuntimeError(
            "sentinel_v2 is feature-flagged off (set TRIPWIRE_V2=1); with the "
            "flag off no v2 code path may execute")
    if arm_id not in (TWO_TIER, REBUILT_JUDGE):
        raise KeyError(f"unknown v2 arm: {arm_id!r}")
    raise NotImplementedError(
        f"v2 arm {arm_id!r} is scaffolding only: the interrupt-policy and "
        "cadence layers are judgment work reserved for sessions with the "
        "author present (night-shift hard stop)")
