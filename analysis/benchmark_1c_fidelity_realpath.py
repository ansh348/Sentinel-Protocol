#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark_1c_fidelity_realpath.py  --  BUILD/CHARACTERIZATION / NOT FROZEN / NOT CONFIRMATORY

Re-measure compile fidelity on the REAL grounding path (replaces the RETRACTED phase-4
32/32, which used synthetic samples). One real Sonnet compile on the N=32 width-scaled
named-id benchmark plan, then the REAL compile_pipeline grounding (path_samples_for_rev /
openapi_paths_for_rev with n_regions=32 — the additive fix). Reports the honest coverage.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import yaml  # noqa: E402
from sentinel_v2.compile_probes import (compile_assumptions, compile_pipeline,  # noqa: E402
                                        FAMILY_MEMBER_CAP)
from analysis import benchmark_1c_world as BW                                    # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

N, SEED = 32, 9132


class StubTrace:
    def emit(self, **kw):
        pass


def main():
    task = yaml.safe_load((ROOT / "tasks" / "benchmark_1c.yaml").read_text(encoding="utf-8"))
    plan = task["goal"].strip() + "\n\nPlan steps:\n" + "\n".join(
        f"- {s['subplan_id']}: {s['step']}" for s in task["plan"])
    appendix = task["task_context"].strip()
    print("=" * 92)
    print("COMPILE FIDELITY — REAL GROUNDING PATH (n_regions=32). Replaces the retracted synthetic 32/32.")
    print("=" * 92)

    print("\n[ONE real Sonnet compile -> soft assumptions]...", flush=True)
    soft, results = compile_assumptions(plan, appendix, StubTrace())
    cost = round(sum((r.cost_usd or 0) for r in results), 6)
    if soft is None:
        print(f"[FAIL] no soft set. cost=${cost}"); return
    print(f"  soft assumptions: {len(soft.assumptions)}  cost=${cost}")

    print("[REAL compile_pipeline grounding with n_regions=32]...", flush=True)
    try:
        cr = compile_pipeline(soft, world_rev=4, n_regions=N, world=None,
                              auth_token=None, planned_write_set=set())
    except Exception as e:
        print(f"[GROUNDING ERROR] {type(e).__name__}: {str(e)[:300]}")
        print("  -> /regions did NOT ground on the real path (report as-is).")
        return

    def is_reg(t):
        return isinstance(t, str) and "/regions/" in t and "/evidence" in t

    armed = [p for p in cr.probes if is_reg(p.target)]
    armed_targets = sorted({p.target for p in armed})
    telem = sorted({getattr(a, "surface", "") for a in cr.telemetry_only if is_reg(getattr(a, "surface", ""))}) \
        if cr.telemetry_only else []
    passive = sorted({getattr(a, "surface", "") for a in cr.passive if is_reg(getattr(a, "surface", ""))}) \
        if cr.passive else []
    uncovered = [u for u in (cr.uncovered or []) if "regions" in str(u).lower()]
    grounded = set(armed_targets) | set(telem) | set(passive)

    # value baseline-diff probes: VALUE_CHANGED fault + FIELD_READ lens + PROOF_BASELINE
    # comparison (the baseline-drift comparison — probe_spec has NO 'BASELINE_DRIFT';
    # the two Comparison members are HARD_INVARIANT and PROOF_BASELINE).
    from sentinel_v2.probe_spec import FaultShape, LensOp, Comparison
    def is_value_bdiff(p):
        return (p.fault_shape == FaultShape.VALUE_CHANGED
                and p.lens.op == LensOp.FIELD_READ
                and p.comparison == Comparison.PROOF_BASELINE)
    value_probes = [p for p in armed if is_value_bdiff(p)]
    value_targets = sorted({p.target for p in value_probes})
    # honest histogram of what the 32 armed /regions probes actually got
    from collections import Counter
    hist = Counter((p.fault_shape.value, p.lens.op.value, p.comparison.value) for p in armed)
    print("  armed /regions probe shapes (fault_shape, lens, comparison) -> count:")
    for k, c in hist.most_common():
        print(f"     {k} -> {c}")

    # the shard that WILL be mutated at this seed
    inj = BW.build_world(N, SEED, inject=True)
    mutated_surface = f"/regions/{inj.j_rid}/evidence"
    mutated_has_value = mutated_surface in set(value_targets)

    print(f"\n[REAL-PATH coverage]  FAMILY_MEMBER_CAP={FAMILY_MEMBER_CAP}")
    print(f"  /regions surfaces GROUNDED (not hallucinated): {len(grounded)} / {N}")
    print(f"  /regions surfaces ARMED with a probe:          {len(armed_targets)} / {N}")
    print(f"  ARMED with a VALUE baseline-diff probe:        {len(value_targets)} / {N}")
    print(f"  cap bites here (<=24 despite 32 named)?        {len(armed_targets) <= FAMILY_MEMBER_CAP}")
    print(f"  telemetry_only(/regions): {len(telem)}  passive: {len(passive)}  uncovered: {len(uncovered)}")
    print(f"  mutated shard {inj.j_rid} ({mutated_surface}) gets a VALUE baseline-diff probe: {mutated_has_value}")
    print(f"\n  spend this re-measure: ${cost}")
    print("BUILD/CHARACTERIZATION / NOT FROZEN / NOT CONFIRMATORY")


if __name__ == "__main__":
    main()
