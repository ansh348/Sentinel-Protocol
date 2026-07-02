"""A1 — Bar-robustness sweep (feeds Edit 1b).

Read-only. Computes the cost-gate verdict as a function of the clean-overhead cap,
swept 1%..60% in 1% steps, for three readings:
  (a) v1 pilot        — S5 vs S1 clean medians (kill_gates_final.md, frozen KG3)
  (b) v2 confirmatory  — 55.49% (cost_autopsy_v3.json partA, frozen 1bKG3)
  (c) V3 second-family — floor +17.1% at cap-6 (paper Table, GPT-5.5 live, batch denom)

Verdict rule (as pre-registered): a cost gate FAILs when measured clean overhead
exceeds the cap. Overhead is fixed per reading; the cap sweeps. So a reading FAILs
exactly the caps strictly below its overhead. No new measurement is taken.
"""
from __future__ import annotations
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

# (a) v1 pilot clean overhead — from the frozen KG3 block (kill_gates_final.md)
S5_CLEAN_MED = 1.178952
S1_CLEAN_MED_V1 = 0.340831
v1_overhead = S5_CLEAN_MED / S1_CLEAN_MED_V1 - 1.0  # 245.9%

# (b) v2 confirmatory clean overhead — frozen 1bKG3 (cost_autopsy_v3.json partA)
ca = json.loads((REPO / "runs/matrix_1b/cost_autopsy_v3.json").read_text(encoding="utf-8"))
v2_overhead = ca["partA_1bKG3_clean_overhead"]["overhead_fraction"]  # 0.55494...

# (c) V3 second-family floor — most favorable coverage cap (cap-6), batch/live denom
#     Paper Table (fse_focused_v4.tex): cap-6 -> +17.1% (batch denominator column).
v3_floor_overhead = 0.171  # +17.1% at cap-6, the cheapest coverage setting

CAP_PRE_REG = 0.12  # the pre-registered cap

def fail_caps(overhead, lo=1, hi=60):
    """Integer caps (percent) in [lo,hi] at which the reading FAILs (cap < overhead)."""
    return [c for c in range(lo, hi + 1) if (c / 100.0) < overhead]

def rng(caps):
    return (f"{caps[0]}%-{caps[-1]}%" if caps else "none")

readings = {
    "v1_pilot":        {"overhead": v1_overhead,     "label": "v1 pilot (S5 vs S1 clean)"},
    "v2_confirmatory": {"overhead": v2_overhead,     "label": "v2 confirmatory redesign"},
    "v3_second_family":{"overhead": v3_floor_overhead,"label": "second-family floor (GPT-5.5, cap-6)"},
}
for r in readings.values():
    fc = fail_caps(r["overhead"])
    r["fail_cap_range_pct"] = rng(fc)
    r["fails_entire_sweep"] = (len(fc) == 60)
    r["fails_pre_reg_12pct"] = (0.12 < r["overhead"])
    r["flip_cap_pct"] = None if r["fails_entire_sweep"] else (fc[-1] + 1 if fc else 1)

out = {
    "meta": {"read_only": True, "sweep": "1%..60% by 1%",
             "verdict_rule": "FAIL iff cap < measured clean overhead",
             "sources": {
                 "v1": "decisions/kill_gates_final.md (frozen KG3: S5 $1.178952 vs S1 $0.340831)",
                 "v2": "runs/matrix_1b/cost_autopsy_v3.json partA (frozen 1bKG3 overhead_fraction)",
                 "v3": "paper fse_focused_v4.tex Table (GPT-5.5 cap-6 = +17.1%, batch denom)"}},
    "readings": readings,
    "pre_registered_cap_pct": 12,
}
(HERE / "a1_bar_robustness.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

paste = (
    "The verdict is invariant to the cap's exact value: v2 fails any cap below "
    f"{v2_overhead*100:.1f}%, and the second-family floor of +{v3_floor_overhead*100:.0f}% "
    f"fails any cap below {v3_floor_overhead*100:.0f}% --- every bar a deployer could "
    "plausibly have set returns the same verdict."
)

md = f"""# A1 --- Bar-robustness sweep (feeds Edit 1b)

**Read-only.** No new measurement. The cost gate FAILs when measured clean overhead
exceeds the cap; overhead is fixed per reading and the cap is swept 1%--60% in 1% steps.
A reading therefore FAILs exactly the caps strictly below its overhead.

## Measured clean overheads (all frozen artifacts)
| reading | clean overhead | source | fails 12% cap? |
|---|---|---|---|
| v1 pilot (S5 vs S1) | **{v1_overhead*100:.1f}%** | kill_gates_final.md (KG3: \\$1.178952 vs \\$0.340831) | {"yes" if readings['v1_pilot']['fails_pre_reg_12pct'] else "no"} |
| v2 confirmatory (redesign) | **{v2_overhead*100:.2f}%** | cost_autopsy_v3.json partA (1bKG3) | {"yes" if readings['v2_confirmatory']['fails_pre_reg_12pct'] else "no"} |
| second-family floor (GPT-5.5 cap-6) | **+{v3_floor_overhead*100:.1f}%** | paper Table, batch/live denom | {"yes" if readings['v3_second_family']['fails_pre_reg_12pct'] else "no"} |

## Verdict as a function of the cap (1%--60%)
| reading | FAIL cap range | PASS only if cap >= | fails entire 1--60% sweep? |
|---|---|---|---|
| v1 pilot | {readings['v1_pilot']['fail_cap_range_pct']} | {'(never passes in range)' if readings['v1_pilot']['fails_entire_sweep'] else str(readings['v1_pilot']['flip_cap_pct'])+'%'} | {readings['v1_pilot']['fails_entire_sweep']} |
| v2 confirmatory | {readings['v2_confirmatory']['fail_cap_range_pct']} | {str(readings['v2_confirmatory']['flip_cap_pct'])+'%'} | {readings['v2_confirmatory']['fails_entire_sweep']} |
| second-family floor | {readings['v3_second_family']['fail_cap_range_pct']} | {str(readings['v3_second_family']['flip_cap_pct'])+'%'} | {readings['v3_second_family']['fails_entire_sweep']} |

The v1 pilot fails **every** cap in the sweep (its overhead, ~{v1_overhead*100:.0f}%, is above 60%).
v2 fails every cap below {v2_overhead*100:.1f}% (i.e. it would only pass at a cap of 56% or higher).
The second-family floor fails every cap below {v3_floor_overhead*100:.0f}% (it would only pass at a cap of 18% or higher),
and no coverage setting of the second-family writer ever reaches the 12% cap at all.

## PASTE-READY SENTENCE (Edit 1b)
> {paste}

*(Framing note for the rewrite: this is disclosed post-hoc robustness of a
pre-registered judgment, not a new result. Label as post-hoc in text.)*
"""
(HERE / "A1_bar_robustness.md").write_text(md, encoding="utf-8")
print("A1 done")
print(f"  v1 overhead   = {v1_overhead*100:.2f}%  -> FAIL caps {readings['v1_pilot']['fail_cap_range_pct']}")
print(f"  v2 overhead   = {v2_overhead*100:.4f}%  -> FAIL caps {readings['v2_confirmatory']['fail_cap_range_pct']}")
print(f"  v3 floor      = {v3_floor_overhead*100:.2f}%  -> FAIL caps {readings['v3_second_family']['fail_cap_range_pct']}")
print("  PASTE:", paste)
