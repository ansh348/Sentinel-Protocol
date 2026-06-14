"""C5 acceptance: wobble throttling, terminal-time routing, probe-failure policy
(decisions/cadence_semantics.md §11, §12, §13; D26/D29). Deterministic, synthetic.
"""
from __future__ import annotations

from sentinel_v2.cadence import (TRANSPORT_RETRY_BUDGET, CoverageLedger,
                                 PlanAssumption, TerminalState, WobbleThrottle,
                                 probe_with_retry, route_probe_outcome,
                                 route_terminal_time_singleton)
from sentinel_v2.corroboration import (Grade, PersistenceDecision, Signal,
                                       corroborate_signal)
from sentinel_v2.probe_spec import (CadenceHint, Comparison, CostClass,
                                    EvidenceClass, FaultShape, Lens, LensOp, Probe,
                                    Provenance)
from sentinel_v2.probes import ProbeResult


def R(body, *, status=200) -> ProbeResult:
    return ProbeResult(method="GET", path="/s", status=status, headers={}, body=body)


def _pa(aid):
    return PlanAssumption(assumption_id=aid, surface_id="/s",
                          required_shape=FaultShape.VALUE_CHANGED, downstream_steps=1,
                          total_remaining_steps=2, downstream_commits=False,
                          single_visit=True)


# -- dedup + coalesce + count-invariance (D28 anti-aggregation preserved) -------

def test_flood_of_transient_wobbles_coalesces_to_one_open_decision():
    th = WobbleThrottle()
    for tick in range(500):
        th.observe_wobble("/s", "a", tick=tick, work_at_risk=0.3)
    assert th.open_count == 1                       # 500 raw wobbles -> ONE open wobble
    assert th.open_wobbles()[0].raw_count == 500    # diagnostic only


def test_confirmation_is_count_invariant_and_promotes_nothing_when_transient():
    th = WobbleThrottle()
    led = CoverageLedger()
    led.register(_pa("a"))
    for tick in range(500):
        th.observe_wobble("/s", "a", tick=tick)
    # the next scheduled re-look shows the surface healed (transient) -> TELEMETRY
    decision = th.confirm("/s", "a", [True, False], ledger=led)
    assert decision is PersistenceDecision.TELEMETRY        # promotes nothing
    assert th.open_count == 0
    assert led.entry("a").verdict is TerminalState.OBSERVED_FRESH   # observed (healed)


def test_persisted_wobble_promotes_but_coverage_is_observed():
    th = WobbleThrottle()
    led = CoverageLedger()
    led.register(_pa("a"))
    th.observe_wobble("/s", "a", tick=1, work_at_risk=0.9)
    decision = th.confirm("/s", "a", [True, True], ledger=led)   # persisted across re-look
    assert decision is PersistenceDecision.PROMOTE
    assert led.entry("a").verdict is TerminalState.OBSERVED_FRESH   # re-evaluated = covered


def test_unconfirmed_wobble_terminates_uncovered_caution_at_finalization():
    th = WobbleThrottle()
    led = CoverageLedger()
    led.register(_pa("a"))
    th.observe_wobble("/s", "a", tick=1)
    assert th.finalize_open(led) == ["a"]
    assert led.entry("a").verdict is TerminalState.UNCOVERED_CAUTION


# -- terminal-time anomaly (§12) -----------------------------------------------

def test_ambiguous_terminal_singleton_routes_to_caution():
    led = CoverageLedger()
    led.register(_pa("a"))
    state = route_terminal_time_singleton(status_coded=False, can_confirm=False,
                                          assumption_id="a", ledger=led)
    assert state is TerminalState.UNCOVERED_CAUTION
    assert led.entry("a").verdict is TerminalState.UNCOVERED_CAUTION


def test_status_coded_singleton_keeps_the_fast_path():
    led = CoverageLedger()
    led.register(_pa("a"))
    # status-coded -> not routed uncovered (the D28 fast path interrupts on its own)
    assert route_terminal_time_singleton(status_coded=True, can_confirm=False,
                                         assumption_id="a", ledger=led) is None
    assert led.entry("a").verdict is None


def test_room_to_confirm_is_not_a_terminal_singleton():
    assert route_terminal_time_singleton(status_coded=False, can_confirm=True,
                                         assumption_id="a") is None


# -- probe-failure policy (§13 / D26) ------------------------------------------

def test_transport_failure_retries_once_then_terminates_uncovered():
    led = CoverageLedger()
    led.register(_pa("a"))
    calls = {"n": 0}

    def always_fails():
        calls["n"] += 1
        return None                                  # transport failure / unreadable

    result, attempts = probe_with_retry(always_fails)
    assert result is None and attempts == 1 + TRANSPORT_RETRY_BUDGET == 2   # one retry
    out = route_probe_outcome(result, assumption_id="a", work_at_risk=0.3, ledger=led)
    assert out.observed is False and out.terminal is TerminalState.UNCOVERED_CAUTION
    assert led.entry("a").verdict is TerminalState.UNCOVERED_CAUTION


def test_retry_succeeds_on_second_attempt():
    seq = [None, R({"x": 1})]

    def flaky():
        return seq.pop(0)

    result, attempts = probe_with_retry(flaky)
    assert result is not None and attempts == 2


def test_clean_response_violating_predicate_is_a_detection_not_uncovered():
    led = CoverageLedger()
    led.register(_pa("a"))
    # a clean (non-transport) response is OBSERVED -> typing/persistence path
    good = R({"unit_price": 25.0})
    out = route_probe_outcome(good, assumption_id="a", work_at_risk=0.3, ledger=led)
    assert out.observed is True and out.terminal is None
    assert led.entry("a").verdict is None            # not uncovered
    # and the typing path turns the predicate violation into a detection (interrupt)
    probe = Probe(method="GET", target="/pricing/quote/WID-001",
                  lens=Lens(op=LensOp.FIELD_READ, pointer="/unit_price"),
                  comparison=Comparison.PROOF_BASELINE, fault_shape=FaultShape.VALUE_CHANGED,
                  evidence_class=EvidenceClass.CONTENT_SHAPED, cost_class=CostClass.LIGHT,
                  cadence_hint=CadenceHint.EVENT_GATED,
                  provenance=Provenance(plan_step="s", world_fact="f",
                                        surface="/pricing/quote/WID-001", read="r",
                                        predicate="p", recovery_hint="h"))
    from sentinel_v2.typing_engine import BaselineObligations
    sig = Signal(probe=probe, baseline=R({"unit_price": 19.68}), observations=[good],
                 obligations=BaselineObligations(clean=True, equivalent=True,
                                                 stationary=True, targeted=True, frozen=True))
    inv = corroborate_signal(sig)
    assert inv is not None and inv.grade is Grade.INTERRUPT
