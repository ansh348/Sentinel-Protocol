#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark_1c_compile_fidelity.py  --  DETERMINATION / NOT FROZEN / NOT CONFIRMATORY

R1-residual check: R1 showed plan-named ids CAN bypass FAMILY_MEMBER_CAP=24 in grounding.
But the compiler is an LLM. Does a REAL Sonnet compile, handed a named-id N=32 plan that
names all 32 shard ids, actually EMIT soft assumptions naming all 32 surfaces (so grounding
arms all 32) — or does it summarize / re-template back toward <=24?

ONE real Sonnet compile (compile_probes.compile_assumptions, unmodified — §3.6), then the
SUT's own grounding (ground_surface + plan_named) against synthetic 32-region samples.
NO Railway, NO benchmark-world build, NO full arm. Reports cost.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sentinel_v2.compile_probes import (compile_assumptions, ground_surface,  # noqa: E402
                                        _normalize_surface, FAMILY_MEMBER_CAP)
from world.server import classify_url_pattern                                  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

N = 32
RIDS = [f"region_{i:04d}" for i in range(1, N + 1)]
SAMPLES = tuple(f"/regions/{r}/evidence" for r in RIDS)


def build_plan():
    waves = [RIDS[i:i + 8] for i in range(0, N, 8)]
    lines = [
        f"PLAN — demand-normalized regional allocation (forced width N={N}).",
        "Goal: compute each region's allocation share = region_demand / shared_total, where shared_total "
        "is the sum of normalized_verified_demand across ALL 32 regions (a shared denominator: every output "
        "depends on every region).", ""]
    for w, ids in enumerate(waves, start=1):
        surfaces = ", ".join(f"GET /regions/{r}/evidence" for r in ids)
        lines.append(f"- step s{w} (worker w{w}): {surfaces} ; for each, extract "
                     f"normalized_verified_demand and provenance_id.")
    lines += [
        "- step reduce: deterministically compute shared_total T = sum of normalized_verified_demand over "
        "all 32 regions (no LLM; exact integer sum).",
        "- step allocate: for each region emit {region_id, verified_demand, provenance_id, global_total=T, "
        "share = verified_demand / T as an exact rational}.",
        "",
        "Assumption: each GET /regions/{rid}/evidence returns a STABLE normalized_verified_demand value and "
        "an invariant provenance_id for the duration of the run; the shared_total depends on all 32 regions, "
        "so a change to any one region's demand invalidates every allocation."]
    return "\n".join(lines)


def build_appendix():
    idlist = ", ".join(RIDS)
    return (
        "API SURFACE — regional demand world (world_rev 4):\n"
        "- GET /regions/{region_id}/evidence -> {region_id, normalized_verified_demand (integer units), "
        "provenance_id (opaque string)}. Bounded family of 32 regions.\n"
        f"  region_id is one of: {idlist}\n"
        "- GET /regions -> {regions: [region_id, ...]} the list of all 32 region ids.\n"
        "The allocation denominator (shared_total) = sum of normalized_verified_demand across all 32 regions."
    )


class StubTrace:
    def emit(self, **kw):
        pass


def main():
    plan = build_plan()
    appendix = build_appendix()
    print("=" * 92)
    print("COMPILE-FIDELITY CHECK — does a REAL Sonnet compile name all N=32 named shard surfaces?")
    print("=" * 92)
    print(f"plan length {len(plan)} chars; appendix {len(appendix)} chars; FAMILY_MEMBER_CAP={FAMILY_MEMBER_CAP}")
    print("named-id plan (head):")
    for ln in plan.splitlines()[:6]:
        print("   " + ln[:110])

    print("\n[running ONE real Sonnet compile via the V2 sub-CLI path]...", flush=True)
    soft, results = compile_assumptions(plan, appendix, StubTrace())
    cost = round(sum((r.cost_usd or 0) for r in results), 6)
    if soft is None:
        print(f"[FAIL] compile returned no valid soft set (attempts={len(results)}). cost=${cost}")
        for r in results:
            print("   exit", r.exit_code, "err", r.is_error, "stderr", (r.stderr or "")[-150:])
        return

    # --- inspect the LLM's soft assumptions ---
    surfaces = [_normalize_surface(a.surface) for a in soft.assumptions]
    region_surfaces = [s for s in surfaces if "/regions/" in s]
    concrete_named = sorted({s for s in region_surfaces if "{" not in s})
    templates = sorted({s for s in region_surfaces if "{" in s})
    with_pointer = sum(1 for a in soft.assumptions
                       if "/regions/" in _normalize_surface(a.surface) and a.pointer)

    print(f"\n[compile output]  assumptions={len(soft.assumptions)}  cost=${cost}")
    print(f"  region surfaces named: {len(region_surfaces)}  "
          f"(distinct concrete ids: {len(concrete_named)}; templates: {len(templates)})")
    print(f"  templates seen: {templates}")
    print(f"  sample of concrete named: {concrete_named[:5]}{' ...' if len(concrete_named)>5 else ''}")
    print(f"  region assumptions carrying a value pointer (-> field baseline-diff): {with_pointer}")

    # --- replicate the SUT grounding (compile_probes.py:291-301), synthetic 32 samples ---
    plan_named = tuple(norm for norm in surfaces
                       if "{" not in norm and classify_url_pattern(norm, SAMPLES) is not None)
    armed = set()
    modes = {}
    for a in soft.assumptions:
        s = _normalize_surface(a.surface)
        if "/regions/" not in s:
            continue
        g = ground_surface(a.surface, SAMPLES, plan_named=plan_named)
        modes[g.mode] = modes.get(g.mode, 0) + 1
        if not g.hallucinated and not g.unbounded:
            armed.update(g.members)
    print(f"\n[SUT grounding on synthetic 32 samples]  plan_named ids={len(set(plan_named) & set(SAMPLES))}")
    print(f"  grounding modes: {modes}")
    print(f"  DISTINCT region surfaces ARMED = {len(armed)} / {N}")

    armed_n = len(armed)
    print("\n" + "-" * 60)
    if armed_n >= N:
        verdict = (f"FULL — the real compile named/armed all {N} surfaces. V2's full-coverage path is REAL; "
                   "the V2-vs-V2nc coverage contrast is EQUAL when the compile is faithful, and the cap only "
                   "bites under a bare template.")
    elif armed_n >= N - 2:
        verdict = (f"NEAR-FULL — armed {armed_n}/{N}. Coverage essentially real; small fidelity slippage.")
    elif armed_n <= FAMILY_MEMBER_CAP + 1:
        verdict = (f"CAPPED/RE-TEMPLATED — armed {armed_n}/{N} (~cap {FAMILY_MEMBER_CAP}). V2 full coverage is "
                   "THEORETICAL: even a named-id plan, the LLM collapses toward <=24, so V2 caps near 24 in "
                   "practice and V2nc's enumeration GENUINELY out-covers it at high N — the stronger finding.")
    else:
        verdict = (f"PARTIAL — armed {armed_n}/{N} (between cap and full). Fidelity is imperfect; report the "
                   "exact number; V2nc still out-covers V2 by the shortfall.")
    print("VERDICT:", verdict)
    print(f"\nspend this check: ${cost}")
    print("DETERMINATION / NOT FROZEN / NOT CONFIRMATORY")
    return {"armed": armed_n, "N": N, "concrete_named": len(concrete_named),
            "templates": templates, "cost": cost, "with_pointer": with_pointer}


if __name__ == "__main__":
    main()
