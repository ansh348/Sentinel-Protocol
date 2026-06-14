"""Provisional surface promotion + replan garbage collection
(decisions/cadence_semantics.md §14; D29). DETERMINISTIC, category-blind.

When the harvest watch observes a worker reading an UNREGISTERED surface that feeds
output, it creates a PROVISIONAL load-bearing record that enters the same ledger,
terminal-state machine, and barrier coverage as a compiled one. The provisional
defaults to HIGH work-at-risk but is CAPPED BELOW the blocking threshold (D29 fold):
it earns coverage and the paired-observation reserve, yet cannot by itself trigger a
hard halt. It is promotable to blocking ONLY after a barrier confirms an
irreversible-commit dependency.

Replan GC (keep-not-flush, consistent with D28): a surface is retired to
NOT_LOAD_BEARING only with a no-dependency proof; otherwise it is carried forward.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sentinel_v2.cadence.ledger import CoverageLedger, TerminalState
from sentinel_v2.cadence.workatrisk import (BLOCKING_THRESHOLD,
                                            HIGH_RISK_THRESHOLD, PlanAssumption)
from sentinel_v2.probe_spec import FaultShape

# A provisional surface defaults strictly between the high-risk and blocking thresholds:
# above 0.5 (earns the paired reserve), below 0.8 (cannot by itself halt the run).
PROVISIONAL_WORK_AT_RISK = (HIGH_RISK_THRESHOLD + BLOCKING_THRESHOLD) / 2     # 0.65
# When a barrier confirms an irreversible-commit dependency, the provisional is promoted
# to a blocking work-at-risk (strictly above the blocking threshold).
PROMOTED_BLOCKING_WORK_AT_RISK = BLOCKING_THRESHOLD + 0.1                     # 0.9


@dataclass
class ProvisionalRecord:
    surface_id: str
    assumption_id: str
    work_at_risk: float
    required_shape: FaultShape
    promoted_to_blocking: bool = False


def create_provisional(surface_id: str, *, assumption_id: Optional[str] = None,
                       required_shape: FaultShape = FaultShape.SCHEMA_SHAPE,
                       ledger: Optional[CoverageLedger] = None) -> ProvisionalRecord:
    """Register a provisional load-bearing record for an unregistered output-feeding
    read. High work-at-risk, capped below blocking — earns coverage + the paired
    reserve, cannot halt the run on its own."""
    aid = assumption_id or f"provisional::{surface_id}"
    rec = ProvisionalRecord(surface_id=surface_id, assumption_id=aid,
                            work_at_risk=PROVISIONAL_WORK_AT_RISK,
                            required_shape=required_shape)
    if ledger is not None:
        # Enters the same ledger + terminal-state machine as a compiled assumption.
        # Geometry fields are placeholders: a provisional's work-at-risk is the assigned
        # default (carried on the record), not the formula value.
        ledger.register(PlanAssumption(
            assumption_id=aid, surface_id=surface_id, required_shape=required_shape,
            downstream_steps=1, total_remaining_steps=1, downstream_commits=False,
            single_visit=True))
    return rec


def earns_paired_reserve(rec: ProvisionalRecord) -> bool:
    """A provisional is high work-at-risk, so it earns the paired-observation reserve."""
    return rec.work_at_risk > HIGH_RISK_THRESHOLD


def can_halt_run(rec: ProvisionalRecord) -> bool:
    """Whether the record can by itself trigger a hard halt (blocking). A fresh
    provisional cannot (capped below the threshold); only a commit-confirmed one can."""
    return rec.work_at_risk > BLOCKING_THRESHOLD


def promote_to_blocking(rec: ProvisionalRecord, *,
                        irreversible_commit_confirmed: bool) -> bool:
    """Promote a provisional to blocking ONLY after a barrier confirms it feeds an
    irreversible commit. Returns whether promotion occurred."""
    if irreversible_commit_confirmed and not rec.promoted_to_blocking:
        rec.work_at_risk = PROMOTED_BLOCKING_WORK_AT_RISK
        rec.promoted_to_blocking = True
    return rec.promoted_to_blocking


# -- replan garbage collection (§14; keep-not-flush) ---------------------------

@dataclass(frozen=True)
class DependencyProof:
    """Evidence that NOTHING live still depends on a surface (§14): no live artifact,
    no worker output, no pending decision, no relation. Only a complete proof retires."""
    no_live_artifact: bool
    no_worker_output: bool
    no_pending_decision: bool
    no_relation_dependency: bool

    def complete(self) -> bool:
        return all((self.no_live_artifact, self.no_worker_output,
                    self.no_pending_decision, self.no_relation_dependency))


def replan_gc(ledger: CoverageLedger, assumption_id: str,
              proof: Optional[DependencyProof]) -> Optional[TerminalState]:
    """Retire a surface to NOT_LOAD_BEARING only with a COMPLETE no-dependency proof;
    otherwise carry it forward (keep-not-flush, D28) — it stays open and must still
    reach a terminal state through finalization. Returns the terminal state if retired,
    else None (carried forward)."""
    if proof is not None and proof.complete():
        ledger.mark(assumption_id, TerminalState.NOT_LOAD_BEARING)
        return TerminalState.NOT_LOAD_BEARING
    return None
