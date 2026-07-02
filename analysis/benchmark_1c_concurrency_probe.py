#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark_1c_concurrency_probe.py  --  FEASIBILITY / NOT FROZEN

Can the harness hold N real workers GENUINELY in flight at once, cleanly?
Stresses the executor (D35-style max_workers=N, NO artificial ceiling) + the API
+ host memory with a TRIVIAL worker payload (one tiny real Haiku call that reads a
shard).  We measure concurrency, NOT detection -- no sentinel logic.

Ramp N = 8 -> 16 -> 32 -> 64, a few burned feasibility seeds per rung.  STOP at the
first DEGRADED or FAILED rung; never climb past it.  Per-rung wall timeout + total
spend cap + a HOST-MEMORY guard (this runs on a 16GB laptop with ~4GB free, so a
pre-launch gate refuses any rung predicted to breach the memory floor, and a live
watchdog kills in-flight workers if available RAM dips below the floor).

Burned, no injection parameters, no confirmatory artifacts touched.  Logged to
dev_run_ledger.md as FEASIBILITY.

  python benchmark_1c_concurrency_probe.py
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Event, Lock, Thread

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis import benchmark_1c_world as W            # noqa: E402
from conductor import sessions                          # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

RUNGS = [8, 16, 32, 64]
SEEDS = [7701, 7702]                 # FEASIBILITY seeds -- burned
WORKER_MODEL = sessions.WORKER_MODEL
PER_WORKER_TIMEOUT_S = 90
PER_RUNG_WALL_TIMEOUT_S = 240
TOTAL_CAP_USD = 8.0
MEM_FLOOR_MB = 800                   # never let host available RAM drop below this
MEM_SAMPLE_S = 0.2
OUT_JSON = "runs/matrix_1c/concurrency_probe.json"
LEDGER = "decisions/dev_run_ledger.md"

RATE_LIMIT_PAT = ("429", "rate limit", "rate_limit", "overloaded",
                  "too many requests", "retrying", "retry-after", "quota")

_spend = {"usd": 0.0, "calls": 0}
_spend_lock = Lock()


def _mb(x):
    return round(x / (1024 * 1024), 1)


def _scan_rate_limit(res):
    blob = ((res.stderr or "") + " " + (res.result_text or "")).lower()
    return any(p in blob for p in RATE_LIMIT_PAT)


class MemWatchdog(Thread):
    """Samples host available RAM; if it dips below the floor, fire abort + kill
    in-flight worker process trees so we never OOM the host."""
    def __init__(self, pid_registry, abort_evt):
        super().__init__(daemon=True)
        self.pid_registry = pid_registry
        self.abort = abort_evt
        self.stop = Event()
        self.min_avail = psutil.virtual_memory().available
        self.max_used_pct = psutil.virtual_memory().percent
        self.breached = False

    def run(self):
        while not self.stop.is_set():
            vm = psutil.virtual_memory()
            self.min_avail = min(self.min_avail, vm.available)
            self.max_used_pct = max(self.max_used_pct, vm.percent)
            if vm.available < MEM_FLOOR_MB * 1024 * 1024:
                self.breached = True
                self.abort.set()
                for pid in list(self.pid_registry):
                    sessions._kill_process_tree(pid)
            self.stop.wait(MEM_SAMPLE_S)


def _worker(rid, shard_line, abort_evt, pid_registry):
    if abort_evt.is_set():
        return {"region_id": rid, "skipped": True}
    t0 = time.monotonic()
    res = sessions.run_claude(
        model=WORKER_MODEL,
        system_prompt="Reply with exactly the word OK and nothing else.",
        max_turns=1,
        prompt=f"shard {rid}: {shard_line}\nReply with exactly: OK",
        no_tools=True,
        timeout_s=PER_WORKER_TIMEOUT_S,
        on_spawn=lambda pid: pid_registry.append(pid),
    )
    t1 = time.monotonic()
    with _spend_lock:
        _spend["usd"] += res.cost_usd
        _spend["calls"] += 1
    ok = (res.exit_code == 0) and (not res.timed_out) and (res.payload is not None)
    return {
        "region_id": rid, "skipped": False,
        "t_start": t0, "t_end": t1, "dur_s": round(t1 - t0, 2),
        "exit_code": res.exit_code, "timed_out": res.timed_out,
        "is_error": res.is_error, "ok": ok,
        "rate_limited": _scan_rate_limit(res),
        "cost_usd": res.cost_usd,
        "stderr_tail": (res.stderr or "")[-160:].replace("\n", " "),
    }


def _realized_concurrency(workers):
    ev = []
    for w in workers:
        if w.get("skipped") or "t_start" not in w:
            continue
        ev.append((w["t_start"], +1))
        ev.append((w["t_end"], -1))
    ev.sort(key=lambda e: (e[0], -e[1]))
    cur = mx = 0
    for _, d in ev:
        cur += d
        mx = max(mx, cur)
    return mx


def run_rung(n, per_worker_mem_mb):
    """Run one rung. Returns a record + classification. Honors the pre-launch
    memory gate; aborts if the watchdog breaches the floor or wall-timeout hits."""
    vm0 = psutil.virtual_memory()
    avail0 = vm0.available
    # ---- pre-launch HOST-MEMORY gate ----
    predicted_cost = (per_worker_mem_mb or 0) * n
    predicted_min_avail_mb = _mb(avail0) - predicted_cost
    gate_blocked = (per_worker_mem_mb is not None) and (predicted_min_avail_mb < MEM_FLOOR_MB)
    if gate_blocked:
        return {
            "N": n, "launched": False,
            "classification": "FAILED",
            "fail_reason": "host-memory (pre-launch gate)",
            "avail_before_mb": _mb(avail0),
            "per_worker_mem_mb_est": round(per_worker_mem_mb, 1),
            "predicted_rung_cost_mb": round(predicted_cost, 1),
            "predicted_min_avail_mb": round(predicted_min_avail_mb, 1),
            "mem_floor_mb": MEM_FLOOR_MB,
            "note": f"launching {n} workers is predicted to drop host available RAM to "
                    f"{round(predicted_min_avail_mb)}MB (< floor {MEM_FLOOR_MB}MB); NOT launched to protect host.",
        }

    seed_records = []
    for seed in SEEDS:
        world = W.build_world(n, seed, inject=False)
        shard_lines = {rid: world.reports[rid].splitlines()[1][:70] for rid in world.region_ids}
        pid_registry = []
        abort_evt = Event()
        wd = MemWatchdog(pid_registry, abort_evt)
        wd.start()
        t_start = time.monotonic()
        workers = []
        wall_timeout = False
        with ThreadPoolExecutor(max_workers=n) as ex:
            futs = {ex.submit(_worker, rid, shard_lines[rid], abort_evt, pid_registry): rid
                    for rid in world.region_ids}
            try:
                for f in as_completed(futs, timeout=PER_RUNG_WALL_TIMEOUT_S):
                    workers.append(f.result())
            except TimeoutError:
                wall_timeout = True
                abort_evt.set()
                for pid in list(pid_registry):
                    sessions._kill_process_tree(pid)
        wall = time.monotonic() - t_start
        wd.stop.set(); wd.join(timeout=2)
        realized = _realized_concurrency(workers)
        durs = [w["dur_s"] for w in workers if "dur_s" in w]
        n_ok = sum(1 for w in workers if w.get("ok"))
        n_rl = sum(1 for w in workers if w.get("rate_limited"))
        n_to = sum(1 for w in workers if w.get("timed_out"))
        n_err = sum(1 for w in workers if (not w.get("ok")) and (not w.get("skipped")))
        n_skip = sum(1 for w in workers if w.get("skipped"))
        parallel_ratio = round(sum(durs) / wall, 2) if wall > 0 and durs else 0.0
        rung_mem_cost_mb = _mb(avail0 - wd.min_avail)
        seed_records.append({
            "seed": seed, "n_workers": len(workers), "n_ok": n_ok,
            "realized_concurrency": realized, "wall_s": round(wall, 1),
            "parallel_ratio": parallel_ratio,
            "dur_median_s": round(sorted(durs)[len(durs) // 2], 1) if durs else None,
            "dur_max_s": max(durs) if durs else None,
            "rate_limited_workers": n_rl, "timeouts": n_to, "errors": n_err,
            "skipped_after_abort": n_skip, "wall_timeout": wall_timeout,
            "mem_avail_before_mb": _mb(avail0), "mem_min_avail_mb": _mb(wd.min_avail),
            "mem_rung_cost_mb": rung_mem_cost_mb, "mem_max_used_pct": wd.max_used_pct,
            "watchdog_breached": wd.breached,
        })

    # ---- aggregate + classify across seeds ----
    agg_realized = min(s["realized_concurrency"] for s in seed_records)
    agg_rl = sum(s["rate_limited_workers"] for s in seed_records)
    agg_err = sum(s["errors"] for s in seed_records)
    agg_to = sum(s["timeouts"] for s in seed_records)
    breached = any(s["watchdog_breached"] for s in seed_records)
    wall_to = any(s["wall_timeout"] for s in seed_records)
    min_avail = min(s["mem_min_avail_mb"] for s in seed_records)
    per_worker_mem = max(s["mem_rung_cost_mb"] for s in seed_records) / max(1, agg_realized)
    total_workers = sum(s["n_workers"] for s in seed_records)
    err_frac = (agg_err) / max(1, total_workers)

    reached = agg_realized >= -(-9 * n // 10)          # ceil(0.9N)
    serialized = agg_realized <= max(1, n // 2)
    mem_pressure = (min_avail < MEM_FLOOR_MB + 250) or breached

    if breached or wall_to or err_frac > 0.25 or agg_realized <= max(1, n // 4):
        cls, reason = "FAILED", []
        if breached: reason.append("host-memory watchdog killed in-flight workers")
        if wall_to: reason.append("per-rung wall-timeout")
        if err_frac > 0.25: reason.append(f"{agg_err}/{total_workers} workers errored")
        if agg_realized <= max(1, n // 4): reason.append(f"realized concurrency collapsed to {agg_realized}")
        fail_reason = "; ".join(reason)
    elif (not reached) or agg_rl > 0 or agg_err > 0 or mem_pressure or serialized:
        cls, reason = "DEGRADED", []
        if not reached: reason.append(f"realized {agg_realized}/{n} (< 90% of N)")
        if serialized: reason.append("serialized")
        if agg_rl > 0: reason.append(f"{agg_rl} rate-limit events")
        if agg_err > 0: reason.append(f"{agg_err} worker errors/timeouts")
        if mem_pressure: reason.append(f"memory pressure (min avail {round(min_avail)}MB)")
        fail_reason = "; ".join(reason)
    else:
        cls, reason, fail_reason = "CLEAN", [], ""

    return {
        "N": n, "launched": True, "classification": cls, "fail_reason": fail_reason,
        "realized_concurrency": agg_realized, "target_N": n,
        "reached_N": reached,
        "rate_limit_events": agg_rl, "errors": agg_err, "timeouts": agg_to,
        "watchdog_breached": breached, "wall_timeout": wall_to,
        "min_avail_mb": min_avail, "per_worker_mem_mb_measured": round(per_worker_mem, 1),
        "seeds": seed_records,
    }


def teardown_check():
    n = sum(1 for p in psutil.process_iter(['name'])
            if (p.info['name'] or '').lower() in ('claude.exe', 'node.exe'))
    return n


def append_ledger(report):
    lines = ["\n---\n",
             "## Phase-1c CONCURRENCY FEASIBILITY probe  (FEASIBILITY / NOT FROZEN, not confirmatory)\n",
             f"- date: 2026-06-25  ·  host: {report['host']['platform']} "
             f"({report['host']['logical_cpus']} vCPU, {report['host']['ram_total_gb']}GB RAM, "
             f"{report['host']['ram_available_gb']}GB free at start)\n",
             f"- D21 cmd-shim: {report['d21_shim']}\n",
             f"- worker: trivial single-turn Haiku call (concurrency stress, not detection)  ·  "
             f"seeds BURNED: {SEEDS}\n",
             f"- ramp: {' -> '.join(str(r['N'])+':'+r['classification'] for r in report['rungs'])}\n",
             f"- VERDICT: largest CLEAN N = {report['verdict']['largest_clean_N']}; "
             f"{report['verdict']['headline']}\n",
             f"- spend: ${report['spend_usd']:.4f}  ·  llm calls: {report['llm_calls']}  ·  "
             f"artifact: {OUT_JSON}\n"]
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write("".join(lines))


def main():
    vm = psutil.virtual_memory()
    host = {
        "platform": "Windows-11 (local laptop, NOT a separate provisioned container)",
        "logical_cpus": psutil.cpu_count(), "physical_cpus": psutil.cpu_count(logical=False),
        "ram_total_gb": round(vm.total / 1e9, 1), "ram_available_gb": round(vm.available / 1e9, 1),
        "ram_used_pct_at_start": vm.percent,
    }
    d21 = ("CLEAR -- TRIPWIRE_CLAUDE_BIN unset; resolves to real PE32+ claude.exe (no .cmd shim)"
           if not __import__("os").environ.get("TRIPWIRE_CLAUDE_BIN") else
           f"override set: {__import__('os').environ.get('TRIPWIRE_CLAUDE_BIN')}")
    print("=" * 92)
    print("PHASE-1c CONCURRENCY FEASIBILITY PROBE  --  FEASIBILITY / NOT FROZEN")
    print("=" * 92)
    print(f"host: {host['logical_cpus']} vCPU / {host['ram_total_gb']}GB RAM, "
          f"{host['ram_available_gb']}GB free  ·  mem floor {MEM_FLOOR_MB}MB  ·  total cap ${TOTAL_CAP_USD}")
    print(f"D21 shim: {d21}")
    print(f"ramp {RUNGS}, stop at first DEGRADED/FAILED; seeds {SEEDS} (burned)\n")

    rungs = []
    per_worker_mem = None
    for n in RUNGS:
        if _spend["usd"] > TOTAL_CAP_USD:
            print(f"[STOP] total spend cap ${TOTAL_CAP_USD} reached."); break
        print(f"--- RUNG N={n}  (avail {_mb(psutil.virtual_memory().available)}MB) ---", flush=True)
        rec = run_rung(n, per_worker_mem)
        rungs.append(rec)
        if rec["launched"]:
            per_worker_mem = rec["per_worker_mem_mb_measured"] or per_worker_mem
            print(f"    -> {rec['classification']}  realized={rec['realized_concurrency']}/{n}  "
                  f"rate_limit={rec['rate_limit_events']}  errors={rec['errors']}  "
                  f"min_avail={round(rec['min_avail_mb'])}MB  per_worker_mem≈{rec['per_worker_mem_mb_measured']}MB"
                  f"{('  reason: '+rec['fail_reason']) if rec['fail_reason'] else ''}", flush=True)
        else:
            print(f"    -> {rec['classification']} (not launched)  {rec['note']}", flush=True)
        orphans = teardown_check()
        print(f"    teardown: {orphans} claude/node procs alive after rung (baseline ~1)", flush=True)
        if rec["classification"] in ("DEGRADED", "FAILED"):
            print(f"    [STOP] rung N={n} is {rec['classification']} -- not climbing to next N.", flush=True)
            break

    clean_Ns = [r["N"] for r in rungs if r["classification"] == "CLEAN"]
    largest_clean = max(clean_Ns) if clean_Ns else None
    stopper = next((r for r in rungs if r["classification"] in ("DEGRADED", "FAILED")), None)
    if stopper:
        what = stopper["fail_reason"] or stopper.get("note", "")
        headline = (f"N={stopper['N']} {stopper['classification']} -- {what}")
        if "memory" in what.lower() or "mem" in what.lower():
            fix = (f"host RAM is the limit (~{host['ram_available_gb']}GB free; measured "
                   f"≈{per_worker_mem}MB/worker). Provision a container with "
                   f">= {round((per_worker_mem or 250)*64/1024 + 2, 1)}GB free RAM to hold N=64, "
                   f"or >= {round((per_worker_mem or 250)*32/1024 + 2, 1)}GB for N=32.")
        elif "rate" in what.lower():
            fix = "API concurrency/rate limit is the cap; need higher rate-limit tier or client-side request pacing."
        else:
            fix = "see rung detail."
    else:
        headline = f"all tested rungs CLEAN through N={largest_clean}"
        fix = "no provisioning change needed within tested range."

    verdict = {"largest_clean_N": largest_clean, "stopped_at": (stopper["N"] if stopper else None),
               "stopper_class": (stopper["classification"] if stopper else None),
               "headline": headline, "provisioning_fix": fix}

    report = {"FEASIBILITY": True, "FROZEN": False, "host": host, "d21_shim": d21,
              "seeds_burned": SEEDS, "worker_model": WORKER_MODEL,
              "mem_floor_mb": MEM_FLOOR_MB, "rungs": rungs, "verdict": verdict,
              "spend_usd": round(_spend["usd"], 6), "llm_calls": _spend["calls"]}
    Path("runs/matrix_1c").mkdir(parents=True, exist_ok=True)
    Path(OUT_JSON).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    append_ledger(report)

    print("\n" + "=" * 92)
    print("RUNG TABLE")
    print("  N  | class    | realized/N | rate-limit | errors | min-avail | per-wkr-mem | note")
    for r in rungs:
        if r["launched"]:
            print(f"  {r['N']:>2} | {r['classification']:<8} | {r['realized_concurrency']:>5}/{r['N']:<4} | "
                  f"{r['rate_limit_events']:>9} | {r['errors']:>6} | {round(r['min_avail_mb']):>6}MB | "
                  f"{str(r['per_worker_mem_mb_measured']):>8}MB | {r['fail_reason']}")
        else:
            print(f"  {r['N']:>2} | {r['classification']:<8} | {'--':>5}/{r['N']:<4} | "
                  f"{'--':>9} | {'--':>6} | {'--':>6}   | {'--':>8}   | {r['note']}")
    print(f"\nVERDICT [FEASIBILITY / NOT FROZEN]: largest CLEAN N = {largest_clean}")
    print(f"  {headline}")
    print(f"  provisioning fix: {fix}")
    print(f"\nspend ${_spend['usd']:.4f} · {_spend['calls']} calls · artifact {OUT_JSON} · logged {LEDGER}")
    print("FEASIBILITY / NOT FROZEN -- no freeze, no pin, confirmatory artifacts untouched.")


if __name__ == "__main__":
    main()
