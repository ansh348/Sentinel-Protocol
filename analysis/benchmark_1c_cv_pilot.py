#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""benchmark_1c_cv_pilot.py -- PILOT / NOT FROZEN / NOT CONFIRMATORY.

The net-cost CV pilot on benchmark_1c (D36 width-scaled named-id form). Measures the
per-seed total run cost K of S1, V2, V2nc at clean+injected, so the FROZEN blind resize
formula can size the confirmatory:

  estimand (§6.2):  B_p(N) = (1-p)*[K0_S1 - K0_V2] + p*[K1_S1 - K1_V2]
  formula:          n = max(5, ceil((1.645*SD_seed[B_p(N)] / H)^2)) at worst-case p
                    (max SD over p in {0.10,0.25,0.50}); H=$0.015, B=$450, binding-width n.

This is a MEASUREMENT run: treatment code BYTE-IDENTICAL (no arm/compiler/matcher/probe
changes). It records the quality-floor metrics (clean-success, recovery, detection) so the
CV is of the QUALITY-QUALIFIED net cost, and computes n SIGN-BLIND (from SD only).

Cells run N=8 (primary) BEFORE N=32 (spot-check); a --budget guard skips from the N=32 end
first so the primary cell is preserved under the cap. Resume-safe (append+flush).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("TRIPWIRE_V2", "1")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from analysis import benchmark_1c_world as BW          # noqa: E402
from analysis.benchmark_1c_v2_qual import make_task_for_n  # noqa: E402 (reuse the per-N task builder)
from trace import read_run                              # noqa: E402

# per-cell cost priors (from the §9 qual measurements) for the BEFORE-spend estimate only
COST_PRIOR = {
    (8, "S1", "clean"): 0.30, (8, "S1", "injected"): 0.35,
    (8, "V2", "clean"): 0.42, (8, "V2", "injected"): 0.74,
    (8, "V2nc", "clean"): 0.27, (8, "V2nc", "injected"): 0.40,
    (32, "S1", "clean"): 1.20, (32, "S1", "injected"): 1.30,
    (32, "V2", "clean"): 1.91, (32, "V2", "injected"): 2.63,
    (32, "V2nc", "clean"): 1.10, (32, "V2nc", "injected"): 2.18,
}


def realized_fanout(run_dir: str) -> int:
    """Distinct base worker ids that actually started (the realized fan-out covariate)."""
    try:
        bases = set()
        for e in read_run(Path(run_dir)):
            if e["event_type"] == "worker_start":
                wid = (e.get("actor") or "")
                bases.add(wid.split("r")[0])
        return len(bases)
    except Exception:
        return -1


def run_cell(arm: str, N: int, seed: int, condition: str, n_inject: int,
             runs_root: str, tmpdir: str) -> dict:
    inject = (condition == "injected")
    task_path = make_task_for_n(N, tmpdir)
    cell_root = str(Path(runs_root) / arm / f"n{N}" / condition)
    Path(cell_root).mkdir(parents=True, exist_ok=True)
    injection = "single_shard_value_mutation" if inject else None
    ninj = n_inject if inject else None

    detected, n_interrupts, replans, fir = False, 0, 0, None
    if arm == "S1":
        from conductor.run_one import run_one
        from analysis.metrics import run_metrics
        summary = run_one(task_path=task_path, system_id="S1", injection=injection,
                          n_inject=ninj, seed=seed, runs_root=cell_root, max_replans=2)
        run_dir = summary["run_dir"]
        m = run_metrics(run_dir)
        detected = bool(m["detected"])
        n_interrupts = m["interrupts"]["total"]
        fir = m["interrupts"]["fir"]
        replans = summary.get("replans", 0)
        cost = summary["cost_usd"]
        success = summary["success"]
    else:
        from conductor.run_v2_loop import V2Conductor
        cond = V2Conductor(task_path=task_path, injection=injection, n_inject=ninj,
                           seed=seed, runs_root=cell_root,
                           deterministic_select=(arm == "V2nc"), max_replans=2)
        summary = cond.run()
        run_dir = summary["run_dir"]
        ints = [i for i in cond.v2_invalidations if i.grade.value == "interrupt"]
        detected = bool(ints)
        n_interrupts = len(ints)
        replans = summary.get("replans", cond.replans_done)
        cost = summary["cost_usd"]
        success = summary["success"]

    fan = realized_fanout(run_dir)
    # recovery-quality (injected only): did the arm act on detection (detect-and-recover)?
    # S1 has no detection path -> recovery=None. For V2/V2nc a replan is the recovery action.
    recovered = (detected and replans > 0) if (inject and arm != "S1") else None
    return {
        "arm": arm, "N": N, "seed": seed, "condition": condition,
        "n_inject": ninj, "run_dir": run_dir,
        "K_cost_usd": round(cost, 6),               # the estimand's K (total run cost)
        "checker_success": success,                  # clean-success / injected-wound
        "detected": detected, "n_interrupts": n_interrupts,
        "replans": replans, "fir": fir,
        "realized_fanout": fan,
        "recovered": recovered,
    }


def make_cells(primary_n, primary_seeds, spot_n, spot_seeds, arms, conditions):
    cells = []
    for s in primary_seeds:
        for a in arms:
            for c in conditions:
                cells.append((a, primary_n, s, c))
    for s in spot_seeds:                              # spot-check LAST (trimmed first under budget)
        for a in arms:
            for c in conditions:
                cells.append((a, spot_n, s, c))
    return cells


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="S1,V2,V2nc")
    ap.add_argument("--conditions", default="clean,injected")
    ap.add_argument("--primary-n", type=int, default=8)
    ap.add_argument("--primary-seeds", default="7101,7102,7103,7104,7105")
    ap.add_argument("--spot-n", type=int, default=32)
    ap.add_argument("--spot-seeds", default="7201,7202,7203")
    ap.add_argument("--n-inject", type=int, default=2)
    ap.add_argument("--budget", type=float, default=50.0)
    ap.add_argument("--runs-root", default="runs/matrix_1c/cv_pilot/runs")
    ap.add_argument("--out", default="runs/matrix_1c/cv_pilot/cells.jsonl")
    ap.add_argument("--estimate", action="store_true")
    args = ap.parse_args()

    arms = [a for a in args.arms.split(",") if a]
    conditions = [c for c in args.conditions.split(",") if c]
    pseeds = [int(x) for x in args.primary_seeds.split(",") if x]
    sseeds = [int(x) for x in args.spot_seeds.split(",") if x] if args.spot_seeds else []
    cells = make_cells(args.primary_n, pseeds, args.spot_n, sseeds, arms, conditions)

    def cprior(c):
        a, n, s, cond = c
        return COST_PRIOR.get((n, a, cond), 1.0)

    total_est = sum(cprior(c) for c in cells)
    prim = [c for c in cells if c[1] == args.primary_n]
    spot = [c for c in cells if c[1] == args.spot_n]
    print(f"[plan] {len(cells)} cells = primary N={args.primary_n} x {len(pseeds)} seeds "
          f"({len(prim)} cells) + spot N={args.spot_n} x {len(sseeds)} seeds ({len(spot)} cells); "
          f"arms={arms} conditions={conditions}")
    print(f"[cost estimate BEFORE spend] primary ~${sum(cprior(c) for c in prim):.2f}  "
          f"spot ~${sum(cprior(c) for c in spot):.2f}  TOTAL ~${total_est:.2f}  cap=${args.budget:.0f}")
    print("  per-cell priors:")
    seen = set()
    for c in cells:
        k = (c[1], c[0], c[3])
        if k not in seen:
            seen.add(k); print(f"     N={c[1]:>2d} {c[0]:4s} {c[3]:8s} ~${cprior(c):.2f}")
    if total_est > args.budget:
        print(f"[OVER CAP] est ${total_est:.2f} > ${args.budget:.0f} — the --budget guard trims from the "
              f"N={args.spot_n} (spot) end at runtime, preserving the N={args.primary_n} primary cell.")
    if args.estimate:
        print("[estimate-only] no spend."); return

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    spent = 0.0
    if out.exists():
        for l in out.read_text(encoding="utf-8").splitlines():
            if not l.strip(): continue
            r = json.loads(l)
            if "error" not in r:
                done.add((r["arm"], r["N"], r["seed"], r["condition"]))
                spent += r.get("K_cost_usd", 0) or 0
    print(f"[resume] {len(done)} cells recorded (${spent:.2f} spent); budget left ${args.budget-spent:.2f}")

    with tempfile.TemporaryDirectory() as tmp:
        for c in cells:
            a, n, s, cond = c
            if (a, n, s, cond) in done:
                continue
            # budget guard: stop before a cell whose prior would risk the cap (margin 1.3x prior)
            if spent + cprior(c) * 1.3 > args.budget:
                print(f"[BUDGET STOP] before {a} N={n} seed={s} {cond}: spent ${spent:.2f} + "
                      f"~${cprior(c)*1.3:.2f} would exceed ${args.budget:.0f}. Skipping this and remaining "
                      f"(N={args.spot_n} spot-check trimmed first). Primary N={args.primary_n} preserved.")
                break
            print(f"\n=== CELL {a} N={n} seed={s} {cond} (n_inject={args.n_inject}) ===", flush=True)
            try:
                rec = run_cell(a, n, s, cond, args.n_inject, args.runs_root, tmp)
            except Exception as exc:
                rec = {"arm": a, "N": n, "seed": s, "condition": cond,
                       "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
                print(f"  [ERROR] {rec['error']}", flush=True)
            with open(out, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n"); f.flush()
            if "error" not in rec:
                spent += rec["K_cost_usd"]
                print(f"  K=${rec['K_cost_usd']:.4f} success={rec['checker_success']} "
                      f"detected={rec['detected']} replans={rec['replans']} "
                      f"fanout={rec['realized_fanout']}  cum=${spent:.2f}", flush=True)
    print(f"\n[done] {len(done)} prior + new; cumulative spend ${spent:.2f}; records -> {out}")


if __name__ == "__main__":
    main()
