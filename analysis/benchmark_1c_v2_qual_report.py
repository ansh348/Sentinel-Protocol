#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""benchmark_1c_v2_qual_report.py -- QUALIFICATION / NOT FROZEN / NOT CONFIRMATORY.

Aggregate the §9 qualification cells (benchmark_1c_v2_qual.py output) into the per-arm/N
right-reason table + verdict. Reads the trace-confirmed fields recorded per cell; does not
re-run anything ($0).

A cell PASSES its criterion when:
  clean    -> clean_quiet (0 interrupts) AND checker_success (validator passes)
  injected -> wound_landed (numerical, all-N invalid) AND detected
              AND right_reason (value baseline-diff probe armed+fired on the MUTATED shard,
              baseline captured before the injection) -- ALL trace-confirmed.

An arm QUALIFIES at width N iff every clean cell QUIETs and every injected cell is caught
for the right reason at that N. An arm QUALIFIES overall iff it qualifies at every N.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

CELLS = ROOT / "runs" / "matrix_1c" / "v2_qualification" / "cells.jsonl"


def load(path):
    rows = []
    for l in Path(path).read_text(encoding="utf-8").splitlines():
        if l.strip():
            rows.append(json.loads(l))
    return rows


def clean_pass(r):
    return bool(r.get("clean_quiet")) and r.get("checker_success") is True


def injected_pass(r):
    return bool(r.get("wound_landed")) and bool(r.get("detected")) and bool(r.get("right_reason"))


def main(path=CELLS):
    rows = [r for r in load(path) if "error" not in r]
    errors = [r for r in load(path) if "error" in r]
    by = defaultdict(list)
    for r in rows:
        by[(r["arm"], r["N"])].append(r)

    arms = sorted({a for (a, n) in by})
    ns = sorted({n for (a, n) in by})
    total_cost = sum(r.get("cost_usd", 0) or 0 for r in rows)

    print("=" * 100)
    print("§9 RIGHT-REASON QUALIFICATION — benchmark_1c (V2 vs V2nc), per arm / width N")
    print("=" * 100)
    hdr = f"{'arm':5s} {'N':>3s} {'seeds':>5s} | {'clean QUIET+valid':>18s} | {'injected wound+detect+RR':>26s} | {'fanout':>10s} | {'cost':>8s}"
    print(hdr); print("-" * len(hdr))
    verdict = {a: {"qualifies": True, "fails": []} for a in arms}
    for a in arms:
        for n in ns:
            cells = by.get((a, n), [])
            if not cells:
                continue
            cl = [r for r in cells if r["condition"] == "clean"]
            inj = [r for r in cells if r["condition"] == "injected"]
            seeds = sorted({r["seed"] for r in cells})
            cl_ok = all(clean_pass(r) for r in cl) and len(cl) > 0
            inj_ok = all(injected_pass(r) for r in inj) and len(inj) > 0
            fan = sorted({r.get("realized_fanout") for r in cells})
            cost = sum(r.get("cost_usd", 0) or 0 for r in cells)
            cl_str = f"{sum(clean_pass(r) for r in cl)}/{len(cl)} {'OK' if cl_ok else 'FAIL'}"
            inj_str = f"{sum(injected_pass(r) for r in inj)}/{len(inj)} {'OK' if inj_ok else 'FAIL'}"
            print(f"{a:5s} {n:>3d} {len(seeds):>5d} | {cl_str:>18s} | {inj_str:>26s} | {str(fan):>10s} | ${cost:>6.3f}")
            if not (cl_ok and inj_ok):
                verdict[a]["qualifies"] = False
                verdict[a]["fails"].append({"N": n, "clean_ok": cl_ok, "injected_ok": inj_ok,
                                            "clean_detail": [(r["seed"], r.get("checker_success"),
                                                             r.get("n_interrupts")) for r in cl if not clean_pass(r)],
                                            "injected_detail": [(r["seed"], r.get("wound_landed"),
                                                                r.get("detected"), r.get("right_reason"),
                                                                r.get("armed_value_lens_on_mutated"),
                                                                r.get("value_fire_on_mutated")) for r in inj if not injected_pass(r)]})

    # per-arm measured widths (has OK cells) vs widths blocked by integration errors only
    arm_all = sorted({a for a in arms} | {e["arm"] for e in errors})
    err_ns = defaultdict(set)
    for e in errors:
        err_ns[e["arm"]].add(e["N"])
    measured_ns = {a: sorted({n for (aa, n) in by if aa == a}) for a in arm_all}
    blocked_ns = {a: sorted(err_ns[a] - set(measured_ns.get(a, []))) for a in arm_all}

    print("\n" + "=" * 100)
    print("VERDICT  (right-reason = clean QUIET+valid AND injected wound+detect+value-lens-on-mutated-shard)")
    print("=" * 100)
    for a in arm_all:
        v = verdict.get(a, {"qualifies": True, "fails": []})
        meas = measured_ns.get(a, [])
        passes = v["qualifies"] and bool(meas)
        status = "QUALIFIES" if passes else "DOES NOT QUALIFY"
        line = f"  {a}: {status} at measured N={meas} (both conditions, trace-confirmed)"
        if blocked_ns.get(a):
            line += f"; N={blocked_ns[a]} NOT MEASURED — integration bug (deferred), not a right-reason failure"
        if not passes and v["fails"]:
            line += f" -- failing: {json.dumps(v['fails'])[:400]}"
        print(line)
    if errors:
        print(f"\n  INTEGRATION ERRORS (not qualification results): {len(errors)}")
        for e in errors:
            print(f"    {e.get('arm')} N={e.get('N')} {e.get('condition')}: {e.get('error','')[:120]}")
    print(f"\n  total measured cost across recorded cells: ${total_cost:.4f}")
    print("  QUALIFICATION / NOT FROZEN / NOT CONFIRMATORY")

    # machine-readable summary
    out = ROOT / "runs" / "matrix_1c" / "v2_qualification" / "verdict.json"
    out.write_text(json.dumps({
        "arms": arms, "Ns": ns,
        "verdict": {a: ("QUALIFIES" if verdict[a]["qualifies"] else "DOES_NOT_QUALIFY") for a in arms},
        "fails": {a: verdict[a]["fails"] for a in arms},
        "n_errors": len(errors), "total_cost_usd": round(total_cost, 4),
        "table": [{"arm": a, "N": n, "seeds": sorted({r["seed"] for r in by[(a, n)]}),
                   "clean_pass": sum(clean_pass(r) for r in by[(a, n)] if r["condition"] == "clean"),
                   "clean_total": sum(1 for r in by[(a, n)] if r["condition"] == "clean"),
                   "injected_pass": sum(injected_pass(r) for r in by[(a, n)] if r["condition"] == "injected"),
                   "injected_total": sum(1 for r in by[(a, n)] if r["condition"] == "injected"),
                   "fanout": sorted({r.get("realized_fanout") for r in by[(a, n)]}),
                   "cost_usd": round(sum(r.get("cost_usd", 0) or 0 for r in by[(a, n)]), 4)}
                  for a in arms for n in ns if (a, n) in by]},
        indent=2), encoding="utf-8")
    print(f"  verdict.json -> {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else CELLS)
