"""DIRECTIONAL / WEAK CV-trend check from banked 1b cells (READ-ONLY, scratch).

The Phase-1c power sizing assumes the per-seed cost-difference CV (~2.2 at n~=3) stays roughly
CONSTANT as fan-out grows. This pulls a FREE directional read from 1b cells that emergently ran
at different realized widths. It is a WEAK, short-lever test (realized w spans only ~1..4, and
the useful contrast is 3 vs 4) — NOT a substitute for the N=8 pilot. Do not extrapolate to N>4.

Reads results.jsonl + per-cell trace.jsonl. Writes ONLY runs/matrix_1b/cv_trend_check.json.
No LLM calls, no runs, no edits to anything frozen.

Realized width = max workers ALIVE SIMULTANEOUSLY (interval overlap of [worker_start, worker_end]),
re-derived from the traces (not a cached number).
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LEDGER = REPO / "runs" / "matrix_1b" / "results.jsonl"
RUNS = REPO / "runs" / "matrix_1b" / "runs"
OUT = REPO / "runs" / "matrix_1b" / "cv_trend_check.json"


def mean(xs): return st.fmean(xs) if xs else None
def sd(xs): return st.stdev(xs) if len(xs) > 1 else None
def cv(xs):
    m = mean(xs)
    return (sd(xs) / abs(m)) if (m not in (None, 0) and len(xs) > 1) else None


def realized_width(run_id: str) -> int:
    p = RUNS / run_id / "trace.jsonl"
    if not p.exists():
        return 0
    evs = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    starts, ends = {}, {}
    for e in evs:
        if e["event_type"] == "worker_start":
            starts[e["actor"]] = e["ts"]
        elif e["event_type"] == "worker_end":
            ends[e["actor"]] = e["ts"]
    pts = []
    for a, t0 in starts.items():
        t1 = ends.get(a, t0)               # no end recorded -> degenerate point
        pts.append((t0, 0))                # start: order 0 (process +1 before -1 on a tie)
        pts.append((t1, 1))                # end:   order 1
    pts.sort(key=lambda x: (x[0], x[1]))   # ISO ts sort lexicographically == chronological
    cur = mx = 0
    for _, kind in pts:
        cur += 1 if kind == 0 else -1
        mx = max(mx, cur)
    return mx


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    rows = [json.loads(l) for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()]
    # The ledger carries no run_id; enumerate run dirs directly (name encodes task/arm/injection;
    # run_end.cost_usd gives the cost) and nearest-cost-join the ledger for wasted.usd + slot.
    cells = []
    for d in sorted(RUNS.glob("*")):
        if not (d.is_dir() and (d / "trace.jsonl").exists()):
            continue
        rid = d.name
        parts = rid.split("-")
        task, arm = parts[0], parts[1]
        inj = "-".join(parts[2:-1])
        evs = [json.loads(l) for l in (d / "trace.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        re_ev = next((e for e in evs if e["event_type"] == "run_end"), None)
        cost = (re_ev or {}).get("payload", {}).get("cost_usd")
        cells.append({"rid": rid, "task": task, "arm": arm, "inj": inj,
                      "condition": "clean" if inj == "clean" else "injected",
                      "w": realized_width(rid), "cost": cost})
    # attach ledger metrics (wasted.usd) by matching rid pattern via (task,arm,inj,nearest cost)
    led_by = defaultdict(list)
    for r in rows:
        led_by[(r["task"], r["arm"], r["injection"] or "clean")].append(r)
    for key, cs in [( (c["task"], c["arm"], c["inj"]), c) for c in cells]:
        pass
    # nearest-cost join for wasted.usd
    for c in cells:
        cands = led_by.get((c["task"], c["arm"], c["inj"]), [])
        if cands and c["cost"] is not None:
            best = min(cands, key=lambda r: abs(r["result"]["total_cost_usd"] - c["cost"]))
            c["wasted_usd"] = (best["result"]["wasted"]["usd"] or 0.0)
            c["slot"] = best["slot"]
        else:
            c["wasted_usd"] = None
            c["slot"] = None

    # ---- STEP 1: width buckets per (w, arm, condition) ----
    buckets = defaultdict(int)
    for c in cells:
        buckets[(c["w"], c["arm"], c["condition"])] += 1
    width_dist = defaultdict(int)
    for c in cells:
        width_dist[c["w"]] += 1

    # ---- STEP 2: within-width paired D0/D1 (same task+slot+width across S1,V2) ----
    # pair key: clean (task,slot); injected (task,inj,slot). usable only if BOTH arms same width.
    by_pair = defaultdict(dict)
    for c in cells:
        if c["arm"] in ("S1", "V2") and c["slot"] is not None:
            k = (c["task"], c["inj"], c["slot"], c["condition"])
            by_pair[k][c["arm"]] = c
    D0w, D1w = defaultdict(list), defaultdict(list)
    usable_pairs = defaultdict(lambda: {"clean": 0, "injected": 0})
    dropped_width_mismatch = 0
    for k, d in by_pair.items():
        if "S1" not in d or "V2" not in d:
            continue
        if d["S1"]["w"] != d["V2"]["w"]:
            dropped_width_mismatch += 1
            continue
        w = d["S1"]["w"]
        diff = d["S1"]["cost"] - d["V2"]["cost"]
        if k[3] == "clean":
            D0w[w].append(diff); usable_pairs[w]["clean"] += 1
        else:
            D1w[w].append(diff); usable_pairs[w]["injected"] += 1

    def cv_table(Dw):
        return {str(w): {"n": len(v), "mean": mean(v), "sd": sd(v), "cv": cv(v)}
                for w, v in sorted(Dw.items())}
    d0_table, d1_table = cv_table(D0w), cv_table(D1w)

    # ---- STEP 3: CV trend at w=3 (anchor) vs w=4 (and w=2) ----
    def cvv(table, w): return table.get(str(w), {}).get("cv")
    def nn(table, w): return table.get(str(w), {}).get("n", 0)
    trend = {
        "D0_clean": {f"w={w}": {"cv": cvv(d0_table, w), "n": nn(d0_table, w)} for w in (2, 3, 4)},
        "D1_injected": {f"w={w}": {"cv": cvv(d1_table, w), "n": nn(d1_table, w)} for w in (2, 3, 4)},
    }

    # ---- STEP 4: pooled width-vs-variance proxy (more cells, single-arm |cost| & wasted) ----
    pooled = {}
    for arm in ("S1", "V2"):
        for cond in ("clean", "injected"):
            per_w = defaultdict(list)
            for c in cells:
                if c["arm"] == arm and c["condition"] == cond and c["cost"] is not None:
                    per_w[c["w"]].append(c["cost"])
            pooled[f"{arm}_{cond}_costCV_by_w"] = {
                str(w): {"n": len(v), "mean": mean(v), "cv": cv(v)} for w, v in sorted(per_w.items())}
    # OLS slope of cost on w across ALL cells (pooled), + residual |dev| CV by w
    pts = [(c["w"], c["cost"]) for c in cells if c["cost"] is not None]
    ws = [p[0] for p in pts]; cs = [p[1] for p in pts]
    mw, mc = mean(ws), mean(cs)
    cov = sum((w - mw) * (cc - mc) for w, cc in pts) / len(pts)
    varw = sum((w - mw) ** 2 for w in ws) / len(ws)
    slope = cov / varw if varw else None
    inter = mc - slope * mw if slope is not None else None
    resid_by_w = defaultdict(list)
    for w, cc in pts:
        resid_by_w[w].append(abs(cc - (inter + slope * w)) if slope is not None else 0.0)
    resid_spread = {str(w): {"n": len(v), "mean_abs_resid": mean(v)} for w, v in sorted(resid_by_w.items())}

    # ---- STEP 5: verdict (DIRECTIONAL / WEAK) ----
    n4 = max(nn(d0_table, 4), nn(d1_table, 4))
    n3 = max(nn(d0_table, 3), nn(d1_table, 3))
    cv3 = cvv(d1_table, 3) or cvv(d0_table, 3)
    cv4 = cvv(d1_table, 4) or cvv(d0_table, 4)
    if n4 < 3 or n3 < 3:
        verdict = ("(c) INDETERMINATE — too few usable within-width pairs to tell "
                   f"(usable injected/clean pairs: w3={usable_pairs.get(3)}, w4={usable_pairs.get(4)}). "
                   "The realized 1b widths barely vary (mostly 1 and 3); the N=8 pilot is the only "
                   "way to know whether CV holds at higher fan-out.")
        verdict_code = "c"
    elif cv3 and cv4 and cv4 > 1.5 * cv3:
        verdict = (f"(b) CV RISES 3->4 (CV3={cv3:.2f} n={n3}, CV4={cv4:.2f} n={n4}); constant-CV "
                   "suspect -> high-N grid likely underpowered; cap N and/or expect far more seeds. "
                   "WEAK (3-vs-4 lever, tiny n).")
        verdict_code = "b"
    else:
        verdict = (f"(a) NO CV rise detected 3->4 (CV3={cv3}, n={n3}; CV4={cv4}, n={n4}); consistent "
                   "with constant-CV but NOT confirmation — still recommend the real N=8 pilot before "
                   "freeze. WEAK (3-vs-4 lever, tiny n).")
        verdict_code = "a"

    artifact = {
        "meta": {"generated_by": "analysis/cv_trend_check.py", "read_only": True,
                 "FROZEN": False, "nature": "DIRECTIONAL / WEAK; realized w spans ~1..4 only; "
                 "do NOT extrapolate to N>4", "width_def": "max workers alive simultaneously "
                 "(interval overlap), re-derived from traces"},
        "step1_width_buckets": {
            "realized_width_distribution_all_cells": dict(sorted(width_dist.items())),
            "per_w_arm_condition": {f"w{w}|{a}|{c}": n for (w, a, c), n in sorted(buckets.items())},
            "note": "most buckets are tiny; widths barely vary in 1b (planner consolidation).",
        },
        "step2_paired_within_width": {
            "D0_clean_by_width": d0_table, "D1_injected_by_width": d1_table,
            "usable_pairs_per_width": {str(w): usable_pairs[w] for w in sorted(usable_pairs)},
            "pairs_dropped_width_mismatch": dropped_width_mismatch,
            "anchor_cv_1b_reference": "D0~2.43 / D1~2.10 pooled-across-widths (fanout_power_sim)",
        },
        "step3_cv_trend": trend,
        "step4_pooled_proxy": {
            "cost_CV_by_width": pooled,
            "ols_cost_on_width": {"slope": slope, "intercept": inter, "n": len(pts)},
            "mean_abs_residual_by_width": resid_spread,
            "note": "single-arm cost CV (not the difference); a second, weaker signal — cost mean "
                    "rises with w trivially, so watch the CV/residual-spread trend, not the mean.",
        },
        "step5_verdict": {"code": verdict_code, "text": verdict},
    }
    OUT.write_text(json.dumps(artifact, indent=1), encoding="utf-8")

    # ----------------------------- printed report -----------------------------
    print("=" * 80)
    print("CV-TREND DIRECTIONAL CHECK (1b banked; READ-ONLY; WEAK 3-vs-4 lever)")
    print("=" * 80)
    print("\n(1) REALIZED-WIDTH BUCKETS (max workers alive simultaneously)")
    print(f"  width distribution (all 172 cells): {dict(sorted(width_dist.items()))}")
    for (w, a, cond), n in sorted(buckets.items()):
        print(f"    w={w} {a:3s} {cond:9s}: {n}")
    print("  (most buckets tiny — 1b widths barely vary; stated, not hidden.)")

    print("\n(2) PAIRED WITHIN-WIDTH D0/D1 (same task+slot+width across S1,V2)")
    print(f"  pairs dropped for width-mismatch across arms: {dropped_width_mismatch}")
    print("  D0 clean:    " + " | ".join(
        f"w{w}: n={d['n']} cv={d['cv'] if d['cv'] is None else round(d['cv'],2)}" for w, d in d0_table.items()))
    print("  D1 injected: " + " | ".join(
        f"w{w}: n={d['n']} cv={d['cv'] if d['cv'] is None else round(d['cv'],2)}" for w, d in d1_table.items()))

    print("\n(3) CV TREND w=2/3/4 (anchor w=3 ~2.1-2.4)")
    for lab, t in trend.items():
        print(f"  {lab}: " + " | ".join(
            f"{w}: cv={v['cv'] if v['cv'] is None else round(v['cv'],2)} (n={v['n']})" for w, v in t.items()))

    print("\n(4) POOLED width-vs-variance proxy (single-arm cost CV by width)")
    print(f"  OLS cost~width: slope ${slope:.4f}/worker, intercept ${inter:.4f} (n={len(pts)})")
    print("  mean |residual| by width: " + " | ".join(
        f"w{w}: ${d['mean_abs_resid']:.3f} (n={d['n']})" for w, d in resid_spread.items()))
    for key, tab in pooled.items():
        print(f"  {key}: " + " | ".join(
            f"w{w}: cv={d['cv'] if d['cv'] is None else round(d['cv'],2)}(n={d['n']})" for w, d in tab.items()))

    print("\n(5) VERDICT [DIRECTIONAL / WEAK]")
    print(" ", verdict)
    print(f"\nartifact -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
