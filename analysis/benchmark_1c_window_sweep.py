#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark_1c_window_sweep.py  --  DRAFT / NOT FROZEN

Pure-arithmetic wound x anomaly window sweep for the Phase-1c sharded-allocation
benchmark (decisions/benchmark_1c_sharded_allocation_v3.md).

NO treatment system, NO workers, NO sentinel, NO LLM calls, NO billed runs.
This is *calculation only*: the world demand distribution + the exact-rational
oracle (spec §6) + the static anomaly audit (spec §4).  It maps, for each
(N, single-shard corruption size), whether the corruption WOUNDS (fails the §6
validator) and whether it is ANOMALOUS (trips the §4 static audit), and reads off
the usable window per N.

It implements EXACTLY the spec's rules:
  - §6 validator: a package set passes iff global_total == T (exact rational).
    => WOUND <=> T' != T <=> d'_j != d_j <=> |Delta| >= 1 unit (integer demands).
  - §4 single-shard mutation: corrupt EXACTLY ONE shard d_j -> d'_j, drawn from
    the same demand distribution, fixed-width encoding, non-outlying, with a
    static anomaly audit over: range, z-score, rank, digit-length, schema,
    provenance, response-size.  schema/provenance/response-size are held INVARIANT
    by §4 construction (never trip; size-independent) -> the size-dependent checks
    are: digit-length (fixed-width cap), range (plausibility band), z/rank
    (outlier test, unified as Grubbs' single-outlier test on the realized N-sample).

Author knobs left as [AUTHOR-CONFIRM] in the spec are filled here with stated,
defensible DRAFT proposals (reported in STEP B) for the author to ratify/override.

stdlib only (numpy is not installed): math + json.
"""

import json
import math
import os

# --------------------------------------------------------------------------- #
# numerics: Student-t inverse-CDF (for Grubbs critical) via regularized
# incomplete beta + bisection.  No scipy/numpy.
# --------------------------------------------------------------------------- #

def _betacf(a, b, x):
    # Lentz's continued fraction for the incomplete beta (Numerical Recipes).
    MAXIT, EPS, FPMIN = 200, 3.0e-12, 1.0e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            break
    return h


def _betai(a, b, x):
    # regularized incomplete beta I_x(a, b)
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    bt = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_cdf(t, df):
    # Student-t CDF
    x = df / (df + t * t)
    ib = 0.5 * _betai(df / 2.0, 0.5, x)
    return 1.0 - ib if t > 0 else ib


def t_ppf(p, df):
    # inverse Student-t CDF by bisection
    lo, hi = -1.0e4, 1.0e4
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def grubbs_critical(n, alpha=0.05):
    # two-sided Grubbs critical value G_crit(N, alpha) for the single most-extreme
    # value in a sample of size N.  G_crit = ((N-1)/sqrt(N)) * sqrt(t^2/(N-2+t^2)),
    # t = upper-(alpha/(2N)) Student-t critical with N-2 dof.
    if n < 3:
        return None
    p = 1.0 - alpha / (2.0 * n)
    t = t_ppf(p, n - 2)
    return ((n - 1) / math.sqrt(n)) * math.sqrt(t * t / ((n - 2) + t * t))


# normal quantile multipliers (z) for the plausibility band -- standard constants
Z = {"p1": 2.326348, "p2.5": 1.959964, "p5": 1.644854,
     "p95": 1.644854, "p97.5": 1.959964, "p99": 2.326348, "p0.5": 2.575829, "p99.5": 2.575829}

# --------------------------------------------------------------------------- #
# STEP B -- proposed demand distribution (DRAFT; author ratifies/overrides)
# --------------------------------------------------------------------------- #
MU = 5000.0           # mean regional demand (units, e.g. weekly orders/region)
SIGMA = 1200.0        # std  (CV = 0.24 -- moderate regional heterogeneity)
ENC_LO, ENC_HI = 1000, 9999   # 4-digit fixed-width encoding (pad to 4 chars)
D_J = 5000            # canonical mid-rank swept shard value (= MU); non-extreme
# range/plausibility band for d'_j ("from same distribution, non-outlying"):
# primary = central 95% [p2.5, p97.5]; reported also for [p5,p95] and [p1,p99].
RANGE_BANDS = {
    "p5_p95":   (MU - Z["p5"] * SIGMA,   MU + Z["p95"] * SIGMA),
    "p2.5_p97.5": (MU - Z["p2.5"] * SIGMA, MU + Z["p97.5"] * SIGMA),
    "p1_p99":   (MU - Z["p1"] * SIGMA,   MU + Z["p99"] * SIGMA),
}
PRIMARY_BAND = "p2.5_p97.5"
GRUBBS_ALPHA = 0.05

# corruption ladders
ABS_LADDER = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096]
PCT_LADDER = [1, 2, 4, 8, 16, 32, 64]      # % of d_j
N_GRID = [2, 4, 8, 16, 32, 64]


# --------------------------------------------------------------------------- #
# anomaly ceilings (largest non-anomalous |Delta|), per check, per N
# --------------------------------------------------------------------------- #
def digit_len(v):
    return len(str(int(round(v))))


def digit_ceiling(d_j, direction):
    # fixed-width: d'_j must keep the SAME digit length as d_j AND stay in encoding.
    L = digit_len(d_j)
    band_lo = max(ENC_LO, 10 ** (L - 1))
    band_hi = min(ENC_HI, 10 ** L - 1)
    return (band_hi - d_j) if direction > 0 else (d_j - band_lo)


def range_ceiling(d_j, direction, band):
    lo, hi = RANGE_BANDS[band]
    return (hi - d_j) if direction > 0 else (d_j - lo)


def grubbs_ceiling(direction, n, sigma=SIGMA, alpha=GRUBBS_ALPHA):
    # Largest |Delta| keeping the mutated shard's Grubbs statistic <= G_crit(N).
    # Studentized deviation of the single outlier in a sample of N where N-1 are
    # clean (std sigma) and one is shifted by Delta:
    #   G(Delta) = (Delta*(N-1)/N) / sqrt(sigma^2 + Delta^2/N)
    # which -> (N-1)/sqrt(N) as Delta->inf (the max attainable studentized dev).
    # Solve G(Delta)=G_crit:
    #   Delta = G_crit*sigma / sqrt((N-1)^2/N^2 - G_crit^2/N)   (real iff
    #   (N-1)/sqrt(N) > G_crit, i.e. an outlier is *detectable at all* at this N).
    g = grubbs_critical(n, alpha)
    if g is None:
        return math.inf, None, False   # N<3: undefined
    max_stud = (n - 1) / math.sqrt(n)
    denom_sq = (n - 1) ** 2 / n ** 2 - g * g / n
    if denom_sq <= 0:
        # G_crit unreachable -> no Delta makes the shard a Grubbs outlier
        return math.inf, g, False
    return g * sigma / math.sqrt(denom_sq), g, True


# --------------------------------------------------------------------------- #
# §6 validator (exact rational) -- WOUND boolean + diagnostics
# --------------------------------------------------------------------------- #
def wound(n, d_j, dprime):
    # T = N*MU canonical clean sum (exact: integer demands); T' = T - d_j + d'_j.
    # exact-rational check: global_total == T  <=>  T' == T  <=> d'_j == d_j.
    delta = dprime - d_j
    T = int(round(MU)) * n           # canonical clean total at this width
    Tp = T - d_j + dprime
    wounded = (Tp != T)              # exact: any nonzero delta wounds
    rel = abs(Tp - T) / T if T else 0.0
    return wounded, abs(Tp - T), rel


# --------------------------------------------------------------------------- #
# anomaly evaluation for a given mutated value
# --------------------------------------------------------------------------- #
def anomaly(n, d_j, dprime, band=PRIMARY_BAND, model="combined"):
    """Return (is_anomalous, which_check_trips, margin_to_nearest_ceiling).
    model='combined' : range-band AND digit AND grubbs all apply (realistic audit)
    model='datadriven': drop the frozen band -> digit cap + Grubbs only (shows the
                        N-dependent narrowing in isolation).
    """
    direction = 1 if dprime >= d_j else -1
    delta = abs(dprime - d_j)
    ceils = {}
    ceils["digit_length"] = digit_ceiling(d_j, direction)
    g_ceil, gval, g_active = grubbs_ceiling(direction, n)
    ceils["grubbs_zrank"] = g_ceil
    if model == "combined":
        ceils["range_band"] = range_ceiling(d_j, direction, band)
    # checks that never trip by §4 construction (held invariant) -> infinite ceiling
    # schema / provenance / response_size : not size-dependent.
    binding_check = min(ceils, key=lambda k: ceils[k])
    binding_ceiling = ceils[binding_check]
    is_anom = delta > binding_ceiling + 1e-9
    # which check actually trips (smallest ceiling that delta exceeds)
    tripped = [k for k, c in ceils.items() if delta > c + 1e-9]
    which = min(tripped, key=lambda k: ceils[k]) if tripped else None
    return is_anom, which, binding_ceiling, ceils, gval, g_active


# --------------------------------------------------------------------------- #
# build the map
# --------------------------------------------------------------------------- #
def window_for_N(n, band=PRIMARY_BAND, model="combined"):
    """Smallest wounding |Delta| (floor) and largest non-anomalous |Delta|
    (ceiling), per direction, plus combined symmetric usable window."""
    out = {"N": n}
    for direction, name in ((+1, "up"), (-1, "down")):
        # floor: smallest wounding step = 1 unit (exact rational); report robust min = 1
        floor = 1
        # ceiling: largest non-anomalous delta
        # evaluate the binding ceiling at this direction
        dprime_probe = d_j_for(n) + direction * 1  # tiny step to get ceilings/dir
        _, _, binding_ceiling, ceils, gval, g_active = anomaly(
            n, d_j_for(n), dprime_probe, band=band, model=model)
        out[name] = {
            "wound_floor_units": floor,
            "anomaly_ceiling_units": None if math.isinf(binding_ceiling) else round(binding_ceiling, 2),
            "binding_check": min(ceils, key=lambda k: ceils[k]),
            "ceilings_units": {k: (None if math.isinf(v) else round(v, 1)) for k, v in ceils.items()},
            "grubbs_Gcrit": (None if gval is None else round(gval, 4)),
            "grubbs_detectable_at_this_N": g_active,
            "max_studentized_bound": round((n - 1) / math.sqrt(n), 4),
            "window_exists": (binding_ceiling >= floor),
            "window_width_units": None if math.isinf(binding_ceiling) else round(binding_ceiling - floor, 2),
            "ceiling_pct_of_dj": None if math.isinf(binding_ceiling) else round(100.0 * binding_ceiling / d_j_for(n), 2),
        }
    return out


def d_j_for(n):
    return D_J


def sweep_cell(n, delta_units, band=PRIMARY_BAND, model="combined"):
    d_j = d_j_for(n)
    dprime = d_j + delta_units
    w, absdiff, rel = wound(n, d_j, dprime)
    a, which, binding_ceiling, ceils, gval, g_active = anomaly(n, d_j, dprime, band=band, model=model)
    usable = w and (not a)
    return {
        "N": n,
        "delta_units": delta_units,
        "delta_pct_of_dj": round(100.0 * delta_units / d_j, 3),
        "d_prime": dprime,
        "in_encoding": ENC_LO <= dprime <= ENC_HI,
        "wound": bool(w),
        "abs_T_diff": absdiff,
        "rel_T_diff": round(rel, 6),
        "anomaly": bool(a),
        "anomaly_check": which,
        "usable": bool(usable),
    }


def main():
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # ---- numeric self-tests (trust the t/Grubbs machinery) ----
    selftest = {
        "t_ppf(0.975,df=10)": round(t_ppf(0.975, 10), 4),   # expect ~2.2281
        "t_ppf(0.995,df=5)": round(t_ppf(0.995, 5), 4),     # expect ~4.0321
        "grubbs_G(N=3)": round(grubbs_critical(3), 4),       # expect ~1.1543
        "grubbs_G(N=10)": round(grubbs_critical(10), 4),     # expect ~2.290 (two-sided 5%)
        "grubbs_G(N=20)": round(grubbs_critical(20), 4),     # expect ~2.709
    }

    report = {
        "DRAFT": True, "FROZEN": False, "spent_usd": 0.0, "llm_calls": 0,
        "spec": "decisions/benchmark_1c_sharded_allocation_v3.md",
        "implements": {"validator": "spec §6 (exact rational)",
                       "mutation_and_audit": "spec §4 (single-shard; range/z/rank/digit-length/schema/provenance/response-size)"},
        "selftest": selftest,
        "distribution": {
            "shape": "truncated normal (regional demand ledgers)",
            "mu": MU, "sigma": SIGMA, "cv": round(SIGMA / MU, 3),
            "encoding": f"4-digit fixed-width [{ENC_LO},{ENC_HI}] (pad to 4 chars)",
            "shard_pick_excludes": "extreme quantiles [p5,p95] (spec §4)",
            "canonical_swept_shard_d_j": D_J,
            "range_bands_units": {k: [round(v[0], 1), round(v[1], 1)] for k, v in RANGE_BANDS.items()},
            "primary_band": PRIMARY_BAND,
            "grubbs_alpha": GRUBBS_ALPHA,
        },
    }

    # ---- STEP C: full (N x corruption) map, combined audit (primary) ----
    full_map = []
    for n in N_GRID:
        for du in ABS_LADDER:
            for sgn in (+1, -1):
                full_map.append(sweep_cell(n, sgn * du))
        for pct in PCT_LADDER:
            du = int(round(pct / 100.0 * D_J))
            for sgn in (+1, -1):
                c = sweep_cell(n, sgn * du)
                c["from_pct_ladder"] = pct * sgn
                full_map.append(c)
    report["full_map_combined_audit"] = full_map

    # ---- STEP D: per-N window summary, combined audit + data-driven audit ----
    report["window_summary_combined"] = [window_for_N(n, model="combined") for n in N_GRID]
    report["window_summary_datadriven"] = [window_for_N(n, model="datadriven") for n in N_GRID]
    report["window_summary_bands_sensitivity"] = {
        b: [window_for_N(n, band=b, model="combined") for n in N_GRID] for b in RANGE_BANDS
    }

    # ---- STEP E: granular zoom -- fine N grid + Grubbs ceiling curve ----
    fine_N = [8, 10, 12, 14, 16, 20, 24, 28, 32, 40, 48, 56, 64, 96, 128]
    zoom = []
    for n in fine_N:
        gc_up, gval, gact = grubbs_ceiling(+1, n)
        # combined ceiling (up direction) = min(range, digit, grubbs)
        comb_up = min(range_ceiling(D_J, +1, PRIMARY_BAND), digit_ceiling(D_J, +1),
                      gc_up if not math.isinf(gc_up) else 1e18)
        dd_up = min(digit_ceiling(D_J, +1), gc_up if not math.isinf(gc_up) else 1e18)
        zoom.append({
            "N": n,
            "Gcrit": None if gval is None else round(gval, 4),
            "max_studentized_bound": round((n - 1) / math.sqrt(n), 4),
            "grubbs_active": gact,
            "grubbs_ceiling_up_units": None if math.isinf(gc_up) else round(gc_up, 1),
            "combined_ceiling_up_units": round(comb_up, 1),
            "datadriven_ceiling_up_units": round(dd_up, 1),
            "wound_floor_units": 1,
            "combined_window_open": comb_up >= 1,
            "datadriven_window_open": dd_up >= 1,
        })
    report["zoom"] = zoom

    # also: relative-wound shrink (|T'-T|/T) at a fixed mid corruption, across N
    rel_trend = []
    for n in N_GRID:
        T = int(round(MU)) * n
        for pct in (4, 16, 32):
            du = int(round(pct / 100.0 * D_J))
            rel_trend.append({"N": n, "delta_units": du, "delta_pct_dj": pct,
                              "abs_T_diff": du, "rel_T_diff": round(du / T, 6),
                              "wounds": True})
    report["relative_wound_trend"] = rel_trend

    os.makedirs("runs/matrix_1c", exist_ok=True)
    out_path = "runs/matrix_1c/window_sweep.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # ----------------------------- printed deliverable ----------------------- #
    P = print
    P("=" * 92)
    P("BENCHMARK-1c  WOUND x ANOMALY  WINDOW SWEEP   --  DRAFT / NOT FROZEN  --  $0 spent, 0 LLM calls")
    P("=" * 92)
    P("\n[self-test of t/Grubbs numerics]  " +
      "  ".join(f"{k}={v}" for k, v in selftest.items()))
    P("  expected ~  t_ppf(.975,10)=2.2281  t_ppf(.995,5)=4.0321  G(3)=1.1543  G(10)=2.290  G(20)=2.709")

    P("\n(B) PROPOSED DEMAND DISTRIBUTION  [DRAFT -- author ratifies]")
    P(f"    truncated normal,  mu={MU:.0f}  sigma={SIGMA:.0f}  (CV={SIGMA/MU:.2f})  "
      f"4-digit fixed-width [{ENC_LO},{ENC_HI}], pad to 4 chars")
    P(f"    canonical swept shard d_j = {D_J} (= mu, mid-rank; shard pick excludes [p5,p95] per §4)")
    P(f"    primary plausibility band ({PRIMARY_BAND}) = "
      f"[{RANGE_BANDS[PRIMARY_BAND][0]:.0f}, {RANGE_BANDS[PRIMARY_BAND][1]:.0f}]  "
      f"(half-width {RANGE_BANDS[PRIMARY_BAND][1]-MU:.0f} = {1.96:.2f}sigma)")

    P("\n(C) FULL (N x corruption) MAP  --  combined audit (range-band & digit & Grubbs)")
    P("    WOUND = fails §6 exact-rational validator (T' != T).  ANOM = trips §4 static audit.")
    P("    Absolute-units ladder (d_j=5000); '+' shown (down-direction symmetric unless noted).")
    hdr = "    N |" + "".join(f"{du:>6}" for du in ABS_LADDER)
    P(hdr); P("    " + "-" * (len(hdr) - 4))
    for n in N_GRID:
        row = f"  {n:>3} |"
        for du in ABS_LADDER:
            c = sweep_cell(n, +du)
            mark = "U" if c["usable"] else ("A" if c["anomaly"] else ".")
            row += f"{mark:>6}"
        P(row)
    P("    legend: U=wound&usable(non-anom)   A=wound but ANOMALOUS   .=no wound")
    P("    (every |delta|>=1 wounds, so there is no '.' except delta=0; columns are all wounds)")

    P("\n    same map in %-of-d_j ladder (up-direction):")
    hdr2 = "    N |" + "".join(f"{p:>5}%" for p in PCT_LADDER)
    P(hdr2); P("    " + "-" * (len(hdr2) - 4))
    for n in N_GRID:
        row = f"  {n:>3} |"
        for pct in PCT_LADDER:
            du = int(round(pct / 100.0 * D_J))
            c = sweep_cell(n, +du)
            mark = "U" if c["usable"] else ("A" if c["anomaly"] else ".")
            row += f"{mark:>6}"
        P(row)

    P("\n(D) PER-N WINDOW SUMMARY  (up-direction; floor=smallest wounding step=1 unit)")
    P("    --- combined audit (range-band & digit & Grubbs) : the REALISTIC audit ---")
    P("    N   | wound_floor | anomaly_ceiling | binding_check  | ceil(%d_j) | window?")
    for w in report["window_summary_combined"]:
        u = w["up"]
        P(f"   {w['N']:>3}  |  {u['wound_floor_units']:>9}  | "
          f"{str(u['anomaly_ceiling_units']):>14}  | {u['binding_check']:>13}  | "
          f"{str(u['ceiling_pct_of_dj']):>8}%  | {'YES' if u['window_exists'] else 'NO'}")
    P("    --- data-driven audit (digit cap + Grubbs only, NO frozen band) : isolates N-effect ---")
    P("    N   | anomaly_ceiling | binding_check | Gcrit  | max-stud bound | Grubbs active?")
    for w in report["window_summary_datadriven"]:
        u = w["up"]
        P(f"   {w['N']:>3}  | {str(u['anomaly_ceiling_units']):>14}  | {u['binding_check']:>12} | "
          f"{str(u['grubbs_Gcrit']):>6} | {u['max_studentized_bound']:>13}  | "
          f"{u['grubbs_detectable_at_this_N']}")

    P("\n(E) GRANULAR ZOOM  --  Grubbs ceiling vs N (up-direction), fine N grid")
    P("    N   | Gcrit  | max-stud | Grubbs active | grubbs_ceil | combined_ceil | datadriven_ceil | floor | open?")
    for z in report["zoom"]:
        P(f"   {z['N']:>3}  | {str(z['Gcrit']):>6} | {z['max_studentized_bound']:>7}  | "
          f"{str(z['grubbs_active']):>5}         | {str(z['grubbs_ceiling_up_units']):>10}  | "
          f"{z['combined_ceiling_up_units']:>11}  | {z['datadriven_ceiling_up_units']:>13}  | "
          f"{z['wound_floor_units']:>4}  | {'yes' if z['combined_window_open'] else 'NO'}")

    P("\n    relative wound |T'-T|/T at fixed corruption sizes, across N (validator is EXACT,")
    P("    so all still WOUND -- this shows the single-shard wound becomes a tiny fraction of T):")
    P("    N   |  +4% of d_j      |  +16% of d_j     |  +32% of d_j")
    by_n = {}
    for r in report["relative_wound_trend"]:
        by_n.setdefault(r["N"], {})[r["delta_pct_dj"]] = r["rel_T_diff"]
    for n in N_GRID:
        d = by_n[n]
        P(f"   {n:>3}  |  {d[4]*100:>7.3f}% of T  |  {d[16]*100:>7.3f}% of T  |  {d[32]*100:>7.3f}% of T")

    P(f"\n[written] {out_path}")
    P("DRAFT / NOT FROZEN -- no hash pin, no deviation number, no spend, no agents.")


if __name__ == "__main__":
    main()
