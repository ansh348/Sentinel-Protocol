"""Barrier hierarchy + freshness + relation coverage
(decisions/cadence_semantics.md §9, §6, §10; D29). DETERMINISTIC, category-blind.

Replaces the single global pre-completion sweep with a hierarchy that closes the
ledger for exactly what each barrier consumes, timed correctly:
  worker barrier (before each worker returns) → shard → relation → global output.
The union of per-worker barrier surfaces equals the load-bearing set, so this is the
same total coverage cost as one global sweep, timed so an early-finishing worker is
not missed.

Freshness (§6): a surface is OBSERVED_FRESH for an assumption only if a sufficient
observation exists AFTER the last consume-affecting point. Call-count "seen recently"
cannot waive a barrier. Relation coverage (§10): a relation is covered only by a
consistent snapshot (all sides within one bounded window), else UNCOVERED for that
relation even when each side is individually fresh.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from sentinel_v2.cadence.harvest import monitored_region_present
from sentinel_v2.cadence.ledger import CoverageLedger, TerminalState
from sentinel_v2.cadence.workatrisk import BLOCKING_THRESHOLD
from sentinel_v2.probe_spec import Lens
from sentinel_v2.probes import ProbeResult

# VERIFIED at C3 (decisions/cadence_semantics.md §10 VERIFY): the soft-assumption
# compile format (sentinel_v2.compile_probes.SoftAssumption) carries no partner-surface
# field, and compile_pipeline never builds a RELATION_BROKEN probe — so the substrate
# UNDER-EMITS relation probes (the known compile-prompt §9.1 weakness). Per D29 this is
# NOT patched; it is a measured residual named in threats to validity (§21). A relation
# assumption supplied to the cadence layer is still a first-class coverage object and is
# accounted here; the gap is purely upstream emission.
RELATION_UNDER_EMISSION_RESIDUAL = (
    "compiler under-emits relations: SoftAssumption has no partner-surface field, so "
    "RELATION_BROKEN probes are not compiled (compile-prompt §9.1). Measured residual, "
    "not patched (D29 §10/§21).")


@dataclass(frozen=True)
class Observation:
    """One re-observation positioned on the run's monotonic tick line (call count)."""
    tick: int
    result: ProbeResult
    obs_id: str = ""


@dataclass(frozen=True)
class CoverageSpec:
    """What a barrier must close for one load-bearing assumption."""
    assumption_id: str
    surface_id: str
    lens: Lens
    last_consume_affecting_tick: int
    work_at_risk: float = 0.0
    # relation coverage object (§10):
    is_relation: bool = False
    partner_surface_id: Optional[str] = None
    relation_window: int = 1            # max tick gap between sides for one snapshot


Timelines = dict          # surface_id -> list[Observation]
ReObserve = Callable[[str], Optional[Observation]]   # surface_id -> a fresh observation


def fresh_observation(spec: CoverageSpec, timeline: Sequence[Observation]
                      ) -> Optional[Observation]:
    """The freshness rule (§6): the latest SUFFICIENT observation strictly AFTER the
    last consume-affecting point. Recency by call-count cannot waive it — an
    observation at tick <= the consume point is stale however recent it is."""
    fresh = [o for o in timeline
             if o.tick > spec.last_consume_affecting_tick
             and monitored_region_present(o.result, spec.lens)]
    return max(fresh, key=lambda o: o.tick) if fresh else None


def had_stale_observation(spec: CoverageSpec, timeline: Sequence[Observation]) -> bool:
    return any(o.tick <= spec.last_consume_affecting_tick
              and monitored_region_present(o.result, spec.lens) for o in timeline)


def relation_consistent_snapshot(spec: CoverageSpec, timelines: Timelines
                                 ) -> Optional[tuple[Observation, Observation]]:
    """A relation is covered only by a CONSISTENT SNAPSHOT: both sides observed within
    one bounded window (|tick_left - tick_right| <= relation_window), both fresh. Two
    sides fresh at different times is false confidence (§10)."""
    left = [o for o in timelines.get(spec.surface_id, [])
            if o.tick > spec.last_consume_affecting_tick]
    right = [o for o in timelines.get(spec.partner_surface_id, [])
             if o.tick > spec.last_consume_affecting_tick]
    best = None
    for lo in left:
        for ro in right:
            if abs(lo.tick - ro.tick) <= spec.relation_window:
                if best is None or (lo.tick + ro.tick) > (best[0].tick + best[1].tick):
                    best = (lo, ro)
    return best


def _route_uncovered(ledger: CoverageLedger, spec: CoverageSpec) -> None:
    state = (TerminalState.UNCOVERED_BLOCKING if spec.work_at_risk > BLOCKING_THRESHOLD
             else TerminalState.UNCOVERED_CAUTION)
    ledger.mark(spec.assumption_id, state)


def close_specs(ledger: CoverageLedger, specs: Sequence[CoverageSpec],
                timelines: Timelines, *, reobserve: Optional[ReObserve] = None) -> None:
    """Close each spec's ledger entry against the available timeline; if no fresh
    sufficient observation exists, attempt one re-observation via `reobserve` (the
    barrier's own look, fresh by construction); else route UNCOVERED (blocking above
    the work-at-risk threshold, else caution). Skips already-terminal entries so an
    outer barrier never reopens what an inner one closed."""
    for spec in specs:
        if ledger.entry(spec.assumption_id).is_terminal:
            continue
        if spec.is_relation:
            snap = relation_consistent_snapshot(spec, timelines)
            if snap is not None:
                ledger.mark(spec.assumption_id, TerminalState.OBSERVED_FRESH,
                            observation_id=f"rel@{snap[0].tick}+{snap[1].tick}")
            else:
                _route_uncovered(ledger, spec)
            continue
        timeline = list(timelines.get(spec.surface_id, []))
        fresh = fresh_observation(spec, timeline)
        if fresh is None and reobserve is not None:
            ro = reobserve(spec.surface_id)
            if ro is not None:
                timeline.append(ro)
                fresh = ro
        if fresh is not None:
            state = (TerminalState.OBSERVED_STALE_BUT_RECHECKED
                     if had_stale_observation(spec, timeline)
                     else TerminalState.OBSERVED_FRESH)
            ledger.mark(spec.assumption_id, state,
                        observation_id=fresh.obs_id or f"obs@{fresh.tick}")
        else:
            _route_uncovered(ledger, spec)


@dataclass
class WorkerPlan:
    worker_id: str
    specs: list[CoverageSpec]
    barrier_tick: int                       # the worker's own return point


def run_barrier_hierarchy(ledger: CoverageLedger, workers: Sequence[WorkerPlan], *,
                          relation_specs: Sequence[CoverageSpec] = (),
                          global_specs: Sequence[CoverageSpec] = (),
                          timelines: Optional[Timelines] = None,
                          reobserve: Optional[ReObserve] = None) -> None:
    """Worker barriers first (each closes its own output-dependency surfaces before the
    worker returns — an early-finishing worker is not missed by a global sweep), then
    relation barriers, then the global output barrier over anything still open."""
    timelines = timelines or {}
    for w in sorted(workers, key=lambda w: w.barrier_tick):
        close_specs(ledger, w.specs, timelines, reobserve=reobserve)
    if relation_specs:
        close_specs(ledger, relation_specs, timelines, reobserve=reobserve)
    if global_specs:
        close_specs(ledger, global_specs, timelines, reobserve=reobserve)
