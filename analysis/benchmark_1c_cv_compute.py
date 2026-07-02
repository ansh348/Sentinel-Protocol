#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""benchmark_1c_cv_compute.py -- PILOT / NOT FROZEN / NOT CONFIRMATORY.

Consume the CV-pilot cells and apply the FROZEN blind resize formula SIGN-BLIND:

  B_p(N) = (1-p)*[K0_S1 - K0_V2] + p*[K1_S1 - K1_V2]      (§6.2 estimand; K = total run cost)
  n_seeds(N) = max(5, ceil((1.645 * SD_seed[B_p(N)] / H)^2)) at worst-case p
               (max SD over p in {0.10,0.25,0.50}); H=$0.015, B=$450; binding-width n.

n is computed from SD ALONE (it never reads the sign/direction of the mean). The point
estimate (mean B_p, i.e. whether V2 looks cheaper or costlier) is reported SEPARATELY and
labelled non-determinative, per the E4 integrity firewall.

Also reports the quality-floor metrics (clean-success, recovery, detection) so the CV is of
the quality-qualified net cost, and the implied confirmatory scope + $ estimate vs B=$450.
"""
from __future__ import annotations

import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

CELLS = ROOT / "runs" / "matrix_1c" / "cv_pilot" / "cells.jsonl"
H = 0.015
Z = 1.645
B_BUDGET = 450.0
PS = [0.10, 0.25, 0.50]
GRID = [1, 3, 8, 16, 32, 64]


def load(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines()
            if l.strip() and "error" not in json.loads(l)]


def n_from_sd(sd):
    return max(5, math.ceil((Z * sd / H) ** 2))


def per_seed_K(rows):
    """K[(N, arm, condition)][seed] = cost."""
    K = defaultdict(dict)
    for r in rows:
        K[(r["N"], r["arm"], r["condition"])][r["seed"]] = r["K_cost_usd"]
    return K


def estimand(K, N, treat):
    """Per-seed D0, D1, and B_p for the (S1 - treat) net cost at width N. Paired seeds only."""
    k0_s1 = K.get((N, "S1", "clean"), {});  k1_s1 = K.get((N, "S1", "injected"), {})
    k0_t = K.get((N, treat, "clean"), {});  k1_t = K.get((N, treat, "injected"), {})
    seeds = sorted(set(k0_s1) & set(k1_s1) & set(k0_t) & set(k1_t))
    D0 = {s: k0_s1[s] - k0_t[s] for s in seeds}
    D1 = {s: k1_s1[s] - k1_t[s] for s in seeds}
    return seeds, D0, D1


def analyze_width(K, N, treat):
    seeds, D0, D1 = estimand(K, N, treat)
    if len(seeds) < 2:
        return {"N": N, "treat": treat, "n_paired_seeds": len(seeds),
                "note": "insufficient paired seeds for SD (need >=2)"}
    rows = []
    for p in PS:
        Bp = [(1 - p) * D0[s] + p * D1[s] for s in seeds]
        sd = st.stdev(Bp)
        mean = st.mean(Bp)
        cv = (sd / abs(mean)) if mean != 0 else float("inf")
        rows.append({"p": p, "sd": sd, "mean": mean, "cv": cv, "n_formula": n_from_sd(sd)})
    worst = max(rows, key=lambda r: r["sd"])           # worst-case p = max SD
    return {
        "N": N, "treat": treat, "n_paired_seeds": len(seeds), "seeds": seeds,
        "D0_mean": st.mean(D0.values()) if D0 else None,
        "D1_mean": st.mean(D1.values()) if D1 else None,
        "per_p": rows,
        "worst_p": worst["p"], "SD_worst": worst["sd"],
        "CV_at_worst_p": worst["cv"],
        "point_estimate_mean_Bp_at_worst_p": worst["mean"],   # SIGN — reported, non-determinative
        "n_seeds_SIGN_BLIND": n_from_sd(worst["sd"]),          # from SD only
    }


def quality_floor(rows):
    """clean-success, detection, recovery per (N, arm); + KG0 (S1 clean pass / injected wound)."""
    by = defaultdict(list)
    for r in rows:
        by[(r["N"], r["arm"])].append(r)
    out = {}
    for (N, arm), cells in sorted(by.items()):
        cl = [c for c in cells if c["condition"] == "clean"]
        inj = [c for c in cells if c["condition"] == "injected"]
        clean_success = (sum(bool(c["checker_success"]) for c in cl), len(cl))
        injected_wound = (sum((c["checker_success"] is False) for c in inj), len(inj))
        detected = (sum(bool(c["detected"]) for c in inj), len(inj))
        recovered = (sum(bool(c.get("recovered")) for c in inj), len(inj))
        out[f"N={N} {arm}"] = {
            "clean_success": f"{clean_success[0]}/{clean_success[1]}",
            "injected_wounded": f"{injected_wound[0]}/{injected_wound[1]}",
            "detected": f"{detected[0]}/{detected[1]}",
            "recovered(detect-and-replan)": f"{recovered[0]}/{recovered[1]}",
        }
    return out


def cost_model(K):
    """Per-arm linear cost model a+b*N from the measured widths (mean over seeds/conditions),
    for the confirmatory $ extrapolation across the grid."""
    pts = defaultdict(dict)  # arm -> {N: mean per-cell cost over conditions+seeds}
    agg = defaultdict(list)
    for (N, arm, cond), seedmap in K.items():
        for s, c in seedmap.items():
            agg[(arm, N)].append(c)
    for (arm, N), cs in agg.items():
        pts[arm][N] = st.mean(cs)
    model = {}
    for arm, d in pts.items():
        Ns = sorted(d)
        if len(Ns) >= 2:
            (n1, n2) = Ns[0], Ns[-1]
            b = (d[n2] - d[n1]) / (n2 - n1)
            a = d[n1] - b * n1
            model[arm] = (a, b, dict(d))
        elif Ns:
            model[arm] = (d[Ns[0]], 0.0, dict(d))   # flat if only one width
    return model


def main(path=CELLS):
    rows = load(path)
    K = per_seed_K(rows)
    Ns = sorted({r["N"] for r in rows})
    arms = sorted({r["arm"] for r in rows})

    print("=" * 100)
    print("CV PILOT — net-cost B_p, frozen blind resize (SIGN-BLIND), quality floor")
    print(f"H=${H}  z={Z}  B=${B_BUDGET}  worst-case p = max SD over {PS}")
    print("=" * 100)

    print("\n[QUALITY FLOOR] (clean-success / injected-wound / detected / recovered)")
    for k, v in quality_floor(rows).items():
        print(f"  {k:10s}: {v}")

    results = {}
    for treat in ("V2", "V2nc"):
        print(f"\n[ESTIMAND S1 - {treat}]  B_p(N) = (1-p)*D0 + p*D1   (B_p>0 => {treat} cheaper)")
        for N in Ns:
            r = analyze_width(K, N, treat)
            results[(treat, N)] = r
            if r.get("n_paired_seeds", 0) < 2:
                print(f"  N={N}: {r.get('note')}"); continue
            print(f"  N={N}  ({r['n_paired_seeds']} paired seeds {r['seeds']})")
            print(f"     D0_mean=${r['D0_mean']:+.4f}  D1_mean=${r['D1_mean']:+.4f}")
            for pr in r["per_p"]:
                print(f"     p={pr['p']:.2f}: SD=${pr['sd']:.4f}  mean=${pr['mean']:+.4f}  "
                      f"CV={pr['cv']:.3f}  n={pr['n_formula']}")
            print(f"     -> worst-case p={r['worst_p']:.2f}  SD_worst=${r['SD_worst']:.4f}  "
                  f"CV={r['CV_at_worst_p']:.3f}")
            print(f"     -> n_seeds (SIGN-BLIND, from SD only) = {r['n_seeds_SIGN_BLIND']}")
            print(f"        point estimate mean B_p=${r['point_estimate_mean_Bp_at_worst_p']:+.4f} "
                  f"({'V2-cheaper' if r['point_estimate_mean_Bp_at_worst_p']>0 else treat+'-costlier'}) "
                  f"-- NON-DETERMINATIVE, not used for n")

    # binding-width n for the PRIMARY estimand (S1 - V2)
    print("\n" + "=" * 100)
    print("RESIZE (primary estimand S1 - V2; V2nc reported as a secondary line)")
    v2_ns = {N: results[("V2", N)] for N in Ns if results[("V2", N)].get("n_paired_seeds", 0) >= 2}
    if v2_ns:
        per_width = {N: r["n_seeds_SIGN_BLIND"] for N, r in v2_ns.items()}
        binding = max(per_width.values())
        binding_N = max(per_width, key=per_width.get)
        print(f"  per-width n (S1-V2): {per_width}")
        print(f"  BINDING-WIDTH n = {binding}  (from N={binding_N}, worst-case p, SD only)")

        # implied confirmatory scope
        model = cost_model(K)
        conf_arms = ["S1", "V2", "V2nc"]
        conditions = 2  # clean + injected
        def cell_cost(arm, N):
            a, b, d = model.get(arm, (1.0, 0.0, {}))
            return d.get(N, max(0.05, a + b * N))
        total_cells = binding * len(GRID) * len(conf_arms) * conditions
        total_cost = sum(binding * cell_cost(arm, N) * conditions
                         for N in GRID for arm in conf_arms)
        print(f"\n  IMPLIED CONFIRMATORY SCOPE (binding n={binding} seeds/cell):")
        print(f"     grid N {GRID} x arms {conf_arms} x {{clean,injected}} = "
              f"{len(GRID)*len(conf_arms)*conditions} cells/seed x {binding} seeds = {total_cells} cells")
        print(f"     implied confirmatory cost ~= ${total_cost:.0f}  vs budget B=${B_BUDGET:.0f}  "
              f"-> {'WITHIN budget' if total_cost <= B_BUDGET else 'OVER budget — surface n-wanted vs n-affordable, STOP for author call (no silent truncation)'}")
        if total_cost > B_BUDGET:
            n_aff = binding
            while n_aff > 5:
                c = sum(n_aff * cell_cost(arm, N) * conditions for N in GRID for arm in conf_arms)
                if c <= B_BUDGET: break
                n_aff -= 1
            print(f"     n-wanted={binding}  n-affordable(<=B)~={n_aff}  (REPORT BOTH; do not silently shrink)")

    print("\nPILOT / NOT FROZEN / NOT CONFIRMATORY")
    # machine-readable
    out = ROOT / "runs" / "matrix_1c" / "cv_pilot" / "cv_result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    ser = {f"{t}_N{N}": {k: v for k, v in r.items() if k != "per_p"} | {"per_p": r.get("per_p")}
           for (t, N), r in results.items()}
    out.write_text(json.dumps({"H": H, "z": Z, "B": B_BUDGET, "worst_case_p_set": PS,
                               "quality_floor": quality_floor(rows), "estimands": ser}, indent=2,
                              default=str), encoding="utf-8")
    print(f"cv_result.json -> {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else CELLS)
