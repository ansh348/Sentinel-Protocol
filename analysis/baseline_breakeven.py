"""TASK F (archaeology v2): baseline honesty + KG3 break-even fit.
EXPLORATORY — recomputes no gate quantity. S2's strict recall was never a
gate input (KG1 is S5-only); it is owed to the decision memo per H5. The
break-even fit is owed by KG3's own pre-committed branch; its model form,
estimators, and acceptance rule were committed in
decisions/phase1b_precommitments.md §F.1 BEFORE this script ran:

    pay iff  C + J + p*R < p*(W_batch(n) - W_sent(n)),   W_x(n) = W_x(n0)*n/n0

C/J = median S5 per-run compile/judge cost; R = median per-replan
orchestrator+recompile cost over S5 runs with replans; W from the
instrument's own wasted_work USD on injected cells; n0 = 3; crossover n* at
p in {0.1, 0.25, 0.5}; bootstrap (seed 11, 1000 resamples) 90% CI;
acceptance: plausible iff n* <= 8 at some p <= 0.5 with finite CI lower
bound.
"""
from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from analysis.gates import INJECTION_CATEGORY, cell_run_dir  # noqa: E402
from analysis.metrics import (_usage_cost, first_attributable_pause,  # noqa: E402
                              injection_info, wasted_work)
from trace import read_run  # noqa: E402

RUNS = REPO_ROOT / "runs"
OUT_DIR = RUNS / "archaeology_v2"
CELLS = json.loads((REPO_ROOT / "analysis" / "matrix_manifest.json")
                   .read_text(encoding="utf-8"))
N0 = 3
P_GRID = (0.1, 0.25, 0.5)
N_BOOT = 1000


def median(xs) -> Optional[float]:
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def strict_recall(system: str) -> dict:
    per_cat: dict[str, list[bool]] = {}
    rows = []
    for cell in CELLS:
        if cell["system"] != system or cell["injection"] is None:
            continue
        rd = cell_run_dir(RUNS, cell)
        events = read_run(rd)
        inj = injection_info(events)
        det = (first_attributable_pause(events, inj) is not None
               if inj else False)
        cat = INJECTION_CATEGORY[cell["injection"]]
        per_cat.setdefault(cat, []).append(det)
        rows.append({"cell": f"{cell['task']}+{cell['injection']}"
                             f"/s{cell['seed']}", "dir": rd.name,
                     "injection_fired": inj is not None, "detected": det})
    total = sum(r["detected"] for r in rows)
    fired = [r for r in rows if r["injection_fired"]]
    return {
        "system": system,
        "per_cell": rows,
        "recall_all_cells": f"{total}/{len(rows)}",
        "recall_fired_only": f"{sum(r['detected'] for r in fired)}/{len(fired)}",
        "per_category": {c: f"{sum(v)}/{len(v)}" for c, v in
                         sorted(per_cat.items())},
    }


def collect_costs() -> dict:
    s5_compile, s5_judge, per_replan = [], [], []
    w_s1, w_s5 = [], []
    for cell in CELLS:
        if cell["system"] not in ("S1", "S5"):
            continue
        rd = cell_run_dir(RUNS, cell)
        events = read_run(rd)
        if cell["system"] == "S5":
            s5_compile.append(sum(_usage_cost(e) for e in events
                                  if e["event_type"] == "compile"))
            s5_judge.append(sum(_usage_cost(e) for e in events
                                if e["event_type"] == "judge_verdict"))
            replans = [e for e in events if e["event_type"] == "replan"]
            if replans:
                first_ts = replans[0]["ts"]
                cost = (sum(_usage_cost(e) for e in events
                            if e["event_type"] == "replan")
                        + sum(_usage_cost(e) for e in events
                              if e["event_type"] == "compile"
                              and e["ts"] >= first_ts))
                per_replan.append(cost / len(replans))
        if cell["injection"] is not None:
            inj = injection_info(events)
            usd = wasted_work(events, inj)["usd"]
            (w_s1 if cell["system"] == "S1" else w_s5).append(usd)
    return {"C_samples": s5_compile, "J_samples": s5_judge,
            "R_samples": per_replan, "Wb_samples": w_s1, "Ws_samples": w_s5}


def crossover(C: float, J: float, R: float, wb: float, ws: float,
              p: float, n_max: int = 64) -> Optional[int]:
    for n in range(1, n_max + 1):
        if C + J + p * R < p * (wb - ws) * (n / N0):
            return n
    return None


def main() -> int:
    s2 = strict_recall("S2")
    s5 = strict_recall("S5")
    costs = collect_costs()

    C = median(costs["C_samples"])
    J = median(costs["J_samples"])
    R = median(costs["R_samples"])
    Wb = median(costs["Wb_samples"])
    Ws = median(costs["Ws_samples"])

    fit = {"C_median": C, "J_median": J, "R_median_per_replan": R,
           "W_batch_median_usd": Wb, "W_sent_median_usd": Ws,
           "W_delta": round(Wb - Ws, 6), "n0": N0}
    rng = random.Random(11)

    cross = {}
    for p in P_GRID:
        point = crossover(C, J, R, Wb, Ws, p)
        boots = []
        for _ in range(N_BOOT):
            def rs(xs):
                return median([rng.choice(xs) for _ in xs]) if xs else None
            b = crossover(rs(costs["C_samples"]), rs(costs["J_samples"]),
                          rs(costs["R_samples"]), rs(costs["Wb_samples"]),
                          rs(costs["Ws_samples"]), p)
            boots.append(b if b is not None else 10**9)
        boots.sort()
        lo, hi = boots[int(0.05 * N_BOOT)], boots[int(0.95 * N_BOOT)]
        cross[p] = {"n_star": point,
                    "ci90": [lo if lo < 10**9 else None,
                             hi if hi < 10**9 else None],
                    "share_no_crossover_le8":
                        sum(1 for b in boots if b > 8) / N_BOOT}
    plausible = any(v["n_star"] is not None and v["n_star"] <= 8
                    and v["ci90"][0] is not None
                    for v in cross.values())

    out = {"s2_strict_recall": s2, "s5_strict_recall_mirror": {
               k: v for k, v in s5.items() if k != "per_cell"},
           "breakeven_fit": fit, "crossover": {str(k): v for k, v in
                                               cross.items()},
           "acceptance_rule_met": plausible}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "baseline_breakeven.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")

    print("TASK F — S2 strict recall (instrument rule, exploratory)")
    print(f"  S2 overall: {s2['recall_all_cells']} (fired-only "
          f"{s2['recall_fired_only']}) | per category: {s2['per_category']}")
    print(f"  S5 mirror : {s5['recall_all_cells']} | per category: "
          f"{s5['per_category']}")
    print("\nTASK F — KG3 break-even fit (model form pre-committed)")
    print(f"  C={C:.4f} J={J:.4f} R={R:.4f} W_batch={Wb:.4f} W_sent={Ws:.4f} "
          f"delta={Wb - Ws:.4f}")
    for p, v in cross.items():
        print(f"  p={p}: n*={v['n_star']} ci90={v['ci90']} "
              f"P(no crossover<=8)={v['share_no_crossover_le8']:.2f}")
    print(f"  acceptance (plausible crossover <= 8 workers): "
          f"{'YES' if plausible else 'NO'}")
    print(f"detail -> {OUT_DIR / 'baseline_breakeven.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
