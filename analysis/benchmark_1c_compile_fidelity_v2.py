#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark_1c_compile_fidelity_v2.py  --  DETERMINATION / NOT FROZEN / NOT CONFIRMATORY

Compile-fidelity RE-CHECK on the D36 WIDTH-SCALED form (32 one-shard worker steps),
loaded from the actual restructured tasks/benchmark_1c.yaml. Does the different plan
structure (32 one-shard steps vs the prior 4-step form) still get all 32 surfaces
named + armed, or does it change coverage? ONE real Sonnet compile (unmodified §3.6).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import yaml  # noqa: E402
from sentinel_v2.compile_probes import (compile_assumptions, ground_surface,  # noqa: E402
                                        _normalize_surface, FAMILY_MEMBER_CAP)
from world.server import classify_url_pattern                                # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

N = 32
RIDS = [f"R-{i:04d}" for i in range(1, N + 1)]
SAMPLES = tuple(f"/regions/{r}/evidence" for r in RIDS)


class StubTrace:
    def emit(self, **kw):
        pass


def render_plan_text(task):
    """Mirror what the conductor's plan_text() feeds the compile: goal + the steps."""
    lines = [task["goal"].strip(), "", "Plan steps:"]
    for s in task["plan"]:
        lines.append(f"- {s['subplan_id']}: {s['step']}")
    return "\n".join(lines)


def build_appendix(task):
    idlist = ", ".join(RIDS)
    return (
        f"{task['task_context'].strip()}\n"
        "API SURFACE (world_rev 4): GET /regions/{region_id}/evidence -> "
        "{region_id, normalized_verified_demand (integer), provenance_id (opaque), reporting_period, status}; "
        f"bounded family of 32 regions, region_id one of: {idlist}. "
        "GET /regions -> list of all 32 region ids."
    )


def main():
    task = yaml.safe_load((ROOT / "tasks" / "benchmark_1c.yaml").read_text(encoding="utf-8"))
    plan = render_plan_text(task)
    appendix = build_appendix(task)
    ws = [s for s in task["plan"] if s["step"].startswith("Worker")]
    print("=" * 92)
    print("COMPILE-FIDELITY RE-CHECK on the D36 WIDTH-SCALED form (32 one-shard steps)")
    print("=" * 92)
    print(f"plan: {len(ws)} one-shard worker steps; plan_text {len(plan)} chars; FAMILY_MEMBER_CAP={FAMILY_MEMBER_CAP}")

    print("\n[running ONE real Sonnet compile via the V2 sub-CLI path]...", flush=True)
    soft, results = compile_assumptions(plan, appendix, StubTrace())
    cost = round(sum((r.cost_usd or 0) for r in results), 6)
    if soft is None:
        print(f"[FAIL] no valid soft set. cost=${cost}")
        return

    surfaces = [_normalize_surface(a.surface) for a in soft.assumptions]
    region_surfaces = [s for s in surfaces if "/regions/" in s]
    concrete = sorted({s for s in region_surfaces if "{" not in s})
    templates = sorted({s for s in region_surfaces if "{" in s})
    with_ptr = sum(1 for a in soft.assumptions if "/regions/" in _normalize_surface(a.surface) and a.pointer)

    plan_named = tuple(norm for norm in surfaces
                       if "{" not in norm and classify_url_pattern(norm, SAMPLES) is not None)
    armed = set(); modes = {}
    for a in soft.assumptions:
        s = _normalize_surface(a.surface)
        if "/regions/" not in s:
            continue
        g = ground_surface(a.surface, SAMPLES, plan_named=plan_named)
        modes[g.mode] = modes.get(g.mode, 0) + 1
        if not g.hallucinated and not g.unbounded:
            armed.update(g.members)

    print(f"\n[compile output] assumptions={len(soft.assumptions)} cost=${cost}")
    print(f"  region surfaces named: {len(region_surfaces)} (distinct concrete ids: {len(concrete)}; templates: {len(templates)} {templates})")
    print(f"  region assumptions with a value pointer (field baseline-diff): {with_ptr}")
    print(f"  grounding modes: {modes}")
    print(f"  DISTINCT region surfaces ARMED = {len(armed)} / {N}")

    a = len(armed)
    if a >= N:
        v = (f"FULL — the width-scaled (32 one-shard) plan still arms all {N} surfaces. Coverage is "
             "structure-robust: the D36 estimand-correct form does NOT degrade coverage vs the 4-step form.")
    elif a <= FAMILY_MEMBER_CAP + 1:
        v = (f"CAPPED/RE-TEMPLATED — armed {a}/{N} (~cap). The one-shard structure made the compile collapse "
             f"toward <=24; coverage DROPPED vs the 4-step form (which armed 32). Report as MEASURED.")
    else:
        v = f"PARTIAL — armed {a}/{N}. Coverage differs from the 4-step form; report the exact number."
    print("\nVERDICT:", v)
    print(f"\nspend this re-check: ${cost}")
    print("DETERMINATION / NOT FROZEN / NOT CONFIRMATORY")


if __name__ == "__main__":
    main()
