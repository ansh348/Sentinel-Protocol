"""Probe-primary corroboration: persistence over time (design v0.4 §2.2; author
ruling D28).

DETERMINISTIC — no LLM on this path. The typing engine
(`sentinel_v2.typing_engine`) types a SINGLE observation; this layer decides, over
an ORDERED SEQUENCE of observations of one surface, whether an AMBIGUOUS signal
(non-status-coded shapeless drift the engine returned as telemetry) earns a route
to the orchestrator.

Corroboration = PERSISTENCE, not breadth. The dead v0.3 "second independent
signal" clause is retired (correlated noise self-corroborates: 6/18 false
interrupts passed it; archaeology_v2 §E.4). An ambiguous signal promotes ONLY if a
confirming re-observation of the SAME surface still shows the anomaly; a one-shot
wobble that has healed by the re-look stays telemetry.

Threshold (D28, frozen pre-data, least-latency): ONE confirming re-look — two
CONSECUTIVE anomalous observations. NO raw-count aggregation anywhere (the v1
escalation-cap pathology, 172 noise fires); this module counts nothing.

Rule Zero: the persistence logic is GENERAL and category-blind — it names no
holdout category and has no quota/version/resource-specific behaviour.
"""
from __future__ import annotations

from enum import Enum
from typing import Sequence


class PersistenceDecision(str, Enum):
    PROMOTE = "promote"      # a confirming re-look STILL shows the anomaly
    TELEMETRY = "telemetry"  # healed by the re-look, or no confirming re-look yet


def decide_persistence(anomaly_flags: Sequence[bool]) -> PersistenceDecision:
    """The pure persistence rule (D28). `anomaly_flags` is the ordered
    "is this observation of the surface still anomalous?" sequence (oldest first).

    PROMOTE iff two CONSECUTIVE observations are anomalous — the first sighting
    plus ONE confirming re-look (the least-latency threshold, D28). Everything
    else is TELEMETRY:
      - a single observation (no re-look yet) is never promoted blind;
      - a one-shot wobble that has healed by the re-look stays telemetry;
      - intermittent wobbles that never persist across a re-look stay telemetry.

    This is ADJACENCY, not a count: it short-circuits on the first consecutive
    anomalous pair and never tallies how many wobbles occurred (D28's hard
    prohibition on raw-count aggregation — no "exceeds N" path exists here)."""
    prev = False
    for flag in anomaly_flags:
        cur = bool(flag)
        if prev and cur:
            return PersistenceDecision.PROMOTE
        prev = cur
    return PersistenceDecision.TELEMETRY
