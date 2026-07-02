"""A7 Phase-4: compute the A7-FIR table from the banked runs (runs/a7).

Read-only over banked traces. A7 runs are CLEAN tasks under benign noise, so ANY
orchestrator interrupt is a FALSE interrupt (base A7 pre-reg). Per-cell interrupt count =
run_end.replans (the disruptive orchestrator interrupts that re-planned); escalations,
interrupt-events, dismissals, and grind-death (reason==escalation_loop) are reported as
context. A7-FIR (addendum metric, denominator = interruptible-events) is operationalized
here as false-interrupts / qualified-cell, one qualified cell = one interruptible-event
(stated explicitly; the frozen text left the event unit open). This differs from prereg §6.1
FIR (denominator = total interrupts) and is labelled A7-FIR throughout.
"""
import json, os, statistics

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER = os.path.join(REPO, "runs", "a7", "a7_results.jsonl")
ROWS = [json.loads(l) for l in open(LEDGER, encoding="utf-8") if l.strip()]

CLASS_ORDER = ["transient_500", "additive_field", "latency_spike"]
TASKS = ["a1", "b1", "c1", "d1"]


def trace(run_dir):
    p = os.path.join(REPO, run_dir, "trace.jsonl")
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def cell(r):
    ev = trace(r["run_dir"])
    re = next((e["payload"] for e in ev if e["event_type"] == "run_end"), {})
    n = lambda t: sum(1 for e in ev if e["event_type"] == t)
    land = r.get("noise_landed_on") or {}
    return {
        "task": r["task"], "seed": r["seed"], "success": r["success"],
        "replans": re.get("replans", 0), "escalations": re.get("escalations", 0),
        "interrupt_events": n("interrupt"), "pauses": n("pause"),
        "dismissals": n("dismissal"),
        "grind": re.get("reason") == "escalation_loop",
        "reason": re.get("reason"),
        "landing": (land.get("landed_on") if land else None),
        "landing_counter": land.get("counter") if land else None,
    }


def pct(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    i = min(len(s) - 1, int(round(p / 100.0 * (len(s) - 1))))
    return s[i]


qual = {(r["task"], r["noise_class"]): r["success"]
        for r in ROWS if r["phase"] == "qual"}
fir_ran = [r for r in ROWS if r["phase"] == "fir" and r["status"] == "ran"]
disq = [r for r in ROWS if r["status"] == "disqualified"]

print("=" * 78)
print("A7 BENIGN-NOISE SMOKE — FIR RESULTS (post-hoc exploratory; addendum 2026-07-02)")
print("run date 2026-07-03 | CLI 2.1.198 | matrix COMPLETE 36/36 | total $%.4f | cap $15 not bound"
      % sum(r["cost_usd"] for r in ROWS))
print("=" * 78)

print("\nS1 QUALIFICATION (per-cell M6 gate): S1 must PASS clean under the noise, else DISQUALIFY")
for cls in CLASS_ORDER:
    line = []
    for t in TASKS:
        q = qual.get((t, cls))
        line.append(f"{t}={'PASS' if q else 'FAIL/DISQ' if q is False else '-'}")
    print(f"  {cls:15s}: " + "  ".join(line))
print("  -> DISQUALIFIED (S1 failed under noise): "
      + ", ".join(sorted(d["key"].split(':')[1] + '/' + d["key"].split(':')[2] for d in disq)) or "none")

print("\nPER-CELL A7-FIR (interrupt = run_end.replans; all false since benign). "
      "'land' = the transient-500 landing call.")
hdr = f"  {'arm':3s} {'class':15s} {'task':4s} {'seed':4s} {'FIR':>3s} {'esc':>3s} {'intEv':>5s} {'pause':>5s} {'dis':>3s} {'grind':>5s} {'ok':>3s} {'land':>7s}"
print(hdr); print("  " + "-" * (len(hdr) - 2))
agg = {}
for arm in ("V2", "S2"):
    for cls in CLASS_ORDER:
        cells = [cell(r) for r in fir_ran
                 if r["arm"] == arm and r["noise_class"] == cls]
        agg[(arm, cls)] = cells
        for c in cells:
            print(f"  {arm:3s} {cls:15s} {c['task']:4s} {str(c['seed']):4s} "
                  f"{c['replans']:>3d} {c['escalations']:>3d} {c['interrupt_events']:>5d} "
                  f"{c['pauses']:>5d} {c['dismissals']:>3d} {str(c['grind']):>5s} "
                  f"{'Y' if c['success'] else 'N':>3s} {str(c['landing'] or ''):>7s}")

print("\nA7-FIR PER (arm x class)  [FIR-rate = sum(false interrupts) / qualified cells]")
print(f"  {'arm':3s} {'class':15s} {'cells':>5s} {'sumFIR':>6s} {'cells_w_int':>11s} {'FIR_rate':>8s} {'grind':>5s}")
for arm in ("V2", "S2"):
    for cls in CLASS_ORDER:
        cs = agg[(arm, cls)]
        s = sum(c["replans"] for c in cs)
        cwi = sum(1 for c in cs if c["replans"] > 0)
        gr = sum(1 for c in cs if c["grind"])
        rate = (s / len(cs)) if cs else float('nan')
        print(f"  {arm:3s} {cls:15s} {len(cs):>5d} {s:>6d} {cwi:>11d} {rate:>8.3f} {gr:>5d}")

print("\nA7-FIR DISTRIBUTION per arm (over all its ran FIR cells; false interrupts/cell)")
for arm in ("V2", "S2"):
    allc = [c["replans"] for cls in CLASS_ORDER for c in agg[(arm, cls)]]
    print(f"  {arm}: n={len(allc)}  median={statistics.median(allc) if allc else '-'}  "
          f"P95={pct(allc, 95)}  max={max(allc) if allc else '-'}  "
          f"total_false_interrupts={sum(allc)}  grind_deaths="
          f"{sum(1 for cls in CLASS_ORDER for c in agg[(arm, cls)] if c['grind'])}")

print("\nCLEAN-RUN SUCCESS UNDER NOISE (A7) vs noise-free baseline")
for arm in ("V2", "S2"):
    allc = [c for cls in CLASS_ORDER for c in agg[(arm, cls)]]
    ok = sum(1 for c in allc if c["success"])
    print(f"  {arm}: {ok}/{len(allc)} = {ok/len(allc)*100:.1f}%  under A7 noise")
print("  (noise-free confirmatory reference: V2 clean 8/12 = 66.7%, A6; S2 baseline per confirmatory)")

print("\nSELF-STARVATION (§6) INDICATOR: cells where a false interrupt coincided with a "
      "grind-death or a task failure")
for arm in ("V2", "S2"):
    allc = [c for cls in CLASS_ORDER for c in agg[(arm, cls)]]
    ss = [c for c in allc if c["replans"] > 0 and (c["grind"] or not c["success"])]
    print(f"  {arm}: {len(ss)} cell(s) with false-interrupt + (grind or fail): "
          + (", ".join(f"{c['task']}({c['reason']})" for c in ss) or "none"))
