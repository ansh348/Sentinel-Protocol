"""B4 acceptance: the attachment-policy evaluator (probe_compiler_design_v0.4.md
§3). Gate order, the §3.1 predicate, §1.1 lens selection, and the §3.2
self-reobserving-but-non-self-validating surface earning a probe.
"""
from __future__ import annotations

import pytest

from sentinel_v2.attachment import (Assumption, AssumptionKind, Disposition,
                                    evaluate_attachment)
from sentinel_v2.probe_spec import (Comparison, FaultShape, LensOp, Provenance)


def _prov(complete: bool = True) -> Provenance:
    return Provenance(plan_step="s", world_fact="f", surface="/x",
                      read="r", predicate="p",
                      recovery_hint="h" if complete else "")


def _assume(kind: AssumptionKind, **o) -> Assumption:
    base = dict(assumption_id="a1", kind=kind, surface="/pricing/quote/WID-001",
                provenance=_prov(), truth_carried_by_ordinary_traffic=False)
    base.update(o)
    return Assumption(**base)


# -- gate order ----------------------------------------------------------------

def test_write_set_gate_wins_first():
    """A surface in the global planned write-set is FOOTPRINT-scoped (D31) — not an
    active drift probe (it legitimately drifts) and not silently passive — even with
    complete provenance and a non-self-revealing surface."""
    a = _assume(AssumptionKind.VALUE, surface="/repo/files/config/settings.yaml",
                pointer="/content")
    d = evaluate_attachment(a, planned_write_set=("/repo/files/*",))
    assert d.disposition is Disposition.WRITE_FOOTPRINT and "footprint" in d.reason
    assert d.probe is None
    # write-footprint beats an incomplete provenance too (ordering check)
    a2 = _assume(AssumptionKind.VALUE, surface="/repo/files/x", pointer="/c",
                 provenance=_prov(complete=False))
    assert evaluate_attachment(a2, planned_write_set=("/repo/files/*",)).disposition \
        is Disposition.WRITE_FOOTPRINT


def test_incomplete_provenance_is_telemetry_only():
    a = _assume(AssumptionKind.VALUE, pointer="/unit_price",
                provenance=_prov(complete=False))
    d = evaluate_attachment(a)
    assert d.disposition is Disposition.TELEMETRY_ONLY and d.probe is None


def test_self_revealing_surface_is_passive():
    a = _assume(AssumptionKind.STATUS, truth_carried_by_ordinary_traffic=True)
    d = evaluate_attachment(a)
    assert d.disposition is Disposition.PASSIVE and "ordinary" in d.reason


# -- §3.2: self-reobserving but non-self-validating earns a probe --------------

def test_enforcing_gate_earns_a_probe():
    """The §3.2 class: the gate keeps answering (self-reobserving) while whether
    it ENFORCES is not carried by that traffic (non-self-validating). It must
    earn a probe — a GATE_SHADOW probe."""
    a = _assume(AssumptionKind.GATE, surface="/repo/validate", pointer="/enforcing",
                truth_carried_by_ordinary_traffic=False)
    d = evaluate_attachment(a)
    assert d.disposition is Disposition.ATTACH
    assert d.probe.lens.op is LensOp.GATE_SHADOW
    assert d.probe.comparison is Comparison.HARD_INVARIANT
    assert d.probe.subject_to_typing() is False  # fires on its own


# -- §1.1 lens / granularity selection -----------------------------------------

def test_lens_selection_value():
    d = evaluate_attachment(_assume(AssumptionKind.VALUE, pointer="/unit_price"))
    assert d.disposition is Disposition.ATTACH
    assert d.probe.lens.op is LensOp.FIELD_READ
    assert d.probe.fault_shape is FaultShape.VALUE_CHANGED
    assert d.probe.comparison is Comparison.PROOF_BASELINE
    assert d.probe.subject_to_typing() is True


def test_lens_selection_order():
    d = evaluate_attachment(_assume(AssumptionKind.ORDER, surface="/docs/search",
                                    pointer="/results", field="id"))
    assert d.probe.lens.op is LensOp.ORDERED_SUBARRAY
    assert d.probe.fault_shape is FaultShape.ORDER_CHANGED


def test_lens_selection_relation():
    d = evaluate_attachment(_assume(
        AssumptionKind.RELATION, surface="/orders", pointer="/lines", field="sku",
        partner_target="/inventory/items", partner_pointer="/items",
        partner_field="sku", relation="subset"))
    assert d.probe.lens.op is LensOp.RELATION
    assert d.probe.fault_shape is FaultShape.RELATION_BROKEN
    assert d.probe.comparison is Comparison.HARD_INVARIANT


def test_lens_selection_structure_status_presence_whole_payload():
    structure = evaluate_attachment(_assume(AssumptionKind.STRUCTURE)).probe
    assert structure.lens.op is LensOp.SCHEMA_FINGERPRINT
    assert structure.fault_shape is FaultShape.SCHEMA_SHAPE

    status = evaluate_attachment(_assume(AssumptionKind.STATUS)).probe
    assert status.lens.op is LensOp.STATUS_READ
    assert status.comparison is Comparison.HARD_INVARIANT

    presence = evaluate_attachment(_assume(AssumptionKind.PRESENCE,
                                           pointer="/unit_price")).probe
    assert presence.fault_shape is FaultShape.FIELD_ABSENT
    assert presence.comparison is Comparison.HARD_INVARIANT

    whole = evaluate_attachment(_assume(AssumptionKind.WHOLE_PAYLOAD)).probe
    assert whole.lens.op is LensOp.CONTENT_HASH


# -- relation read-and-trust spans both surfaces -------------------------------

def test_relation_partner_in_write_set_is_footprint_scoped():
    a = _assume(AssumptionKind.RELATION, surface="/orders", pointer="/lines",
                field="sku", partner_target="/repo/files/index",
                partner_pointer="/items", partner_field="sku", relation="subset")
    d = evaluate_attachment(a, planned_write_set=("/repo/files/*",))
    assert d.disposition is Disposition.WRITE_FOOTPRINT and "footprint" in d.reason
