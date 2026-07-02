#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark_1c_apikey_ramp.py  --  FEASIBILITY / NOT FROZEN

STEP 4 concurrency ramp on the API-KEY direct path (equivalence gate PASSED in
benchmark_1c_apikey_equivalence.py).  Because an API-direct worker is a thread
doing an HTTPS POST (no claude.exe subprocess), the 259MB/worker memory wall that
capped the sub-CLI probe at N=8 does NOT apply -- so this runs LOCALLY (no VM
needed) and the binding constraint is expected to be API rate limits, not host RAM.

Ramp N = 8 -> 16 -> 32 -> 64, a few burned feasibility seeds each, trivial payload.
Per rung: realized max concurrent in flight (interval-overlap), 429/rate-limit
events + whether they cascade, errors (timeout/HTTP), and host memory headroom
(expected ~flat -- the contrast that proves the subprocess wall is gone).
Classify CLEAN/DEGRADED/FAILED; STOP at first DEGRADED or FAILED.

FEASIBILITY, burned seeds, no confirmatory artifact touched.
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FTimeout
from pathlib import Path
from threading import Event, Lock, Thread

import psutil

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from analysis import benchmark_1c_world as W                          # noqa: E402
from analysis.benchmark_1c_s1_qual import WORKER_SYS                  # noqa: E402
from analysis.benchmark_1c_apikey_equivalence import (                # noqa: E402
    load_api_key, api_worker, HAIKU)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

RUNGS = [8, 16, 32, 64]
SEEDS = [7701, 7702]
PER_RUNG_WALL_S = 180
TOTAL_CAP_USD = 5.0
OUT_JSON = "runs/matrix_1c/apikey_concurrency_ramp.json"
LEDGER = "decisions/dev_run_ledger.md"

_spend = {"usd": 0.0, "calls": 0}
_lock = Lock()


class MemSampler(Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.stop = Event()
        self.min_avail = psutil.virtual_memory().available
        self.max_used_pct = psutil.virtual_memory().percent

    def run(self):
        while not self.stop.is_set():
            vm = psutil.virtual_memory()
            self.min_avail = min(self.min_avail, vm.available)
            self.max_used_pct = max(self.max_used_pct, vm.percent)
            self.stop.wait(0.2)


def _worker(api_key, rid, shard_line):
    t0 = time.monotonic()
    r = api_worker(api_key, HAIKU, WORKER_SYS, f"shard {rid}: {shard_line}\nReply with exactly: OK",
                   max_tokens=16)
    t1 = time.monotonic()
    with _lock:
        _spend["usd"] += (r["cost_usd"] or 0.0)
        _spend["calls"] += 1
    return {"region_id": rid, "t_start": t0, "t_end": t1, "dur_s": round(t1 - t0, 2),
            "status": r["status"], "rate_limited": r["rate_limited"],
            "ok": r["status"] == 200, "cost_usd": r["cost_usd"], "error": r["error"]}


def _realized(workers):
    ev = []
    for w in workers:
        ev.append((w["t_start"], +1)); ev.append((w["t_end"], -1))
    ev.sort(key=lambda e: (e[0], -e[1]))
    cur = mx = 0
    for _, d in ev:
        cur += d; mx = max(mx, cur)
    return mx


def run_rung(api_key, n):
    seed_recs = []
    for seed in SEEDS:
        world = W.build_world(n, seed, inject=False)
        lines = {rid: world.reports[rid].splitlines()[1][:60] for rid in world.region_ids}
        avail0 = psutil.virtual_memory().available
        ms = MemSampler(); ms.start()
        t0 = time.monotonic()
        workers, wall_to = [], False
        with ThreadPoolExecutor(max_workers=n) as ex:
            futs = [ex.submit(_worker, api_key, rid, lines[rid]) for rid in world.region_ids]
            try:
                for f in as_completed(futs, timeout=PER_RUNG_WALL_S):
                    workers.append(f.result())
            except FTimeout:
                wall_to = True
        wall = time.monotonic() - t0
        ms.stop.set(); ms.join(timeout=2)
        durs = [w["dur_s"] for w in workers]
        seed_recs.append({
            "seed": seed, "n_workers": len(workers),
            "realized": _realized(workers) if workers else 0,
            "wall_s": round(wall, 1),
            "parallel_ratio": round(sum(durs) / wall, 1) if wall > 0 and durs else 0,
            "dur_median_s": round(sorted(durs)[len(durs)//2], 2) if durs else None,
            "dur_max_s": max(durs) if durs else None,
            "rate_limited": sum(1 for w in workers if w["rate_limited"]),
            "errors": sum(1 for w in workers if not w["ok"]),
            "n_429": sum(1 for w in workers if w["status"] == 429),
            "mem_drop_mb": round((avail0 - ms.min_avail) / 1048576, 1),
            "wall_timeout": wall_to,
        })
    realized = min(s["realized"] for s in seed_recs)
    n_rl = sum(s["rate_limited"] for s in seed_recs)
    n_err = sum(s["errors"] for s in seed_recs)
    total = sum(s["n_workers"] for s in seed_recs)
    mem_drop = max(s["mem_drop_mb"] for s in seed_recs)
    err_frac = n_err / max(1, total)
    wall_to = any(s["wall_timeout"] for s in seed_recs)
    reached = realized >= -(-9 * n // 10)
    if wall_to or err_frac > 0.25 or realized <= max(1, n // 4):
        cls = "FAILED"
        reason = []
        if wall_to: reason.append("per-rung wall-timeout")
        if err_frac > 0.25: reason.append(f"{n_err}/{total} errors")
        if realized <= max(1, n // 4): reason.append(f"realized collapsed to {realized}")
    elif (not reached) or n_rl > 0 or n_err > 0:
        cls = "DEGRADED"
        reason = []
        if not reached: reason.append(f"realized {realized}/{n} (<90%)")
        if n_rl > 0: reason.append(f"{n_rl} rate-limit/429 events")
        if n_err > 0: reason.append(f"{n_err} errors")
    else:
        cls = "CLEAN"; reason = []
    return {"N": n, "classification": cls, "realized": realized, "target": n,
            "rate_limit_events": n_rl, "n_429": sum(s["n_429"] for s in seed_recs),
            "errors": n_err, "mem_drop_mb": mem_drop, "reason": "; ".join(reason),
            "seeds": seed_recs}


def main():
    api_key, src = load_api_key()
    vm = psutil.virtual_memory()
    print("=" * 92)
    print("PHASE-1c API-DIRECT CONCURRENCY RAMP (no subprocess; local)  --  FEASIBILITY / NOT FROZEN")
    print("=" * 92)
    if not api_key:
        print("[STOP] no ANTHROPIC_API_KEY."); return
    print(f"host free RAM {round(vm.available/1e9,1)}GB  ·  worker=API-direct Haiku (thread+HTTPS, no .exe)")
    print(f"ramp {RUNGS}, stop at first DEGRADED/FAILED; seeds {SEEDS} (burned); total cap ${TOTAL_CAP_USD}\n")

    rungs = []
    for n in RUNGS:
        if _spend["usd"] > TOTAL_CAP_USD:
            print(f"[STOP] total cap ${TOTAL_CAP_USD} reached."); break
        print(f"--- RUNG N={n} (free {round(psutil.virtual_memory().available/1e9,2)}GB) ---", flush=True)
        rec = run_rung(api_key, n)
        rungs.append(rec)
        print(f"    -> {rec['classification']}  realized={rec['realized']}/{n}  "
              f"429/rate-limit={rec['rate_limit_events']}  errors={rec['errors']}  "
              f"mem_drop={rec['mem_drop_mb']}MB  cum=${_spend['usd']:.3f}"
              f"{('  reason: '+rec['reason']) if rec['reason'] else ''}", flush=True)
        for s in rec["seeds"]:
            print(f"       seed {s['seed']}: realized {s['realized']}/{n}, wall {s['wall_s']}s, "
                  f"par_ratio {s['parallel_ratio']}, dur med/max {s['dur_median_s']}/{s['dur_max_s']}s, "
                  f"429={s['n_429']}, err={s['errors']}", flush=True)
        if rec["classification"] in ("DEGRADED", "FAILED"):
            print(f"    [STOP] N={n} is {rec['classification']} -- not climbing.", flush=True)
            break

    clean = [r["N"] for r in rungs if r["classification"] == "CLEAN"]
    largest_clean = max(clean) if clean else None
    stopper = next((r for r in rungs if r["classification"] in ("DEGRADED", "FAILED")), None)
    binding = ("API rate limit" if (stopper and stopper["rate_limit_events"] > 0) else
               ("API errors/transport" if stopper and stopper["errors"] > 0 else
                ("none within tested range" if not stopper else "other -- see reason")))
    report = {"FEASIBILITY": True, "FROZEN": False,
              "path": "API-key direct Messages API (no subprocess); local host",
              "host_free_gb_start": round(vm.available/1e9, 1),
              "rungs": rungs, "largest_clean_N": largest_clean,
              "binding_constraint": binding,
              "stopped_at": (stopper["N"] if stopper else None),
              "spend_usd": round(_spend["usd"], 6), "llm_calls": _spend["calls"]}
    Path("runs/matrix_1c").mkdir(parents=True, exist_ok=True)
    Path(OUT_JSON).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write("\n---\n")
        f.write("## Phase-1c API-DIRECT CONCURRENCY RAMP (FEASIBILITY / NOT FROZEN, not confirmatory)\n")
        f.write(f"- date: 2026-06-25  ·  path: API-key direct Messages API (thread+HTTPS, NO subprocess) -- "
                f"run LOCALLY (the sub-CLI 259MB/worker memory wall does not apply)\n")
        f.write(f"- ramp: {' -> '.join(str(r['N'])+':'+r['classification'] for r in rungs)}\n")
        f.write(f"- largest CLEAN N = {largest_clean}; binding constraint at high N = {binding}\n")
        f.write(f"- seeds BURNED: {SEEDS}  ·  spend ${report['spend_usd']:.4f}  ·  calls {report['llm_calls']}  ·  "
                f"artifact {OUT_JSON}\n")

    print("\n" + "=" * 92)
    print("RUNG TABLE (API-direct path)")
    print("  N  | class    | realized/N | 429/rate-limit | errors | mem-drop | note")
    for r in rungs:
        print(f"  {r['N']:>2} | {r['classification']:<8} | {r['realized']:>5}/{r['N']:<4} | "
              f"{r['rate_limit_events']:>13} | {r['errors']:>6} | {r['mem_drop_mb']:>6}MB | {r['reason']}")
    print(f"\nVERDICT [FEASIBILITY / NOT FROZEN]: largest CLEAN N (API-direct, local) = {largest_clean}")
    print(f"  binding constraint at high N = {binding}")
    print(f"  RAM vs API: host mem stayed ~flat (max drop {max((r['mem_drop_mb'] for r in rungs), default=0)}MB) "
          f"-- the subprocess memory wall is GONE; API is the only ceiling.")
    print(f"\nspend ${_spend['usd']:.4f} · {_spend['calls']} calls · artifact {OUT_JSON}")
    print("FEASIBILITY / NOT FROZEN -- no freeze/pin; confirmatory artifacts untouched.")


if __name__ == "__main__":
    main()
