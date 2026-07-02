"""§8 fan-out arm scaffold — extract the REAL break-even parameters and fan-out
classification needed to pre-register a fan-out crossover study (READ-ONLY, scratch).

Reads frozen artifacts, writes ONLY runs/matrix_1b/fanout_model_inputs.json. No LLM calls,
no matrix re-run, no edits to any paper / gate report / ledger / prereg / frozen file.

The committed model form (phase1b_precommitments §F.1; analysis/baseline_breakeven.py:8;
v6_1 §11.4):
    pay iff  C + J + p*R < p*(W_batch(n) - W_sent(n)),   with  W_x(n) = W_x(n0)*n/n0
C, J, R are FIXED per plan; BOTH waste terms scale linearly in fan-out n (anchored n0=3).
Under this form the crossover exists iff dW(n0) = W_batch(n0) - W_sent(n0) > 0, and then
    F*(p) = ceil( n0 * (C + J + p*R) / (p * dW(n0)) ).
If dW(n0) <= 0 the RHS is <= 0 < the positive LHS for every n -> NO crossover at any n
(the v1 outcome). We do NOT assume a crossover; we extract dW's sign from the data.
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

LEDGER = REPO / "runs" / "matrix_1b" / "results.jsonl"
RUNS = REPO / "runs" / "matrix_1b" / "runs"
AUTOPSY = REPO / "runs" / "matrix_1b" / "cost_autopsy_v3.json"
V1_FIT = REPO / "runs" / "archaeology_v2" / "baseline_breakeven.json"
OUT = REPO / "runs" / "matrix_1b" / "fanout_model_inputs.json"

N0 = 3
P_GRID = (0.1, 0.25, 0.5)


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def load_ledger():
    return [json.loads(l) for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()]


def worker_fanout(run_id: str) -> dict:
    """Concurrent worker count per cell from the trace: distinct worker_start actors, and
    the max workers sharing a wave (the true parallel fan-out)."""
    p = RUNS / run_id / "trace.jsonl"
    if not p.exists():
        return {}
    evs = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    starts = [e for e in evs if e["event_type"] == "worker_start"]
    actors = {e["actor"] for e in starts}
    by_wave = Counter(e["payload"].get("wave", 0) for e in starts)
    return {"distinct_workers": len(actors),
            "max_workers_in_a_wave": (max(by_wave.values()) if by_wave else 0),
            "n_waves": (len(by_wave) if by_wave else 0)}


def crossover_F(C, J, R, dW, p, n_max=4096):
    """Smallest integer n with C + J + p*R < p*dW*(n/N0). None if dW<=0 (never)."""
    if dW is None or dW <= 0:
        return None
    n = N0 * (C + J + p * R) / (p * dW)
    F = math.ceil(n)
    return F if F >= 1 else 1


def main() -> int:
    rows = load_ledger()
    autopsy = json.loads(AUTOPSY.read_text(encoding="utf-8"))
    cen = {c["run_id"]: c for c in autopsy["per_cell"]}
    v1 = json.loads(V1_FIT.read_text(encoding="utf-8"))["breakeven_fit"]

    def lrows(arm, kind):
        out = []
        for r in rows:
            if r["arm"] != arm:
                continue
            if kind == "injected" and r["kind"] != "matrix-injected":
                continue
            if kind == "nonclean" and r["kind"] == "matrix-clean":
                continue
            if kind == "clean" and r["kind"] != "matrix-clean":
                continue
            out.append(r)
        return out

    # ---- v2 cost parameters (mirror baseline_breakeven estimator; J=0, no judge) ----
    def cell_compile(rid):
        b = cen.get(rid, {}).get("by_origin_cost", {})
        return sum(v for k, v in b.items() if k.startswith("compile"))

    def cell_replan_bucket(rid):
        b = cen.get(rid, {}).get("by_origin_cost", {})
        return b.get("replan", 0.0) + b.get("compile_recompile", 0.0)

    # join ledger row -> census run_id by (task,arm,inj, nearest cost) — seed absent in ledger
    from collections import defaultdict
    cen_by_grp = defaultdict(list)
    for c in autopsy["per_cell"]:
        cen_by_grp[(c["task"], c["arm"], c["inj"])].append(c)
    rid_for = {}
    for key, cs in cen_by_grp.items():
        L = sorted([r for r in rows if (r["task"], r["arm"], r["injection"] or "clean") == key],
                   key=lambda r: r["result"]["total_cost_usd"])
        C = sorted(cs, key=lambda c: c["census_cost_raw"])
        for r, c in zip(L, C):
            rid_for[id(r)] = c["run_id"]

    v2_all = lrows("V2", "all") if False else [r for r in rows if r["arm"] == "V2"]
    v2_clean = lrows("V2", "clean")
    v2_inj = lrows("V2", "injected")
    s1_inj = lrows("S1", "injected")
    v2_nonclean = lrows("V2", "nonclean")
    s1_nonclean = lrows("S1", "nonclean")

    C_v2 = med([cell_compile(rid_for[id(r)]) for r in v2_all if id(r) in rid_for])
    C_v2_clean = med([cell_compile(rid_for[id(r)]) for r in v2_clean if id(r) in rid_for])
    # per-replan R over V2 cells with >=1 replan
    R_samples = []
    for r in v2_all:
        rid = rid_for.get(id(r))
        if rid is None:
            continue
        nrep = cen[rid].get("replans") or 0
        if nrep >= 1:
            R_samples.append(cell_replan_bucket(rid) / nrep)
    R_v2 = med(R_samples)
    J_v2 = 0.0  # v2 has no judge (V2J deferred, judge_enabled=False; D33). 0 judge cost events.

    Wb_inj = med([r["result"]["wasted"]["usd"] for r in s1_inj])
    Ws_inj = med([r["result"]["wasted"]["usd"] for r in v2_inj])
    Wb_nc = med([r["result"]["wasted"]["usd"] for r in s1_nonclean])
    Ws_nc = med([r["result"]["wasted"]["usd"] for r in v2_nonclean])
    dW_inj = round(Wb_inj - Ws_inj, 6) if (Wb_inj is not None and Ws_inj is not None) else None
    dW_nc = round(Wb_nc - Ws_nc, 6) if (Wb_nc is not None and Ws_nc is not None) else None

    # ---- crossover F* under the committed model, v2 (use injected-pair set, mirror v1) ----
    F_v2 = {str(p): crossover_F(C_v2, J_v2, R_v2, dW_inj, p) for p in P_GRID}
    # v1 (reproduce from the frozen fit, should be all None)
    F_v1 = {str(p): crossover_F(v1["C_median"], v1["J_median"], v1["R_median_per_replan"],
                                v1["W_delta"], p) for p in P_GRID}

    # ---- actual pilot fan-out distribution (1b) ----
    fan = {}
    for r in rows:
        rid = rid_for.get(id(r))
        if rid:
            fan[rid] = {"arm": r["arm"], "task": r["task"], "kind": r["kind"],
                        **worker_fanout(rid)}
    v2_fan = [f for f in fan.values() if f["arm"] == "V2" and f.get("max_workers_in_a_wave")]
    fan_dist_v2 = Counter(f["max_workers_in_a_wave"] for f in v2_fan)
    fan_by_task = {}
    for t in ("a1", "b1", "c1", "d1"):
        ws = [f["max_workers_in_a_wave"] for f in v2_fan if f["task"] == t]
        fan_by_task[t] = {"median_parallel_workers": med(ws), "values": sorted(set(ws))}

    fixed_vs_scales = {
        "C_compile": {"class": "FIXED per plan",
                      "evidence": "exactly 1 compile invocation per V2 clean cell "
                                  "(cost_autopsy_v3: invocations {1:12}); one compile_and_arm "
                                  "at run start regardless of worker count (run_v2_loop.py:112,163). "
                                  "Independent of N."},
        "J_judge": {"class": "N/A (=0 in v2)",
                    "evidence": "V2 has no judge tier (V2J deferred, judge_enabled=False, D33); "
                                "0 judge cost events in any V2 trace."},
        "R_replan": {"class": "FIXED per replan event (per-plan, not per-worker)",
                     "evidence": "R = orchestrator replan call + one recompile per replan "
                                 "(run_v2_loop.py:481-506); cost is per replan DECISION, "
                                 "issued once per interrupt, not per worker. The NUMBER of "
                                 "replans is bounded by max_replans=2, not by N."},
        "W_batch": {"class": "SCALES WITH FAN-OUT n",
                    "evidence": "batch runs all N parallel workers to completion before "
                                "aggregating, so on a dead plan all N burn the post-injection "
                                "window; committed model sets W_batch(n)=W_batch(n0)*n/n0 "
                                "(baseline_breakeven.py:8). Measured term = worker tokens "
                                "(metrics.wasted_work, window+discarded)."},
        "W_sent": {"class": "SCALES WITH FAN-OUT n (committed model: SAME rate as W_batch)",
                   "evidence": "v2's waste is 100% worker rework (cost_autopsy_v3: monitoring "
                               "tokens = 0; window+discarded only). The committed model assumes "
                               "W_sent(n)=W_sent(n0)*n/n0 — i.e. it scales at the SAME rate as "
                               "W_batch. The MONITORING component (compile/probe/sweep) is fixed "
                               "per plan and $0 on the substrate, so it does NOT scale with N. "
                               "*** KEY INFERENCE (flagged): the committed equal-rate form means "
                               "fan-out only multiplies the EXISTING gap dW(n0); it cannot create "
                               "a crossover if dW(n0)<=0. The physical mechanism for a fan-out "
                               "advantage (early detection -> sentinel discards fewer of N workers "
                               "than batch runs to completion -> W_sent grows SLOWER than W_batch) "
                               "is NOT representable in W_x(n)=W_x(n0)*n/n0. The real arm must "
                               "measure W_batch(n) and W_sent(n) scaling rates SEPARATELY."},
    }

    artifact = {
        "meta": {"generated_by": "analysis/fanout_model_scratch.py", "read_only": True,
                 "model_form": "C + J + p*R < p*(W_batch(n) - W_sent(n)); W_x(n)=W_x(n0)*n/n0",
                 "model_form_source": "phase1b_precommitments §F.1; baseline_breakeven.py:8; v6_1 §11.4",
                 "n0": N0, "p_grid": list(P_GRID)},
        "param_table": {
            "v1_fitted": {  # authoritative frozen fit
                "C": v1["C_median"], "J": v1["J_median"], "R": v1["R_median_per_replan"],
                "W_batch": v1["W_batch_median_usd"], "W_sent": v1["W_sent_median_usd"],
                "dW": v1["W_delta"], "n0": v1["n0"],
                "source": "runs/archaeology_v2/baseline_breakeven.json (Task F, "
                          "analysis/baseline_breakeven.py); paper §9; v6_1 §11.4; "
                          "decision_memo §2 (ΔW=-$0.072, P=1.00).",
                "crossover_v1": F_v1,
                "P_no_crossover_le8": "1.00 at p in {0.1,0.25,0.5} (frozen fit)",
            },
            "v2_estimated_from_1b": {  # mirror estimator, J=0
                "C": C_v2, "C_clean_only": C_v2_clean, "J": J_v2, "R": R_v2,
                "W_batch_injected": Wb_inj, "W_sent_injected": Ws_inj, "dW_injected": dW_inj,
                "W_batch_nonclean": Wb_nc, "W_sent_nonclean": Ws_nc, "dW_nonclean": dW_nc,
                "source": "C/R from cost_autopsy_v3.json by_origin_cost (V2); W_* from "
                          "results.jsonl result.wasted.usd (S1=batch, V2=sentinel); "
                          "estimator mirrors baseline_breakeven.collect_costs with J=0.",
                "crossover_v2_injected": F_v2,
            },
        },
        "fixed_vs_scales_classification": fixed_vs_scales,
        "actual_pilot_fanout_1b": {
            "v2_max_parallel_workers_distribution": dict(fan_dist_v2),
            "by_task": fan_by_task,
            "note": "fan-out n = max workers sharing a wave (true parallel breadth). §4's "
                    "'1 worker in 5/6' was the v1 pilot's consolidation; this is the measured "
                    "1b distribution.",
        },
        "crossover_solution": {
            "symbolic": "F*(p) = ceil( n0 * (C + J + p*R) / (p * dW(n0)) )  iff dW(n0)>0, "
                        "else NONE (no positive n satisfies the inequality).",
            "v1": {"dW": v1["W_delta"], "exists": v1["W_delta"] > 0, "F_star": F_v1},
            "v2_injected": {"dW": dW_inj, "exists": (dW_inj is not None and dW_inj > 0),
                            "F_star": F_v2},
            "interpretation": "Under the committed equal-rate model, crossover existence is "
                              "decided ENTIRELY by sign(dW(n0)). dW<=0 => no crossover at any "
                              "fan-out; dW>0 => finite F*.",
        },
        "real_suite_arm_requirements": {
            "which_suites_produce_multiworker_fanout":
                "Fan-out is a property of the ORCHESTRATION harness, not the suite. GAIA, "
                "tau-bench, and SWE-bench Verified are natively SINGLE-agent (single worker "
                "per task), so none produces multi-worker fan-out as-is. The fan-out arm must "
                "WRAP a parallelizable task in an N-worker plan (the §4 archetypes already "
                "fan out: a1 fetch-3-services is the natural multi-worker shape) and SWEEP N.",
            "min_N_range_to_bracket_Fstar":
                "Sweep N over {1, 3, 8, 16, 32} (n0=3 anchor; the v1 KG3 branch's plausibility "
                "ceiling was fan-out <= 8, so bracket below 3 and well past 8). If dW(n0)<=0 "
                "for v2, F* does not exist under the committed model -> the arm must instead "
                "measure W_batch(N) and W_sent(N) SEPARATELY at each N to test whether the "
                "scaling rates diverge (the only way a crossover emerges when dW(n0)<=0).",
            "metrics_prereg_defs":
                "wasted work (post-injection tokens+tool-calls not contributing + discarded "
                "partials, USD & tokens; prereg.md 6.1), clean overhead (treatment-S1 clean "
                "cost / S1; 6.1/6.2), success (programmatic), per-N W_batch(N)/W_sent(N) curves, "
                "and the fixed C, J(=0), R. Crossover is then F* where p*(W_batch(N)-W_sent(N)) "
                "first exceeds C+J+p*R, measured not assumed.",
        },
    }
    OUT.write_text(json.dumps(artifact, indent=1), encoding="utf-8")

    # ------------------------------- printed report -------------------------------
    print("=" * 80)
    print("§8 FAN-OUT ARM SCAFFOLD — break-even parameters & crossover (read-only)")
    print("=" * 80)
    print("\n(1) PARAMETER TABLE (with provenance)")
    print(f"  model: C + J + p*R < p*(W_batch(n) - W_sent(n)); W_x(n)=W_x(n0)*n/n0; n0={N0}")
    print(f"  v1 FITTED (frozen baseline_breakeven.json / paper §9 / v6_1 §11.4):")
    print(f"     C={v1['C_median']:.4f} J={v1['J_median']:.4f} R={v1['R_median_per_replan']:.4f} "
          f"W_batch={v1['W_batch_median_usd']:.4f} W_sent={v1['W_sent_median_usd']:.4f} "
          f"dW={v1['W_delta']:.4f}  (P(no crossover<=8)=1.00)")
    print(f"  v2 ESTIMATED (1b; cost_autopsy_v3 + results.jsonl; J=0, no judge):")
    print(f"     C={C_v2:.4f} (clean-only {C_v2_clean:.4f}) J={J_v2:.4f} R={R_v2:.4f} "
          f"W_batch={Wb_inj:.4f} W_sent={Ws_inj:.4f} dW(injected)={dW_inj}")
    print(f"     [non-clean set: W_batch={Wb_nc:.4f} W_sent={Ws_nc:.4f} dW={dW_nc}]")

    print("\n(2) FIXED vs SCALES-WITH-FANOUT")
    for k, v in fixed_vs_scales.items():
        print(f"  {k:9s}: {v['class']}")
    print("  KEY: C/J/R fixed per plan; W_batch & W_sent both scale with n (committed model: "
          "SAME rate). Monitoring (compile/probe/sweep) is fixed & $0 -> does NOT scale with N.")

    print("\n(3) ACTUAL PILOT FAN-OUT (1b, V2)")
    print(f"  max-parallel-workers distribution: {dict(fan_dist_v2)}")
    for t, d in fan_by_task.items():
        print(f"    {t}: median parallel workers {d['median_parallel_workers']} "
              f"(seen {d['values']})")

    print("\n(4) CROSSOVER F*")
    print("  F*(p) = ceil( n0*(C+J+p*R) / (p*dW(n0)) )  iff dW(n0)>0, else NONE")
    print(f"  v1: dW={v1['W_delta']:.4f} (<0) -> F* = {F_v1}  => NO CROSSOVER at any fan-out")
    if dW_inj is not None and dW_inj > 0:
        print(f"  v2: dW(injected)={dW_inj} (>0) -> F* = {F_v2}")
    else:
        print(f"  v2: dW(injected)={dW_inj} (<=0) -> F* = {F_v2}  => NO positive crossover under "
              f"the committed equal-rate model (W_sent scales at batch's rate; fan-out only "
              f"multiplies a negative gap). Real arm must measure W_batch(N)/W_sent(N) rates "
              f"SEPARATELY.")

    print("\n(5) decision_memo §2/§4 deferral clause — see fanout_model_inputs.json / report")
    print(f"\nartifact -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
