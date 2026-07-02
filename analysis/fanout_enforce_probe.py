"""Is worker fan-out ENFORCEABLE or EMERGENT in the v2 harness? (READ-ONLY, scratch)

Analyzes the BANKED 1b traces + harness code only. Writes ONLY
runs/matrix_1b/fanout_enforce.json. No LLM calls, no matrix re-run, no new agent runs, no
edits to any paper / gate report / ledger / prereg / frozen file.

Mechanism established by reading the harness (line refs in the cap inventory below):
  - worker count = len(LLM-emitted plan.steps); the orchestrator EMITS the plan
    (run_one.py:949 make_plan; Plan.steps min_length=1 at run_one.py:68), seeded but not
    forced by the task-yaml `plan:` block rendered into orchestrator.md (run_one.py:516-551).
  - every step is executor.submit()'d to a SINGLE ThreadPoolExecutor(max_workers=4)
    (run_one.py:953; dispatch run_one.py:622-638); V2 reuses it via the inherited dispatch
    (run_v2_loop.py:500,512).
  - cell-level concurrency is 1 (queue claims one job at a time, queue.py:91-103; prereg_1b
    §5.2 "concurrency 1"; world/server.py:18 "one process serves exactly one run").
This script measures requested-vs-actual fan-out per V2 cell from the traces and emits the
cap inventory + executability verdict.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNS = REPO / "runs" / "matrix_1b" / "runs"
TASKS = REPO / "tasks"
OUT = REPO / "runs" / "matrix_1b" / "fanout_enforce.json"


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def seeded_widths() -> dict:
    """Per task: declared fan_out (metadata) + count of seeded plan subplans."""
    out = {}
    for t in ("a1", "b1", "c1", "d1"):
        txt = (TASKS / f"{t}.yaml").read_text(encoding="utf-8")
        fan = re.search(r"^fan_out:\s*(\d+)", txt, re.MULTILINE)
        n_sub = len(re.findall(r"-\s*subplan_id:", txt))
        out[t] = {"declared_fan_out": int(fan.group(1)) if fan else None,
                  "seeded_plan_subplans": n_sub}
    return out


def cell_fanout(d: Path) -> dict:
    evs = [json.loads(l) for l in (d / "trace.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    rid = evs[0]["run_id"]
    parts = rid.split("-")
    task, arm = parts[0], parts[1]
    # orchestrator-EMITTED initial plan width (first plan event, the LLM's choice)
    plan_ev = next((e for e in evs if e["event_type"] == "plan"
                    and (e.get("payload") or {}).get("reply")), None)
    emitted_steps = (len((plan_ev["payload"]["reply"].get("steps") or []))
                     if plan_ev else None)
    # actual concurrency = max workers sharing a wave (true parallel breadth)
    starts = [e for e in evs if e["event_type"] == "worker_start"]
    by_wave = Counter(e["payload"].get("wave", 0) for e in starts)
    max_concurrent = max(by_wave.values()) if by_wave else 0
    distinct = len({e["actor"] for e in starts})
    return {"run_id": rid, "task": task, "arm": arm,
            "emitted_plan_steps": emitted_steps,
            "max_concurrent_workers": max_concurrent,
            "distinct_workers_total": distinct,
            "n_waves": len(by_wave) if by_wave else 0}


def main() -> int:
    seeds = seeded_widths()
    cells = [cell_fanout(d) for d in sorted(RUNS.glob("*"))
             if d.is_dir() and (d / "trace.jsonl").exists()]
    v2 = [c for c in cells if c["arm"] == "V2"]

    # requested (declared fan_out=4 for all) -> actual
    dist_actual = Counter(c["max_concurrent_workers"] for c in v2)
    dist_emitted = Counter(c["emitted_plan_steps"] for c in v2)
    below_declared = sum(1 for c in v2 if c["max_concurrent_workers"] < 4)
    full_consolidation = sum(1 for c in v2 if c["max_concurrent_workers"] <= 1)
    by_task = {}
    for t in ("a1", "b1", "c1", "d1"):
        ts = [c for c in v2 if c["task"] == t]
        by_task[t] = {
            "declared_fan_out": seeds[t]["declared_fan_out"],
            "seeded_plan_subplans": seeds[t]["seeded_plan_subplans"],
            "actual_max_concurrent_median": med([c["max_concurrent_workers"] for c in ts]),
            "actual_values": sorted(Counter(c["max_concurrent_workers"] for c in ts).items()),
            "emitted_plan_steps_median": med([c["emitted_plan_steps"] for c in ts]),
        }

    cap_inventory = [
        {"limit": "ThreadPoolExecutor(max_workers=4)", "value": 4,
         "location": "conductor/run_one.py:953",
         "kind": "HARD CAP on concurrent workers (genuinely-in-flight)",
         "applies_to_v2": True,
         "evidence": "the ONLY executor in the conductor; every plan step is "
                     "executor.submit()'d (run_one.py:622-638); V2 reuses it via the "
                     "inherited dispatch (run_v2_loop.py:500,512). >4 steps would queue and "
                     "run in batches of 4 — NOT 32 genuinely in flight."},
        {"limit": "plan width = len(LLM plan.steps), orchestrator-emitted", "value": "emergent",
         "location": "run_one.py:949 make_plan; Plan.steps min_length=1 (run_one.py:68); "
                     "seeded plan rendered to orchestrator.md (run_one.py:516-551)",
         "kind": "EMERGENT (LLM decides; seed proposes, model can consolidate)",
         "applies_to_v2": True,
         "evidence": "the task-yaml `plan:` block + `fan_out:4` are shown to the orchestrator "
                     "but it emits its own steps; consolidation observed in the traces below."},
        {"limit": "cell-level concurrency 1", "value": 1,
         "location": "prereg_1b.md §5.2 ('concurrency 1'); queue.py:91-103 claim_next "
                     "(one job at a time); world/server.py:18 (one process per run)",
         "kind": "cell/run-level (NOT a worker limit) — one cell at a time",
         "applies_to_v2": True,
         "evidence": "orthogonal to worker fan-out; bounds how many CELLS run at once, not "
                     "workers within a cell."},
        {"limit": "worker_max_turns 14 (b1: 24)", "value": 14,
         "location": "run_one.py:597 (task.get('worker_max_turns', 14))",
         "kind": "per-worker turn budget (NOT a count cap)", "applies_to_v2": True,
         "evidence": "bounds turns per worker, independent of N."},
        {"limit": "world-server concurrent-request cap", "value": None,
         "location": "world/server.py (no Semaphore/Lock/connection cap found)",
         "kind": "NONE — the world is not the limiter",
         "applies_to_v2": True,
         "evidence": "no per-request concurrency cap; the unlocked quota decrement "
                     "(world/server.py:571-576, D34) confirms concurrent in-flight requests "
                     "are permitted. The binding limit is the ThreadPool(4), not the world."},
        {"limit": "declared fan_out: 4 (task yaml)", "value": 4,
         "location": "tasks/{a1,b1,c1,d1}.yaml fan_out",
         "kind": "DECLARATIVE metadata — UNENFORCED",
         "applies_to_v2": True,
         "evidence": "grep finds `fan_out` only in the yamls; the conductor never reads it. "
                     "It documents intent; it does not set worker count."},
    ]

    verdict = {
        "q1_decision_point":
            "(c) seed proposes, orchestrator OVERRIDES/consolidates. Worker count = "
            "len(LLM-emitted plan.steps) at run_one.py:949 (make_plan) -> dispatch "
            "run_one.py:955; the task-yaml `plan:`/`fan_out:4` is rendered into orchestrator.md "
            "(run_one.py:516-551) as a SUGGESTION the model can collapse. Not harness-forced.",
        "q3_binding_cap": "ThreadPoolExecutor(max_workers=4) at run_one.py:953 — genuine "
                          "concurrency is capped at 4 for ALL arms incl. V2. N=8/16/32 cannot "
                          "run in parallel as-is; they would serialize in batches of 4.",
        "q4_force_without_contaminating":
            "Two SUT-NEUTRAL knobs are needed and sufficient: (1) parameterize the hard-coded "
            "max_workers (run_one.py:953) to N; (2) a deterministic PLAN-WIDTH SEED that emits "
            "N templated parallel worker shards, bypassing the orchestrator's consolidation "
            "(analogous to how injection counters are seeded). Both change only the PLAN INPUT "
            "and the executor width — the compile/probe/corroboration/cadence/detection code "
            "paths stay byte-identical (the compiler still grounds on whatever plan it is given; "
            "its LOGIC is untouched). Forcing N by PROMPTING alone does NOT work (the LLM "
            "consolidates), so the deterministic seed is required; but it is a controlled-"
            "variable knob, not a detector change. CAVEAT: fixing plan width removes the "
            "'plan-shape variance' that the confirmatory arm measured as emergent — the fan-out "
            "arm must pre-register N as a SET independent variable, distinct from that.",
        "q5_executability":
            "N in {1,3}: executable on the current harness (within the cap; seeds already "
            "produce <=4 and a1/c1 reach 3). N in {8,16,32}: NOT executable as-is "
            "(ThreadPool(4) cap + LLM consolidation); executable ONLY with the two pre-"
            "registerable knobs in q4 (parameterized max_workers=N + deterministic N-shard "
            "plan-width seed). Both leave the detection/probe/compile path byte-identical, so "
            "fan-out varies while the system-under-test stays fixed. NOT executable by changing "
            "the orchestrator PROMPT to 'request more workers' — that would make fan-out an "
            "LLM outcome again (and fold plan-shape into the treatment).",
    }

    artifact = {
        "meta": {"generated_by": "analysis/fanout_enforce_probe.py", "read_only": True,
                 "n_v2_cells": len(v2)},
        "q1_worker_count_decision": verdict["q1_decision_point"],
        "q2_requested_vs_actual": {
            "declared_fan_out_all_tasks": 4,
            "v2_actual_max_concurrent_distribution": dict(dist_actual),
            "v2_emitted_plan_steps_distribution": dict(dist_emitted),
            "cells_below_declared_4": f"{below_declared}/{len(v2)}",
            "cells_fully_consolidated_to_1": f"{full_consolidation}/{len(v2)}",
            "by_task": by_task,
            "consolidation_characterization":
                "Consolidation is task/plan-shape driven: a1 (independent 3-service fetch) and "
                "c1 hold ~3-4 parallel workers; b1 (sequential repo migration) collapses to 1 "
                "(its work is inherently serial); d1 to ~2. The wider the genuinely-independent "
                "subtask structure, the more parallel workers survive; serial tasks consolidate. "
                "It is the orchestrator's plan-emission choice, not a harness cap, that drives "
                "actual<declared here (all observed widths are <=4, so the ThreadPool cap never "
                "bound in the pilot — the LLM never asked for >4).",
        },
        "q3_hard_cap_inventory": cap_inventory,
        "q4_force_without_contaminating": verdict["q4_force_without_contaminating"],
        "q5_executability_verdict": verdict["q5_executability"],
        "per_cell_v2": v2,
    }
    OUT.write_text(json.dumps(artifact, indent=1), encoding="utf-8")

    print("=" * 80)
    print("FAN-OUT: ENFORCEABLE or EMERGENT?   V2 cells:", len(v2))
    print("=" * 80)
    print("\n(1) WORKER-COUNT DECISION POINT")
    print(" ", verdict["q1_decision_point"])
    print("\n(2) REQUESTED (declared fan_out=4) vs ACTUAL (max concurrent workers)")
    print(f"  actual max-concurrent distribution: {dict(dist_actual)}")
    print(f"  emitted plan-steps distribution:    {dict(dist_emitted)}")
    print(f"  cells below declared 4: {below_declared}/{len(v2)}  ; "
          f"fully consolidated to 1: {full_consolidation}/{len(v2)}")
    for t, d in by_task.items():
        print(f"    {t}: declared {d['declared_fan_out']} / seeded-subplans "
              f"{d['seeded_plan_subplans']} -> actual median "
              f"{d['actual_max_concurrent_median']} {d['actual_values']}")
    print("  => consolidation is plan-shape driven (serial b1->1; parallel a1/c1->3-4); "
          "all observed widths <=4 so the ThreadPool cap never bound in the pilot.")
    print("\n(3) HARD-CAP INVENTORY")
    for c in cap_inventory:
        print(f"  [{c['kind'].split('(')[0].strip()}] {c['limit']}  @ {c['location'].split(';')[0]}")
    print("\n(4) FORCE WITHOUT CONTAMINATING")
    print(" ", verdict["q4_force_without_contaminating"])
    print("\n(5) N-SWEEP EXECUTABILITY VERDICT")
    print(" ", verdict["q5_executability"])
    print(f"\nartifact -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
