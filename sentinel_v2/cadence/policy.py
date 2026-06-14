"""The live cadence policy (decisions/cadence_semantics.md §0, §9, §3; D29).
DETERMINISTIC, category-blind. Behind the v2 flag; flag-off is byte-identical to
Phase 1 (this module is imported only by v2 entry points).

Replaces the NoOp placeholder with the event-gated, work-at-risk-weighted cadence with
a guaranteed pre-completion sweep. NOT the withdrawn fixed-k flood (G15: up to 2,322
probe calls vs 107 worker calls). The policy plugs into the existing
sentinel_v2.scheduler.ProbeScheduler seam unchanged.
"""
from __future__ import annotations

from typing import Any, Mapping

from sentinel_v2.scheduler import CadencePolicy


class EventGatedCadence(CadencePolicy):
    """A sweep is due on an EVENT, never on a fixed call interval:

    - the guaranteed PRE-COMPLETION sweep (a barrier before output) — always due;
    - any barrier point (worker / shard / relation / global) — due;
    - an event-gated trigger: an un-re-observed HIGH-work-at-risk surface — due.

    Otherwise not due (quiet single-visit surfaces are funded by the speculative
    reserve, not a heartbeat). Deterministic in the context snapshot."""

    def due(self, context: Mapping[str, Any]) -> bool:
        if context.get("pre_completion"):
            return True
        if context.get("barrier"):
            return True
        if context.get("uncovered_high_risk"):
            return True
        return False


def make_cadence_policy(*, live: bool = True) -> CadencePolicy:
    """Select the cadence policy. `live=True` (the v2 default) returns the event-gated
    policy so the scheduler actually sweeps; `live=False` returns the NoOp placeholder.
    The flag-off path never calls this (it never imports the v2 cadence)."""
    if live:
        return EventGatedCadence()
    from sentinel_v2.scheduler import NoOpCadence
    return NoOpCadence()
