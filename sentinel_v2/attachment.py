"""The attachment-policy evaluator (B4; probe_compiler_design_v0.4.md §3).

Pure and deterministic: given an assumption (its surface, provenance, and the
§3.1 self-revelation property) and the GLOBAL planned write-set, decide whether
to ATTACH a compiled probe, leave the surface PASSIVE, or watch it
TELEMETRY_ONLY. On ATTACH it also performs §1.1 lens/granularity selection and
returns the compiled Probe skeleton.

Gate order (each gate is a hard precondition for the next):
  1. read-and-trust (§3.3 + A4): a surface ANY worker is planned to write per
     the global write-set legitimately drifts — a frozen baseline would fire on
     the plan's own intended work — so it is not probed (PASSIVE).
  2. provenance (§3.3): an incomplete plan-step→…→recovery_hint chain is not
     interrupt-grade ⇒ TELEMETRY_ONLY.
  3. self-revelation (§3.1, A6): if the assumption's truth is carried by the
     surface's ordinary worker-visible traffic, the worker's own calls reveal a
     violation ⇒ PASSIVE, no probe needed.
  4. otherwise ATTACH, selecting the narrowest lens that covers the assumption.

No compilation of WHAT to probe from raw plan text (that is the LLM compile
prompt, a hard stop): the assumption is supplied already extracted. Rule Zero:
the kinds and lenses are ontology-general; none names a holdout category.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fnmatch import fnmatchcase
from typing import Optional

from sentinel_v2.probe_spec import (CadenceHint, Comparison, CostClass,
                                    EvidenceClass, FaultShape, Lens, LensOp,
                                    Probe, Provenance)


class AssumptionKind(str, Enum):
    """The general shape of what an assumption pins (drives §1.1 lens choice)."""
    VALUE = "value"                 # a specific field value
    STRUCTURE = "structure"         # a {key:type} shape
    ORDER = "order"                 # the order of a load-bearing array
    RELATION = "relation"           # a cross-surface relation
    PRESENCE = "presence"           # a required field's presence
    STATUS = "status"               # a compiled status class
    WHOLE_PAYLOAD = "whole_payload" # whole-payload integrity
    GATE = "gate"                   # a downstream gate is actually enforcing


class Disposition(str, Enum):
    ATTACH = "attach"
    PASSIVE = "passive"
    TELEMETRY_ONLY = "telemetry_only"
    WRITE_FOOTPRINT = "write_footprint"     # D31: a planned-write surface, footprint-scoped


@dataclass(frozen=True)
class _LensSpec:
    op: LensOp
    fault_shape: FaultShape
    comparison: Comparison
    cost_class: CostClass
    evidence_class: EvidenceClass
    cadence_hint: CadenceHint


# §1.1 lens/granularity selection, ontology-general. The narrowest lens that
# covers each assumption kind, with its comparison path, cost, evidence class
# (field-shape is v1's low-trust class), and a cadence hint (data only).
_KIND_LENS: dict[AssumptionKind, _LensSpec] = {
    AssumptionKind.VALUE: _LensSpec(
        LensOp.FIELD_READ, FaultShape.VALUE_CHANGED, Comparison.PROOF_BASELINE,
        CostClass.LIGHT, EvidenceClass.FIELD_SHAPE, CadenceHint.EVENT_GATED),
    AssumptionKind.STRUCTURE: _LensSpec(
        LensOp.SCHEMA_FINGERPRINT, FaultShape.SCHEMA_SHAPE, Comparison.PROOF_BASELINE,
        CostClass.MODERATE, EvidenceClass.CONTENT_SHAPED, CadenceHint.EVENT_GATED),
    AssumptionKind.ORDER: _LensSpec(
        LensOp.ORDERED_SUBARRAY, FaultShape.ORDER_CHANGED, Comparison.PROOF_BASELINE,
        CostClass.MODERATE, EvidenceClass.CONTENT_SHAPED, CadenceHint.EVENT_GATED),
    AssumptionKind.RELATION: _LensSpec(
        LensOp.RELATION, FaultShape.RELATION_BROKEN, Comparison.HARD_INVARIANT,
        CostClass.HEAVY, EvidenceClass.CONTENT_SHAPED, CadenceHint.EVENT_GATED),
    AssumptionKind.PRESENCE: _LensSpec(
        LensOp.FIELD_READ, FaultShape.FIELD_ABSENT, Comparison.HARD_INVARIANT,
        CostClass.LIGHT, EvidenceClass.FIELD_SHAPE, CadenceHint.EVENT_GATED),
    AssumptionKind.STATUS: _LensSpec(
        LensOp.STATUS_READ, FaultShape.STATUS_CLASS, Comparison.HARD_INVARIANT,
        CostClass.LIGHT, EvidenceClass.STATUS_CODED, CadenceHint.EVENT_GATED),
    AssumptionKind.WHOLE_PAYLOAD: _LensSpec(
        LensOp.CONTENT_HASH, FaultShape.VALUE_CHANGED, Comparison.PROOF_BASELINE,
        CostClass.MODERATE, EvidenceClass.CONTENT_SHAPED, CadenceHint.PRE_COMPLETION),
    AssumptionKind.GATE: _LensSpec(
        LensOp.GATE_SHADOW, FaultShape.VALUE_CHANGED, Comparison.HARD_INVARIANT,
        CostClass.LIGHT, EvidenceClass.STATUS_CODED, CadenceHint.PRE_COMPLETION),
}


@dataclass(frozen=True)
class Assumption:
    """An already-extracted plan assumption and the surface it depends on. The
    slice fields populate the selected lens; only those the kind needs are used."""
    assumption_id: str
    kind: AssumptionKind
    surface: str
    provenance: Provenance
    # §3.1 (A6): is the assumption's truth carried by the surface's ordinary
    # worker-visible traffic? A self-reobserving-but-non-self-validating surface
    # (§3.2: the gate still answers 200 while not enforcing) is False here.
    truth_carried_by_ordinary_traffic: bool
    pointer: Optional[str] = None
    field: Optional[str] = None
    header_name: Optional[str] = None
    partner_target: Optional[str] = None
    partner_pointer: Optional[str] = None
    partner_field: Optional[str] = None
    relation: Optional[str] = None


@dataclass(frozen=True)
class AttachmentDecision:
    disposition: Disposition
    reason: str
    probe: Optional[Probe] = None


def _written(surface: str, write_set) -> bool:
    return any(fnmatchcase(surface, pat) for pat in write_set)


def _build_lens(a: Assumption, spec: _LensSpec) -> Lens:
    return Lens(op=spec.op, pointer=a.pointer, field=a.field,
                header_name=a.header_name, partner_target=a.partner_target,
                partner_pointer=a.partner_pointer, partner_field=a.partner_field,
                relation=a.relation)


def evaluate_attachment(assumption: Assumption, *, planned_write_set=()) -> AttachmentDecision:
    """Decide attach / passive / telemetry-only for one assumption."""
    write_set = tuple(planned_write_set)

    # 1. write-footprint gate (D31, replacing the old §3.3/A4 read-and-trust gate).
    #    A surface ANY worker is planned to write legitimately drifts — a frozen
    #    baseline would fire on the plan's own intended work — so it is NOT compiled
    #    as an ordinary active drift probe. But it is NOT silently PASSIVE either:
    #    it is FOOTPRINT-SCOPED (off-footprint monitored, in-footprint
    #    verify-or-UNCOVERED_CAUTION; loud, scored by C7). For a relation, EITHER
    #    surface being written routes the join here.
    surfaces = [assumption.surface]
    if assumption.kind is AssumptionKind.RELATION and assumption.partner_target:
        surfaces.append(assumption.partner_target)
    written = [s for s in surfaces if _written(s, write_set)]
    if written:
        return AttachmentDecision(
            Disposition.WRITE_FOOTPRINT,
            reason=f"surface(s) {written} in the global planned write-set; "
                   "footprint-scoped, not silently passive (D31)")

    # 2. provenance gate (§3.3)
    if not assumption.provenance.is_complete():
        return AttachmentDecision(
            Disposition.TELEMETRY_ONLY,
            reason="incomplete provenance chain (§3.3) — watch, never interrupt")

    # 3. §3.1 self-revelation predicate (A6)
    if assumption.truth_carried_by_ordinary_traffic:
        return AttachmentDecision(
            Disposition.PASSIVE,
            reason="truth carried by the surface's ordinary worker-visible "
                   "traffic (§3.1) — passive predicate matching suffices")

    # 4. ATTACH with §1.1 lens selection
    spec = _KIND_LENS[assumption.kind]
    probe = Probe(method="GET", target=assumption.surface,
                  lens=_build_lens(assumption, spec),
                  comparison=spec.comparison, fault_shape=spec.fault_shape,
                  evidence_class=spec.evidence_class, cost_class=spec.cost_class,
                  cadence_hint=spec.cadence_hint, provenance=assumption.provenance)
    return AttachmentDecision(
        Disposition.ATTACH, probe=probe,
        reason="load-bearing (complete provenance), read-and-trust, and not "
               "self-revealing — earns a compiled probe")
