"""B3 acceptance: the comparison + typing engine (pure, synthetic fixtures;
probe_compiler_design_v0.4.md §2/§2.1). Covers the Break-A hard-invariant path,
the five baseline obligations, and the §2.1 drift typing gate.
"""
from __future__ import annotations

import pytest

from sentinel_v2.probe_spec import (CadenceHint, Comparison, CostClass,
                                    EvidenceClass, FaultShape, Lens, LensOp,
                                    Probe, Provenance)
from sentinel_v2.probes import ProbeResult
from sentinel_v2.typing_engine import (BaselineObligations, Invariant, Verdict,
                                       evaluate, evaluate_baseline_drift,
                                       evaluate_hard_invariant)


def R(body, status=200, headers=None) -> ProbeResult:
    return ProbeResult(method="GET", path="/x", status=status,
                       headers=headers or {}, body=body)


def _prov(**o) -> Provenance:
    base = dict(plan_step="s", world_fact="f", surface="/x", read="r",
                predicate="p", recovery_hint="h")
    base.update(o)
    return Provenance(**base)


def _probe(fault_shape, comparison, lens, **o) -> Probe:
    base = dict(method="GET", target="/x", lens=lens, comparison=comparison,
                fault_shape=fault_shape, evidence_class=EvidenceClass.CONTENT_SHAPED,
                cost_class=CostClass.LIGHT, cadence_hint=CadenceHint.EVENT_GATED,
                provenance=_prov())
    base.update(o)
    return Probe(**base)


def _obl(**o) -> BaselineObligations:
    base = dict(clean=True, equivalent=True, stationary=True, targeted=True,
                frozen=True)
    base.update(o)
    return BaselineObligations(**base)


# -- Break-A: compiled hard invariants fire on their own -----------------------

def test_break_a_gate_off_from_start_fires_via_hard_invariant():
    """The acceptance test: a gate that was OFF from the first observation (no
    clean 'on' baseline ever existed) is still caught — by the hard-invariant
    path, with NO baseline supplied."""
    probe = _probe(FaultShape.VALUE_CHANGED, Comparison.HARD_INVARIANT,
                   Lens(op=LensOp.GATE_SHADOW, pointer="/enforcing"),
                   target="/repo/gate_status")
    assert probe.subject_to_typing() is False  # hard invariant is not typing-gated

    off = evaluate(probe, current=R({"enforcing": False}),
                   invariant=Invariant(equals=True))
    assert off.verdict is Verdict.INTERRUPT and off.path == "hard_invariant"
    assert off.witness is False

    on = evaluate(probe, current=R({"enforcing": True}),
                  invariant=Invariant(equals=True))
    assert on.verdict is Verdict.CLEAN


def test_hard_invariant_status_class():
    probe = _probe(FaultShape.STATUS_CLASS, Comparison.HARD_INVARIANT,
                   Lens(op=LensOp.STATUS_READ))
    inv = Invariant(status_in=(200,))
    assert evaluate_hard_invariant(probe, R({}, status=404), inv).verdict is Verdict.INTERRUPT
    assert evaluate_hard_invariant(probe, R({}, status=200), inv).verdict is Verdict.CLEAN


def test_hard_invariant_required_field_presence():
    probe = _probe(FaultShape.FIELD_ABSENT, Comparison.HARD_INVARIANT,
                   Lens(op=LensOp.FIELD_READ, pointer="/unit_price"))
    inv = Invariant(require_present=True)
    assert evaluate_hard_invariant(probe, R({"sku": "A"}), inv).verdict is Verdict.INTERRUPT
    assert evaluate_hard_invariant(probe, R({"unit_price": 9.5}), inv).verdict is Verdict.CLEAN


def test_hard_invariant_relation_broken_and_needs_partner():
    lens = Lens(op=LensOp.RELATION, pointer="/lines", field="sku",
                partner_target="/inventory/items", partner_pointer="/items",
                partner_field="sku", relation="subset")
    probe = _probe(FaultShape.RELATION_BROKEN, Comparison.HARD_INVARIANT, lens,
                   cost_class=CostClass.HEAVY, target="/orders")
    inv = Invariant(relation_required=True)
    catalog = R({"items": [{"sku": "A"}, {"sku": "B"}]})
    ok = evaluate_hard_invariant(probe, R({"lines": [{"sku": "A"}]}), inv, partner=catalog)
    assert ok.verdict is Verdict.CLEAN
    broken = evaluate_hard_invariant(probe, R({"lines": [{"sku": "Z"}]}), inv,
                                     partner=catalog)
    assert broken.verdict is Verdict.INTERRUPT and broken.witness == ("Z",)
    # a relation invariant with no partner observation cannot conclude
    assert evaluate_hard_invariant(probe, R({"lines": []}), inv).verdict \
        is Verdict.INCONCLUSIVE


# -- the five baseline obligations ---------------------------------------------

def test_baseline_disqualified_when_any_obligation_fails():
    probe = _probe(FaultShape.VALUE_CHANGED, Comparison.PROOF_BASELINE,
                   Lens(op=LensOp.FIELD_READ, pointer="/x"))
    # value genuinely changed, but a non-stationary baseline is NOT interrupt-grade
    ev = evaluate_baseline_drift(probe, R({"x": 1}), R({"x": 2}),
                                 _obl(stationary=False))
    assert ev.verdict is Verdict.DISQUALIFIED and ev.witness == ("stationary",)
    # a dirty baseline certifies nothing even when the world is genuinely broken


def test_baseline_all_obligations_hold_lets_typed_drift_through():
    probe = _probe(FaultShape.VALUE_CHANGED, Comparison.PROOF_BASELINE,
                   Lens(op=LensOp.FIELD_READ, pointer="/x"))
    assert evaluate_baseline_drift(probe, R({"x": 1}), R({"x": 2}),
                                   _obl()).verdict is Verdict.INTERRUPT


# -- §2.1 typing gate on the drift path ----------------------------------------

def test_typed_value_change_interrupts():
    probe = _probe(FaultShape.VALUE_CHANGED, Comparison.PROOF_BASELINE,
                   Lens(op=LensOp.FIELD_READ, pointer="/x"))
    assert evaluate(probe, baseline=R({"x": 1}), current=R({"x": 2}),
                    obligations=_obl()).verdict is Verdict.INTERRUPT
    assert evaluate(probe, baseline=R({"x": 1}), current=R({"x": 1}),
                    obligations=_obl()).verdict is Verdict.CLEAN


def test_schema_shape_change_and_field_added_interrupt():
    probe = _probe(FaultShape.SCHEMA_SHAPE, Comparison.PROOF_BASELINE,
                   Lens(op=LensOp.SCHEMA_FINGERPRINT))
    # type flip int -> str
    flip = evaluate_baseline_drift(probe, R({"a": 1}), R({"a": "1"}), _obl())
    assert flip.verdict is Verdict.INTERRUPT and flip.typed
    # FIELD-ADDED instantiates SCHEMA_SHAPE (the v0.4 reconciliation)
    added = evaluate_baseline_drift(probe, R({"a": 1}), R({"a": 1, "b": 2}), _obl())
    assert added.verdict is Verdict.INTERRUPT


def test_order_change_interrupts():
    probe = _probe(FaultShape.ORDER_CHANGED, Comparison.PROOF_BASELINE,
                   Lens(op=LensOp.ORDERED_SUBARRAY, pointer="/r", field="sku"),
                   cost_class=CostClass.MODERATE)
    base = R({"r": [{"sku": "A"}, {"sku": "B"}, {"sku": "C"}]})
    reordered = R({"r": [{"sku": "C"}, {"sku": "B"}, {"sku": "A"}]})
    assert evaluate_baseline_drift(probe, base, reordered, _obl()).verdict \
        is Verdict.INTERRUPT
    assert evaluate_baseline_drift(probe, base, base, _obl()).verdict is Verdict.CLEAN


def test_shapeless_drift_is_telemetry_from_the_per_observation_engine():
    """A whole-payload content-hash difference names no shape: telemetry, never a
    raw interrupt — the bounded recall §0/A3 trades away. The per-observation
    engine NEVER escalates it; promotion to caution on PERSISTENCE is the
    corroboration layer's job (D28, tested in test_corroboration.py)."""
    probe = _probe(FaultShape.VALUE_CHANGED, Comparison.PROOF_BASELINE,
                   Lens(op=LensOp.CONTENT_HASH), cost_class=CostClass.MODERATE)
    base, changed = R({"a": 1}), R({"a": 2})

    tele = evaluate_baseline_drift(probe, base, changed, _obl())
    assert tele.verdict is Verdict.TELEMETRY and tele.typed is False

    # identical payload: no drift at all
    assert evaluate_baseline_drift(probe, base, R({"a": 1}), _obl()).verdict \
        is Verdict.CLEAN


def test_field_absent_drift_interrupts():
    probe = _probe(FaultShape.FIELD_ABSENT, Comparison.PROOF_BASELINE,
                   Lens(op=LensOp.FIELD_READ, pointer="/x"))
    assert evaluate_baseline_drift(probe, R({"x": 1}), R({}), _obl()).verdict \
        is Verdict.INTERRUPT


# -- §5.2 inconclusive + dispatch guards ---------------------------------------

def test_inconclusive_when_probe_did_not_complete():
    hi = _probe(FaultShape.STATUS_CLASS, Comparison.HARD_INVARIANT,
                Lens(op=LensOp.STATUS_READ))
    assert evaluate_hard_invariant(hi, None, Invariant(status_in=(200,))).verdict \
        is Verdict.INCONCLUSIVE
    drift = _probe(FaultShape.VALUE_CHANGED, Comparison.PROOF_BASELINE,
                   Lens(op=LensOp.FIELD_READ, pointer="/x"))
    assert evaluate_baseline_drift(drift, None, None, _obl()).verdict \
        is Verdict.INCONCLUSIVE


def test_dispatch_requires_the_right_inputs():
    hi = _probe(FaultShape.STATUS_CLASS, Comparison.HARD_INVARIANT,
                Lens(op=LensOp.STATUS_READ))
    with pytest.raises(ValueError, match="requires a compiled Invariant"):
        evaluate(hi, current=R({}))
    drift = _probe(FaultShape.VALUE_CHANGED, Comparison.PROOF_BASELINE,
                   Lens(op=LensOp.FIELD_READ, pointer="/x"))
    with pytest.raises(ValueError, match="requires BaselineObligations"):
        evaluate(drift, current=R({"x": 1}), baseline=R({"x": 1}))
