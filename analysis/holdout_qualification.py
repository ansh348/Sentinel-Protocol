"""Held-out category manipulation qualification (memo Section 5(b);
benchmark/holdouts/*.md Section 7), mirroring the original nine pairs
(decisions/manipulation_table_s1_seed1.md).

Per category, on its primary host task: 3 clean S1 runs + 3 injected S1 runs
on qualification seeds qseed-901/902/903 — a distinct namespace; 1b matrix
seeds are NOT drawn from these. PASS = injected S1 fails task validation (or
emits wrong output) in >= 2/3 seeds while clean S1 passes in >= 2/3 seeds.

Counter-triggered injections only (M1 amendment 3). Qualification parameters
come from the task yaml holdout entries (RB: a1, q0=8, N=12 — the task's
final Phase 1 n_inject, token_expiry's mid-run pattern; DV: b1, page_size 5,
version 2.0.0, N=1 per the DEPENDENCY_VERSION.md Section 2 fire-window rule).

Also records each clean run's final tool-call counter: the rev-2 b1 clean
median feeds the escrow draw of RB-on-b1 fire counters (RESOURCE_BUDGET.md
Section 6), since the Phase 1 b1 median predates the rev-2 fixture pack.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from conductor.run_one import RunCrash, run_one  # noqa: E402
from trace import read_trace  # noqa: E402

QSEEDS = (901, 902, 903)
RUNS_ROOT = REPO_ROOT / "runs"
OUT_PATH = RUNS_ROOT / "holdout_qualification" / "summary.json"

PLAN = [
    # (task, injection, n_inject)
    ("a1", None, None),
    ("a1", "quota_cliff", 12),
    ("b1", None, None),
    ("b1", "silent_minor_bump", 1),
]


def last_counter_and_detail(run_dir: Path) -> tuple[int, str]:
    counter = 0
    detail = ""
    world_trace = run_dir / "trace_world.jsonl"
    if world_trace.exists():
        for event in read_trace(world_trace):
            if event["event_type"] == "tool_call":
                counter = max(counter, event["payload"].get("counter", 0))
    trace = run_dir / "trace.jsonl"
    if trace.exists():
        for event in read_trace(trace):
            if event["event_type"] == "success_check":
                detail = str(event["payload"].get("detail", ""))[:300]
    return counter, detail


def main() -> int:
    rows = []
    for task, injection, n_inject in PLAN:
        for seed in QSEEDS:
            label = injection or "clean"
            print(f"--- {task} S1 {label} seed {seed} ...", flush=True)
            try:
                summary = run_one(task_path=str(REPO_ROOT / "tasks" / f"{task}.yaml"),
                                  system_id="S1", injection=injection,
                                  n_inject=n_inject, seed=seed,
                                  runs_root=str(RUNS_ROOT))
            except RunCrash as crash:
                summary = {"run_id": Path(crash.run_dir).name,
                           "run_dir": crash.run_dir, "success": False,
                           "reason": "crash", "cost_usd": crash.cost_usd}
            run_dir = Path(summary["run_dir"])
            counter, detail = last_counter_and_detail(run_dir)
            row = {"task": task, "injection": injection, "seed": seed,
                   "tool_calls": counter, "checker_detail": detail, **summary}
            rows.append(row)
            print(json.dumps(row, indent=1), flush=True)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"\nsummary -> {OUT_PATH}")
    total = sum(r.get("cost_usd") or 0 for r in rows)
    print(f"total reported cost: ${total:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
