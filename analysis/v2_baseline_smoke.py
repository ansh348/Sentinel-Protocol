"""D30 validation: content-shaped detection through the REAL V2Conductor path with the
arm-time clean baseline, FOR THE RIGHT REASON (baseline captured before the injection
point). SEEN cells only; NO held-out; the matrix is NOT run.

Usage: python -m analysis.v2_baseline_smoke [label ...]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
os.environ["TRIPWIRE_V2"] = "1"

# (label, task, injection, n_inject) — SEEN cells; n_inject = the seen value.
CELLS = [
    ("endpoint_404",    "a1", "endpoint_404", 12),    # status-coded (control)
    ("clean",           "a1", None, None),            # must stay quiet
    ("schema_drift",    "a1", "schema_drift", 12),    # content-shaped (structure)
    ("doc_contradiction", "c1", "doc_contradiction", 6),  # content-shaped (value)
]
CONTENT_SHAPED = {"schema_drift", "doc_contradiction"}


def main(argv: list[str]) -> int:
    from conductor.run_v2_loop import run_v2_loop
    runs_root = str(REPO / "runs" / "v2_baseline_smoke")
    want = set(argv) if argv else {c[0] for c in CELLS}
    rows = []
    for label, task, injection, n_inject in CELLS:
        if label not in want:
            continue
        print(f"\n=== V2 on {task}+{injection or 'clean'} (label={label}) ===")
        try:
            s = run_v2_loop(task_path=str(REPO / "tasks" / f"{task}.yaml"),
                            injection=injection, n_inject=n_inject, seed=1,
                            runs_root=runs_root)
            detected = s["v2_invalidations"] > 0
            print(f"  detected={detected} invalidations={s['v2_invalidations']} "
                  f"interrupts={s['v2_interrupts']} replans={s['replans']} "
                  f"coalesced={s['v2_coalesced']} grades={s['v2_grades']}")
            print(f"  arm_capture_counter={s['arm_capture_counter']} "
                  f"injection_counter={s['injection_counter']} "
                  f"arm_probes={s['arm_probes']} cost=${s['cost_usd']}")
            for d in s["detected_baselines"]:
                print(f"    detected {d['target']} grade={d['grade']} "
                      f"baseline_source={d['baseline_source']} "
                      f"baseline_counter={d['baseline_counter']}")
            rows.append((label, task, injection, s))
        except Exception as exc:
            import traceback
            traceback.print_exc()
            rows.append((label, task, injection, f"ERROR: {exc}"))

    print("\n================ D30 RIGHT-REASON SUMMARY (seen) ================")
    total = 0.0
    for label, task, injection, s in rows:
        if isinstance(s, str):
            print(f"{task}+{injection or 'clean':16s} {s}")
            continue
        total += s["cost_usd"] or 0.0
        detected = s["v2_invalidations"] > 0
        # right-reason: a content-shaped detection must diff against a baseline captured
        # BEFORE the injection point
        right_reason = ""
        if label in CONTENT_SHAPED:
            inj = s["injection_counter"]
            pre = [d for d in s["detected_baselines"]
                   if d["baseline_counter"] is not None and inj is not None
                   and d["baseline_counter"] < inj]
            right_reason = (f" RIGHT-REASON={'YES' if (detected and pre) else 'NO'}"
                            f" (baseline<{inj}: {[(d['target'], d['baseline_source'], d['baseline_counter']) for d in pre]})")
        print(f"{task}+{(injection or 'clean'):16s} detected={detected!s:5s} "
              f"interrupts={s['v2_interrupts']} replans={s['replans']} "
              f"arm_probes={s['arm_probes']} cost=${s['cost_usd']}{right_reason}")
    print(f"DEV_RUN_SPEND=${round(total, 6)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
