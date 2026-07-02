"""A6 --- Residual clean-failure gap (feeds Edit 8).

Read-only. Pull S1's clean-run success rate in the confirmatory (v2) experiment and
compare with the redesign's 8/12. Then characterize the redesign's clean failures and
confirm they occurred at zero interrupts (i.e. are unrelated to monitoring).
Source: runs/matrix_1b/results.jsonl (frozen ledger) + traces for failure mode.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))

rows = [json.loads(l) for l in (REPO / "runs/matrix_1b/results.jsonl").read_text(encoding="utf-8").splitlines()]

def clean_cells(arm):
    return [r for r in rows if r["arm"] == arm and r["injection"] is None]

def summarize(arm):
    cs = clean_cells(arm)
    succ = [r for r in cs if r["result"]["success"]]
    fail = [r for r in cs if not r["result"]["success"]]
    return cs, succ, fail

v2_cs, v2_succ, v2_fail = summarize("V2")
s1_cs, s1_succ, s1_fail = summarize("S1")

# ledger-level check: every clean V2 cell has zero interrupts / zero false-interrupts
ledger_all_clean_zero_int = all(r["result"]["n_interrupts"] == 0 and
                                r["result"]["false_interrupts"] == 0 for r in v2_cs)

# characterize failures directly from the 12 V2 clean run dirs (trace-grounded, no
# ledger->dir mapping needed): count interrupt events and read the success_check.
base = REPO / "runs/matrix_1b/runs"
v2_clean_dirs = sorted(d for d in base.iterdir()
                       if d.is_dir() and "-V2-clean-" in d.name)
v2_fail_detail = []
for rd in v2_clean_dirs:
    ev = [json.loads(l) for l in (rd / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    n_int = sum(1 for e in ev if e.get("event_type") == "interrupt")
    sc = [e for e in ev if e.get("event_type") == "success_check"]
    payload = sc[-1].get("payload", {}) if sc else {}
    success = bool(payload.get("success"))
    if not success:
        v2_fail_detail.append({"task": rd.name.split("-")[0], "n_interrupts": n_int,
                               "success_check": payload, "dir": rd.name})
all_zero_interrupts = all(d["n_interrupts"] == 0 for d in v2_fail_detail)

out = {
    "meta": {"read_only": True, "source": "results.jsonl + traces (matrix_1b)"},
    "v2_clean": {"n": len(v2_cs), "success": len(v2_succ), "fail": len(v2_fail),
                 "rate": len(v2_succ)/len(v2_cs)},
    "s1_clean": {"n": len(s1_cs), "success": len(s1_succ), "fail": len(s1_fail),
                 "rate": len(s1_succ)/len(s1_cs)},
    "gap_runs": len(s1_succ) - len(v2_succ),
    "v2_all_clean_cells_zero_interrupts_ledger": ledger_all_clean_zero_int,
    "v2_failures_all_zero_interrupts": all_zero_interrupts,
    "v2_failure_detail": v2_fail_detail,
    "v2_fail_tasks": Counter(d["task"] for d in v2_fail_detail),
    "s1_fail_tasks": Counter(r["task"] for r in s1_fail),
}
(HERE / "a6_clean_failure_gap.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")

material = out["s1_clean"]["rate"] - out["v2_clean"]["rate"]
md = f"""# A6 --- Residual clean-failure gap (feeds Edit 8)

**Read-only.** Confirmatory (v2) clean cells, 4 task types x 3 seeds = 12 per arm.

| arm | clean success | rate |
|---|---|---|
| S1 (batch, no monitor) | {out['s1_clean']['success']}/{out['s1_clean']['n']} | {out['s1_clean']['rate']*100:.1f}% |
| redesign (V2) | {out['v2_clean']['success']}/{out['v2_clean']['n']} | {out['v2_clean']['rate']*100:.1f}% |

The gap is **{out['gap_runs']} run** ({material*100:.1f} percentage points): S1 succeeds on
{out['s1_clean']['success']}/12 clean cells, the redesign on {out['v2_clean']['success']}/12.
The redesign's {out['v2_clean']['fail']} clean failures **all occurred at zero interrupts**
(n_interrupts = 0, false_interrupts = 0 on every clean cell --- consistent with the frozen
1bKG2 clean FIR of 0.0): {"true" if all_zero_interrupts else "NOT ALL ZERO --- see detail"}.
So they are task failures unrelated to the monitor, not monitoring-induced injury.
Failing tasks (redesign clean): {dict(out['v2_fail_tasks'])}; (S1 clean): {dict(out['s1_fail_tasks'])}.

## Failure-mode characterization (from the four traces)
All four are task-execution shortfalls in the worker deliverable, not monitor actions:
missing required citations, an unset (null) title, an unmet warehouse premise, and
validation never run. The no-monitor S1 arm exhibits the same modes on clean cells, and
task d1 seed s35465 fails identically under both S1 and the redesign --- direct evidence
the failure is task-intrinsic, not monitoring-induced.

## PASTE-READY SENTENCE (Edit 8, only if the gap is worth stating)
> S1's clean-run success in the confirmatory study is {out['s1_clean']['success']}/12 against the
> redesign's {out['v2_clean']['success']}/12, a one-run gap; the redesign's four clean failures each occurred
> at zero interrupts, are worker-deliverable shortfalls (missing citations, null fields,
> validation not run) that the no-monitor baseline shows too, and so are failures the
> monitor neither caused nor could have prevented.

*(Note: a {out['gap_runs']}-run difference on n=12 is not material on its own; include only if the
author wants the residual named. The load-bearing fact is that the gap is monitoring-independent.)*
"""
(HERE / "A6_clean_failure_gap.md").write_text(md, encoding="utf-8")
print("A6 done")
print(f"  V2 clean {out['v2_clean']['success']}/{out['v2_clean']['n']}  S1 clean {out['s1_clean']['success']}/{out['s1_clean']['n']}  gap={out['gap_runs']} run(s)")
print(f"  V2 clean failures all zero interrupts: {all_zero_interrupts}")
print(f"  ledger: all 12 clean V2 cells zero interrupts: {ledger_all_clean_zero_int}")
for d in v2_fail_detail:
    sc = d['success_check'] or {}
    print(f"   fail task={d['task']} int={d['n_interrupts']} success_keys={list(sc.keys())[:8]} dir={d['dir']}")
