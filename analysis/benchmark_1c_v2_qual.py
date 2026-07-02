#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""benchmark_1c_v2_qual.py -- QUALIFICATION / NOT FROZEN / NOT CONFIRMATORY.

Conductor-path right-reason (§9) qualification for V2 and the V2nc ablation on the
width-scaled benchmark_1c, at width N. One CELL = (arm, N, seed, condition). Runs the
FULL v2 loop (orchestrator make_plan -> compile/deterministic-select -> ground -> arm ->
arm-time baseline -> N concurrent workers -> barriers -> corroboration -> replan) and
TRACE-CONFIRMS detection: the per-surface VALUE baseline-diff probe
(value_changed/field_read/proof_baseline) armed AND fired on the MUTATED shard, with the
arm-time baseline captured BEFORE the injection (clean).

CLEAN  = no injection; must QUIET (validator passes, 0 interrupts).
INJECTED = single_shard_value_mutation at counter n_inject; must WOUND (checker invalid)
           and be CAUGHT via the value lens on the mutated shard.

Costs real LLM (orchestrator + N workers + aggregate + V2 compile). Use --estimate to
print a cost projection without running. Records append to --out (jsonl, flushed).
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

import yaml  # noqa: E402
from trace import read_run  # noqa: E402
from analysis import benchmark_1c_world as BW  # noqa: E402

VALUE_SHAPE = ("value_changed", "field_read", "proof_baseline")  # the value baseline-diff lens


def make_task_for_n(N: int, tmpdir: str) -> str:
    """A per-width task file: count references -> N, forced width N, plan sliced to N
    one-shard steps + reduce (cosmetic; the orchestrator regenerates the plan from
    goal+context+fan_out, so only goal/context/fan_out/n_regions are load-bearing)."""
    task = yaml.safe_load((ROOT / "tasks" / "benchmark_1c.yaml").read_text(encoding="utf-8"))
    task["n_regions"] = N
    task["fan_out"] = N
    task["executor_width"] = N
    task["goal"] = task["goal"].replace("32", str(N))
    task["task_context"] = task["task_context"].replace("32", str(N))
    steps = [s for s in task["plan"] if s["subplan_id"] != "s33"][:N]
    reduce = [dict(s, step=s["step"].replace("32", str(N)))
              for s in task["plan"] if s["subplan_id"] == "s33"]
    task["plan"] = steps + reduce
    p = Path(tmpdir) / f"benchmark_1c_n{N}.yaml"
    p.write_text(yaml.safe_dump(task, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return str(p)


def confirm_from_trace(run_dir: str, mutated_surface: str) -> dict:
    """Read the run trace (trace.jsonl + trace_world.jsonl merged) and extract the
    right-reason evidence DIRECTLY from the trace artifact (not a recomputed summary)."""
    events = list(read_run(Path(run_dir)))
    armed_on_mutated = None
    armed_value_surfaces, armed_targets = set(), set()
    for e in events:
        p = e.get("payload") or {}
        if e["event_type"] == "tripwire_set" and p.get("layer") == "v2_probes":
            for pr in p.get("probes", []):
                armed_targets.add(pr["target"])
                if (pr["fault_shape"], pr["lens"], pr["comparison"]) == VALUE_SHAPE:
                    armed_value_surfaces.add(pr["target"])
                if pr["target"] == mutated_surface:
                    armed_on_mutated = pr            # last set wins (keep-not-flush)
    escalations = [e.get("payload") or {} for e in events if e["event_type"] == "escalation"]
    fires_on_mutated = [pl for pl in escalations
                        if (pl.get("evidence") or {}).get("_path") == mutated_surface]
    value_fire_on_mutated = any(pl.get("fault_shape") == "value_changed"
                                and (pl.get("evidence") or {}).get("grade") == "interrupt"
                                for pl in fires_on_mutated)
    inj = next((e.get("payload") or {} for e in events
                if e["event_type"] == "injection_fired"), None)
    armbase = next((e.get("payload") or {} for e in events
                    if e["event_type"] == "corroboration"
                    and (e.get("payload") or {}).get("layer") == "v2_arm_baseline"), None)
    success = next((bool((e.get("payload") or {}).get("success")) for e in events
                    if e["event_type"] == "success_check"), None)
    # worker reads of the mutated surface, with the counter (did the wound's shard get
    # read after the injection fired?)
    reads = [(e.get("payload") or {}) for e in events
             if e["event_type"] == "tool_call"
             and (e.get("payload") or {}).get("path") == mutated_surface]
    return {
        "armed_on_mutated": armed_on_mutated,
        "armed_value_lens_on_mutated": (armed_on_mutated is not None and
            (armed_on_mutated["fault_shape"], armed_on_mutated["lens"],
             armed_on_mutated["comparison"]) == VALUE_SHAPE),
        "n_armed_value_surfaces": len(armed_value_surfaces),
        "n_armed_targets": len(armed_targets),
        "fires_on_mutated": fires_on_mutated,
        "value_fire_on_mutated": value_fire_on_mutated,
        "n_escalations": len(escalations),
        "injection_event": inj,
        "injection_counter": (inj or {}).get("counter") if inj else None,
        "arm_baseline_event": armbase,
        "arm_baseline_counter": (armbase or {}).get("capture_counter") if armbase else None,
        "checker_success": success,
        "n_mutated_surface_reads": len(reads),
    }


def run_cell(arm: str, N: int, seed: int, condition: str, n_inject: int,
             runs_root: str, tmpdir: str) -> dict:
    from conductor.run_v2_loop import V2Conductor
    inject = (condition == "injected")
    task_path = make_task_for_n(N, tmpdir)
    # per-arm + per-N + per-condition runs-root: V2 and V2nc share the V2_SYSTEM id, so
    # they would otherwise collide on the same run_dir name. Keep them distinct so each
    # cell's trace persists for custody.
    cell_root = str(Path(runs_root) / arm / f"n{N}" / condition)
    Path(cell_root).mkdir(parents=True, exist_ok=True)
    cond = V2Conductor(
        task_path=task_path,
        injection=("single_shard_value_mutation" if inject else None),
        n_inject=(n_inject if inject else None),
        seed=seed, runs_root=cell_root,
        deterministic_select=(arm == "V2nc"), max_replans=2)
    summary = cond.run()

    w = BW.build_world(N, seed, inject=True)
    mutated_surface = f"/regions/{w.j_rid}/evidence"
    ev = confirm_from_trace(summary["run_dir"], mutated_surface)

    interrupts = [i for i in cond.v2_invalidations if i.grade.value == "interrupt"]
    invs = [{"target": i.target, "grade": i.grade.value, "fault_shape": i.fault_shape}
            for i in cond.v2_invalidations]
    realized_fanout = len({o.instance_id.split("r")[0] for o in cond.outcomes.values()})

    clean_quiet = (condition == "clean" and len(interrupts) == 0
                   and ev["checker_success"] is True)
    wound_landed = (condition == "injected" and ev["checker_success"] is False)
    baseline_clean = (ev["arm_baseline_counter"] is not None
                      and ev["injection_counter"] is not None
                      and ev["arm_baseline_counter"] < ev["injection_counter"])
    right_reason = bool(condition == "injected" and wound_landed
                        and ev["armed_value_lens_on_mutated"]
                        and ev["value_fire_on_mutated"] and baseline_clean)

    rec = {
        "arm": arm, "N": N, "seed": seed, "condition": condition,
        "n_inject": (n_inject if inject else None),
        "run_dir": summary["run_dir"], "cost_usd": summary["cost_usd"],
        "checker_success": ev["checker_success"],
        "clean_quiet": (clean_quiet if condition == "clean" else None),
        "wound_landed": (wound_landed if condition == "injected" else None),
        "detected": bool(interrupts),
        "n_interrupts": len(interrupts), "n_escalations": ev["n_escalations"],
        "replans": summary.get("replans"),
        "realized_fanout": realized_fanout, "n_outcomes": len(cond.outcomes),
        "mutated_shard": w.j_rid, "mutated_surface": mutated_surface,
        "armed_value_surfaces": ev["n_armed_value_surfaces"],
        "armed_targets": ev["n_armed_targets"],
        "armed_value_lens_on_mutated": ev["armed_value_lens_on_mutated"],
        "armed_on_mutated": ev["armed_on_mutated"],
        "value_fire_on_mutated": ev["value_fire_on_mutated"],
        "fires_on_mutated": ev["fires_on_mutated"],
        "injection_counter": ev["injection_counter"],
        "arm_baseline_counter": ev["arm_baseline_counter"],
        "baseline_clean": baseline_clean,
        "n_mutated_surface_reads": ev["n_mutated_surface_reads"],
        "right_reason": (right_reason if condition == "injected" else None),
        "all_invalidations": invs,
        "detection_locus": (f"{mutated_surface} :: value_changed/field_read/proof_baseline"
                            if right_reason else None),
        "reason_for_seed_world": w.j_rid,
    }
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="V2,V2nc")
    ap.add_argument("--ns", default="8,16,32")
    ap.add_argument("--seeds", default="9132")
    ap.add_argument("--conditions", default="clean,injected")
    ap.add_argument("--n-inject", type=int, default=2)
    ap.add_argument("--runs-root", default="runs/matrix_1c/v2_qual_runs")
    ap.add_argument("--out", default="runs/matrix_1c/v2_qualification/cells.jsonl")
    ap.add_argument("--estimate", action="store_true",
                    help="print a cost projection and exit (no LLM)")
    ap.add_argument("--per-worker-usd", type=float, default=0.03)
    ap.add_argument("--orchestrator-usd", type=float, default=0.10)
    ap.add_argument("--aggregate-usd", type=float, default=0.05)
    ap.add_argument("--compile-usd", type=float, default=0.38)
    args = ap.parse_args()

    arms = [a for a in args.arms.split(",") if a]
    ns = [int(x) for x in args.ns.split(",") if x]
    seeds = [int(x) for x in args.seeds.split(",") if x]
    conditions = [c for c in args.conditions.split(",") if c]

    cells = [(a, n, s, c) for a in arms for n in ns for s in seeds for c in conditions]

    # cost projection (per cell ~ orchestrator + N workers + aggregate + compile[V2 only])
    def cell_cost(a, n):
        base = args.orchestrator_usd + n * args.per_worker_usd + args.aggregate_usd
        return base + (args.compile_usd if a == "V2" else 0.0)
    projected = sum(cell_cost(a, n) for (a, n, s, c) in cells)
    print(f"[plan] {len(cells)} cells: arms={arms} N={ns} seeds={seeds} conditions={conditions}")
    print(f"[cost estimate] projected ~${projected:.2f} "
          f"(per-worker ${args.per_worker_usd}, orch ${args.orchestrator_usd}, "
          f"agg ${args.aggregate_usd}, compile ${args.compile_usd} V2-only)")
    for a in arms:
        for n in ns:
            print(f"   {a} N={n}: ~${cell_cost(a, n):.2f}/cell x "
                  f"{len(seeds)*len(conditions)} = ${cell_cost(a, n)*len(seeds)*len(conditions):.2f}")
    if args.estimate:
        print("[estimate-only] exiting without running (no LLM spend).")
        return

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # RESUME: skip cells already recorded (non-error) in the output, so re-invoking the
    # same command after a timeout/kill continues where it left off (append+flush durable).
    done = set()
    if out.exists():
        for l in out.read_text(encoding="utf-8").splitlines():
            if not l.strip():
                continue
            r = json.loads(l)
            if "error" not in r:
                done.add((r["arm"], r["N"], r["seed"], r["condition"]))
    pending_cells = [c for c in cells if (c[0], c[1], c[2], c[3]) not in done]
    print(f"[resume] {len(done)} cells already recorded; {len(pending_cells)}/{len(cells)} to run")
    with tempfile.TemporaryDirectory() as tmp:
        for (a, n, s, c) in pending_cells:
            print(f"\n=== CELL {a} N={n} seed={s} {c} (n_inject={args.n_inject}) ===", flush=True)
            try:
                rec = run_cell(a, n, s, c, args.n_inject, args.runs_root, tmp)
            except Exception as exc:
                rec = {"arm": a, "N": n, "seed": s, "condition": c,
                       "error": f"{type(exc).__name__}: {str(exc)[:400]}"}
                print(f"  [INTEGRATION ERROR] {rec['error']}", flush=True)
            with open(out, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
                f.flush()
            if "error" not in rec:
                if c == "clean":
                    print(f"  clean_quiet={rec['clean_quiet']} interrupts={rec['n_interrupts']} "
                          f"success={rec['checker_success']} cost=${rec['cost_usd']:.4f} "
                          f"fanout={rec['realized_fanout']}", flush=True)
                else:
                    print(f"  wound={rec['wound_landed']} detected={rec['detected']} "
                          f"right_reason={rec['right_reason']} "
                          f"armed_value_on_mutated={rec['armed_value_lens_on_mutated']} "
                          f"value_fire_on_mutated={rec['value_fire_on_mutated']} "
                          f"inj@{rec['injection_counter']} base@{rec['arm_baseline_counter']} "
                          f"cost=${rec['cost_usd']:.4f} fanout={rec['realized_fanout']}", flush=True)
    print(f"\n[done] records -> {out}")


if __name__ == "__main__":
    main()
