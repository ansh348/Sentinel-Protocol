"""C7 acceptance: UNCOVERED accounting, escrow-side under D25 quarantine
(decisions/cadence_semantics.md §4, §16; D29). SEEN fixtures only — no held-out read,
no held-out denominator computed in-line.
"""
from __future__ import annotations

from sentinel_v2.cadence import (HELD_OUT_DENOMINATOR_IS_ESCROW_COMPUTED, CellOutcome,
                                 TerminalState, account, is_detection_hit,
                                 is_recall_miss)


def O(aid, terminal, *, detected=False, real_change=False, war=0.0) -> CellOutcome:
    return CellOutcome(assumption_id=aid, terminal=terminal, detected=detected,
                       real_change=real_change, work_at_risk=war)


# -- UNCOVERED is never a hit --------------------------------------------------

def test_uncovered_caution_is_never_a_detection_hit():
    # even if a flag was raised, an uncovered surface cannot be scored a hit
    o = O("a", TerminalState.UNCOVERED_CAUTION, detected=True, real_change=True, war=0.4)
    assert is_detection_hit(o) is False


def test_uncovered_blocking_is_never_a_hit():
    o = O("a", TerminalState.UNCOVERED_BLOCKING, detected=True, real_change=True, war=0.9)
    assert is_detection_hit(o) is False


# -- uncovered over a real change is a (risk-weighted) miss --------------------

def test_uncovered_surface_over_injected_change_is_a_miss():
    o = O("a", TerminalState.UNCOVERED_CAUTION, real_change=True, war=0.4)
    assert is_recall_miss(o) is True
    acc = account([o])
    assert acc.misses == 1 and acc.uncovered_misses == 1
    assert acc.risk_weighted_miss == 0.4
    assert acc.hits == 0


def test_uncovered_without_a_real_change_is_neither_hit_nor_miss():
    o = O("a", TerminalState.UNCOVERED_CAUTION, real_change=False, war=0.4)
    assert not is_detection_hit(o) and not is_recall_miss(o)
    acc = account([o])
    assert acc.hits == 0 and acc.misses == 0


# -- covered detections and covered-but-missed --------------------------------

def test_covered_detection_over_a_real_change_is_a_hit():
    o = O("a", TerminalState.OBSERVED_FRESH, detected=True, real_change=True, war=0.6)
    assert is_detection_hit(o) is True
    acc = account([o])
    assert acc.hits == 1 and acc.misses == 0 and acc.covered == 1


def test_covered_but_undetected_real_change_is_a_miss_not_uncovered():
    o = O("a", TerminalState.OBSERVED_FRESH, detected=False, real_change=True, war=0.6)
    acc = account([o])
    assert acc.misses == 1 and acc.uncovered_misses == 0   # a miss, but not the loophole
    assert acc.risk_weighted_miss == 0.6


# -- coverage-purchased denominator + the closed loophole ---------------------

def test_coverage_purchased_denominator_and_loophole_closed():
    outcomes = [
        O("hit", TerminalState.OBSERVED_FRESH, detected=True, real_change=True, war=0.6),
        O("clean", TerminalState.OBSERVED_FRESH, real_change=False),
        O("dodge", TerminalState.UNCOVERED_CAUTION, real_change=True, war=0.3),  # tried to dodge
        O("retired", TerminalState.NOT_LOAD_BEARING, real_change=False),
    ]
    acc = account(outcomes)
    assert acc.load_bearing_total == 4
    assert acc.covered == 2                                  # two OBSERVED_*
    assert abs(acc.coverage_purchased - 0.5) < 1e-9
    assert acc.hits == 1
    assert acc.misses == 1 and acc.uncovered_misses == 1     # the dodge scores as a miss
    # D25: the held-out denominator is escrow-computed, never derived here
    assert HELD_OUT_DENOMINATOR_IS_ESCROW_COMPUTED is True
