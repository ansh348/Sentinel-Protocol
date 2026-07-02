"""V3 ARCHAEOLOGY — cost autopsy (READ-ONLY, scratch, NOT imported by the suite).

Post-verdict, exploratory decomposition of the 1b confirmatory FAIL for the v3 design.
Reads three frozen artifacts and writes NOTHING:
  - runs/matrix_1b/results.jsonl          (the seal-safe ledger; 172 rows)
  - runs/matrix_1b/runs/<cell>/trace.jsonl (per-cell event stream w/ per-event usage.cost_usd)
  - runs/matrix_1b/gate_report_final.json (authoritative gate numbers; cross-check target)

It re-runs no cell, mutates no ledger/trace/report, and never recomputes the verdict. The
held-out is spent, so per-cell held-out trace reads are permitted (per the brief).

Run:  ../.venv/Scripts/python.exe analysis/v3_autopsy_scratch.py
"""
from __future__ import annotations

import glob
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LEDGER = REPO / "runs" / "matrix_1b" / "results.jsonl"
RUNS = REPO / "runs" / "matrix_1b" / "runs"
GATE = REPO / "runs" / "matrix_1b" / "gate_report_final.json"

# Cost-bearing event_types (verified across all 172 traces). Everything else
# (corroboration, tripwire_set, interrupt, suppressed_refire, escalation, cadence,
# run_start/end, success_check, pause, redispatch, uncovered) carries NO usage.cost_usd.
COST_EVENTS = {"plan", "compile", "worker_end", "aggregate", "replan"}


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def pearson(xs, ys):
    pts = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pts) < 3:
        return None
    xs2, ys2 = [p[0] for p in pts], [p[1] for p in pts]
    mx, my = sum(xs2) / len(xs2), sum(ys2) / len(ys2)
    num = sum((x - mx) * (y - my) for x, y in pts)
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs2))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys2))
    return num / (dx * dy) if dx and dy else None


def load_ledger():
    rows = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def parse_trace(d: Path):
    """One per-cell trace -> a compact record. Joined to the ledger by (task, arm,
    injection, round(total_cost_usd, 6)); total == run_end.cost_usd == sum(usage.cost_usd)."""
    evs = [json.loads(l) for l in d.joinpath("trace.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    if not evs:
        return None
    buckets = Counter()
    for e in evs:
        u = e.get("usage") or {}
        c = u.get("cost_usd") or 0.0
        if c:
            buckets[e["event_type"] if e["event_type"] in COST_EVENTS else "other"] += c
    total = round(sum(buckets.values()), 6)
    run_id = evs[0]["run_id"]
    parts = run_id.split("-")  # task-arm-injection-sSEED (injection uses '_' not '-')
    task, arm, inj = parts[0], parts[1], parts[2]
    re_ev = next((e for e in evs if e["event_type"] == "run_end"), None)
    rep = (re_ev or {}).get("payload", {}) if re_ev else {}
    tw = [e for e in evs if e["event_type"] == "tripwire_set"]
    armed = tw[-1]["payload"].get("count") if tw else 0
    uniq_targets = len(set(tw[-1]["payload"].get("targets", []))) if tw else 0
    arm_sweep = next((e["payload"].get("probed", 0) for e in evs
                      if e["event_type"] == "corroboration"
                      and e["payload"].get("layer") == "v2_arm_baseline"), 0)
    pre_swept = sum(len(e["payload"].get("swept", [])) for e in evs
                    if e["event_type"] == "corroboration"
                    and e["payload"].get("layer") == "v2_pre_completion_sweep")
    return {
        "run_id": run_id, "task": task, "arm": arm, "inj": inj,
        "total": total, "buckets": dict(buckets),
        "compile": round(buckets.get("compile", 0.0), 6),
        "plan": round(buckets.get("plan", 0.0), 6),
        "worker": round(buckets.get("worker_end", 0.0), 6),
        "aggregate": round(buckets.get("aggregate", 0.0), 6),
        "replan_cost": round(buckets.get("replan", 0.0), 6),
        "n_compile_ev": sum(1 for e in evs if e["event_type"] == "compile"),
        "n_replan_ev": sum(1 for e in evs if e["event_type"] == "replan"),
        "n_interrupt_ev": sum(1 for e in evs if e["event_type"] == "interrupt"),
        "armed": armed, "uniq_targets": uniq_targets,
        "arm_sweep_probed": arm_sweep, "pre_swept": pre_swept,
        "success": rep.get("success"), "reason": rep.get("reason"),
        "detail": (rep.get("detail") or "")[:90], "replans": rep.get("replans"),
        "llm_calls": rep.get("llm_calls"),
    }


def load_traces():
    out = {}
    for d in sorted(RUNS.glob("*")):
        if d.is_dir() and d.joinpath("trace.jsonl").exists():
            r = parse_trace(d)
            if r:
                out[(r["task"], r["arm"], r["inj"], r["total"])] = r
    return out


def join(row, traces):
    inj = row["injection"] or "clean"
    key = (row["task"], row["arm"], inj, round(row["result"]["total_cost_usd"], 6))
    if key in traces:
        return traces[key]
    # fallback: nearest cost within the (task,arm,inj) group
    cands = [t for (tk, ar, ij, _), t in traces.items() if (tk, ar, ij) == (row["task"], row["arm"], inj)]
    if not cands:
        return None
    return min(cands, key=lambda t: abs(t["total"] - row["result"]["total_cost_usd"]))


def main():
    rows = load_ledger()
    traces = load_traces()
    gate = json.loads(GATE.read_text(encoding="utf-8"))
    gd = {g["gate"]: g for g in gate["gates"]}

    clean = [r for r in rows if r["kind"] == "matrix-clean"]
    inj = [r for r in rows if r["kind"] == "matrix-injected"]

    def arm(rs, a):
        return [r for r in rs if r["arm"] == a]

    print("=" * 78)
    print("V3 ARCHAEOLOGY — COST AUTOPSY (read-only)   ledger rows:", len(rows),
          " traces:", len(traces))
    print("=" * 78)

    # ---------------------------------------------------------------- G3
    print("\n##### G3 — KG3 CLEAN-CELL OVERHEAD ATTRIBUTION #####")
    v2c, s1c = arm(clean, "V2"), arm(clean, "S1")
    v2_med = med([r["result"]["total_cost_usd"] for r in v2c])
    s1_med = med([r["result"]["total_cost_usd"] for r in s1c])
    print(f"V2 clean median ${v2_med:.6f} | S1 clean median ${s1_med:.6f} | "
          f"overhead {(v2_med - s1_med) / s1_med * 100:.2f}%  "
          f"(gate: {gd['1bKG3']['overhead_fraction']*100:.2f}%)")
    print(f"V2 clean replans all zero? {all(r['result']['replans'] in (0, None) for r in v2c)}")

    def bucket_medians(cells, label):
        ts = [join(r, traces) for r in cells]
        ts = [t for t in ts if t]
        b = {k: med([t[k] for t in ts]) for k in ("plan", "compile", "worker", "aggregate", "replan_cost", "total")}
        print(f"  {label} (n={len(ts)}) median buckets:  "
              f"plan {b['plan']}  compile {b['compile']}  worker {b['worker']}  "
              f"aggregate {b['aggregate']}  replan {b['replan_cost']}  | total {b['total']}")
        return b
    bv = bucket_medians(v2c, "V2 clean")
    bs = bucket_medians(s1c, "S1 clean")
    print(f"  => V2-S1 total delta ${v2_med - s1_med:.4f} ; V2 compile-bucket median "
          f"${bv['compile']:.4f}  (compile ~= overhead delta; S1 has NO compile bucket: "
          f"{bs['compile']})")
    # FIXED vs VARIABLE on clean
    vts = [t for t in (join(r, traces) for r in v2c) if t]
    print(f"  FIXED per-run on clean: compile present in {sum(1 for t in vts if t['compile']>0)}/{len(vts)} "
          f"V2 clean cells; arm-sweep $0 (substrate). VARIABLE (replan) cost on clean: "
          f"{sum(t['replan_cost'] for t in vts):.4f} total (clean has no injection->no replan).")
    # Armed vs fired, clean + injected, per category
    print("\n  Probes ARMED vs FIRED/exercised (D32 family-arming breadth):")
    for scope, cells in (("clean", v2c), ("injected", arm(inj, "V2"))):
        ts = [t for t in (join(r, traces) for r in cells) if t]
        print(f"   V2 {scope}: armed(count) med {med([t['armed'] for t in ts])} | "
              f"unique targets med {med([t['uniq_targets'] for t in ts])} | "
              f"arm-sweep probed med {med([t['arm_sweep_probed'] for t in ts])} | "
              f"pre-completion swept med {med([t['pre_swept'] for t in ts])} | "
              f"interrupts med {med([t['n_interrupt_ev'] for t in ts])}")
    # Injected-cell cost blowup (NOT gated by KG3, but shows compile-paid-per-replan):
    for a in ("V2", "S1", "S3"):
        cc = arm(inj, a)
        cm = med([r["result"]["total_cost_usd"] for r in cc])
        ts2 = [t for t in (join(r, traces) for r in cc) if t]
        comp = med([t["compile"] for t in ts2]) if a == "V2" else 0.0
        repc = med([t["replan_cost"] for t in ts2])
        ncomp = med([t["n_compile_ev"] for t in ts2])
        print(f"  injected median total {a} ${cm:.4f}  (V2 compile-bucket ${comp:.4f}, "
              f"replan-bucket ${repc:.4f}, compile events {ncomp})")
    print("   by category (V2 injected) armed vs arm-sweep-probed vs interrupts:")
    bycat = defaultdict(list)
    for r in arm(inj, "V2"):
        t = join(r, traces)
        if t:
            bycat[r["category"]].append(t)
    for cat, ts in sorted(bycat.items()):
        print(f"     {cat:20s} n={len(ts)} armed {med([t['armed'] for t in ts])}  "
              f"arm-probed {med([t['arm_sweep_probed'] for t in ts])}  "
              f"interrupts {med([t['n_interrupt_ev'] for t in ts])}  "
              f"compiles(events) {med([t['n_compile_ev'] for t in ts])}")

    # ---------------------------------------------------------------- G4
    print("\n##### G4 — KG4 WASTE + TTD DECOMPOSITION #####")
    # KG4 denominator is ALL non-clean cells (injected + holdout = 31/arm) — the brief's
    # "S3 inert 0/31". Holdout (quota_cliff/silent_minor_bump) cells count toward waste
    # and detections, so the gate's medians are over the 31-cell set, not injected-only.
    nonclean = [r for r in rows if r["kind"] != "matrix-clean"]
    v2i, s3i = arm(nonclean, "V2"), arm(nonclean, "S3")
    v2_waste = med([r["result"]["wasted"]["tokens"] for r in v2i])
    s3_waste = med([r["result"]["wasted"]["tokens"] for r in s3i])
    v2_waste_inj = med([r["result"]["wasted"]["tokens"] for r in arm(inj, "V2")])
    print(f"V2 non-clean wasted-tokens median {v2_waste} (injected-only {v2_waste_inj}) | "
          f"S3 {s3_waste} | ratio {v2_waste / s3_waste:.4f}  "
          f"(gate waste_ratio {gd['1bKG4']['waste_ratio']:.4f})  [n_nonclean V2={len(v2i)}]")
    # monitoring overhead in tokens ~ 0 (substrate carries no usage); show discarded-worker churn
    print("  Monitoring overhead (probe LLM tokens): $0 / 0 tokens — corroboration/tripwire/"
          "interrupt events carry NO usage (verified). Waste = discarded worker + replan rework.")
    dw = [(r["result"]["replans"], len(r["result"]["wasted"]["discarded_workers"]),
           r["result"]["wasted"]["tokens"], r["result"]["ttd_tool_calls"]) for r in v2i]
    print(f"  V2 non-clean: median discarded_workers {med([d[1] for d in dw])}, "
          f"cells with >=1 replan {sum(1 for d in dw if (d[0] or 0) >= 1)}/{len(dw)}, "
          f"cells with >=1 discarded worker {sum(1 for d in dw if d[1] >= 1)}/{len(dw)}")
    has = [d[2] for d in dw if d[1] >= 1]
    no = [d[2] for d in dw if d[1] == 0]
    print(f"  waste median WITH discard ({len(has)} cells) {med(has)} vs NO discard "
          f"({len(no)} cells) {med(no)}")
    print(f"  corr(replans, waste) nonclean {pearson([d[0] for d in dw], [d[2] for d in dw]):.3f} ; "
          f"corr(ttd, waste) {pearson([d[3] for d in dw], [d[2] for d in dw]):.3f} ; "
          f"corr(discarded_workers, waste) {pearson([d[1] for d in dw], [d[2] for d in dw]):.3f}")
    di = [(r['result']['replans'], len(r['result']['wasted']['discarded_workers']),
           r['result']['wasted']['tokens'], r['result']['ttd_tool_calls'])
          for r in arm(inj, 'V2') if r['result']['detected']]
    print(f"  [detected-injected n={len(di)}] corr(ttd,waste) {pearson([d[3] for d in di],[d[2] for d in di])} ; "
          f"corr(replans,waste) {pearson([d[0] for d in di],[d[2] for d in di])}")
    # TTD distribution among V2 detections
    det = [r for r in v2i if r["result"]["detected"]]
    ttd_vals = [r["result"]["ttd_tool_calls"] for r in det if r["result"]["ttd_tool_calls"] is not None]
    ttd_null = sum(1 for r in det if r["result"]["ttd_tool_calls"] is None)
    print(f"  V2 detections (injected): {len(det)}; with TTD {len(ttd_vals)} "
          f"(median {med(ttd_vals)}, gate {gd['1bKG4']['v2_ttd_median']}) ; null-TTD (fast-path) {ttd_null}")
    print(f"  TTD values sorted: {sorted(ttd_vals)}")
    print(f"  S3 detections (injected): {sum(1 for r in s3i if r['result']['detected'])} "
          f"-> S3 TTD median {gd['1bKG4']['s3_ttd_median']} -> ttd_ratio {gd['1bKG4']['ttd_ratio']} (KG4 {gd['1bKG4']['status']})")

    # ---------------------------------------------------------------- G2
    print("\n##### G2 — KG2 CLEAN-SUCCESS GAP + FIR-0 ROBUSTNESS #####")
    def succ(cells):
        ok = sum(1 for r in cells if r["result"]["success"] is True)
        return ok, len(cells)
    vo, vn = succ(v2c)
    so, sn = succ(s1c)
    print(f"V2 clean success {vo}/{vn} ({vo/vn*100:.1f}%)  (gate {gd['1bKG2']['clean_success']*100:.1f}%) | "
          f"S1 {so}/{sn} ({so/sn*100:.1f}%) (gate {gd['1bKG2']['s1_clean_success']*100:.1f}%)")
    print(f"  clean FIR median {gd['1bKG2']['clean_median_fir']}, max false-interrupts "
          f"{gd['1bKG2']['clean_max_false_interrupts']}, status {gd['1bKG2']['status']}")

    def fails(cells, a):
        out = []
        for r in cells:
            if r["result"]["success"] is not True:
                t = join(r, traces)
                out.append((r["task"], r["slot"], r["result"]["success"],
                            r["result"]["n_interrupts"], round(r["result"]["total_cost_usd"], 3),
                            (t["reason"] if t else "?"), (t["detail"] if t else "")))
        return out
    print("  V2 clean non-successes (task, slot, success, n_interrupts, cost, run_end.reason, detail):")
    for f in fails(v2c, "V2"):
        print("    ", f)
    print("  S1 clean non-successes:")
    for f in fails(s1c, "S1"):
        print("    ", f[:5])
    # FIR-0 robustness: b1 (legitimate-write / D31 FP-prone) clean cells across arms
    print("\n  FIR-0 robustness — b1 clean (legitimate settings.yaml-migration write, D31 FP-prone):")
    for a in ("V2", "S2", "S1", "S3"):
        b1 = [r for r in clean if r["task"] == "b1" and r["arm"] == a]
        print(f"    {a}: n={len(b1)} interrupts={[r['result']['n_interrupts'] for r in b1]} "
              f"fir={[r['result']['fir'] for r in b1]} success={[r['result']['success'] for r in b1]}")
    # S2 false-positive contrast on all clean
    s2c = arm(clean, "S2")
    s2_fp = [(r['task'], r['slot']) for r in s2c if (r['result']['false_interrupts'] or 0) > 0]
    print(f"  S2 clean false-interrupt cells (FP-prone tripped naive arm): {s2_fp}  "
          f"vs V2 clean false-interrupts total {sum(r['result']['false_interrupts'] or 0 for r in v2c)}")

    print("\n##### CROSS-CHECK vs gate_report_final.json #####")
    print(f"  overhead {(v2_med-s1_med)/s1_med:.6f} vs {gd['1bKG3']['overhead_fraction']:.6f}")
    print(f"  waste_ratio {v2_waste/s3_waste:.6f} vs {gd['1bKG4']['waste_ratio']:.6f}")
    print(f"  v2_waste {v2_waste} vs {gd['1bKG4']['v2_wasted_tokens_median']} ; "
          f"s3_waste {s3_waste} vs {gd['1bKG4']['s3_wasted_tokens_median']}")
    print(f"  n_detections {len(det)} vs {gd['1bKG1']['recovery_quality']['n_detections']}")
    print(f"  verdict (unchanged, not recomputed): {gate['verdict']}")


if __name__ == "__main__":
    main()
