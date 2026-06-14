"""C1 acceptance: coverage ledger, terminal-state machine, admission feasibility,
and the work-at-risk formula (decisions/cadence_semantics.md §1, §2, §3; D29).
Deterministic, synthetic plan-DAG fixtures only — no world, no LLM.
"""
from __future__ import annotations

import pytest

from sentinel_v2.cadence import (BLOCKING_THRESHOLD, HIGH_RISK_THRESHOLD,
                                 CoverageLedger, FinalizationError,
                                 PlanAssumption, TerminalState, admit,
                                 is_blocking_risk, is_high_risk,
                                 min_coverage_lower_bound, work_at_risk)
from sentinel_v2.probe_spec import FaultShape


def _pa(aid, *, shape=FaultShape.VALUE_CHANGED, surface=None, downstream=2,
        total=4, commits=False, single_visit=False, actionable=True) -> PlanAssumption:
    return PlanAssumption(assumption_id=aid, surface_id=surface or f"/s/{aid}",
                          required_shape=shape, downstream_steps=downstream,
                          total_remaining_steps=total, downstream_commits=commits,
                          single_visit=single_visit, actionable=actionable)


# -- work-at-risk: range, ordering, thresholds ---------------------------------

def test_work_at_risk_lands_in_unit_interval():
    # full work, commit, single-visit, actionable -> the maximum, 1.0
    top = _pa("x", downstream=4, total=4, commits=True, single_visit=True)
    assert work_at_risk(top) == 1.0
    # nothing crosses 1.0 or drops below 0
    for pa in (top, _pa("y"), _pa("z", actionable=False)):
        assert 0.0 <= work_at_risk(pa) <= 1.0


def test_single_visit_and_commit_bearing_rise_retouched_sinks():
    single_visit_commit = _pa("a", downstream=4, total=4, commits=True, single_visit=True)
    retouched_read = _pa("b", downstream=4, total=4, commits=False, single_visit=False)
    assert work_at_risk(single_visit_commit) > work_at_risk(retouched_read)
    # commit-bearing outranks a pure read at equal geometry
    assert work_at_risk(_pa("c", commits=True)) > work_at_risk(_pa("d", commits=False))
    # single-visit outranks re-touched at equal geometry
    assert work_at_risk(_pa("e", single_visit=True)) > work_at_risk(_pa("f", single_visit=False))


def test_consumed_assumption_has_zero_work_at_risk():
    assert work_at_risk(_pa("g", actionable=False)) == 0.0


def test_thresholds_separate_the_classes():
    high = _pa("h", downstream=4, total=4, commits=True, single_visit=True)   # 1.0
    assert is_high_risk(high) and is_blocking_risk(high)
    mid = _pa("m", downstream=2, total=4, commits=True, single_visit=True)    # 0.5
    assert work_at_risk(mid) == 0.5
    assert not is_high_risk(mid)            # strict ">" 0.5
    pure_single = _pa("p", downstream=4, total=4, commits=False, single_visit=True)  # 0.30
    assert not is_high_risk(pure_single)    # recoverable wrong-report stays caution-class
    assert HIGH_RISK_THRESHOLD == 0.5 and BLOCKING_THRESHOLD == 0.8


# -- terminal-state machine ----------------------------------------------------

def test_every_assumption_resolves_to_exactly_one_terminal_state():
    led = CoverageLedger()
    for pa in (_pa("a1"), _pa("a2"), _pa("a3")):
        led.register(pa)
    led.mark("a1", TerminalState.OBSERVED_FRESH, observation_id="o1")
    led.mark("a2", TerminalState.OBSERVED_STALE_BUT_RECHECKED, observation_id="o2")
    led.mark("a3", TerminalState.NOT_LOAD_BEARING)
    final = led.finalize()
    assert {e.verdict for e in final.values()} == {
        TerminalState.OBSERVED_FRESH, TerminalState.OBSERVED_STALE_BUT_RECHECKED,
        TerminalState.NOT_LOAD_BEARING}
    assert final["a1"].observation_id == "o1"


def test_open_entry_is_illegal_at_finalization():
    led = CoverageLedger()
    led.register(_pa("a1"))
    led.register(_pa("a2"))
    led.mark("a1", TerminalState.OBSERVED_FRESH)
    assert led.open_entries()[0].assumption_id == "a2"
    with pytest.raises(FinalizationError, match="non-terminal"):
        led.finalize()


def test_non_terminal_string_is_rejected_as_a_coverage_outcome():
    led = CoverageLedger()
    led.register(_pa("a1"))
    with pytest.raises(ValueError, match="not a terminal state"):
        led.mark("a1", "prioritized")          # the illegal non-terminal "outcome"


def test_ledger_key_is_the_five_tuple():
    led = CoverageLedger()
    led.register(_pa("a1", surface="/repo/files", shape=FaultShape.ORDER_CHANGED))
    led.mark("a1", TerminalState.OBSERVED_FRESH, observation_id="obs-7")
    k = led.entry("a1").key()
    assert k == ("/repo/files", "a1", FaultShape.ORDER_CHANGED, "obs-7",
                 TerminalState.OBSERVED_FRESH)


# -- admission feasibility -----------------------------------------------------

def test_lower_bound_counts_two_for_high_risk_one_otherwise():
    high = _pa("h", downstream=4, total=4, commits=True, single_visit=True)   # high -> 2
    low = _pa("l", downstream=1, total=4, commits=False, single_visit=False)  # low  -> 1
    assert min_coverage_lower_bound([high, low]) == 3


def test_admission_unbounded_declares_no_debt():
    led = CoverageLedger()
    res = admit(led, [_pa("a1"), _pa("a2")])     # affordable=None (dollar reality)
    assert res.declared is False and res.coverage_debt == []
    assert led.open_entries()                     # registered, still open, no debt


def test_admission_declares_debt_on_the_lowest_work_at_risk_first():
    led = CoverageLedger()
    high = _pa("h", downstream=4, total=4, commits=True, single_visit=True)   # war 1.0, cost 2
    mid = _pa("m", downstream=4, total=4, commits=True, single_visit=False)   # war 0.2, cost 1
    low = _pa("l", downstream=1, total=4, commits=False, single_visit=False)  # war 0.05, cost 1
    # lower bound = 2 + 1 + 1 = 4; afford only 2 -> drop lowest-risk until it fits
    res = admit(led, [high, mid, low], affordable_observations=2)
    assert res.declared is True
    assert res.coverage_debt == ["l", "m"]        # lowest-risk first, in risk order
    assert led.entry("l").verdict is TerminalState.UNCOVERED_CAUTION
    assert led.entry("h").verdict is None         # the high-risk surface is kept (covered)


def test_admission_debt_routes_blocking_above_the_threshold():
    led = CoverageLedger()
    blocking = _pa("b", downstream=4, total=4, commits=True, single_visit=True)  # 1.0 > 0.8
    res = admit(led, [blocking], affordable_observations=0)
    assert "b" in res.coverage_debt
    assert led.entry("b").verdict is TerminalState.UNCOVERED_BLOCKING
