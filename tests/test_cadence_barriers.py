"""C3 acceptance: barrier hierarchy, freshness, relation coverage
(decisions/cadence_semantics.md §9, §6, §10; D29). Deterministic, synthetic.
"""
from __future__ import annotations

from sentinel_v2.cadence import (RELATION_UNDER_EMISSION_RESIDUAL, CoverageLedger,
                                 CoverageSpec, Observation, TerminalState,
                                 WorkerPlan, close_specs, fresh_observation,
                                 run_barrier_hierarchy)
from sentinel_v2.probe_spec import Lens, LensOp
from sentinel_v2.probes import ProbeResult


def R(body, *, path="/s", status=200) -> ProbeResult:
    return ProbeResult(method="GET", path=path, status=status, headers={}, body=body)


FIELD = Lens(op=LensOp.FIELD_READ, pointer="/q")


def _spec(aid, surface, *, consume=5, war=0.0, **o) -> CoverageSpec:
    return CoverageSpec(assumption_id=aid, surface_id=surface, lens=FIELD,
                        last_consume_affecting_tick=consume, work_at_risk=war, **o)


def _reg(ledger, *specs):
    from sentinel_v2.cadence.workatrisk import PlanAssumption
    from sentinel_v2.probe_spec import FaultShape
    for s in specs:
        ledger.register(PlanAssumption(assumption_id=s.assumption_id,
                                       surface_id=s.surface_id,
                                       required_shape=FaultShape.VALUE_CHANGED,
                                       downstream_steps=1, total_remaining_steps=2,
                                       downstream_commits=False, single_visit=True))


# -- freshness (§6): observed-after-consume; recency cannot waive ---------------

def test_fresh_only_after_last_consume_affecting_point():
    spec = _spec("a", "/s", consume=10)
    # the most RECENT observation is at tick 9 — before the consume point -> stale
    recent_but_stale = [Observation(tick=9, result=R({"q": 1}))]
    assert fresh_observation(spec, recent_but_stale) is None
    # an observation after the consume point is fresh
    after = recent_but_stale + [Observation(tick=11, result=R({"q": 1}))]
    assert fresh_observation(spec, after).tick == 11


def test_recency_does_not_waive_a_barrier():
    led = CoverageLedger()
    spec = _spec("a", "/s", consume=10, war=0.0)
    _reg(led, spec)
    # timeline has only a recent-but-pre-consume read; no re-observation available
    close_specs(led, [spec], {"/s": [Observation(tick=9, result=R({"q": 1}))]},
                reobserve=None)
    assert led.entry("a").verdict is TerminalState.UNCOVERED_CAUTION   # not waived


def test_barrier_reobservation_makes_it_fresh():
    led = CoverageLedger()
    spec = _spec("a", "/s", consume=10)
    _reg(led, spec)
    # the barrier re-observes at its own tick (fresh by construction)
    close_specs(led, [spec], {"/s": [Observation(tick=9, result=R({"q": 1}))]},
                reobserve=lambda s: Observation(tick=12, result=R({"q": 1})))
    e = led.entry("a")
    assert e.verdict is TerminalState.OBSERVED_STALE_BUT_RECHECKED  # stale early + fresh re-look


def test_purely_fresh_is_observed_fresh():
    led = CoverageLedger()
    spec = _spec("a", "/s", consume=5)
    _reg(led, spec)
    close_specs(led, [spec], {"/s": [Observation(tick=8, result=R({"q": 1}))]})
    assert led.entry("a").verdict is TerminalState.OBSERVED_FRESH


# -- worker barrier catches the early-finishing worker -------------------------

def test_early_finishing_worker_gets_its_barrier():
    led = CoverageLedger()
    early = _spec("a_early", "/early", consume=3)
    late = _spec("a_late", "/late", consume=20)
    _reg(led, early, late)
    workers = [
        WorkerPlan("w_early", [early], barrier_tick=4),     # finishes early
        WorkerPlan("w_late", [late], barrier_tick=25),
    ]
    timelines = {"/early": [Observation(tick=4, result=R({"q": 1}))],
                 "/late": [Observation(tick=22, result=R({"q": 1}))]}
    run_barrier_hierarchy(led, workers, timelines=timelines)
    # the early worker's surface is closed at its own barrier, not missed
    assert led.entry("a_early").verdict is TerminalState.OBSERVED_FRESH
    assert led.entry("a_late").verdict is TerminalState.OBSERVED_FRESH
    led.finalize()        # all terminal


def test_union_of_worker_barriers_equals_load_bearing_set():
    led = CoverageLedger()
    specs = [_spec(f"a{i}", f"/s{i}", consume=1) for i in range(4)]
    _reg(led, *specs)
    workers = [WorkerPlan(f"w{i}", [specs[i]], barrier_tick=2 + i) for i in range(4)]
    timelines = {f"/s{i}": [Observation(tick=3 + i, result=R({"q": 1}))] for i in range(4)}
    run_barrier_hierarchy(led, workers, timelines=timelines)   # no global barrier needed
    assert all(e.is_terminal for e in led.entries())           # union covers everything
    led.finalize()


# -- relation coverage (§10): consistent snapshot or uncovered -----------------

def test_consistent_snapshot_covers_the_relation():
    led = CoverageLedger()
    rel = _spec("rel", "/left", consume=2, is_relation=True,
                partner_surface_id="/right", relation_window=2)
    _reg(led, rel)
    timelines = {"/left": [Observation(tick=10, result=R({"q": 1}))],
                 "/right": [Observation(tick=11, result=R({"q": 1}))]}   # within window 2
    close_specs(led, [rel], timelines)
    assert led.entry("rel").verdict is TerminalState.OBSERVED_FRESH


def test_non_overlapping_relation_windows_yield_uncovered():
    led = CoverageLedger()
    rel = _spec("rel", "/left", consume=2, war=0.9, is_relation=True,
                partner_surface_id="/right", relation_window=2)
    _reg(led, rel)
    # each side individually fresh (both > consume 2), but 45 ticks apart
    timelines = {"/left": [Observation(tick=5, result=R({"q": 1}))],
                 "/right": [Observation(tick=50, result=R({"q": 1}))]}
    close_specs(led, [rel], timelines)
    # uncovered for the relation; blocking because war 0.9 > 0.8
    assert led.entry("rel").verdict is TerminalState.UNCOVERED_BLOCKING


# -- the VERIFY: relation under-emission is a measured residual -----------------

def test_relation_under_emission_recorded_not_patched():
    # the soft-assumption compile format has no partner-surface field
    from sentinel_v2.compile_probes import SoftAssumption
    assert "partner" not in SoftAssumption.model_fields
    assert "relation" not in SoftAssumption.model_fields
    # the residual is recorded (named), not patched toward any category
    assert "under-emit" in RELATION_UNDER_EMISSION_RESIDUAL
    assert "not patched" in RELATION_UNDER_EMISSION_RESIDUAL
