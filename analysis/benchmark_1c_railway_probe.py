#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark_1c_railway_probe.py  --  FEASIBILITY / NOT FROZEN

In-container concurrency probe with the REAL multi-turn tool worker (the
run_one.py:589 pattern: a Claude CLI agent, max_turns up to 14, tool=Bash(curl
http://localhost:PORT/*) against a localhost world), authenticated B2 = the real
CLI + ANTHROPIC_API_KEY (no OAuth token in-container -> sessions.run_claude uses
the API key automatically).

Ramps N over the grid, writes each rung to <data> (append+flush) AND streams a
progress line to stdout. Per rung: realized max concurrent (interval-overlap),
429/rate-limit + cascade, errors (timeout/exit/oom), container memory headroom,
classification CLEAN/DEGRADED/FAILED. STOP at first DEGRADED/FAILED.

Usage:  python benchmark_1c_railway_probe.py --data /data/railway_concurrency --ramp 16,32,64
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FTimeout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Lock, Thread

import psutil

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from analysis import benchmark_1c_world as W           # noqa: E402
from conductor import sessions                         # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SEEDS = [7701, 7702]
PER_RUNG_WALL_S = 600
PER_WORKER_TIMEOUT_S = 180
TOTAL_CAP_USD = 15.0
RATE_PAT = ("429", "rate limit", "rate_limit", "overloaded", "too many requests", "retry-after")
_spend = {"usd": 0.0, "calls": 0}
_lock = Lock()


# ---------------- minimal localhost world the real worker curls ----------------
def make_world_server(world, port):
    reports = {rid: world.reports[rid] for rid in world.region_ids}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            rid = self.path.rstrip("/").split("/")[-2] if "/evidence" in self.path else None
            body = reports.get(rid, "").encode("utf-8")
            if body:
                self.send_response(200)
            else:
                self.send_response(404); body = b'{"error":"not found"}'
            self.send_header("content-type", "text/plain")
            self.send_header("content-length", str(len(body)))
            self.end_headers(); self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    Thread(target=srv.serve_forever, daemon=True).start()
    return srv


WORKER_SYS = (
    "You are a regional demand worker. Use the Bash curl tool to GET the evidence URL you are given, "
    "read the line 'normalized_verified_demand: NNNN units' and the provenance_id, then reply with ONLY "
    "a JSON object {\"region_id\":..., \"demand_units\":<int>, \"provenance_id\":...}. Use the tool; do not guess."
)


def run_worker(rid, base_url, port):
    if _spend["usd"] > TOTAL_CAP_USD:
        return {"region_id": rid, "skipped": True}
    sub = f"GET {base_url}/regions/{rid}/evidence with curl and report its demand_units and provenance_id as JSON."
    t0 = time.monotonic()
    res = sessions.run_claude(
        model=sessions.WORKER_MODEL, system_prompt=WORKER_SYS, prompt=sub,
        max_turns=14, allowed_tools=f"Bash(curl http://localhost:{port}/*)",
        timeout_s=PER_WORKER_TIMEOUT_S)
    t1 = time.monotonic()
    u = res.usage or {}
    with _lock:
        _spend["usd"] += res.cost_usd; _spend["calls"] += 1
    blob = ((res.stderr or "") + (res.result_text or "")).lower()
    return {"region_id": rid, "skipped": False, "t_start": t0, "t_end": t1, "dur_s": round(t1 - t0, 2),
            "exit_code": res.exit_code, "timed_out": res.timed_out, "ok": res.exit_code == 0 and not res.timed_out,
            "rate_limited": any(p in blob for p in RATE_PAT),
            "cost_usd": res.cost_usd, "num_turns": res.num_turns,
            "input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens"),
            "cache_read": u.get("cache_read_input_tokens"), "cache_creation": u.get("cache_creation_input_tokens")}


def realized(workers):
    ev = []
    for w in workers:
        if w.get("skipped") or "t_start" not in w:
            continue
        ev.append((w["t_start"], 1)); ev.append((w["t_end"], -1))
    ev.sort(key=lambda e: (e[0], -e[1]))
    cur = mx = 0
    for _, d in ev:
        cur += d; mx = max(mx, cur)
    return mx


def run_rung(n, data_dir):
    recs = []
    for seed in SEEDS:
        world = W.build_world(n, seed, inject=False)
        port = 8900 + (seed % 50)
        srv = make_world_server(world, port)
        base = f"http://localhost:{port}"
        avail0 = psutil.virtual_memory().available
        minav = [avail0]
        stop = Event()

        def mon():
            while not stop.is_set():
                minav[0] = min(minav[0], psutil.virtual_memory().available)
                stop.wait(0.3)
        Thread(target=mon, daemon=True).start()
        t0 = time.monotonic(); workers = []; wto = False
        with ThreadPoolExecutor(max_workers=n) as ex:
            futs = [ex.submit(run_worker, rid, base, port) for rid in world.region_ids]
            try:
                for f in as_completed(futs, timeout=PER_RUNG_WALL_S):
                    workers.append(f.result())
            except FTimeout:
                wto = True
        wall = time.monotonic() - t0
        stop.set(); srv.shutdown()
        durs = [w["dur_s"] for w in workers if "dur_s" in w]
        recs.append({"seed": seed, "n_workers": len(workers), "realized": realized(workers),
                     "wall_s": round(wall, 1), "rate_limited": sum(1 for w in workers if w.get("rate_limited")),
                     "errors": sum(1 for w in workers if not w.get("ok") and not w.get("skipped")),
                     "mem_drop_mb": round((avail0 - minav[0]) / 1048576, 1),
                     "min_avail_mb": round(minav[0] / 1048576, 1), "wall_timeout": wto,
                     "cost_usd": round(sum(w.get("cost_usd", 0) for w in workers), 4),
                     "per_worker": [{"cost": w.get("cost_usd"), "turns": w.get("num_turns"),
                                     "in": w.get("input_tokens"), "out": w.get("output_tokens"),
                                     "cache_read": w.get("cache_read")} for w in workers if not w.get("skipped")]})
    rz = min(r["realized"] for r in recs)
    rl = sum(r["rate_limited"] for r in recs); er = sum(r["errors"] for r in recs)
    tot = sum(r["n_workers"] for r in recs); minav = min(r["min_avail_mb"] for r in recs)
    wto = any(r["wall_timeout"] for r in recs)
    reached = rz >= -(-9 * n // 10)
    if wto or er / max(1, tot) > 0.25 or rz <= max(1, n // 4) or minav < 400:
        cls = "FAILED"
    elif not reached or rl > 0 or er > 0 or minav < 800:
        cls = "DEGRADED"
    else:
        cls = "CLEAN"
    rec = {"N": n, "classification": cls, "realized": rz, "target": n, "rate_limit": rl,
           "errors": er, "min_avail_mb": minav, "mem_drop_mb": max(r["mem_drop_mb"] for r in recs),
           "seeds": recs, "cum_spend_usd": round(_spend["usd"], 4)}
    # append + flush to /data (crash-safe)
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    with open(Path(data_dir) / "rungs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n"); f.flush()
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/data/railway_concurrency")
    ap.add_argument("--ramp", default="16,32,64")
    a = ap.parse_args()
    grid = [int(x) for x in a.ramp.split(",")]
    print(f"=== REAL multi-turn worker concurrency probe (B2)  ramp={grid}  data={a.data} ===", flush=True)
    print(f"claude: {sessions.get_cli_version()}  | auth: ANTHROPIC_API_KEY={'set' if __import__('os').environ.get('ANTHROPIC_API_KEY') else 'MISSING'}", flush=True)
    rungs = []
    for n in grid:
        if _spend["usd"] > TOTAL_CAP_USD:
            print(f"[STOP] spend cap ${TOTAL_CAP_USD} hit"); break
        print(f"--- RUNG N={n} (free {round(psutil.virtual_memory().available/1e9,2)}GB) ---", flush=True)
        rec = run_rung(n, a.data)
        rungs.append(rec)
        pw = [p for s in rec["seeds"] for p in s["per_worker"] if p.get("cost")]
        med = sorted([p["cost"] for p in pw])[len(pw)//2] if pw else None
        cr = sum(1 for p in pw if (p.get("cache_read") or 0) > 0)
        print(f"  -> {rec['classification']}  realized={rec['realized']}/{n}  429={rec['rate_limit']}  "
              f"errors={rec['errors']}  min_avail={rec['min_avail_mb']}MB  per_worker_med=${med}  "
              f"cache_hit_workers={cr}/{len(pw)}  cum=${_spend['usd']:.2f}", flush=True)
        if rec["classification"] in ("DEGRADED", "FAILED"):
            print(f"  [STOP] N={n} {rec['classification']}", flush=True); break
    clean = [r["N"] for r in rungs if r["classification"] == "CLEAN"]
    summary = {"largest_clean_N": max(clean) if clean else None, "rungs": rungs,
               "spend_usd": round(_spend["usd"], 4), "calls": _spend["calls"]}
    Path(a.data).mkdir(parents=True, exist_ok=True)
    with open(Path(a.data) / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"=== DONE largest_clean_N={summary['largest_clean_N']} spend=${_spend['usd']:.2f} -> {a.data}/summary.json ===", flush=True)


if __name__ == "__main__":
    main()
