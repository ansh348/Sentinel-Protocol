"""Wobble throttling + terminal-time routing + probe-failure policy
(decisions/cadence_semantics.md §11, §12, §13; D26/D29). DETERMINISTIC, category-blind.

Defends against v1's flood re-emerging as confirmation demand WITHOUT re-introducing
raw-count aggregation (D28 preserved): one open wobble per (surface, assumption),
repeats coalesce, the confirming re-look is the NEXT scheduled re-observation (never an
immediate re-fire), and confirmation is risk-ordered. A throttled wobble still reaches a
terminal state. Confirmation itself is D28's persistence rule — count-invariant.

Probe-failure (discharges D26): retry budget 1, then a transport failure terminates
UNCOVERED; a clean response that violates the predicate is a detection (the typing /
persistence path), never UNCOVERED.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from sentinel_v2.cadence.ledger import CoverageLedger, TerminalState
from sentinel_v2.cadence.workatrisk import BLOCKING_THRESHOLD
from sentinel_v2.corroboration import PersistenceDecision, decide_persistence
from sentinel_v2.probes import ProbeResult

# Probe-failure retry budget (D26/D29 §13). Principled: seen transport-failure rate is
# 0; mirrors D28's one confirming re-look. One retry, then terminate uncovered.
TRANSPORT_RETRY_BUDGET = 1


@dataclass
class OpenWobble:
    surface_id: str
    assumption_id: str
    work_at_risk: float
    first_tick: int
    raw_count: int = 0          # DIAGNOSTIC only — never a promotion input (D28 no raw-count)


class WobbleThrottle:
    """One open wobble per (surface_id, assumption_id); repeats coalesce into it. The
    confirming re-look is deferred to the next scheduled re-observation. No raw-count
    aggregation: `raw_count` is diagnostic and never decides anything."""

    def __init__(self) -> None:
        self._open: dict[tuple, OpenWobble] = {}

    def observe_wobble(self, surface_id: str, assumption_id: str, *, tick: int,
                       work_at_risk: float = 0.0) -> OpenWobble:
        """Record a raw wobble. Dedup + coalesce: at most one open wobble per key;
        a repeat collapses into the existing one (no new incident, no escalation)."""
        key = (surface_id, assumption_id)
        wob = self._open.get(key)
        if wob is None:
            wob = OpenWobble(surface_id, assumption_id, work_at_risk, tick)
            self._open[key] = wob
        wob.raw_count += 1
        return wob

    @property
    def open_count(self) -> int:
        return len(self._open)

    def open_wobbles(self) -> list[OpenWobble]:
        """Risk-ordered (highest work-at-risk first) for confirmation within the reserve."""
        return sorted(self._open.values(), key=lambda w: w.work_at_risk, reverse=True)

    def confirm(self, surface_id: str, assumption_id: str,
                anomaly_flags: Sequence[bool], *,
                ledger: Optional[CoverageLedger] = None) -> PersistenceDecision:
        """At the next scheduled re-look, confirm via the D28 persistence rule over the
        observed sequence (count-invariant). Either way the assumption was RE-EVALUATED,
        so coverage resolves OBSERVED; PROMOTE additionally means corroboration emits a
        caution (D28), TELEMETRY means it healed. The open wobble is closed."""
        key = (surface_id, assumption_id)
        decision = decide_persistence(anomaly_flags)
        self._open.pop(key, None)
        if ledger is not None and not ledger.entry(assumption_id).is_terminal:
            ledger.mark(assumption_id, TerminalState.OBSERVED_FRESH)
        return decision

    def finalize_open(self, ledger: CoverageLedger) -> list[str]:
        """Any wobble never confirmed terminates UNCOVERED_CAUTION (D29 §11 invariant:
        a throttled-but-unconfirmed wobble still reaches a terminal state)."""
        terminated = []
        for key, wob in list(self._open.items()):
            if not ledger.entry(wob.assumption_id).is_terminal:
                ledger.mark(wob.assumption_id, TerminalState.UNCOVERED_CAUTION)
                terminated.append(wob.assumption_id)
            self._open.pop(key)
        return terminated


# -- terminal-time anomaly (§12) -----------------------------------------------

def route_terminal_time_singleton(*, status_coded: bool, can_confirm: bool,
                                  assumption_id: str,
                                  ledger: Optional[CoverageLedger] = None
                                  ) -> Optional[TerminalState]:
    """An ambiguous (non-status-coded) observation first seen at a barrier with no room
    to confirm terminates UNCOVERED_CAUTION — never scored clean, never a one-shot
    interrupt (that would violate D28 persistence). A status-coded anomaly keeps the
    D28 fast path (returns None: it interrupts on its own, not routed uncovered). If
    there is room to confirm, it is not a terminal singleton (None)."""
    if status_coded or can_confirm:
        return None
    if ledger is not None and not ledger.entry(assumption_id).is_terminal:
        ledger.mark(assumption_id, TerminalState.UNCOVERED_CAUTION)
    return TerminalState.UNCOVERED_CAUTION


# -- probe-failure policy (§13 / D26) ------------------------------------------

def probe_with_retry(attempt: Callable[[], Optional[ProbeResult]], *,
                     retries: int = TRANSPORT_RETRY_BUDGET) -> tuple[Optional[ProbeResult], int]:
    """`attempt()` returns a ProbeResult on success, or None on a transport failure /
    unreadable-or-partial payload. Tries up to (1 + retries) times; returns
    (first result or None, number_of_attempts). One retry, then give up (D26)."""
    attempts = 0
    for _ in range(1 + max(0, retries)):
        attempts += 1
        result = attempt()
        if result is not None:
            return result, attempts
    return None, attempts


@dataclass
class ProbeOutcome:
    observed: bool                       # a clean response obtained (typing/persistence decides detection)
    terminal: Optional[TerminalState]    # set when a transport failure terminates UNCOVERED


def route_probe_outcome(result: Optional[ProbeResult], *, assumption_id: str,
                        work_at_risk: float = 0.0,
                        ledger: Optional[CoverageLedger] = None) -> ProbeOutcome:
    """Transport failure (None after retries) terminates UNCOVERED (blocking above the
    §3 threshold, else caution). A clean response is OBSERVED and flows to the typing /
    persistence path, where a predicate violation is a genuine detection (D26)."""
    if result is None:
        state = (TerminalState.UNCOVERED_BLOCKING if work_at_risk > BLOCKING_THRESHOLD
                 else TerminalState.UNCOVERED_CAUTION)
        if ledger is not None and not ledger.entry(assumption_id).is_terminal:
            ledger.mark(assumption_id, state)
        return ProbeOutcome(observed=False, terminal=state)
    return ProbeOutcome(observed=True, terminal=None)
