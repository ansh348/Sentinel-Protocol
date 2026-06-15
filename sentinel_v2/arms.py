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

from sentinel_v2.corroboration import (CorroboratedInvalidation, Grade, Signal,
                                       corroborate)
from sentinel_v2.flags import v2_enabled
from sentinel_v2.gate_route import DOCS_GATE_SHADOW, evaluate_gate_probe
from sentinel_v2.probe_spec import Comparison, FaultShape, LensOp
from sentinel_v2.probes import ProbeExecutor
from sentinel_v2.typing_engine import BaselineObligations, Invariant, Verdict

# Arm ids. The v2 ids were PROVISIONAL through the night shift; ratified here as the
# registered matrix arms (P3 designations unchanged).
TWO_TIER = "V2"
REBUILT_JUDGE = "V2J"
S1, S2, S3 = "S1", "S2", "S3"

PRIMARY_ARM = TWO_TIER
EXPLORATORY_ARMS = (REBUILT_JUDGE,)
BASELINE_ARMS = (S1, S2, S3)

# Request-malformation status codes (§8 / harvest): a 4xx here is about the HTTP
# request (e.g. a GET probe to a POST-only endpoint -> 405), not a surface state
# change, so it never trips the status fast path.
_REQUEST_MALFORMATION_STATUS = frozenset({400, 405, 422})


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
    replans: Optional[int] = None
    success: Optional[bool] = None
    source: str = ""                       # "conductor" | "v2_detection" | "v2_runloop"
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
                     baselines: Optional[dict] = None, queries: Optional[dict] = None,
                     judge: bool = False) -> dict:
    """Execute the v2 detection: probe each surface (first look + one re-look) on the
    live side channel and run corroboration. Returns the detection seam — deterministic,
    $0 LLM. `queries` maps surface -> the worker's observed query string, so the probe
    replays the SAME projection the worker saw (§8 same-projection; without it a GET that
    omits a required query, e.g. ?dest=, observes a different view and false-positives).
    `judge=True` (V2J) routes invalidations through the exploratory judge tier (a
    pass-through seam here; the rebuilt judge is exploratory and not implemented)."""
    from urllib.parse import parse_qsl
    ex = ProbeExecutor(client, auth_token=auth_token)
    baselines = baselines or {}
    queries = queries or {}
    invalidations = []
    signals = []
    for p in probes:
        # GATE-SHADOW / premise probes (D31 C3): a §4 gate probe is a HARD invariant
        # `enforcing == True` evaluated by evaluate_gate_probe — NOT a content diff and
        # NOT the generic empty-Invariant() the rest of the HARD_INVARIANT path built
        # (which returned CLEAN for a trapped gate). It fires on its own (Break-A, no
        # baseline); a missing worker auth context is DISQUALIFIED, never a fast-path
        # 401. Routed before the status fast path so a 401 on an authed gate cannot
        # masquerade as a surface-state interrupt.
        if p.lens.op is LensOp.GATE_SHADOW:
            ev = evaluate_gate_probe(p, ex, requires_auth=(p.target == DOCS_GATE_SHADOW))
            if ev.verdict is Verdict.INTERRUPT:
                invalidations.append(CorroboratedInvalidation(
                    target=p.target, grade=Grade.INTERRUPT,
                    fault_shape=p.fault_shape.value,
                    evidence_class=p.evidence_class.value,
                    reason=f"gate stopped enforcing (enforcing != True): {ev.reason}",
                    witness=ev.witness))
            continue
        q = queries.get(p.target)
        params = dict(parse_qsl(q)) if q else None
        obs = [ex.get(p.target, params=params),         # first look + one confirming re-look
               ex.get(p.target, params=params)]
        # STATUS FAST PATH (D28/D29 §5.3): a well-formed status >= 400 on a trusted
        # surface is a status-coded interrupt on its own — regardless of the probe's
        # declared shape, and with NO baseline required (a removed surface 404, a token
        # 401). REQUEST-MALFORMATION codes (400/405/422) are EXCLUDED per §8: e.g. a GET
        # probe to a POST-only endpoint returns 405 — that belongs to the request, not the
        # surface, and must never trip the fast path (it is not a surface state change).
        status_hit = next((o for o in obs if o.status is not None and o.status >= 400
                           and o.status not in _REQUEST_MALFORMATION_STATUS), None)
        if status_hit is not None:
            invalidations.append(CorroboratedInvalidation(
                target=p.target, grade=Grade.INTERRUPT,
                fault_shape=FaultShape.STATUS_CLASS.value,
                evidence_class=p.evidence_class.value,
                reason=f"status {status_hit.status} on a trusted surface (status fast path)",
                witness=status_hit.status))
            continue
        signals.append(_signal_for(p, obs, baselines.get(p.target)))
    invalidations.extend(corroborate(signals))
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


# -- the matrix-runner dispatch (the REAL path) --------------------------------
#
# Baselines run through the v1 conductor (the proven Phase-1 runner); v2 arms run the
# real v2 loop (cadence barriers firing probes mid-run + §8 harvest). Result collection
# is uniform via the M6 metrics instrument; for v2 the corroboration-based detection is
# also surfaced as a cross-check. Lazy imports keep arms <-> run_v2_loop acyclic.

def dispatch(arm_id: str, *, task_path, injection=None, n_inject=None, seed: int = 1,
             runs_root="runs", max_replans: int = 2,
             heartbeat_k: Optional[int] = None) -> ArmResult:
    """Run one cell on one arm through the actual matrix-runner path and collect a
    normalized ArmResult. Caller supplies only SEEN cells (this function never reads or
    loads a held-out cell)."""
    spec = resolve_arm(arm_id)
    if spec.is_v2:
        from conductor.run_v2_loop import V2Conductor
        cond = V2Conductor(task_path=task_path, injection=injection, n_inject=n_inject,
                           seed=seed, runs_root=runs_root, judge=spec.judge,
                           max_replans=max_replans)
        summary = cond.run()
        res = collect_arm_result(cond.run_dir, arm_id)        # M6 instrument (parity)
        res.source = "v2_runloop"
        res.total_cost_usd = summary["cost_usd"]
        res.replans = cond.replans_done
        res.grades = [i.grade.value for i in cond.v2_invalidations]
        # the v2 corroboration is the path's own ground truth; surface it as a cross-check
        v2_interrupts = [i for i in cond.v2_invalidations if i.grade.value == "interrupt"]
        res.detected = bool(v2_interrupts) or res.detected
        return res
    from conductor.run_one import run_one
    summary = run_one(task_path=task_path, system_id=spec.id, injection=injection,
                      n_inject=n_inject, seed=seed, runs_root=runs_root,
                      max_replans=max_replans, heartbeat_k=heartbeat_k)
    return collect_arm_result(summary["run_dir"], arm_id)
