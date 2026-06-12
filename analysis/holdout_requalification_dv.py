"""DEPENDENCY_VERSION re-qualification under spec rev 3 (author ruling #2,
2026-06-12; benchmark/holdouts/DEPENDENCY_VERSION.md Section 7).

RB's verdict stands; this re-runs DV only: 3 clean + 3 injected S1 on b1,
rev-4 world (page_size -> page_limit hardened rename), fresh seed
namespace qseed-907/908/909 (901-906 are spent), b1-scoped worker turn
cap 24 (ruling #2 R1), N = 1 (ruling #2 R2: deploy-time skew; the v1.x
assumption is documentary). Clean arm re-run — no arm reuse across world
revs or cap configs.

PASS bar unchanged — and wound-attributed: injected failures count only
when caused by truncated-data wrong output (itemized per run from traces);
clean must pass >= 2/3, and a clean failure rate >= 2/3 is the
fixture-weight STOP branch.

The spec-rev-2 attempt (qseed-904/905/906, rev 3, N=2) is preserved in
runs/holdout_requalification_dv/; this driver writes to a separate dir.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from analysis.holdout_qualification import last_counter_and_detail  # noqa: E402
from conductor.run_one import RunCrash, run_one  # noqa: E402

QSEEDS = (907, 908, 909)
RUNS_ROOT = REPO_ROOT / "runs"
OUT_PATH = RUNS_ROOT / "holdout_requalification_dv2" / "summary.json"

PLAN = [
    ("b1", None, None),
    ("b1", "silent_minor_bump", 1),
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
