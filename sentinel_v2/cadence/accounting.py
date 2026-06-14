"""UNCOVERED accounting (decisions/cadence_semantics.md §4, §16; D29), ESCROW-SIDE
under the D25 quarantine. DETERMINISTIC, category-blind.

Cost honesty (§4): UNCOVERED_CAUTION is never scored as a detection hit. An uncovered
load-bearing surface that coincided with a real injected change is a recall MISS against
KG1, weighted by work-at-risk — this closes the path where the system passes the 12%
gate by declining to probe. The cost table reports a coverage-purchased denominator
alongside overhead.

D25 quarantine: this accounting is built escrow-side. It NEVER feeds compiler iteration
and NEVER computes against a held-out denominator in-line — it scores only the outcomes
it is handed (seen fixtures in tests; the escrow holder's set in the study). The
held-out load-bearing count stays escrow-computed and is not derived here.
"""
from __future__ import annotations

from dataclasses import dataclass

from sentinel_v2.cadence.ledger import TerminalState

# This module reads NO escrowed/held-out file and computes NO held-out denominator
# in-line (D25). The held-out count is escrow-computed and never reaches here.
HELD_OUT_DENOMINATOR_IS_ESCROW_COMPUTED = True

UNCOVERED_STATES = frozenset({TerminalState.UNCOVERED_CAUTION,
                              TerminalState.UNCOVERED_BLOCKING})
OBSERVED_STATES = frozenset({TerminalState.OBSERVED_FRESH,
                             TerminalState.OBSERVED_STALE_BUT_RECHECKED})


@dataclass(frozen=True)
class CellOutcome:
    """Per load-bearing assumption: its terminal ledger state, whether a detection
    (invalidation) was emitted for it, whether a real injected change coincided (ground
    truth, supplied by the escrow holder / the seen fixture), and its work-at-risk."""
    assumption_id: str
    terminal: TerminalState
    detected: bool
    real_change: bool
    work_at_risk: float = 0.0


def is_detection_hit(o: CellOutcome) -> bool:
    """A hit requires a real change AND an emitted detection AND a covered surface.
    UNCOVERED_* is NEVER a hit (cost honesty, §4) — even if something was flagged."""
    if o.terminal in UNCOVERED_STATES:
        return False
    return o.real_change and o.detected


def is_recall_miss(o: CellOutcome) -> bool:
    """A real injected change that was not detected — whether the surface was uncovered
    (the closed loophole) or covered-but-missed."""
    return o.real_change and not is_detection_hit(o)


@dataclass
class CoverageAccounting:
    hits: int = 0
    misses: int = 0
    uncovered_misses: int = 0        # the subset of misses that were uncovered (loophole closed)
    risk_weighted_miss: float = 0.0  # sum of work-at-risk over misses (KG1, risk-weighted)
    covered: int = 0                 # surfaces actually covered (OBSERVED_*)
    load_bearing_total: int = 0

    @property
    def coverage_purchased(self) -> float:
        """The coverage-purchased denominator reported alongside overhead (§4)."""
        return self.covered / self.load_bearing_total if self.load_bearing_total else 0.0


def account(outcomes) -> CoverageAccounting:
    """Score a set of per-assumption outcomes (seen / escrow-provided only). UNCOVERED
    is never a hit; an uncovered surface over a real change is a risk-weighted miss."""
    items = list(outcomes)
    acc = CoverageAccounting(load_bearing_total=len(items))
    for o in items:
        if o.terminal in OBSERVED_STATES:
            acc.covered += 1
        if is_detection_hit(o):
            acc.hits += 1
        elif is_recall_miss(o):
            acc.misses += 1
            acc.risk_weighted_miss += o.work_at_risk
            if o.terminal in UNCOVERED_STATES:
                acc.uncovered_misses += 1
    return acc
