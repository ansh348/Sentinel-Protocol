"""Coverage ledger + terminal-state machine + admission feasibility
(decisions/cadence_semantics.md §1, §2; D29). DETERMINISTIC, category-blind.

The ledger is the heart of the cadence layer: it is a coverage-ACCOUNTING structure,
not only a scheduler. Every load-bearing assumption carries one entry and must reach
exactly one terminal state before final output. "Covered" requires the compiled
predicate re-evaluated against a sufficient observation (the monitored shape present),
never a mere endpoint touch.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence

from sentinel_v2.cadence.workatrisk import (PlanAssumption, is_blocking_risk,
                                            is_high_risk, work_at_risk)
from sentinel_v2.probe_spec import FaultShape


class TerminalState(str, Enum):
    OBSERVED_FRESH = "observed_fresh"
    OBSERVED_STALE_BUT_RECHECKED = "observed_stale_but_rechecked"
    UNCOVERED_CAUTION = "uncovered_caution"
    UNCOVERED_BLOCKING = "uncovered_blocking"
    NOT_LOAD_BEARING = "not_load_bearing"


# Non-terminal states are illegal at finalization (D29 §1 invariant). They are
# represented by `verdict=None` (open); naming any of these as a coverage outcome is
# a finalization error.
NON_TERMINAL = ("queued", "prioritized", "reserved", "deferred")


class FinalizationError(Exception):
    """Raised if any load-bearing assumption is still open (non-terminal) at output."""


@dataclass
class LedgerEntry:
    """One assumption-and-shape coverage record, keyed
    (surface_id, assumption_id, required_shape, observation_id, verdict)."""
    surface_id: str
    assumption_id: str
    required_shape: FaultShape
    observation_id: Optional[str] = None
    verdict: Optional[TerminalState] = None     # None == open (non-terminal)

    @property
    def is_terminal(self) -> bool:
        return self.verdict is not None

    def key(self) -> tuple:
        return (self.surface_id, self.assumption_id, self.required_shape,
                self.observation_id, self.verdict)


class CoverageLedger:
    """Tracks one entry per load-bearing assumption (keyed by assumption_id) through
    the terminal-state machine."""

    def __init__(self) -> None:
        self._entries: dict[str, LedgerEntry] = {}

    def register(self, pa: PlanAssumption) -> LedgerEntry:
        if pa.assumption_id in self._entries:
            return self._entries[pa.assumption_id]
        entry = LedgerEntry(surface_id=pa.surface_id, assumption_id=pa.assumption_id,
                            required_shape=pa.required_shape)
        self._entries[pa.assumption_id] = entry
        return entry

    def mark(self, assumption_id: str, verdict: TerminalState, *,
             observation_id: Optional[str] = None) -> LedgerEntry:
        if not isinstance(verdict, TerminalState):
            raise ValueError(
                f"{verdict!r} is not a terminal state; "
                f"{NON_TERMINAL} are non-terminal and illegal as a coverage outcome")
        entry = self._entries.get(assumption_id)
        if entry is None:
            raise KeyError(f"unknown assumption {assumption_id!r}; register it first")
        entry.verdict = verdict
        if observation_id is not None:
            entry.observation_id = observation_id
        return entry

    def entry(self, assumption_id: str) -> LedgerEntry:
        return self._entries[assumption_id]

    def entries(self) -> list[LedgerEntry]:
        return list(self._entries.values())

    def open_entries(self) -> list[LedgerEntry]:
        return [e for e in self._entries.values() if not e.is_terminal]

    def finalize(self) -> dict[str, LedgerEntry]:
        """Assert every load-bearing assumption reached exactly one terminal state.
        queued/prioritized/reserved/deferred/absent are illegal here (D29 §1)."""
        still_open = self.open_entries()
        if still_open:
            ids = [e.assumption_id for e in still_open]
            raise FinalizationError(
                f"{len(ids)} load-bearing assumption(s) non-terminal at finalization: "
                f"{ids} — queued/prioritized/deferred are illegal coverage outcomes")
        return dict(self._entries)


# -- Admission-time feasibility (§2) ------------------------------------------------

def min_coverage_lower_bound(assumptions: Sequence[PlanAssumption]) -> int:
    """At least one sufficient observation per load-bearing assumption, and at least
    two for any high-work-at-risk assumption (so a terminal-time wobble can still be
    confirmed, §12)."""
    return sum(2 if is_high_risk(pa) else 1 for pa in assumptions)


@dataclass
class AdmissionResult:
    lower_bound: int
    affordable: Optional[int]               # None == unbounded (dollar reality)
    coverage_debt: list[str] = field(default_factory=list)   # assumption_ids named UNCOVERED
    declared: bool = False


def admit(ledger: CoverageLedger, assumptions: Sequence[PlanAssumption], *,
          affordable_observations: Optional[int] = None) -> AdmissionResult:
    """Register every assumption and compute the minimum-coverage lower bound. If it
    exceeds the affordable budget, declare coverage debt UP FRONT (D29 §2): the
    LOWEST-work-at-risk surfaces are named UNCOVERED at admission (blocking above the
    Section 3 threshold, else caution), and the run never discovers the debt at the
    end. `affordable_observations=None` means unbounded — the dollar reality, where
    probes are ≈ $0 and everything fits."""
    for pa in assumptions:
        ledger.register(pa)
    lower_bound = min_coverage_lower_bound(assumptions)
    result = AdmissionResult(lower_bound=lower_bound, affordable=affordable_observations)
    if affordable_observations is None or lower_bound <= affordable_observations:
        return result

    # Coverage debt: drop the lowest-work-at-risk assumptions until the rest fit.
    # Each high-risk assumption costs 2 observations, others 1 (§2).
    ranked = sorted(assumptions, key=work_at_risk)          # lowest risk first
    cost = {pa.assumption_id: (2 if is_high_risk(pa) else 1) for pa in assumptions}
    spend = lower_bound
    for pa in ranked:
        if spend <= affordable_observations:
            break
        state = (TerminalState.UNCOVERED_BLOCKING if is_blocking_risk(pa)
                 else TerminalState.UNCOVERED_CAUTION)
        ledger.mark(pa.assumption_id, state)
        result.coverage_debt.append(pa.assumption_id)
        spend -= cost[pa.assumption_id]
    result.declared = bool(result.coverage_debt)
    return result
