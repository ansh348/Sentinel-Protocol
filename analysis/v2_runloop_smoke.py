"""Run-loop fidelity dev-run: the V2 arm through the REAL matrix path on SEEN cells
(cadence barriers firing probes mid-run + §8 harvest, same world-instance/token), plus
a baseline through the same runner. NO held-out cell; NO full matrix; bounded.

Usage: python -m analysis.v2_runloop_smoke [label ...]
  labels select which cells to run (e.g. endpoint_404 clean schema_drift baseline).
  No args -> the full small seen set.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
os.environ["TRIPWIRE_V2"] = "1"

A1 = str(REPO / "tasks" / "a1.yaml")
N_INJECT = 12          # a1's frozen seen n_inject (manipulation_table_s1_seed1)

# (label, arm, task, injection, n_inject) — SEEN cells only.
CELLS = [
    ("endpoint_404", "V2", A1, "endpoint_404", N_INJECT),   # structure/status change-shape
    ("clean",        "V2", A1, None, None),                 # clean -> must be quiet
    ("schema_drift", "V2", A1, "schema_drift", N_INJECT),   # structure-changed change-shape
    ("baseline",     "S2", A1, "endpoint_404", N_INJECT),   # baseline dispatch via the runner
]


def main(argv: list[str]) -> int:
    from sentinel_v2.arms import dispatch
    runs_root = str(REPO / "runs" / "v2_runloop_smoke")
    want = set(argv) if argv else {label for label, *_ in CELLS}
    rows = []
    for label, arm, task, injection, n_inject in CELLS:
        if label not in want:
            continue
        seed = 1
        print(f"\n=== {arm} on a1+{injection or 'clean'} (label={label}) ===")
        try:
            res = dispatch(arm, task_path=task, injection=injection, n_inject=n_inject,
                           seed=seed, runs_root=runs_root)
            rows.append((label, arm, injection or "clean", res))
            print(f"  detected={res.detected} interrupts={res.n_interrupts} "
                  f"replans={res.replans} fir={res.fir} ttd={res.ttd_tool_calls} "
                  f"cost=${res.total_cost_usd} src={res.source} grades={res.grades}")
        except Exception as exc:
            import traceback
            traceback.print_exc()
            rows.append((label, arm, injection or "clean", f"ERROR: {type(exc).__name__}: {exc}"))

    print("\n================ RUN-LOOP FIDELITY SUMMARY (seen cells) ================")
    total = 0.0
    for label, arm, inj, res in rows:
        if isinstance(res, str):
            print(f"{arm:4s} a1+{inj:14s} {res}")
            continue
        total += res.total_cost_usd or 0.0
        print(f"{arm:4s} a1+{inj:14s} detected={res.detected!s:5s} "
              f"interrupts={res.n_interrupts} replans={res.replans} fir={res.fir} "
              f"ttd={res.ttd_tool_calls} cost=${res.total_cost_usd} src={res.source}")
    print(f"DEV_RUN_SPEND=${round(total, 6)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
