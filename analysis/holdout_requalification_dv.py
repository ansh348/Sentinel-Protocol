"""DEPENDENCY_VERSION re-qualification under spec rev 2 (author ruling
2026-06-12; benchmark/holdouts/DEPENDENCY_VERSION.md Section 7).

RB's verdict stands; this re-runs DV only: 3 clean + 3 injected S1 on b1,
rev-3 world, fresh seed namespace qseed-904/905/906 (901-903 are spent),
clean arm re-run (no arm reuse across world revs). N = 2, recorded per the
ruling: the latest counter at which the wound stays live across worker
dispatch orders (the banked b1 enumerations land at counters 1-3) while
the run still begins under genuine v1.x behavior.

PASS bar unchanged — and wound-attributed: injected failures count only
when caused by truncated-data wrong output (itemized per run from traces);
clean must pass >= 2/3, and a clean failure rate >= 2/3 is the
fixture-weight STOP branch.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from analysis.holdout_qualification import last_counter_and_detail  # noqa: E402
from conductor.run_one import RunCrash, run_one  # noqa: E402

QSEEDS = (904, 905, 906)
RUNS_ROOT = REPO_ROOT / "runs"
OUT_PATH = RUNS_ROOT / "holdout_requalification_dv" / "summary.json"

PLAN = [
    ("b1", None, None),
    ("b1", "silent_minor_bump", 2),
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
