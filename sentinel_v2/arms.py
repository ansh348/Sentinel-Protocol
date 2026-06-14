"""Phase 1b matrix arms: registration + dispatch + result collection
(decision_memo_phase1.md §2, §4; prereg_1b P3). Category-blind.

The FIVE matrix arms:
  V2   the full v2 stack (substrate + compile D4 + corroboration D28 + cadence D29),
       behind the flag. COMMITTED PRIMARY (P3, in ink before any battery result).
  V2J  v2 with the rebuilt judge tier. EXPLORATORY only — never compared post-hoc
       against V2 as if co-primary.
  S1   batch baseline.
  S2   naive anomaly-gated escalation. MANDATORY head-to-head under the honesty
       clause (if S2 dominates V2 on recall at <= FIR, the paper says so in the
       results, not a footnote).
  S3   cost-matched heartbeat (periodic-revalidation baseline).

Baseline arms (S1/S2/S3) dispatch through the existing v1 conductor (decision #5:
conductor configuration, not separate codebases). The v2 arms run the deterministic
v2 stack; they are NOT v1 SystemConfigs and never run through the v1 tripwire/judge
loop. Result collection is uniform: a normalized ArmResult carrying
detection / interrupts / total_cost_usd / TTD, the matrix runner's per-cell record.

Rule Zero: nothing here reads or loads a held-out cell; the held-out set enters only
at matrix-fire from escrow. This module wires arms and is smoke-tested on SEEN cells.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sentinel_v2.corroboration import Signal, corroborate
from sentinel_v2.flags import v2_enabled
from sentinel_v2.probe_spec import Comparison, FaultShape
from sentinel_v2.probes import ProbeExecutor
from sentinel_v2.typing_engine import BaselineObligations, Invariant

# Arm ids. The v2 ids were PROVISIONAL through the night shift; ratified here as the
# registered matrix arms (P3 designations unchanged).
TWO_TIER = "V2"
REBUILT_JUDGE = "V2J"
S1, S2, S3 = "S1", "S2", "S3"

PRIMARY_ARM = TWO_TIER
EXPLORATORY_ARMS = (REBUILT_JUDGE,)
BASELINE_ARMS = (S1, S2, S3)


@dataclass(frozen=True)
class ArmSpec:
    """A registered matrix arm. `kind` is 'v2' or 'baseline'; `system_id` is the v1
    conductor system for baselines (None for v2 arms)."""
    id: str
    kind: str                       # "v2" | "baseline"
    role: str                       # "primary" | "exploratory" | "baseline"
    description: str
    judge: bool = False             # the (rebuilt, exploratory) judge tier — V2J only
    honesty_clause: bool = False    # S2: mandatory head-to-head, reported in results not a footnote
    heartbeat: bool = False         # S3: cost-matched periodic revalidation

    @property
    def is_v2(self) -> bool:
        return self.kind == "v2"


ARMS: dict[str, ArmSpec] = {
    TWO_TIER: ArmSpec(
        TWO_TIER, "v2", "primary",
        "Full v2 stack: substrate + compile (D4) + corroboration (D28) + cadence (D29); "
        "two-tier, no judge. Committed primary (P3)."),
    REBUILT_JUDGE: ArmSpec(
        REBUILT_JUDGE, "v2", "exploratory",
        "v2 with the rebuilt judge tier; exploratory only, never co-primary with V2.",
        judge=True),
    S1: ArmSpec(S1, "baseline", "baseline", "Batch baseline (dispatch, wait, aggregate)."),
    S2: ArmSpec(S2, "baseline", "baseline",
                "Naive anomaly-gated escalation; mandatory head-to-head (honesty clause).",
                honesty_clause=True),
    S3: ArmSpec(S3, "baseline", "baseline",
                "Cost-matched heartbeat (periodic-revalidation baseline).",
                heartbeat=True),
}


def resolve_arm(arm_id: str) -> ArmSpec:
    """Resolve a registered matrix arm. v2 arms require the v2 flag (no v2 path may
    execute with the flag off); baselines resolve regardless. Unknown ids raise."""
    if arm_id not in ARMS:
        raise KeyError(f"unknown matrix arm: {arm_id!r} (registered: {sorted(ARMS)})")
    spec = ARMS[arm_id]
    if spec.is_v2 and not v2_enabled():
        raise RuntimeError(
            f"v2 arm {arm_id!r}: sentinel_v2 is feature-flagged off (set TRIPWIRE_V2=1); "
            "with the flag off no v2 code path may execute")
    return spec


# -- the normalized per-cell result the matrix runner collects -----------------

@dataclass
class ArmResult:
    """One arm's result on one cell: detection, interrupts, cost (total_cost_usd),
    TTD. The matrix runner's per-cell record, uniform across arms."""
    arm_id: str
    detected: bool
    n_interrupts: int
    total_cost_usd: float
    ttd_tool_calls: Optional[int] = None
    false_interrupts: Optional[int] = None
    fir: Optional[float] = None
    success: Optional[bool] = None
    source: str = ""                       # "conductor" | "v2_detection"
    grades: list[str] = field(default_factory=list)

    def well_formed(self) -> bool:
        return (isinstance(self.detected, bool) and self.n_interrupts >= 0
                and isinstance(self.total_cost_usd, (int, float)))


def collect_arm_result(run_dir, arm_id: str) -> ArmResult:
    """Collect a baseline arm's result from a completed run via the M6 metrics
    (detection/ttd/interrupts/cost), the same instrument the gates consume."""
    from analysis.metrics import run_metrics
    m = run_metrics(run_dir)
    interrupts = m["interrupts"]
    return ArmResult(
        arm_id=arm_id, detected=bool(m["detected"]),
        n_interrupts=interrupts["total"], total_cost_usd=m["total_cost_usd"],
        ttd_tool_calls=m["ttd_tool_calls"],
        false_interrupts=interrupts["false"], fir=interrupts["fir"],
        success=m["success"], source="conductor")


# -- the v2 detection seam (deterministic; $0 LLM) -----------------------------
#
# The cadence pre-completion sweep over the compiled probes, fed to corroboration.
# Each probe is observed (first look + one confirming re-look, D28 persistence); the
# typing/corroboration stack decides invalidations. Status-coded signals fast-path;
# baseline-drift probes consult a clean baseline when one was harvested. Deterministic.

def _signal_for(probe, observations, baseline) -> Signal:
    invariant = None
    obligations = None
    if probe.comparison is Comparison.HARD_INVARIANT:
        if probe.fault_shape is FaultShape.STATUS_CLASS:
            invariant = Invariant(status_in=(200,))
        elif probe.fault_shape is FaultShape.FIELD_ABSENT:
            invariant = Invariant(require_present=True)
        elif probe.fault_shape is FaultShape.RELATION_BROKEN:
            invariant = Invariant(relation_required=True)
        else:
            invariant = Invariant()
    else:
        obligations = BaselineObligations(clean=True, equivalent=True, stationary=True,
                                          targeted=True, frozen=True)
    return Signal(probe=probe, observations=observations, baseline=baseline,
                  obligations=obligations, invariant=invariant)


def run_v2_detection(probes, client, *, auth_token: Optional[str] = None,
                     baselines: Optional[dict] = None, judge: bool = False) -> dict:
    """Execute the v2 detection: probe each surface (first look + one re-look) on the
    live side channel and run corroboration. Returns the detection seam — deterministic,
    $0 LLM. `judge=True` (V2J) routes invalidations through the exploratory judge tier
    (a pass-through seam here; the rebuilt judge is exploratory and not implemented)."""
    ex = ProbeExecutor(client, auth_token=auth_token)
    baselines = baselines or {}
    signals = [
        _signal_for(p, [ex.get(p.target), ex.get(p.target)], baselines.get(p.target))
        for p in probes
    ]
    invalidations = corroborate(signals)
    if judge:
        invalidations = _exploratory_judge(invalidations)
    return {"detected": bool(invalidations), "n_interrupts": len(invalidations),
            "grades": [i.grade.value for i in invalidations],
            "invalidations": invalidations}


def _exploratory_judge(invalidations):
    """The V2J rebuilt-judge tier is EXPLORATORY and not implemented in this task; the
    seam is a pass-through (it never filters a corroborated invalidation here). Wiring a
    real rebuilt judge is reserved work and never compared co-primary with V2."""
    return invalidations


def v2_result(arm_id: str, detection: dict, *, total_cost_usd: float = 0.0,
              ttd_tool_calls: Optional[int] = None,
              success: Optional[bool] = None) -> ArmResult:
    """Build an ArmResult from a v2 detection seam output."""
    return ArmResult(
        arm_id=arm_id, detected=detection["detected"],
        n_interrupts=detection["n_interrupts"], total_cost_usd=total_cost_usd,
        ttd_tool_calls=ttd_tool_calls, success=success, source="v2_detection",
        grades=list(detection["grades"]))
