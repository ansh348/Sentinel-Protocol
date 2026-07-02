"""V2nc — the no-LLM-compiler ablation's deterministic assumption selector.

V2nc replaces the ONE LLM compile call (compile_assumptions, the only model call on
the v2 compile path) with a DETERMINISTIC enumeration: for every plan-touched
/regions surface, emit exactly one VALUE soft assumption on the value-bearing field.
Nothing else changes — the SAME deterministic compile_pipeline grounds, types, and
arms these into per-surface VALUE baseline-diff probes (FaultShape.VALUE_CHANGED +
LensOp.FIELD_READ + Comparison.PROOF_BASELINE), and the SAME run loop (arm-time
baseline capture, barriers, corroboration, replan) runs downstream. No model is
called; the compile cost is $0.

Plan-touched derivation. The benchmark_1c task is WIDTH-FORCED: fan_out = n_regions,
one worker per shard, so the plan touches exactly the N region-evidence surfaces
R-0001 .. R-{N:04d}. That forced width is the authoritative plan-touched set — robust
to how the orchestrator LLM phrases the plan and correct at every N (deriving from the
yaml's 32-step spec text would mis-count at N<32). Each surface gets a VALUE probe on
`normalized_verified_demand` — the numeric demand the shared denominator T sums over.

The selection is injection-BLIND: it arms ALL N shards (it does not know, and does not
read, which shard is mutated). The mutated shard is covered because it is one of the N,
not because the selector singled it out. Category-blind by construction (it knows only
this task's surface family + value field, the ablation's fixed deterministic knowledge).
"""
from __future__ import annotations

from typing import Optional

from sentinel_v2.compile_probes import SoftAssumption, SoftAssumptionSet

# The value field the shared allocation denominator sums over (world/services/regions.py).
VALUE_FIELD = "normalized_verified_demand"


def region_evidence_surfaces(n_regions: int) -> list[str]:
    """The N plan-touched region-evidence surfaces for a width-N run (R-0001..R-000N).
    This IS the plan-touched set for the width-forced benchmark (fan_out == n_regions,
    one shard per worker)."""
    return [f"/regions/R-{i:04d}/evidence" for i in range(1, int(n_regions) + 1)]


def select_region_value_assumptions(task: dict, plan=None, trace=None
                                    ) -> SoftAssumptionSet:
    """Deterministically build the soft-assumption set V2nc arms: one VALUE assumption
    (pointer at the demand field) per plan-touched /regions surface. No LLM call.

    `plan` is accepted for signature parity with the compile path but is not required —
    the width-forced n_regions is the authoritative plan-touched surface set. `trace`,
    when given, receives a `compile` event mirroring compile_assumptions' (so a V2nc run
    trace is self-describing: a $0 deterministic select, n assumptions, no model)."""
    n = int(task.get("n_regions") or 0)
    surfaces = region_evidence_surfaces(n)
    assumptions = [
        SoftAssumption(
            plan_step=(f"a worker reads {surf} and records its {VALUE_FIELD} "
                       "for the shared allocation denominator"),
            world_fact=(f"{surf} returns a stable {VALUE_FIELD} that the shared total T "
                        "sums over all regions; changing it invalidates every allocation"),
            surface=surf,
            pointer=VALUE_FIELD,
            recovery_hint=("re-fetch the region evidence and recompute the shared total T "
                           "and every dependent allocation share"))
        for surf in surfaces]
    soft = SoftAssumptionSet(plan_id=str(task.get("id", "benchmark_1c")),
                             assumptions=assumptions)
    if trace is not None:
        trace.emit(
            actor="sentinel_v2", event_type="compile",
            payload={"layer": "v2_deterministic_select", "valid": True,
                     "n_assumptions": len(assumptions),
                     "n_regions": n, "cost_usd": 0.0, "model": None,
                     "note": "V2nc no-LLM-compiler ablation: deterministic per-surface "
                             "VALUE selection on the plan-touched /regions family"})
    return soft
