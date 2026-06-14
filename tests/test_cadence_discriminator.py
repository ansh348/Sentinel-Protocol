"""Close acceptance: the scheduler is live behind the flag; the §17 two-build replay
discriminator proves the freeze is complete; the §19 dependency-graph audit runs
(decisions/cadence_semantics.md §17, §19; D29). Deterministic, synthetic, $0 LLM.
"""
from __future__ import annotations

from sentinel_v2.cadence import (CellOutcome, CoverageItem, CoverageLedger,
                                 EventGatedCadence, PlanAssumption, TerminalState,
                                 account, allocate, dependency_graph_audit,
                                 make_cadence_policy,
                                 two_build_replay_discriminator)
from sentinel_v2.probe_spec import FaultShape
from sentinel_v2.scheduler import NoOpCadence, ProbeScheduler


# -- the scheduler is now live behind the flag ---------------------------------

def test_scheduler_is_live_event_gated_with_guaranteed_pre_completion():
    swept = {"n": 0}

    def sweep():
        swept["n"] += 1
        return "swept"

    live = ProbeScheduler(EventGatedCadence())
    assert live.maybe_sweep({"barrier": True}, sweep) == "swept"          # event-gated
    assert live.maybe_sweep({"pre_completion": True}, sweep) == "swept"   # guaranteed sweep
    assert live.maybe_sweep({"uncovered_high_risk": True}, sweep) == "swept"
    assert live.maybe_sweep({}, sweep) is None                           # quiet -> no fixed-k flood
    assert swept["n"] == 3
    # the prior NoOp baseline never sweeps
    assert ProbeScheduler(NoOpCadence()).maybe_sweep({"barrier": True}, sweep) is None
    assert isinstance(make_cadence_policy(live=True), EventGatedCadence)
    assert isinstance(make_cadence_policy(live=False), NoOpCadence)


# -- the §17 two-build replay discriminator ------------------------------------

def _items():
    # (assumption_id, work_at_risk, cost, real_change)
    return [("hi", 0.9, 2.0, True), ("mid", 0.6, 2.0, False), ("lo", 0.1, 2.0, True)]


def _run_scenario(hidden_choice):
    """A full mini cadence pipeline. The HIDDEN CHOICE is the input ordering — NOT a
    frozen knob. The outcome is canonicalized; if any frozen dial were replaced by a
    hidden choice (e.g. dropping in input order instead of work-at-risk order), the two
    builds would diverge."""
    items = list(reversed(_items())) if hidden_choice else _items()
    led = CoverageLedger()
    for aid, war, cost, rc in items:
        led.register(PlanAssumption(aid, f"/s/{aid}", FaultShape.VALUE_CHANGED,
                                    downstream_steps=1, total_remaining_steps=2,
                                    downstream_commits=False, single_visit=True))
    cov = [CoverageItem(aid, war, cost) for aid, war, cost, rc in items]
    allocate(2.0, cov, run_length=8, paid_probe_count=1, ledger=led)   # valve drops lowest-risk
    for aid, war, cost, rc in items:                                   # cover the kept ones
        if not led.entry(aid).is_terminal:
            led.mark(aid, TerminalState.OBSERVED_FRESH)
    led.finalize()
    acc = account([CellOutcome(aid, led.entry(aid).verdict, detected=False,
                               real_change=rc, work_at_risk=war)
                   for aid, war, cost, rc in items])
    terminal_map = tuple(sorted((aid, led.entry(aid).verdict.value)
                                for aid, _, _, _ in items))
    return (terminal_map, acc.hits, acc.misses, acc.uncovered_misses,
            round(acc.risk_weighted_miss, 6), round(acc.coverage_purchased, 6))


def test_two_build_replay_discriminator_outcomes_identical():
    # identical frozen dials, different hidden choice (input order) -> identical outcome
    assert two_build_replay_discriminator(_run_scenario) is True


def test_discriminator_catches_a_hidden_knob_leak():
    """Negative control: a build whose outcome depends on the hidden choice (drops in
    input order rather than by the frozen work-at-risk dial) is CAUGHT."""
    def _leaky(hidden_choice):
        items = list(reversed(_items())) if hidden_choice else _items()
        return items[0][0]            # keeps the first by INPUT order — order-dependent
    assert two_build_replay_discriminator(_leaky) is False


# -- the §19 dependency-graph audit (escrow-side, D25) -------------------------

def test_dependency_graph_audit_reports_silent_miss_and_passes_when_complete():
    led = CoverageLedger()
    for aid in ("a1", "a2"):
        led.register(PlanAssumption(aid, f"/s/{aid}", FaultShape.VALUE_CHANGED,
                                    1, 2, False, True))
    led.mark("a1", TerminalState.OBSERVED_FRESH)
    led.mark("a2", TerminalState.UNCOVERED_CAUTION)
    led.finalize()
    report = dependency_graph_audit(
        registry={"/s/a1", "/s/a2"},
        dependency_surfaces={"/s/a1", "/s/a2", "/s/unregistered"},   # one absentee
        ledger=led,
        coverage_purchased=0.5,
        clean_treatment_usd=0.1000001, clean_batch_usd=0.10,
        discriminator=_run_scenario)
    assert report.silent_misses == ["/s/unregistered"]    # the §14 residual, measured
    assert report.all_terminal is True
    assert report.discriminator_identical is True
    assert report.overhead_ok is True
    assert report.passed is True


def test_audit_flags_an_open_assumption():
    led = CoverageLedger()
    led.register(PlanAssumption("a1", "/s/a1", FaultShape.VALUE_CHANGED, 1, 2, False, True))
    report = dependency_graph_audit(registry={"/s/a1"}, dependency_surfaces={"/s/a1"},
                                    ledger=led)
    assert report.all_terminal is False and report.open_assumptions == ["a1"]
    assert report.passed is False
