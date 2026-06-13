"""The compiled-probe spec and the ontology-general fault-shape vocabulary
(B2; probe_compiler_design_v0.4.md §1, §2, §2.1).

A `Probe` is the deterministic, zero-LLM description the compiler emits and the
runtime executes — distinct from `sentinel_v2.probes`, which holds the read
PRIMITIVES a probe's lens invokes. This module is pure vocabulary + validation:
no compilation (what to probe — D4, hard stop), no corroboration (what an
anomalous read means — hard stop), no cadence semantics (when to sweep — hard
stop). The cadence_hint and evidence-trust priors are carried as DATA for those
future judgment layers; nothing here consumes them.

Rule Zero: every shape, lens, and class below is ontology-general. The fault
shapes name no holdout category; the lenses are generic extraction ops.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
from typing import Optional


# -- the six general fault-shapes (design v0.4 §2.1) ---------------------------
#
# FIELD-ADDED is represented as SCHEMA_SHAPE (an added {key:type} pair),
# including on value-watched surfaces, per the v0.4 count-reconciliation note
# (six enum members, not seven). If the author later prefers a distinct
# FIELD_ADDED member it is a one-line addition here.

class FaultShape(str, Enum):
    FIELD_ABSENT = "field_absent"        # a present, load-bearing field is now absent
    STATUS_CLASS = "status_class"        # a status left its compiled class
    SCHEMA_SHAPE = "schema_shape"        # {key:type} set changed (incl. field-added)
    VALUE_CHANGED = "value_changed"      # read-trusted value changed on a stationary surface
    ORDER_CHANGED = "order_changed"      # order/sequence of a load-bearing array changed
    RELATION_BROKEN = "relation_broken"  # a cross-surface relation broke


class Comparison(str, Enum):
    HARD_INVARIANT = "hard_invariant"    # §2(i): auditable ex ante; fires on its own
    PROOF_BASELINE = "proof_baseline"    # §2(ii): drift from a proof-obligated baseline


class LensOp(str, Enum):
    STATUS_READ = "status_read"
    FIELD_READ = "field_read"
    HEADER_READ = "header_read"
    SCHEMA_FINGERPRINT = "schema_fingerprint"
    CONTENT_HASH = "content_hash"
    ORDERED_SUBARRAY = "ordered_subarray"   # B1 order-sensitive lens
    RELATION = "relation"                   # B1 cross-surface lens
    GATE_SHADOW = "gate_shadow"             # §4 enforcement re-read (wired in B5)


class EvidenceClass(str, Enum):
    STATUS_CODED = "status_coded"
    CONTENT_SHAPED = "content_shaped"
    FIELD_SHAPE = "field_shape"           # v1's false-interrupt engine: low trust prior
    COUNTER = "counter"


class CostClass(str, Enum):
    LIGHT = "light"        # a single field / header / status read
    MODERATE = "moderate"  # a whole-payload fingerprint / hash / ordered sub-array
    HEAVY = "heavy"        # a cross-surface relation (two or more reads)


class CadenceHint(str, Enum):
    """A HINT for the future event-gated cadence layer (semantics are a hard
    stop this session). Carried, never interpreted here."""
    ON_DEMAND = "on_demand"
    EVENT_GATED = "event_gated"
    PRE_COMPLETION = "pre_completion"   # the guaranteed pre-completion sweep


# Trust priors for the future corroboration layer (design §1). DATA only — no
# corroboration logic is built this session. field-shape starts low (v1's
# 14/18 false-interrupt engine); a status from a compiled class is trusted high.
EVIDENCE_TRUST_PRIOR: dict[EvidenceClass, float] = {
    EvidenceClass.STATUS_CODED: 0.9,
    EvidenceClass.CONTENT_SHAPED: 0.7,
    EvidenceClass.COUNTER: 0.6,
    EvidenceClass.FIELD_SHAPE: 0.3,
}

# Which lens ops can express each fault-shape (structural validity).
_SHAPE_LENS_OPS: dict[FaultShape, frozenset] = {
    FaultShape.FIELD_ABSENT: frozenset({LensOp.FIELD_READ, LensOp.SCHEMA_FINGERPRINT}),
    FaultShape.STATUS_CLASS: frozenset({LensOp.STATUS_READ}),
    # SCHEMA_SHAPE carries FIELD_READ so a value-watched probe can also fingerprint
    # the watched object and catch a field ADDED beside the watched value (§1.1).
    FaultShape.SCHEMA_SHAPE: frozenset({LensOp.SCHEMA_FINGERPRINT, LensOp.FIELD_READ}),
    FaultShape.VALUE_CHANGED: frozenset({LensOp.FIELD_READ, LensOp.HEADER_READ,
                                         LensOp.CONTENT_HASH, LensOp.GATE_SHADOW}),
    FaultShape.ORDER_CHANGED: frozenset({LensOp.ORDERED_SUBARRAY}),
    FaultShape.RELATION_BROKEN: frozenset({LensOp.RELATION}),
}

# Fault-shapes whose interrupt is exempt from the §2.1 transition-typing rule
# because they have no single-surface clean baseline and fire on their own.
TYPING_EXEMPT_SHAPES: frozenset = frozenset({FaultShape.RELATION_BROKEN})

_READ_METHODS = frozenset({"GET", "HEAD"})


@dataclass(frozen=True)
class Lens:
    """The extraction op and the SLICE it covers (design §1.1). Op-specific
    slice fields are validated below; unused fields stay None."""
    op: LensOp
    pointer: Optional[str] = None         # slice within `target` (pointer dialect)
    field: Optional[str] = None           # element projection (ordered / relation)
    header_name: Optional[str] = None     # HEADER_READ
    partner_target: Optional[str] = None  # second surface for RELATION
    partner_pointer: Optional[str] = None
    partner_field: Optional[str] = None
    relation: Optional[str] = None        # "subset" | "equal" for RELATION

    def __post_init__(self) -> None:
        op = self.op
        if op in (LensOp.FIELD_READ, LensOp.ORDERED_SUBARRAY) and not self.pointer:
            raise ValueError(f"lens {op.value} requires a pointer slice")
        if op is LensOp.HEADER_READ and not self.header_name:
            raise ValueError("header_read lens requires header_name")
        if op is LensOp.RELATION:
            if not (self.pointer and self.partner_target and self.partner_pointer):
                raise ValueError("relation lens requires pointer, partner_target, "
                                 "and partner_pointer")
            if self.relation not in ("subset", "equal"):
                raise ValueError("relation lens requires relation in {subset, equal}")


@dataclass(frozen=True)
class Provenance:
    """The §3.3 dependency chain justifying a probe. Every link must be present
    for the probe to be interrupt-grade; a missing link ⇒ telemetry only."""
    plan_step: str        # the plan step that depends on the fact
    world_fact: str       # the required world fact
    surface: str          # the observable surface
    read: str             # the deterministic read
    predicate: str        # the comparison predicate
    recovery_hint: str    # the recovery move on violation

    def is_complete(self) -> bool:
        return all(str(getattr(self, f.name)).strip() for f in fields(self))


@dataclass(frozen=True)
class Probe:
    """A compiled probe (design §1 schema). Validates structural well-formedness
    only; attachment (B4), comparison/typing (B3), and the §4 route (B5) live in
    their own modules."""
    method: str
    target: str
    lens: Lens
    comparison: Comparison
    fault_shape: FaultShape
    evidence_class: EvidenceClass
    cost_class: CostClass
    cadence_hint: CadenceHint
    provenance: Provenance

    def __post_init__(self) -> None:
        if self.method.upper() not in _READ_METHODS:
            raise ValueError(f"probe method must be read-only {sorted(_READ_METHODS)};"
                             f" got {self.method!r}")
        if not self.target or not str(self.target).strip():
            raise ValueError("probe target must be a non-empty surface path")
        allowed = _SHAPE_LENS_OPS[self.fault_shape]
        if self.lens.op not in allowed:
            raise ValueError(
                f"fault_shape {self.fault_shape.value} cannot be expressed by lens "
                f"{self.lens.op.value}; allowed: {sorted(o.value for o in allowed)}")
        # RELATION_BROKEN has no single-surface baseline: it is a hard invariant
        # (the relation predicate), evaluated directly and exempt from typing.
        if self.fault_shape is FaultShape.RELATION_BROKEN \
                and self.comparison is not Comparison.HARD_INVARIANT:
            raise ValueError("RELATION_BROKEN must use a HARD_INVARIANT comparison "
                             "(it has no single-surface baseline)")
        if not self.provenance.is_complete():
            raise ValueError("probe provenance chain is incomplete; an interrupt-"
                             "grade probe needs plan_step→world_fact→surface→read→"
                             "predicate→recovery_hint (design §3.3)")

    def subject_to_typing(self) -> bool:
        """The §2.1 typing rule gates the DRIFT path ONLY (Break-A, v0.4 §2.1).
        Compiled hard invariants — and RELATION_BROKEN, which is always one —
        fire on their own."""
        return (self.comparison is Comparison.PROOF_BASELINE
                and self.fault_shape not in TYPING_EXEMPT_SHAPES)

    def trust_prior(self) -> float:
        """The evidence-class trust prior (data for the future corroboration
        layer; design §1). Not consumed here."""
        return EVIDENCE_TRUST_PRIOR[self.evidence_class]
