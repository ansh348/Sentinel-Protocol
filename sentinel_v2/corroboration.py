"""Probe-primary corroboration: persistence over time (design v0.4 §2.2; author
ruling D28).

DETERMINISTIC — no LLM on this path. The typing engine
(`sentinel_v2.typing_engine`) types a SINGLE observation; this layer decides, over
an ORDERED SEQUENCE of observations of one surface, whether an AMBIGUOUS signal
(non-status-coded shapeless drift the engine returned as telemetry) earns a route
to the orchestrator.

Corroboration = PERSISTENCE, not breadth. The dead v0.3 "second independent
signal" clause is retired (correlated noise self-corroborates: 6/18 false
interrupts passed it; archaeology_v2 §E.4). An ambiguous signal promotes ONLY if a
confirming re-observation of the SAME surface still shows the anomaly; a one-shot
wobble that has healed by the re-look stays telemetry.

Threshold (D28, frozen pre-data, least-latency): ONE confirming re-look — two
CONSECUTIVE anomalous observations. NO raw-count aggregation anywhere (the v1
escalation-cap pathology, 172 noise fires); this module counts nothing.

Rule Zero: the persistence logic is GENERAL and category-blind — it names no
holdout category and has no quota/version/resource-specific behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Optional, Protocol, Sequence

from sentinel_v2.probe_spec import Comparison, EvidenceClass, Probe
from sentinel_v2.probes import ProbeResult
from sentinel_v2.typing_engine import (BaselineObligations, Evaluation,
                                       Invariant, Verdict, evaluate)


class PersistenceDecision(str, Enum):
    PROMOTE = "promote"      # a confirming re-look STILL shows the anomaly
    TELEMETRY = "telemetry"  # healed by the re-look, or no confirming re-look yet


def decide_persistence(anomaly_flags: Sequence[bool]) -> PersistenceDecision:
    """The pure persistence rule (D28). `anomaly_flags` is the ordered
    "is this observation of the surface still anomalous?" sequence (oldest first).

    PROMOTE iff two CONSECUTIVE observations are anomalous — the first sighting
    plus ONE confirming re-look (the least-latency threshold, D28). Everything
    else is TELEMETRY:
      - a single observation (no re-look yet) is never promoted blind;
      - a one-shot wobble that has healed by the re-look stays telemetry;
      - intermittent wobbles that never persist across a re-look stay telemetry.

    This is ADJACENCY, not a count: it short-circuits on the first consecutive
    anomalous pair and never tallies how many wobbles occurred (D28's hard
    prohibition on raw-count aggregation — no "exceeds N" path exists here)."""
    prev = False
    for flag in anomaly_flags:
        cur = bool(flag)
        if prev and cur:
            return PersistenceDecision.PROMOTE
        prev = cur
    return PersistenceDecision.TELEMETRY


# -- C2: the corroboration layer (route a surface from its observation sequence) --
#
# This replaces the inert engine seam. Per the typing engine each observation
# yields a Verdict; this layer decides the SURFACE's route from the ORDERED
# sequence of those verdicts:
#   - any INTERRUPT verdict  -> INTERRUPT grade, on its own, no persistence
#     (clean fault-shapes, hard invariants, and the status-coded fast path);
#   - shapeless drift (TELEMETRY) that PERSISTS across a confirming re-look
#     -> CAUTION grade (D28);
#   - everything else stays telemetry (no invalidation emitted).


class Grade(str, Enum):
    INTERRUPT = "interrupt"  # hard, plan-breaking: interrupt-and-replan (fast path)
    CAUTION = "caution"      # recommended action routed to orchestrator; kept distinct


@dataclass(frozen=True)
class CorroboratedInvalidation:
    """One surface's route to the orchestrator. INTERRUPT grade is the hard path;
    CAUTION grade is a persistence-confirmed recommended action (D28). Each surface
    emits at most one of these; the layer aggregates nothing across surfaces."""
    target: str
    grade: Grade
    fault_shape: str
    evidence_class: str
    reason: str
    persistence: Optional[PersistenceDecision] = None  # set on the caution path
    witness: Any = None


@dataclass(frozen=True)
class Signal:
    """One probe plus the ORDERED observations of its surface (oldest first), with
    the comparison inputs the engine needs. `observations` come from the trace now
    and from the cadence layer's re-observations next session (§3, C3)."""
    probe: Probe
    observations: Sequence[Optional[ProbeResult]]
    baseline: Optional[ProbeResult] = None
    obligations: Optional[BaselineObligations] = None
    invariant: Optional[Invariant] = None
    partner: Optional[ProbeResult] = None


def _evaluate_each(sig: Signal) -> list[Evaluation]:
    return [evaluate(sig.probe, current=obs, baseline=sig.baseline,
                     invariant=sig.invariant, obligations=sig.obligations,
                     partner=sig.partner)
            for obs in sig.observations]


def corroborate_signal(sig: Signal) -> Optional[CorroboratedInvalidation]:
    """Decide ONE surface's route from its observation sequence. Returns an
    invalidation (INTERRUPT or CAUTION grade) or None (stays telemetry).
    Deterministic; no LLM."""
    evals = _evaluate_each(sig)
    probe = sig.probe

    # Fast path: clean fault-shapes, hard invariants, and the status-coded signal
    # all interrupt on their own — no persistence required (D28).
    for ev in evals:
        if ev.verdict is Verdict.INTERRUPT:
            return CorroboratedInvalidation(
                target=probe.target, grade=Grade.INTERRUPT,
                fault_shape=probe.fault_shape.value,
                evidence_class=probe.evidence_class.value,
                reason=ev.reason, witness=ev.witness)

    # Ambiguous path: shapeless drift is telemetry per observation; it earns a
    # CAUTION route only if it PERSISTS across a confirming re-look (§2.2). The
    # anomaly flag is exactly "the engine still sees shapeless drift on this look".
    anomaly_flags = [ev.verdict is Verdict.TELEMETRY for ev in evals]
    decision = decide_persistence(anomaly_flags)
    if decision is PersistenceDecision.PROMOTE:
        return CorroboratedInvalidation(
            target=probe.target, grade=Grade.CAUTION,
            fault_shape=probe.fault_shape.value,
            evidence_class=probe.evidence_class.value,
            reason="ambiguous drift persisted across a confirming re-observation "
                   "of the same surface (caution, D28)",
            persistence=decision)
    return None


def corroborate(signals: Iterable[Signal]) -> list[CorroboratedInvalidation]:
    """Run each surface's signal INDEPENDENTLY and emit each promoted/fast-path
    surface as a SEPARATE corroborated invalidation. Aggregates NOTHING (D28): no
    counter, no breadth threshold, no cross-surface merge. Breadth across surfaces
    is the orchestrator's existing replan decision, which sees the live cautions."""
    out: list[CorroboratedInvalidation] = []
    for sig in signals:
        inv = corroborate_signal(sig)
        if inv is not None:
            out.append(inv)
    return out


# -- C3: the re-observation interface (the cadence seam) -----------------------
#
# Corroboration needs the ORDERED observations of a surface to decide persistence.
# It pulls them through this minimal interface. Today the only source is the run
# trace (the observations already present). NEXT SESSION the event-gated cadence
# layer fills the same interface, including the guaranteed pre-completion sweep.
# Cadence SCHEDULING is a hard stop this session; corroboration only declares the
# dependency and consumes whatever observations exist.

# The named dependency on cadence (NOT built this session; design §3.1, D28):
# corroboration never promotes a surface blind. A surface with no confirming
# re-observation stays telemetry; the cadence layer's GUARANTEED PRE-COMPLETION
# SWEEP supplies a final re-look before run end so an un-re-observed load-bearing
# surface still gets its one confirming look. This module DECLARES the requirement
# only — the sweep mechanism is the next session's work.
PRE_COMPLETION_SWEEP_DEPENDENCY = (
    "cadence.pre_completion_sweep: guarantees a final re-observation of each "
    "load-bearing surface before run end (design §3.1); not built this session "
    "(D28). Until it exists, an un-re-observed surface stays telemetry, never "
    "promoted blind.")


class ReObservationSource(Protocol):
    """The minimal interface corroboration consumes re-observations through. It
    returns the ORDERED observations of a surface (oldest first). Fed from the
    trace now; filled by the cadence layer (incl. the pre-completion sweep) next
    session — corroboration is agnostic to which."""

    def observations(self, target: str) -> list[ProbeResult]: ...


class TraceReObservations:
    """A `ReObservationSource` backed by a run trace's probe side channel: pairs
    `probe_call` (method/path) with `probe_response` (status/body) by `probe_seq`
    and groups the observations by surface path, in trace order.

    Headers are not carried in the trace probe events, so reconstructed
    observations have empty headers — sufficient for status / body / shape / hash
    reads; a header-watched probe needs the live cadence source."""

    def __init__(self, events: Iterable[dict]) -> None:
        self._by_target: dict[str, list[ProbeResult]] = {}
        calls: dict[Any, tuple[str, str]] = {}
        for e in events:
            etype = e.get("event_type")
            payload = e.get("payload") or {}
            if etype == "probe_call":
                calls[payload.get("probe_seq")] = (payload.get("method", "GET"),
                                                   payload.get("path", ""))
            elif etype == "probe_response":
                seq = payload.get("probe_seq")
                if seq not in calls:
                    continue
                method, path = calls[seq]
                obs = ProbeResult(method=method, path=path,
                                  status=payload.get("status"), headers={},
                                  body=payload.get("body"))
                self._by_target.setdefault(path, []).append(obs)

    def observations(self, target: str) -> list[ProbeResult]:
        return list(self._by_target.get(target, []))


def signal_from_source(probe: Probe, source: ReObservationSource, *,
                       baseline: Optional[ProbeResult] = None,
                       obligations: Optional[BaselineObligations] = None,
                       invariant: Optional[Invariant] = None,
                       partner: Optional[ProbeResult] = None) -> Signal:
    """Build a Signal by pulling the surface's ordered observations from a
    `ReObservationSource`. A surface the source has not (yet) re-observed yields a
    short sequence — which stays telemetry, never promoted blind (the
    pre-completion-sweep dependency above is what later supplies the re-look)."""
    return Signal(probe=probe, observations=source.observations(probe.target),
                  baseline=baseline, obligations=obligations, invariant=invariant,
                  partner=partner)
