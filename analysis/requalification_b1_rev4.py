"""Re-qualification of the two ORIGINAL b1 pairs under the rev-4 world
(prereg_1b.md AUTHOR-6 ruling, 2026-06-12).

The Phase 1 verdicts for b1+schema_drift and b1+gate_skip_trap were earned
on the rev-1 fixture pack (4 files) under the worker turn cap of 14; the 1b
matrix runs b1 at world_rev 4 (8-file REPO_FILES_V2 pack) under the
b1-scoped cap of 24 (author ruling #2 R1). The host environment moved, so
the verdicts re-earn under the frozen rule: 3 clean + 3 injected S1 per
pair, PASS = injected fails task validation (or emits wrong output) in
>= 2/3 seeds while clean passes in >= 2/3 seeds. The bar is never revised.

Seeds: qseed-910/911/912 (fresh namespace; 901-909 are spent; matrix seeds
are NOT drawn from any qseed). n_inject = 7 = floor(0.5 * 14): the Phase 1
mechanical convention (50% of the task's clean median, floored — D17 rule)
applied to the rev-4 clean median of 14 (decisions/holdout_escrow_record.md
draw basis); 7 also sits inside the sealed matrix draw range [5, 8], whose
per-cell values remain unseen. The clean arm is re-run (no arm reuse across
world revs or cap configs — the holdout re-qualification discipline).

S1-only: no v2 component exists or runs (prereg_1b Section 6.1 carve-out;
the holdout-qualification precedent). Every run is ledgered.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from analysis.holdout_qualification import last_counter_and_detail  # noqa: E402
from conductor.run_one import RunCrash, run_one  # noqa: E402

QSEEDS = (910, 911, 912)
N_INJECT = 7
RUNS_ROOT = REPO_ROOT / "runs"
OUT_PATH = RUNS_ROOT / "requalification_b1_rev4" / "summary.json"

PLAN = [
    ("b1", None, None),
    ("b1", "schema_drift", N_INJECT),
    ("b1", "gate_skip_trap", N_INJECT),
]


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
