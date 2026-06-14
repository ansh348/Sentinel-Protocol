"""C4 acceptance: budget allocator + work-at-risk (decisions/cadence_semantics.md
§4, §3; D29). Deterministic, synthetic.
"""
from __future__ import annotations

from sentinel_v2.cadence import (BLOCKING_THRESHOLD, CONFIRMATION_RESERVE_FRACTION,
                                 KG3_OVERHEAD_CAP, ConfirmationItem, CoverageItem,
                                 CoverageLedger, PlanAssumption, TerminalState,
                                 allocate, clean_overhead, clean_overhead_ok,
                                 is_high_risk, work_at_risk)
from sentinel_v2.probe_spec import FaultShape


def _pa(aid, **o):
    base = dict(assumption_id=aid, surface_id=f"/s/{aid}",
                required_shape=FaultShape.VALUE_CHANGED, downstream_steps=4,
                total_remaining_steps=4, downstream_commits=False, single_visit=False)
    base.update(o)
    return PlanAssumption(**base)


# -- the KG3 dollar gate, verbatim ---------------------------------------------

def test_kg3_overhead_is_the_pinned_dollar_formula():
    # (clean5 - clean1) / clean1 <= 0.12
    assert abs(clean_overhead(0.112, 0.10) - 0.12) < 1e-9   # 12% overhead
    assert clean_overhead_ok(0.112, 0.10)              # exactly 12% passes
    assert not clean_overhead_ok(0.12, 0.10)           # 20% fails
    assert clean_overhead_ok(0.10, 0.10)               # 0% passes
    assert KG3_OVERHEAD_CAP == 0.12


def test_dollar_gate_is_slack_when_probes_are_free():
    # probes ~ $0: treatment clean cost barely above batch -> well under 12%
    assert clean_overhead_ok(0.1000001, 0.10)


# -- work-at-risk ordering (re-confirmed at C4) --------------------------------

def test_product_in_unit_interval_and_ordering():
    sv_commit = _pa("a", downstream_commits=True, single_visit=True)   # 1.0
    retouched = _pa("b", downstream_commits=False, single_visit=False)  # 0.06
    assert 0.0 < work_at_risk(sv_commit) <= 1.0
    assert work_at_risk(sv_commit) > work_at_risk(retouched)
    assert is_high_risk(sv_commit) and not is_high_risk(retouched)


# -- three-way priority + the paired reserve ----------------------------------

def test_coverage_first_then_confirmation_capped_at_40pct_then_speculation():
    cov = [CoverageItem("a", work_at_risk=0.9, cost=2.0)]
    conf = [ConfirmationItem("/s/a", work_at_risk=0.9, cost=10.0)]
    plan = allocate(10.0, cov, confirmation_items=conf, run_length=20, paid_probe_count=3)
    assert plan.coverage_reserved == 2.0
    remainder = 10.0 - 2.0
    assert plan.confirmation_cap == CONFIRMATION_RESERVE_FRACTION * remainder  # 0.4*8 = 3.2
    assert plan.confirmation_reserved == 0.0       # the $10 confirmation can't fit the $3.2 cap
    assert plan.speculation_reserved == remainder  # speculation gets the rest


def test_confirmation_cannot_starve_speculation_beyond_its_cap():
    cov = [CoverageItem("a", 0.9, 1.0)]
    conf = [ConfirmationItem("/s/a", 0.9, 1.0), ConfirmationItem("/s/b", 0.8, 1.0)]
    plan = allocate(10.0, cov, confirmation_items=conf, run_length=20, paid_probe_count=2)
    remainder = 9.0
    assert plan.confirmation_reserved <= CONFIRMATION_RESERVE_FRACTION * remainder
    assert plan.speculation_reserved >= remainder - plan.confirmation_cap


# -- the uncovered valve flags lowest-work-at-risk first ----------------------

def test_valve_drops_lowest_work_at_risk_first_marks_ledger():
    led = CoverageLedger()
    for pa in (_pa("hi", downstream_commits=True, single_visit=True),    # war 1.0
               _pa("lo", downstream_commits=False, single_visit=False)):  # war 0.06
        led.register(pa)
    cov = [CoverageItem("hi", 1.0, 2.0), CoverageItem("lo", 0.06, 2.0)]
    plan = allocate(2.0, cov, run_length=8, paid_probe_count=2, ledger=led)
    assert plan.uncovered == ["lo"]                # lowest-risk dropped, highest kept
    assert led.entry("lo").verdict is TerminalState.UNCOVERED_CAUTION
    assert led.entry("hi").verdict is None         # high-risk surface kept (covered)


def test_uncovered_high_risk_surface_routes_to_blocking():
    led = CoverageLedger()
    led.register(_pa("b", downstream_commits=True, single_visit=True))   # war 1.0 > 0.8
    cov = [CoverageItem("b", work_at_risk=1.0, cost=5.0)]
    plan = allocate(0.0, cov, run_length=8, paid_probe_count=1, ledger=led)  # cap 0 -> can't fit
    assert "b" in plan.uncovered and 1.0 > BLOCKING_THRESHOLD
    assert led.entry("b").verdict is TerminalState.UNCOVERED_BLOCKING


# -- the count submetric is reported -------------------------------------------

def test_paid_probe_per_run_length_submetric_reported():
    plan = allocate(100.0, [CoverageItem("a", 0.5, 1.0)], run_length=8, paid_probe_count=5)
    assert plan.paid_probe_count == 5 and plan.run_length == 8
    assert abs(plan.paid_probe_per_run_length - 5 / 8) < 1e-9
