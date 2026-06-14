"""C6 acceptance: provisional promotion + replan GC (decisions/cadence_semantics.md
§14; D29). Deterministic, synthetic.
"""
from __future__ import annotations

from sentinel_v2.cadence import (BLOCKING_THRESHOLD, HIGH_RISK_THRESHOLD,
                                 PROVISIONAL_WORK_AT_RISK, CoverageLedger,
                                 DependencyProof, TerminalState, can_halt_run,
                                 create_provisional, earns_paired_reserve,
                                 promote_to_blocking, replan_gc, route_probe_outcome)


# -- provisional default: high risk, capped below blocking ---------------------

def test_provisional_is_high_risk_but_cannot_halt():
    rec = create_provisional("/incidental/surface")
    assert HIGH_RISK_THRESHOLD < rec.work_at_risk < BLOCKING_THRESHOLD   # 0.5 < 0.65 < 0.8
    assert earns_paired_reserve(rec)        # earns the paired-observation reserve
    assert not can_halt_run(rec)            # cannot by itself trigger a hard halt


def test_incidental_off_plan_read_creates_a_record_that_cannot_halt():
    led = CoverageLedger()
    rec = create_provisional("/incidental/surface", ledger=led)
    # it enters the same ledger + terminal-state machine
    assert led.entry(rec.assumption_id).verdict is None      # registered, open
    # if it goes uncovered, it routes to CAUTION (not BLOCKING) -> cannot halt the run
    out = route_probe_outcome(None, assumption_id=rec.assumption_id,
                              work_at_risk=rec.work_at_risk, ledger=led)
    assert out.terminal is TerminalState.UNCOVERED_CAUTION


def test_promotable_to_blocking_only_after_commit_confirmed():
    rec = create_provisional("/incidental/surface")
    assert promote_to_blocking(rec, irreversible_commit_confirmed=False) is False
    assert not can_halt_run(rec)            # still cannot halt
    assert promote_to_blocking(rec, irreversible_commit_confirmed=True) is True
    assert rec.work_at_risk > BLOCKING_THRESHOLD and can_halt_run(rec)  # now can block


def test_promoted_provisional_routes_blocking_when_uncovered():
    led = CoverageLedger()
    rec = create_provisional("/incidental/surface", ledger=led)
    promote_to_blocking(rec, irreversible_commit_confirmed=True)
    out = route_probe_outcome(None, assumption_id=rec.assumption_id,
                              work_at_risk=rec.work_at_risk, ledger=led)
    assert out.terminal is TerminalState.UNCOVERED_BLOCKING


# -- replan GC: retire only with a no-dependency proof -------------------------

def test_retire_only_with_a_complete_proof():
    led = CoverageLedger()
    rec = create_provisional("/incidental/surface", ledger=led)
    # incomplete proof -> carried forward (still open, keep-not-flush)
    incomplete = DependencyProof(no_live_artifact=True, no_worker_output=True,
                                 no_pending_decision=False, no_relation_dependency=True)
    assert replan_gc(led, rec.assumption_id, incomplete) is None
    assert led.entry(rec.assumption_id).verdict is None        # carried forward
    # complete proof -> retired NOT_LOAD_BEARING
    complete = DependencyProof(True, True, True, True)
    assert replan_gc(led, rec.assumption_id, complete) is TerminalState.NOT_LOAD_BEARING
    assert led.entry(rec.assumption_id).verdict is TerminalState.NOT_LOAD_BEARING


def test_no_proof_carries_forward():
    led = CoverageLedger()
    rec = create_provisional("/incidental/surface", ledger=led)
    assert replan_gc(led, rec.assumption_id, None) is None
    assert led.entry(rec.assumption_id).verdict is None        # not retired
