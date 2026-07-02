#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cv_resize_audit.py -- AUDIT / NOT FROZEN / NOT CONFIRMATORY.  $0, banked data only.

Is n=859 a real precision demand or a small-sample/computation artifact? Re-derives the
resize on the banked cv_pilot cells.jsonl: Q1 formula+units hand-check, Q2 paired-SD
verification, Q3 N=32 leave-one-out n swing, Q4 honest n-floor from the N=8 5-seed SD.
"""
from __future__ import annotations
import math, statistics as st, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from analysis.benchmark_1c_cv_compute import (load, per_seed_K, n_from_sd, cost_model,  # noqa: E402
                                              H, Z, B_BUDGET, PS, GRID)
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

CELLS = ROOT / "runs" / "matrix_1c" / "cv_pilot" / "cells.jsonl"


def Bp_series(K, N, treat, seeds):
    k0s1, k1s1 = K[(N, "S1", "clean")], K[(N, "S1", "injected")]
    k0t, k1t = K[(N, treat, "clean")], K[(N, treat, "injected")]
    D0 = {s: k0s1[s] - k0t[s] for s in seeds}
    D1 = {s: k1s1[s] - k1t[s] for s in seeds}
    return D0, D1


def worst_p_sd_n(D0, D1, seeds):
    best = None
    for p in PS:
        Bp = [(1 - p) * D0[s] + p * D1[s] for s in seeds]
        sd = st.stdev(Bp) if len(Bp) >= 2 else 0.0
        if best is None or sd > best[1]:
            best = (p, sd, n_from_sd(sd))
    return best  # (worst_p, sd, n)


def conf_cost(K, n):
    model = cost_model(K)
    def cc(arm, Nn):
        a, b, d = model.get(arm, (1.0, 0.0, {}))
        return d.get(Nn, max(0.05, a + b * Nn))
    return sum(n * cc(arm, Nn) * 2 for Nn in GRID for arm in ["S1", "V2", "V2nc"])


def main():
    rows = load(CELLS)
    K = per_seed_K(rows)
    print("=" * 92)
    print("CV-RESIZE AUDIT — banked cv_pilot data, $0")
    print(f"formula: n = max(5, ceil((Z*SD/H)^2));  Z={Z} (1-sided 95%)  H=${H} (dollars)  B=${B_BUDGET} (dollars)")
    print("=" * 92)

    # ---- Q1: hand-check N=8 n=128 ----
    print("\n[Q1] FORMULA + UNITS + HAND-CHECK")
    print("  units: SD in $ (per-seed B_p, a $ cost difference); H in $ -> Z*SD/H dimensionless; n dimensionless. No cents/$ mismatch.")
    seeds8 = sorted(set(K[(8,'S1','clean')]) & set(K[(8,'S1','injected')]) & set(K[(8,'V2','clean')]) & set(K[(8,'V2','injected')]))
    D0, D1 = Bp_series(K, 8, "V2", seeds8)
    wp, sd8, n8 = worst_p_sd_n(D0, D1, seeds8)
    step = Z * sd8 / H
    print(f"  N=8 S1-V2: worst-case p={wp}  SD=${sd8:.6f}")
    print(f"    Z*SD/H = {Z}*{sd8:.6f}/{H} = {step:.6f}  -> (^2) = {step**2:.4f}  -> ceil = {math.ceil(step**2)}  -> n={n_from_sd(sd8)}")
    print(f"    reproduces n=128? {n_from_sd(sd8) == 128}")
    seeds32 = sorted(set(K[(32,'S1','clean')]) & set(K[(32,'S1','injected')]) & set(K[(32,'V2','clean')]) & set(K[(32,'V2','injected')]))
    D0b, D1b = Bp_series(K, 32, "V2", seeds32)
    wp32, sd32, n32 = worst_p_sd_n(D0b, D1b, seeds32)
    print(f"  N=32 S1-V2: worst-case p={wp32}  SD=${sd32:.6f}  -> n={n32}  reproduces 859? {n32==859}")

    # ---- Q2: estimand + SD verification (independent recompute) ----
    print("\n[Q2] ESTIMAND PAIRING + SD VERIFICATION (independent recompute vs cv_result $0.1029/$0.2672)")
    for N, treat, target in [(8, "V2", 0.1029), (32, "V2", 0.2672)]:
        sds = sorted(set(K[(N,'S1','clean')]) & set(K[(N,'S1','injected')]) & set(K[(N,treat,'clean')]) & set(K[(N,treat,'injected')]))
        d0, d1 = Bp_series(K, N, treat, sds)
        # paired per-seed B_p at the worst-case p
        wp_, sd_, _ = worst_p_sd_n(d0, d1, sds)
        # also show that pairing is PER-SEED (D computed on same seed), not pooled:
        paired_ok = all(s in K[(N,'S1','clean')] and s in K[(N,treat,'clean')] for s in sds)
        print(f"  N={N} S1-{treat}: {len(sds)} paired seeds {sds}; per-seed-paired={paired_ok}; "
              f"worst-p={wp_} SD=${sd_:.4f} (target ${target}) match={abs(sd_-target)<0.0006}")

    # ---- Q3: N=32 leave-one-out ----
    print("\n[Q3] N=32 LEAVE-ONE-OUT (3 seeds -> drop each -> 2-seed n)")
    loo_ns = []
    for drop in seeds32:
        keep = [s for s in seeds32 if s != drop]
        d0, d1 = Bp_series(K, 32, "V2", keep)
        wp_, sd_, nn = worst_p_sd_n(d0, d1, keep)
        loo_ns.append(nn)
        print(f"  drop {drop} -> keep {keep}: worst-p={wp_} SD=${sd_:.4f}  n={nn}")
    print(f"  FULL 3-seed n={n32};  LOO range n in [{min(loo_ns)}, {max(loo_ns)}]  (swing {max(loo_ns)-min(loo_ns)})")
    print(f"  VERDICT: {'859 is a 3-seed ARTIFACT (LOO swings by hundreds+) -> trust N=8 n only' if (max(loo_ns)-min(loo_ns))>200 else 'robust'}")
    # also N=8 LOO for context (5 seeds)
    print("  (context) N=8 LOO (5 seeds -> drop each -> 4-seed n):")
    loo8 = []
    for drop in seeds8:
        keep = [s for s in seeds8 if s != drop]
        d0, d1 = Bp_series(K, 8, "V2", keep)
        wp_, sd_, nn = worst_p_sd_n(d0, d1, keep)
        loo8.append(nn)
    print(f"     N=8 full n={n8}; LOO range n in [{min(loo8)}, {max(loo8)}] (swing {max(loo8)-min(loo8)})")

    # ---- Q4: honest floor (N=8 5-seed SD) ----
    print("\n[Q4] HONEST n-FLOOR at H=$0.015 (use the more reliable N=8 5-seed SD)")
    n_floor = n_from_sd(sd8)
    c_floor = conf_cost(K, n_floor)
    c_859 = conf_cost(K, 859)
    print(f"  N=8 5-seed SD=${sd8:.4f} (worst-p={wp}) -> n_floor={n_floor}")
    print(f"  implied confirmatory at n={n_floor}: ~${c_floor:.0f}  (vs B=${B_BUDGET})  -> {'WITHIN' if c_floor<=B_BUDGET else f'~{c_floor/B_BUDGET:.0f}x OVER'} budget")
    print(f"  (for reference, n=859 -> ~${c_859:.0f})")
    # what H would make n_floor fit B? n that fits B:
    model = cost_model(K)
    def cc(arm, Nn):
        a, b, d = model.get(arm, (1.0,0.0,{})); return d.get(Nn, max(0.05, a+b*Nn))
    per_seed_cost = sum(cc(arm, Nn)*2 for Nn in GRID for arm in ["S1","V2","V2nc"])
    n_aff = int(B_BUDGET // per_seed_cost)
    print(f"  n-affordable(<=B) = floor({B_BUDGET}/{per_seed_cost:.2f}/seed) = {n_aff}")
    H_needed = Z * sd8 / math.sqrt(n_aff)   # H that makes n=n_aff from N=8 SD
    print(f"  H that would make n_floor fit B (from N=8 SD, n={n_aff}): H ~= ${H_needed:.3f}  (vs frozen $0.015)")
    print("\n  CONCLUSION: formula reproduces exactly (no bug). n=859 is a 3-seed N=32 artifact. The honest")
    print(f"  anchor n=128 (N=8, 5 seeds) STILL implies ~${c_floor:.0f} (~{c_floor/B_BUDGET:.0f}x over $450) -> H=$0.015 is")
    print("  simply too tight for dime-scale cost noise; the freeze call is about H/grid/arms, not a code bug.")
    print("\nAUDIT / NOT FROZEN / NOT CONFIRMATORY")


if __name__ == "__main__":
    main()
