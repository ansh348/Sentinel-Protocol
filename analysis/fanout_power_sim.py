"""Phase-1c fan-out arm — ANALYTIC power sizing (READ-ONLY, first pass).

Sizes decisions/prereg_1c_fanout_v3.md §5/§6.0 against the REAL 1b per-seed variance.
NOTHING here is frozen: it computes the numbers that would fill the four [AUTHOR-CONFIRM]
slots (half-width target, δ_rec, N=3 similarity margin, S2 promotion is out of scope).

Reads runs/matrix_1b/results.jsonl + cost_autopsy_v3.json; writes ONLY
runs/matrix_1b/fanout_power_sim.json. No LLM calls, no matrix re-run.

METHOD NOTE (flagged): numpy is NOT installed, so the §6.0 B=10,000 × ≥2,000-rep Monte
Carlo is not run as-written. This pass uses ANALYTIC normal approximations (z-based one-sided
95% LCB half-widths for the paired-mean contrast B_p; standard NI-proportion power), validated
by a small pure-Python bootstrap (B=2000) at N=3. Re-run with the full bootstrap once numpy is
available and the §6.2/§6.0 values are frozen.

B_p (prereg_1c §6.2, verbatim):
  B_p(N) = (1-p)*[K0_S1(N) - K0_V2(N)] + p*[K1_S1(N) - K1_V2(N)],  D0=K0_S1-K0_V2, D1=K1_S1-K1_V2

LOAD-BEARING SIMULATION ASSUMPTION (flagged; sensitivity arm at 1.5x/2x CV):
  width-scaled per §3 — W_x(N)=W_x(3)*N/3, C & R fixed. So per injected seed-pair the WASTE
  part of D1 scales N/3 and the monitoring part (compile+replan) is held fixed:
    D1_seed(N) = (D1_seed(3) - dW_seed) + dW_seed*(N/3),   dW_seed = wasted_usd_S1 - wasted_usd_V2
  D0 (clean diff ~ -C; no waste, worker base cancels) is held fixed in N. Variance: CV held
  constant (the empirical seed spread scales with the mean it rides on).
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LEDGER = REPO / "runs" / "matrix_1b" / "results.jsonl"
OUT = REPO / "runs" / "matrix_1b" / "fanout_power_sim.json"

N_GRID = (1, 3, 8, 16, 32, 64)
P_GRID = (0.10, 0.25, 0.50)
N_SEEDS_GRID = (5, 8, 12, 16, 20, 30)
N0 = 3
HALFWIDTH_TARGET = 0.02          # [AUTHOR-CONFIRM: §5 proposed]
DELTA_CS = 0.10                  # §6.0 frozen (inherited 1bKG2)
DELTA_REC_GRID = (0.10, 0.15, 0.20)   # §6.0 δ_rec [AUTHOR-CONFIRM: proposed 0.10]
Z_A = 1.6448536269514722         # one-sided 95%
Z_B = 0.8416212335729143         # 80% power
CV_SENS = (1.0, 1.5, 2.0)
BOOT = 2000


def mean(xs): return statistics.fmean(xs) if xs else 0.0
def sd(xs): return statistics.stdev(xs) if len(xs) > 1 else 0.0


def load():
    rows = [json.loads(l) for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()]
    # pair by (task, slot) clean ; (task, injection, slot) injected, across S1/V2
    clean = defaultdict(dict)
    inj = defaultdict(dict)
    for r in rows:
        res = r["result"]
        if r["kind"] == "matrix-clean":
            clean[(r["task"], r["slot"])][r["arm"]] = res
        else:
            inj[(r["task"], r["injection"], r["slot"])][r["arm"]] = res
    D0, D1, dW = [], [], []
    for k, d in clean.items():
        if "S1" in d and "V2" in d:
            D0.append(d["S1"]["total_cost_usd"] - d["V2"]["total_cost_usd"])
    for k, d in inj.items():
        if "S1" in d and "V2" in d:
            D1.append(d["S1"]["total_cost_usd"] - d["V2"]["total_cost_usd"])
            dW.append((d["S1"]["wasted"]["usd"] or 0.0) - (d["V2"]["wasted"]["usd"] or 0.0))
    return rows, D0, D1, dW, clean, inj


def d1_scaled(D1, dW, N):
    """per-seed D1 at fan-out N: fixed monitoring part + waste part * N/N0."""
    return [(d1 - w) + w * (N / N0) for d1, w in zip(D1, dW)]


def halfwidth(var0, var1, p, n, cv=1.0):
    """one-sided 95% LCB half-width of B_p = z * sqrt((1-p)^2 var0/n + p^2 var1/n), CV-scaled."""
    v = ((1 - p) ** 2 * var0 * cv * cv + p ** 2 * var1 * cv * cv) / n
    return Z_A * math.sqrt(v)


def n_for_halfwidth(var0, var1, p, target, cv=1.0):
    num = (Z_A ** 2) * ((1 - p) ** 2 * var0 * cv * cv + p ** 2 * var1 * cv * cv)
    return math.ceil(num / (target ** 2)) if target > 0 else None


def ni_n_one_sample(p_a, delta):
    """NI vs a fixed anchor at margin delta: n for 80% power, truth = anchor (p_a). Standard
    NI-proportion size using variance at the alternative (p_a) AND the NI null boundary
    p0 = p_a - delta (NOT p_hat(1-p_hat), which degenerates to 0 when observed recall = 1.0)."""
    pa = max(1e-6, min(1 - 1e-6, p_a))
    p0 = max(1e-6, min(1 - 1e-6, p_a - delta))
    return math.ceil((Z_A * math.sqrt(p0 * (1 - p0)) + Z_B * math.sqrt(pa * (1 - pa))) ** 2
                     / (delta ** 2))


def ni_n_two_sample(p_t, p_c, delta):
    """NI of treatment vs comparator proportions (clean success V2 vs S1), truth=observed."""
    eff = delta - (p_c - p_t)         # effective margin given the observed gap
    if eff <= 0:
        return None                    # cannot be powered: observed gap already exceeds margin
    return math.ceil((Z_A + Z_B) ** 2 * (p_t * (1 - p_t) + p_c * (1 - p_c)) / (eff ** 2))


def power_one_sample(p_hat, delta, n):
    if n <= 0:
        return 0.0
    se = math.sqrt(p_hat * (1 - p_hat) / n)
    return _norm_cdf(delta / se - Z_A) if se > 0 else 1.0


def power_two_sample(p_t, p_c, delta, n):
    if n <= 0:
        return 0.0
    eff = delta - (p_c - p_t)
    se = math.sqrt((p_t * (1 - p_t) + p_c * (1 - p_c)) / n)
    return _norm_cdf(eff / se - Z_A) if se > 0 else (1.0 if eff > 0 else 0.0)


def _norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def boot_halfwidth(D0, D1N, p, n_seeds, reps=BOOT, seed=20260625):
    """pure-Python paired cluster bootstrap of the LCB half-width at one (N,p,n_seeds),
    drawing n_seeds clean and n_seeds injected with replacement (validates the normal approx)."""
    import random
    rng = random.Random(seed)
    means = []
    for _ in range(reps):
        s0 = [rng.choice(D0) for _ in range(n_seeds)]
        s1 = [rng.choice(D1N) for _ in range(n_seeds)]
        means.append((1 - p) * mean(s0) + p * mean(s1))
    means.sort()
    point = (1 - p) * mean(D0) + p * mean(D1N)
    lcb = means[int(0.05 * reps)]
    return point - lcb


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    rows, D0, D1, dW, clean, inj = load()
    var0, var1_3 = sd(D0) ** 2, sd(D1) ** 2

    # ---- (1) input distributions ----
    inputs = {
        "n_clean_pairs": len(D0), "n_injected_pairs": len(D1),
        "D0_clean": {"mean": mean(D0), "sd": sd(D0),
                     "cv": (sd(D0) / abs(mean(D0))) if mean(D0) else None},
        "D1_injected": {"mean": mean(D1), "sd": sd(D1),
                        "cv": (sd(D1) / abs(mean(D1))) if mean(D1) else None},
        "dW_waste_diff": {"mean": mean(dW), "sd": sd(dW)},
        "source": "results.jsonl total_cost_usd & wasted.usd, paired S1-V2 by "
                  "(task,slot)/(task,injection,slot); cost_autopsy_v3 reconciled.",
    }

    # quality base rates (1b)
    def rate(kind, arm, field):
        rs = [r for r in rows if r["kind"] == kind and r["arm"] == arm]
        ok = sum(1 for r in rs if r["result"].get(field) is True)
        return ok, len(rs)
    v2_cs = rate("matrix-clean", "V2", "success")
    s1_cs = rate("matrix-clean", "S1", "success")
    # recoverable-class recall (gate denominator = ALL injected incl. holdout, recovery_class
    # RECOVERABLE -> matches gate's 10/15; the earlier matrix-injected-only filter wrongly
    # dropped the holdout RB/DV cells)
    recov = [r for r in rows if r["injection"] is not None and r["arm"] == "V2"
             and r.get("recovery_class") == "RECOVERABLE"]
    rec_k = sum(1 for r in recov if r["result"]["detected"])
    percat = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["kind"] == "matrix-injected" and r["arm"] == "V2":
            c = percat[r["category"]]
            c[1] += 1
            c[0] += 1 if r["result"]["detected"] else 0
    base = {"v2_clean_success": f"{v2_cs[0]}/{v2_cs[1]}", "s1_clean_success": f"{s1_cs[0]}/{s1_cs[1]}",
            "v2_clean_success_rate": v2_cs[0] / v2_cs[1], "s1_clean_success_rate": s1_cs[0] / s1_cs[1],
            "recoverable_recall": f"{rec_k}/{len(recov)}",
            "recoverable_recall_rate": (rec_k / len(recov)) if recov else None,
            "per_category_recall": {k: f"{v[0]}/{v[1]}" for k, v in sorted(percat.items())}}

    # ---- (2) half-width curves: n_seeds x N x p, plus n_seeds needed for target ----
    hw_curves, n_needed = {}, {}
    for N in N_GRID:
        D1N = d1_scaled(D1, dW, N)
        var1N = sd(D1N) ** 2
        for p in P_GRID:
            key = f"N{N}_p{p}"
            hw_curves[key] = {str(ns): round(halfwidth(var0, var1N, p, ns), 5)
                              for ns in N_SEEDS_GRID}
            n_needed[key] = n_for_halfwidth(var0, var1N, p, HALFWIDTH_TARGET)
    # binding grid point = worst (largest n needed), typically N=64
    worst = max(n_needed.items(), key=lambda kv: (kv[1] or 0))

    # bootstrap validation at N=3, p=0.25, n_seeds=12 (normal-approx vs empirical)
    D1_3 = d1_scaled(D1, dW, 3)
    boot_hw = boot_halfwidth(D0, D1_3, 0.25, 12)
    norm_hw = halfwidth(var0, sd(D1_3) ** 2, 0.25, 12)

    # ---- (3) NI testability (clean-success δ_cs ; recall δ_rec pooled & per-category) ----
    # assume the fan-out arm runs the width-scaled a1 template -> clean obs per N = n_seeds
    # (1 task); per-category recall obs per N = (#recoverable injection-shapes in cat) x n_seeds.
    ni = {"clean_success_NI": {
              "delta_cs": DELTA_CS,
              "n_seeds_required_80pct": ni_n_two_sample(base["v2_clean_success_rate"],
                                                        base["s1_clean_success_rate"], DELTA_CS),
              "note": "two-sample NI V2 vs S1 clean success; per-N clean obs = n_seeds (1 task)."},
          "recall_NI_pooled": {}, "recall_NI_per_category": {}}
    p_rec = base["recoverable_recall_rate"] or 0.85
    # pooled recoverable injection-shapes in the 1b recoverable class:
    n_recov_shapes = len({(r["task"], r["injection"]) for r in recov})
    for d in DELTA_REC_GRID:
        n_obs = ni_n_one_sample(p_rec, d)
        ni["recall_NI_pooled"][f"delta_{int(d*100)}pp"] = {
            "n_binary_obs_required": n_obs,
            "n_seeds_required": math.ceil(n_obs / max(1, n_recov_shapes)),
            "pooled_recoverable_shapes": n_recov_shapes}
        # per-category: ~1-2 recoverable shapes/category -> obs = ~1.5 x n_seeds
        ni["recall_NI_per_category"][f"delta_{int(d*100)}pp"] = {
            "n_binary_obs_required_per_category": n_obs,
            "n_seeds_required_per_category_assuming_1.5_shapes": math.ceil(n_obs / 1.5)}

    # ---- (4) Holm note on the 18 B_p>0 sign tests (affects sign power, not half-width) ----
    holm = {"family_size": 18, "fwer": 0.05,
            "z_most_significant": round(_inv_norm(1 - 0.05 / 18), 4),
            "note": "Holm step-down: the smallest threshold is 0.05/18 (z~2.77 vs per-test "
                    "1.645). Raises the effect needed to DECLARE B_p(N)>0; does not change the "
                    "§5 half-width precision target."}

    # ---- (5) sensitivity at 1.5x / 2x CV (n_seeds for target at the binding point) ----
    sens = {}
    Nworst = int(worst[0].split("_")[0][1:])
    pworst = float(worst[0].split("_p")[1])
    D1w = d1_scaled(D1, dW, Nworst)
    for cv in CV_SENS:
        sens[f"cv_{cv}x"] = {
            "n_seeds_for_target_at_binding_point": n_for_halfwidth(var0, sd(D1w) ** 2, pworst,
                                                                   HALFWIDTH_TARGET, cv),
            "binding_point": worst[0]}

    # ---- (6) recommended freeze tuple + cell/compute estimate ----
    # buyable half-width at the floor-ish n_seeds=12 across the grid (worst N=64):
    buyable_12 = {f"N{N}_p{p}": round(halfwidth(var0, sd(d1_scaled(D1, dW, N)) ** 2, p, 12), 4)
                  for N in N_GRID for p in P_GRID}
    n_arms = 3  # S1,S3,V2 (S2 exploratory)
    n_conditions = 2  # injected + clean
    rec = {
        "binding_constraint": ("B_p half-width at N=64 (waste-scaled variance) — NOT the "
                               "quality gates" if (worst[1] or 0) > 30 else "quality gate"),
        "buyable_halfwidth_at_n_seeds_12": buyable_12,
        "halfwidth_002_feasible": (worst[1] is not None and worst[1] <= 30),
        "recommended_freeze_tuple_PROPOSED_not_frozen": {
            "n_seeds": 30,
            "n_seeds_rationale": "driven by pooled recoverable-recall NI at delta_rec=10pp "
                                 "(~30 seeds); the $0.02 B_p half-width (6831) and per-category "
                                 "/ clean-success NI at 10pp are NOT the achievable driver — "
                                 "they are relaxed/demoted below. n_seeds=12-14 if delta_rec "
                                 "widened to 15pp pooled.",
            "delta_rec": "10pp POOLED recoverable-class only (~30 seeds); per-category "
                         "DESCRIPTIVE (10pp needs ~98 seeds/cat — infeasible).",
            "delta_cs_clean_success": "FLAG: NI at 10pp needs ~9120 seeds because V2's 1b clean "
                                      "success (0.667) already trails S1 (0.75) by 8.3pp, "
                                      "near-exhausting the margin. Either re-estimate the gap at "
                                      "higher N (the 1b gap is 1 cell at n=12, plausibly noise; "
                                      "truth-equal needs ~260 seeds) or report clean-success "
                                      "descriptively. NOT gateable at 10pp on the 1b point gap.",
            "halfwidth_target": ("DROP the $0.02 absolute target — infeasible beyond N~8 "
                                 "(CV 2.1-2.4; $0.02 at N=64 needs 6831 seeds). Use the §6.2 "
                                 "sign test LCB[B_p]>0 for crossover (its actual rule) and "
                                 "report the ACHIEVED half-width descriptively (~$0.04 at N=3 "
                                 "to ~$0.15 at N=64 at n_seeds=30). Or cap the N grid at 32."),
        },
        "cells_per_n": {f"n_seeds={ns}": ns * n_arms * n_conditions * len(N_GRID)
                        for ns in (5, 12, 20)},
        "compute_note": "N=64 cells cost ~64x per-worker token cost; a single n_seeds=12 grid "
                        "is 12*3*2*6 = 432 cells but the N in {32,64} cells dominate cost "
                        "(~21x and ~43x the N=3 per-cell worker cost). Budget the high-N tail, "
                        "not the cell count.",
    }

    artifact = {
        "meta": {"generated_by": "analysis/fanout_power_sim.py", "read_only": True,
                 "FROZEN": False,
                 "method": "ANALYTIC normal-approx (numpy absent; §6.0 full bootstrap deferred)",
                 "doc": "decisions/prereg_1c_fanout_v3.md (DRAFT, un-pinned)",
                 "Bp_formula": "(1-p)*D0 + p*D1, D0=K0_S1-K0_V2, D1=K1_S1-K1_V2 (§6.2)",
                 "scaling_assumption": "D1 waste part *N/3, C/R fixed; CV constant (LOAD-BEARING)"},
        "input_distributions": inputs,
        "quality_base_rates_1b": base,
        "halfwidth_curves": hw_curves,
        "n_seeds_for_002_target": n_needed,
        "binding_grid_point": {"point": worst[0], "n_seeds_needed": worst[1]},
        "bootstrap_validation_N3_p25_n12": {"bootstrap_halfwidth": round(boot_hw, 5),
                                            "normal_approx_halfwidth": round(norm_hw, 5),
                                            "agree_within_10pct":
                                                abs(boot_hw - norm_hw) <= 0.1 * max(boot_hw, norm_hw)},
        "NI_testability": ni,
        "holm_18_Bp_tests": holm,
        "cv_sensitivity": sens,
        "recommendation": rec,
    }
    OUT.write_text(json.dumps(artifact, indent=1), encoding="utf-8")

    # ----------------------------- printed report -----------------------------
    print("=" * 80)
    print("PHASE-1c FAN-OUT POWER SIZING (analytic; NOT FROZEN)  draft: decisions/prereg_1c_fanout_v3.md")
    print("=" * 80)
    print("\n(1) INPUT DISTRIBUTIONS (real 1b paired, source: results.jsonl)")
    print(f"  D0 clean (K0_S1-K0_V2)  n={len(D0)}  mean ${mean(D0):+.4f}  sd ${sd(D0):.4f}  "
          f"CV {inputs['D0_clean']['cv']:.2f}")
    print(f"  D1 injected (K1_S1-K1_V2) n={len(D1)}  mean ${mean(D1):+.4f}  sd ${sd(D1):.4f}  "
          f"CV {inputs['D1_injected']['cv']:.2f}")
    print(f"  dW waste diff (S1-V2)   mean ${mean(dW):+.4f}  sd ${sd(dW):.4f}")
    print(f"  base: V2 clean {base['v2_clean_success']} S1 {base['s1_clean_success']}; "
          f"recoverable recall {base['recoverable_recall']}; per-cat {base['per_category_recall']}")

    print("\n(2) n_seeds vs HALF-WIDTH ($0.02 target) — buyable half-width @ n_seeds=12:")
    for p in P_GRID:
        line = "  p=%.2f: " % p + "  ".join(
            f"N{N}={buyable_12[f'N{N}_p{p}']:.3f}" for N in N_GRID)
        print(line)
    print(f"  n_seeds needed for $0.02: binding point {worst[0]} -> {worst[1]} seeds")
    print(f"  bootstrap check (N3,p.25,n12): boot {boot_hw:.4f} vs normal {norm_hw:.4f} "
          f"(agree: {artifact['bootstrap_validation_N3_p25_n12']['agree_within_10pct']})")

    print("\n(3) PER-GATE TESTABILITY")
    print(f"  clean-success NI (δ=10pp): n_seeds required ~{ni['clean_success_NI']['n_seeds_required_80pct']}")
    for d in DELTA_REC_GRID:
        k = f"delta_{int(d*100)}pp"
        print(f"  recall NI δ={int(d*100)}pp: pooled needs ~{ni['recall_NI_pooled'][k]['n_seeds_required']} seeds "
              f"| per-category needs ~{ni['recall_NI_per_category'][k]['n_seeds_required_per_category_assuming_1.5_shapes']} seeds/cat")

    print("\n(4) DETECTION-NI VERDICT")
    p10 = ni["recall_NI_per_category"]["delta_10pp"]["n_seeds_required_per_category_assuming_1.5_shapes"]
    print(f"  δ_rec=10pp per-category needs ~{p10} seeds/category -> INFEASIBLE. "
          f"Pooled 10pp ~{ni['recall_NI_pooled']['delta_10pp']['n_seeds_required']} seeds (feasible). "
          f"=> gate pooled recoverable-class recall NI; report per-category DESCRIPTIVE.")

    print("\n(5) CV SENSITIVITY (n_seeds for $0.02 at binding point %s)" % worst[0])
    for cv, v in sens.items():
        print(f"  {cv}: {v['n_seeds_for_target_at_binding_point']} seeds")

    print("\n(6) RECOMMENDED FREEZE TUPLE (PROPOSED, not frozen)")
    print(f"  binding constraint: {rec['binding_constraint']}")
    print(f"  $0.02 half-width feasible across full grid (incl N=64)? {rec['halfwidth_002_feasible']}")
    print(f"  proposed: n_seeds={rec['recommended_freeze_tuple_PROPOSED_not_frozen']['n_seeds']}, "
          f"δ_rec={rec['recommended_freeze_tuple_PROPOSED_not_frozen']['delta_rec']}")
    print(f"  half-width: {rec['recommended_freeze_tuple_PROPOSED_not_frozen']['halfwidth_target']}")
    print(f"  cells @ n_seeds=12: {rec['cells_per_n']['n_seeds=12']} (N=32/64 dominate token cost)")
    print(f"\nartifact -> {OUT}")
    return 0


def _inv_norm(p):
    # Acklam approximation (enough for the Holm z note)
    a = [-39.6968302866538, 220.946098424521, -275.928510446969,
         138.357751867269, -30.6647980661472, 2.50662827745924]
    b = [-54.4760987982241, 161.585836858041, -155.698979859887,
         66.8013118877197, -13.2806815528857]
    c = [-0.00778489400243029, -0.322396458041136, -2.40075827716184,
         -2.54973253934373, 4.37466414146497, 2.93816398269878]
    d = [0.00778469570904146, 0.32246712907004, 2.445134137143, 3.75440866190742]
    pl = 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p <= 1 - pl:
        q = p - 0.5; r = q*q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)


if __name__ == "__main__":
    sys.exit(main())
