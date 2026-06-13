"""The comparison + typing engine (B3; probe_compiler_design_v0.4.md §2/§2.1).

Pure and deterministic: it consumes a compiled Probe and probe OBSERVATIONS
(sentinel_v2.probes.ProbeResult) and returns a Verdict. Two interrupt-grade
paths:

  (i)  COMPILED HARD INVARIANT — evaluated against the current observation
       alone; fires on its own with NO typing gate (Break-A, v0.4 §2/§2.1).
       A guarantee that was off from the very first observation (no clean "on"
       baseline ever existed) is still caught here.

  (ii) PROOF-OBLIGATED BASELINE — a baseline feeds an interrupt only if all
       five obligations hold (Clean/Equivalent/Stationary/Targeted/Frozen,
       §2); otherwise the comparison is DISQUALIFIED to telemetry. When the
       obligations hold, the §2.1 typing rule gates the drift: drift interrupts
       iff it instantiates the declared fault-shape OR is corroborated, else it
       is telemetry. Shapeless drift (a whole-payload content-hash difference
       that names no shape) is the bounded recall the design trades away (§0
       honesty, v0.4 A3).

Hard stops respected: corroboration is a SEAM (an input the engine honors),
never computed here; cadence and the compile prompt live elsewhere. No LLM.
Rule Zero: nothing here names a holdout category.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
from typing import Any, Optional

from sentinel_v2.probe_spec import Comparison, FaultShape, LensOp, Probe
from sentinel_v2.probes import (ProbeResult, content_sha256, ordered_subarray,
                                read_field, read_header, relation_holds,
                                schema_fingerprint)
from world.server import _MISSING, _pointer_lookup

_MISS = object()
_UNSET = object()


class Verdict(str, Enum):
    INTERRUPT = "interrupt"        # plan-breaking; escalate
    TELEMETRY = "telemetry"        # logged, low-confidence; never a raw interrupt
    CLEAN = "clean"                # invariant held / no drift
    DISQUALIFIED = "disqualified"  # baseline failed an obligation; not interrupt-grade
    INCONCLUSIVE = "inconclusive"  # probe could not complete (§5.2); certifies nothing


@dataclass(frozen=True)
class BaselineObligations:
    """The five §2(ii) obligations. These are PROVENANCE facts the compiler /
    runtime certify about how the baseline was captured — not computable from
    payload bytes — so the engine takes them as inputs and enforces them."""
    clean: bool
    equivalent: bool
    stationary: bool
    targeted: bool
    frozen: bool

    def all_hold(self) -> bool:
        return all(getattr(self, f.name) for f in fields(self))

    def failed(self) -> tuple[str, ...]:
        return tuple(f.name for f in fields(self) if not getattr(self, f.name))


@dataclass(frozen=True)
class Invariant:
    """The compiled expectation for a HARD_INVARIANT probe. Exactly the form
    matching the probe's fault-shape is set; the others stay unset."""
    status_in: Optional[tuple] = None     # STATUS_CLASS: status must be in this class
    require_present: bool = False          # FIELD_ABSENT: lens.pointer must resolve
    equals: Any = _UNSET                    # VALUE_CHANGED hard: the lens read must equal this
    fingerprint: Optional[tuple] = None    # SCHEMA_SHAPE hard: the required {key:type} shape
    relation_required: bool = False         # RELATION_BROKEN: the lens relation must hold


@dataclass(frozen=True)
class Corroboration:
    """The §2.1 corroboration SEAM. The probe-primary corroboration WIRING is a
    hard stop; the engine only honors a verdict the future layer supplies."""
    confirmed: bool


@dataclass(frozen=True)
class Evaluation:
    verdict: Verdict
    path: str                       # "hard_invariant" | "baseline_drift" | "n/a"
    typed: bool = False             # instantiated the declared fault-shape?
    corroborated: bool = False
    reason: str = ""
    witness: Any = None


# -- helpers -------------------------------------------------------------------

def _fingerprint_slice(obs: ProbeResult, pointer: Optional[str]) -> tuple:
    body = obs.body
    target = _pointer_lookup(body, pointer) if pointer else body
    if target is _MISSING:
        target = None
    return schema_fingerprint(target)


def _equals_read(probe: Probe, obs: ProbeResult) -> Any:
    lens = probe.lens
    if lens.op is LensOp.HEADER_READ:
        return read_header(obs, lens.header_name)
    if lens.pointer:
        return read_field(obs, lens.pointer, default=_MISS)
    return obs.body


def _drift_instantiates_shape(probe: Probe, baseline: ProbeResult,
                              current: ProbeResult) -> bool:
    """Does the baseline→current drift, read through the probe's lens, instantiate
    the declared fault-shape? A whole-payload CONTENT_HASH difference is SHAPELESS
    by construction (it names no shape) and never instantiates one — that is the
    bounded recall §0/A3 trades for noise protection."""
    shape, lens = probe.fault_shape, probe.lens
    if lens.op is LensOp.CONTENT_HASH:
        return False
    if shape is FaultShape.FIELD_ABSENT:
        b = read_field(baseline, lens.pointer, default=_MISS)
        c = read_field(current, lens.pointer, default=_MISS)
        return b is not _MISS and c is _MISS
    if shape is FaultShape.VALUE_CHANGED:
        if lens.op is LensOp.HEADER_READ:
            return read_header(baseline, lens.header_name) != \
                read_header(current, lens.header_name)
        b = read_field(baseline, lens.pointer, default=_MISS)
        c = read_field(current, lens.pointer, default=_MISS)
        return b is not _MISS and c is not _MISS and b != c
    if shape is FaultShape.SCHEMA_SHAPE:
        return _fingerprint_slice(baseline, lens.pointer) != \
            _fingerprint_slice(current, lens.pointer)
    if shape is FaultShape.ORDER_CHANGED:
        return ordered_subarray(baseline, lens.pointer, field=lens.field) != \
            ordered_subarray(current, lens.pointer, field=lens.field)
    if shape is FaultShape.STATUS_CLASS:
        return baseline.status != current.status
    return False


def _any_difference(probe: Probe, baseline: ProbeResult,
                    current: ProbeResult) -> bool:
    if probe.lens.op is LensOp.CONTENT_HASH:
        return content_sha256(baseline) != content_sha256(current)
    return _drift_instantiates_shape(probe, baseline, current)


# -- the two paths -------------------------------------------------------------

def evaluate_hard_invariant(probe: Probe, current: Optional[ProbeResult],
                            invariant: Invariant, *,
                            partner: Optional[ProbeResult] = None) -> Evaluation:
    """§2(i): evaluate the compiled invariant against the current observation
    alone. Fires on its own — NO typing gate, NO baseline (Break-A)."""
    if current is None:
        return Evaluation(Verdict.INCONCLUSIVE, "hard_invariant",
                          reason="probe did not complete (§5.2)")
    lens = probe.lens

    if invariant.status_in is not None and current.status not in invariant.status_in:
        return Evaluation(Verdict.INTERRUPT, "hard_invariant", typed=True,
                          reason=f"status {current.status} left compiled class "
                                 f"{list(invariant.status_in)}",
                          witness=current.status)
    if invariant.require_present:
        if read_field(current, lens.pointer, default=_MISS) is _MISS:
            return Evaluation(Verdict.INTERRUPT, "hard_invariant", typed=True,
                              reason=f"required field {lens.pointer} absent",
                              witness=lens.pointer)
    if invariant.fingerprint is not None:
        got = _fingerprint_slice(current, lens.pointer)
        if got != tuple(invariant.fingerprint):
            return Evaluation(Verdict.INTERRUPT, "hard_invariant", typed=True,
                              reason="schema shape left its compiled form",
                              witness=got)
    if invariant.equals is not _UNSET:
        got = _equals_read(probe, current)
        if got != invariant.equals:
            return Evaluation(Verdict.INTERRUPT, "hard_invariant", typed=True,
                              reason=f"value left compiled invariant "
                                     f"(expected {invariant.equals!r}, got {got!r})",
                              witness=got)
    if invariant.relation_required:
        if partner is None:
            return Evaluation(Verdict.INCONCLUSIVE, "hard_invariant",
                              reason="relation invariant needs a partner observation")
        join = relation_holds(current, lens.pointer, partner, lens.partner_pointer,
                              left_field=lens.field, right_field=lens.partner_field,
                              relation=lens.relation)
        if not join.holds:
            return Evaluation(Verdict.INTERRUPT, "hard_invariant", typed=True,
                              reason=f"cross-surface {lens.relation} relation broke",
                              witness=join.left_only or join.right_only)

    return Evaluation(Verdict.CLEAN, "hard_invariant")


def evaluate_baseline_drift(probe: Probe, baseline: Optional[ProbeResult],
                            current: Optional[ProbeResult],
                            obligations: BaselineObligations, *,
                            corroboration: Optional[Corroboration] = None) -> Evaluation:
    """§2(ii) + §2.1: enforce the five obligations, then type the drift."""
    if current is None or baseline is None:
        return Evaluation(Verdict.INCONCLUSIVE, "baseline_drift",
                          reason="probe did not complete (§5.2)")
    if not obligations.all_hold():
        failed = obligations.failed()
        return Evaluation(Verdict.DISQUALIFIED, "baseline_drift",
                          reason=f"baseline failed obligation(s): {', '.join(failed)}"
                                 " — not interrupt-grade (a dirty baseline certifies "
                                 "the mutated world as normal)",
                          witness=failed)

    if _drift_instantiates_shape(probe, baseline, current):
        return Evaluation(Verdict.INTERRUPT, "baseline_drift", typed=True,
                          reason=f"drift instantiates {probe.fault_shape.value}")
    if not _any_difference(probe, baseline, current):
        return Evaluation(Verdict.CLEAN, "baseline_drift")
    # shapeless drift: telemetry unless an independent probe corroborates (§2.1)
    if corroboration is not None and corroboration.confirmed:
        return Evaluation(Verdict.INTERRUPT, "baseline_drift", typed=False,
                          corroborated=True,
                          reason="shapeless drift corroborated by an independent probe")
    return Evaluation(Verdict.TELEMETRY, "baseline_drift",
                      reason="drift maps to no fault-shape and is uncorroborated "
                             "(the bounded recall §0/A3 trades for noise protection)")


def evaluate(probe: Probe, *, current: Optional[ProbeResult],
             baseline: Optional[ProbeResult] = None,
             invariant: Optional[Invariant] = None,
             obligations: Optional[BaselineObligations] = None,
             corroboration: Optional[Corroboration] = None,
             partner: Optional[ProbeResult] = None) -> Evaluation:
    """Dispatch on the probe's comparison path."""
    if probe.comparison is Comparison.HARD_INVARIANT:
        if invariant is None:
            raise ValueError("a HARD_INVARIANT probe requires a compiled Invariant")
        return evaluate_hard_invariant(probe, current, invariant, partner=partner)
    if obligations is None:
        raise ValueError("a PROOF_BASELINE probe requires BaselineObligations")
    return evaluate_baseline_drift(probe, baseline, current, obligations,
                                   corroboration=corroboration)
