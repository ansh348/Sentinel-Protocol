"""B2 acceptance: the compiled-probe spec + the fault-shape vocabulary
(probe_compiler_design_v0.4.md §1/§2/§2.1). Validation only — no compilation,
corroboration, or cadence semantics (all hard stops).
"""
from __future__ import annotations

import pytest

from sentinel_v2.probe_spec import (EVIDENCE_TRUST_PRIOR, TYPING_EXEMPT_SHAPES,
                                    CadenceHint, Comparison, CostClass,
                                    EvidenceClass, FaultShape, Lens, LensOp,
                                    Probe, Provenance, _SHAPE_LENS_OPS)


def _prov(**over) -> Provenance:
    base = dict(plan_step="aggregate prices", world_fact="pricing serves unit_price",
                surface="/pricing/quote/WID-001", read="field_read /unit_price",
                predicate="unit_price present & numeric", recovery_hint="replan pricing")
    base.update(over)
    return Provenance(**base)


def _probe(**over) -> Probe:
    base = dict(method="GET", target="/pricing/quote/WID-001",
                lens=Lens(op=LensOp.FIELD_READ, pointer="/unit_price"),
                comparison=Comparison.PROOF_BASELINE,
                fault_shape=FaultShape.VALUE_CHANGED,
                evidence_class=EvidenceClass.CONTENT_SHAPED,
                cost_class=CostClass.LIGHT, cadence_hint=CadenceHint.EVENT_GATED,
                provenance=_prov())
    base.update(over)
    return Probe(**base)


# -- vocabulary anchors --------------------------------------------------------

def test_exactly_six_general_fault_shapes():
    assert len(list(FaultShape)) == 6
    assert {s.name for s in FaultShape} == {
        "FIELD_ABSENT", "STATUS_CLASS", "SCHEMA_SHAPE",
        "VALUE_CHANGED", "ORDER_CHANGED", "RELATION_BROKEN"}
    # every shape has at least one expressing lens
    assert set(_SHAPE_LENS_OPS) == set(FaultShape)
    assert all(_SHAPE_LENS_OPS[s] for s in FaultShape)


def test_only_relation_broken_is_typing_exempt():
    assert TYPING_EXEMPT_SHAPES == frozenset({FaultShape.RELATION_BROKEN})


# -- typing-path logic (Break-A) -----------------------------------------------

def test_drift_baseline_probe_is_subject_to_typing():
    p = _probe(comparison=Comparison.PROOF_BASELINE, fault_shape=FaultShape.VALUE_CHANGED)
    assert p.subject_to_typing() is True


def test_hard_invariant_fires_on_its_own():
    """Break-A: a compiled hard invariant is NOT gated by §2.1 typing."""
    p = _probe(comparison=Comparison.HARD_INVARIANT, fault_shape=FaultShape.STATUS_CLASS,
               target="/inventory/items", lens=Lens(op=LensOp.STATUS_READ))
    assert p.subject_to_typing() is False


def test_relation_broken_is_hard_invariant_and_typing_exempt():
    lens = Lens(op=LensOp.RELATION, pointer="/lines", partner_target="/inventory/items",
                partner_pointer="/items", relation="subset", field="sku")
    p = _probe(fault_shape=FaultShape.RELATION_BROKEN,
               comparison=Comparison.HARD_INVARIANT, lens=lens, cost_class=CostClass.HEAVY,
               target="/orders")
    assert p.subject_to_typing() is False
    with pytest.raises(ValueError, match="RELATION_BROKEN must use a HARD_INVARIANT"):
        _probe(fault_shape=FaultShape.RELATION_BROKEN,
               comparison=Comparison.PROOF_BASELINE, lens=lens, target="/orders")


# -- structural validation -----------------------------------------------------

def test_fault_shape_lens_mismatch_rejected():
    with pytest.raises(ValueError, match="cannot be expressed by lens"):
        _probe(fault_shape=FaultShape.STATUS_CLASS,
               lens=Lens(op=LensOp.FIELD_READ, pointer="/x"))


def test_order_changed_requires_ordered_subarray_lens():
    ok = _probe(fault_shape=FaultShape.ORDER_CHANGED,
                lens=Lens(op=LensOp.ORDERED_SUBARRAY, pointer="/results", field="sku"),
                comparison=Comparison.PROOF_BASELINE, cost_class=CostClass.MODERATE)
    assert ok.fault_shape is FaultShape.ORDER_CHANGED and ok.subject_to_typing() is True
    with pytest.raises(ValueError):
        _probe(fault_shape=FaultShape.ORDER_CHANGED,
               lens=Lens(op=LensOp.FIELD_READ, pointer="/results"))


def test_schema_shape_allows_field_read_for_field_added():
    """FIELD-ADDED on a value-watched surface = SCHEMA_SHAPE via a FIELD_READ
    lens (the v0.4 reconciliation)."""
    p = _probe(fault_shape=FaultShape.SCHEMA_SHAPE,
               lens=Lens(op=LensOp.FIELD_READ, pointer="/quote"),
               comparison=Comparison.PROOF_BASELINE)
    assert p.fault_shape is FaultShape.SCHEMA_SHAPE


def test_read_only_method_enforced():
    with pytest.raises(ValueError, match="read-only"):
        _probe(method="POST")
    assert _probe(method="head").method == "head"  # case-insensitive accept


def test_incomplete_provenance_rejected():
    with pytest.raises(ValueError, match="provenance chain is incomplete"):
        _probe(provenance=_prov(recovery_hint="   "))
    with pytest.raises(ValueError, match="provenance chain is incomplete"):
        _probe(provenance=_prov(world_fact=""))


def test_empty_target_rejected():
    with pytest.raises(ValueError, match="non-empty surface"):
        _probe(target="")


# -- lens slice validation -----------------------------------------------------

def test_lens_slice_requirements():
    with pytest.raises(ValueError, match="requires a pointer"):
        Lens(op=LensOp.FIELD_READ)
    with pytest.raises(ValueError, match="header_name"):
        Lens(op=LensOp.HEADER_READ)
    with pytest.raises(ValueError, match="relation lens requires pointer"):
        Lens(op=LensOp.RELATION, pointer="/a")  # missing partner
    with pytest.raises(ValueError, match="relation in"):
        Lens(op=LensOp.RELATION, pointer="/a", partner_target="/b",
             partner_pointer="/c", relation="bogus")


# -- evidence trust priors (data for the future corroboration layer) -----------

def test_field_shape_is_low_trust_status_is_high():
    assert EVIDENCE_TRUST_PRIOR[EvidenceClass.FIELD_SHAPE] < \
        EVIDENCE_TRUST_PRIOR[EvidenceClass.STATUS_CODED]
    assert _probe(evidence_class=EvidenceClass.FIELD_SHAPE).trust_prior() == \
        EVIDENCE_TRUST_PRIOR[EvidenceClass.FIELD_SHAPE]
    assert set(EVIDENCE_TRUST_PRIOR) == set(EvidenceClass)
