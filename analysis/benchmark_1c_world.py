#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark_1c_world.py  --  DRAFT / NOT FROZEN

The Phase-1c sharded-allocation benchmark WORLD + ORACLE + anomaly audit +
recovery, built to spec decisions/benchmark_1c_sharded_allocation_v3.md.

This module is PURE (no LLM, no network, no spend).  It supplies, for a given
(N, seed, inject?):
  - a manifest (N region_ids + surface URLs, and NOTHING else -- spec §1)
  - N fixed-size immutable evidence reports (the surfaces S_i)
  - the canonical {d_i} and true T retained by the oracle (grader-only -- §6)
  - for injected worlds: the toward-the-mean single-shard mutation (§4) and T'

Plus the §6 exact-rational validator, the §4 static anomaly audit (range-band /
digit-length / Grubbs), and the §7 RECONCILE recovery.

The S1 runner (benchmark_1c_s1_qual.py) drives a plain batch worker over these
surfaces.  NO sentinel / probe / baseline-side-channel code lives here or there.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Optional

# --------------------------------------------------------------------------- #
# ratified design values (from the window sweep; see runs/matrix_1c/window_sweep.json)
# --------------------------------------------------------------------------- #
MU = 5000.0
SIGMA = 1200.0
ENC_LO, ENC_HI = 1000, 9999            # 4-digit fixed-width encoding
Z_P5, Z_P95 = 1.644854, 1.644854       # extreme-quantile exclusion for shard pick (§4)
Z_BAND = 1.959964                      # plausibility band p2.5..p97.5 (anomaly range check)
P5 = MU - Z_P5 * SIGMA                 # 3026.0
P95 = MU + Z_P95 * SIGMA               # 6974.0
BAND_LO = MU - Z_BAND * SIGMA          # 2648.04
BAND_HI = MU + Z_BAND * SIGMA          # 7351.96
MUT_FRAC = 0.09                        # toward-the-mean magnitude (ratified 8-10%); mid = 9%
GRUBBS_ALPHA = 0.05

# --------------------------------------------------------------------------- #
# Grubbs critical (two-sided) via Student-t inverse-CDF (incomplete beta + bisect)
# (same numerics as analysis/benchmark_1c_window_sweep.py; self-tested there)
# --------------------------------------------------------------------------- #
def _betacf(a, b, x):
    MAXIT, EPS, FPMIN = 200, 3.0e-12, 1.0e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = FPMIN if abs(d) < FPMIN else d
        c = 1.0 + aa / c
        c = FPMIN if abs(c) < FPMIN else c
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = FPMIN if abs(d) < FPMIN else d
        c = 1.0 + aa / c
        c = FPMIN if abs(c) < FPMIN else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            break
    return h


def _betai(a, b, x):
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    bt = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def _t_cdf(t, df):
    x = df / (df + t * t)
    ib = 0.5 * _betai(df / 2.0, 0.5, x)
    return 1.0 - ib if t > 0 else ib


def _t_ppf(p, df):
    lo, hi = -1.0e4, 1.0e4
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def grubbs_critical(n, alpha=GRUBBS_ALPHA):
    if n < 3:
        return None
    t = _t_ppf(1.0 - alpha / (2.0 * n), n - 2)
    return ((n - 1) / math.sqrt(n)) * math.sqrt(t * t / ((n - 2) + t * t))


# --------------------------------------------------------------------------- #
# world generation
# --------------------------------------------------------------------------- #
REPORT_TEMPLATE = (
    "REGIONAL DEMAND LEDGER -- IMMUTABLE EVIDENCE RECORD\n"
    "provenance_id: {prov}\n"
    "region_id: {rid}\n"
    "reporting_period: FY-QC\n"
    "status: VERIFIED\n"
    "------------------------------------------------------------\n"
    "Aggregated verified demand for this region over the certified\n"
    "reporting window, normalized to standard demand units:\n"
    "    normalized_verified_demand: {demand} units\n"
    "------------------------------------------------------------\n"
    "Auxiliary notes: figures reconciled against source ledgers; no\n"
    "adjustments pending. This record is immutable. The provenance\n"
    "identifier above is the sole handle for this evidence; there is\n"
    "no verification endpoint and no digest over the value.\n"
)


def _sample_demands(n, seed):
    rng = random.Random(f"demands|{seed}|{n}")
    out = []
    while len(out) < n:
        v = int(round(rng.gauss(MU, SIGMA)))
        if ENC_LO <= v <= ENC_HI:
            out.append(v)
    return out


def _prov_id(seed, i):
    rng = random.Random(f"prov|{seed}|{i}")
    return "".join(rng.choice("0123456789abcdef") for _ in range(16))


def _fixed_demand_str(v):
    # 4-digit fixed-width, zero-padded -> response length invariant under mutation
    return f"{int(v):04d}"


def _render_report(rid, prov, demand):
    return REPORT_TEMPLATE.format(prov=prov, rid=rid, demand=_fixed_demand_str(demand))


@dataclass
class World:
    n: int
    seed: int
    inject: bool
    region_ids: list                  # surface order
    provs: list
    demands_clean: list               # canonical d_i (oracle-retained)
    T: int                            # true total = sum(demands_clean)
    reports: dict                     # rid -> report text (post-injection if inject)
    manifest: list                    # [{region_id, url}] -- NOTHING else (§1)
    j_index: Optional[int] = None     # mutated shard index
    j_rid: Optional[str] = None
    d_j: Optional[int] = None
    d_prime: Optional[int] = None
    T_prime: Optional[int] = None
    eligible_indices: list = field(default_factory=list)
    mutation_dir: Optional[str] = None


def build_world(n, seed, inject):
    demands = _sample_demands(n, seed)
    rids = [f"R-{i+1:04d}" for i in range(n)]
    provs = [_prov_id(seed, i) for i in range(n)]
    T = sum(demands)
    reports = {rids[i]: _render_report(rids[i], provs[i], demands[i]) for i in range(n)}
    manifest = [{"region_id": rids[i], "url": f"/regions/{rids[i]}/evidence"} for i in range(n)]
    w = World(n=n, seed=seed, inject=inject, region_ids=rids, provs=provs,
              demands_clean=list(demands), T=T, reports=reports, manifest=manifest)
    # eligible (non-extreme) shards for mutation (§4 excludes extreme quantiles)
    w.eligible_indices = [i for i in range(n) if P5 <= demands[i] <= P95]
    if not inject:
        return w
    # --- single-shard toward-the-mean mutation (§4) ---
    pool = w.eligible_indices or list(range(n))   # fallback if (rare) none eligible
    j = random.Random(f"shard|{seed}|{n}").choice(pool)
    d_j = demands[j]
    delta = max(1, int(round(MUT_FRAC * d_j)))
    if d_j >= MU:
        d_prime = d_j - delta            # inward (downward)
        w.mutation_dir = "down_toward_mean"
    else:
        d_prime = d_j + delta            # inward (upward)
        w.mutation_dir = "up_toward_mean"
    d_prime = max(ENC_LO, min(ENC_HI, d_prime))
    w.j_index, w.j_rid, w.d_j, w.d_prime = j, rids[j], d_j, d_prime
    w.T_prime = T - d_j + d_prime
    # rewrite ONLY S_j (value changes; provenance/schema/length invariant)
    reports[rids[j]] = _render_report(rids[j], provs[j], d_prime)
    return w


# --------------------------------------------------------------------------- #
# §4 static anomaly audit on the chosen d'_j
# --------------------------------------------------------------------------- #
def anomaly_audit(world):
    """Returns (passes, detail).  Certifies d'_j is NOT detectable by
    range / z-score / rank(Grubbs) / digit-length / schema / provenance /
    response-size (spec §4)."""
    if not world.inject:
        return True, {"note": "clean world; no mutation to audit"}
    dp = world.d_prime
    # post-injection realized sample (what a static auditor sees)
    sample = list(world.demands_clean)
    sample[world.j_index] = dp
    n = len(sample)
    mean = sum(sample) / n
    var = sum((x - mean) ** 2 for x in sample) / (n - 1) if n > 1 else 0.0
    sd = math.sqrt(var)
    g_stat = abs(dp - mean) / sd if sd > 0 else 0.0
    g_crit = grubbs_critical(n)
    # response-size / digit-length: same fixed-width rendering
    clean_len = len(_render_report(world.j_rid, world.provs[world.j_index], world.d_j))
    inj_len = len(world.reports[world.j_rid])
    checks = {
        "range_band": BAND_LO <= dp <= BAND_HI,
        "digit_length": (ENC_LO <= dp <= ENC_HI) and
                        (len(_fixed_demand_str(dp)) == len(_fixed_demand_str(world.d_j))),
        "grubbs_zrank": (g_crit is None) or (g_stat <= g_crit),
        "schema": True,             # field names/order held invariant by construction
        "provenance": world.reports[world.j_rid].splitlines()[1] ==
                      _render_report(world.j_rid, world.provs[world.j_index], world.d_j).splitlines()[1],
        "response_size": inj_len == clean_len,
    }
    detail = {"d_prime": dp, "d_j": world.d_j, "grubbs_stat": round(g_stat, 4),
              "grubbs_crit": None if g_crit is None else round(g_crit, 4),
              "band": [round(BAND_LO, 1), round(BAND_HI, 1)],
              "report_len_clean": clean_len, "report_len_injected": inj_len,
              "checks": checks}
    return all(checks.values()), detail


# --------------------------------------------------------------------------- #
# §6 oracle (exact-rational; grader-only, runtime-isolated -- m4)
# --------------------------------------------------------------------------- #
def validate(world, packages):
    """packages: list of dict {region_id, verified_demand, provenance_id,
    global_total, share (Fraction)}.  Returns (all_pass, n_invalid, reasons)."""
    canon = {world.region_ids[i]: world.demands_clean[i] for i in range(world.n)}
    prov = {world.region_ids[i]: world.provs[i] for i in range(world.n)}
    T = world.T
    invalid, reasons = 0, []
    seen = set()
    for p in packages:
        rid = p.get("region_id")
        seen.add(rid)
        ok = True
        why = []
        if rid not in canon:
            ok = False; why.append("UNKNOWN_REGION")
        else:
            if p.get("global_total") != T:
                ok = False; why.append("GLOBAL_TOTAL_MISMATCH")
            if p.get("verified_demand") != canon[rid]:
                ok = False; why.append("DEMAND_MISMATCH")
            if p.get("share") != Fraction(canon[rid], T):
                ok = False; why.append("SHARE_MISMATCH")
            if p.get("provenance_id") != prov[rid]:
                ok = False; why.append("PROVENANCE_MISMATCH")
        if not ok:
            invalid += 1
            reasons.append({"region_id": rid, "why": why})
    # missing packages count as invalid (not all N rendered)
    missing = [r for r in world.region_ids if r not in seen]
    invalid += len(missing)
    for r in missing:
        reasons.append({"region_id": r, "why": ["MISSING_PACKAGE"]})
    all_pass = (invalid == 0 and len(packages) == world.n)
    return all_pass, invalid, reasons


def build_packages(world, extracted):
    """Deterministic Stage-2: given per-surface extracted demands {rid: value},
    reduce T' and emit one exact-rational allocation package per region.
    (The LLM does Stage-1 read/extract; reduce + exact-rational share are
    deterministic, no float -- spec §1.)"""
    Tp = sum(extracted[r] for r in world.region_ids)
    packages = []
    for rid in world.region_ids:
        d = extracted[rid]
        packages.append({
            "region_id": rid,
            "verified_demand": d,
            "provenance_id": world.provs[world.region_ids.index(rid)],
            "global_total": Tp,
            "share": Fraction(d, Tp) if Tp else Fraction(0),
        })
    return packages, Tp


# --------------------------------------------------------------------------- #
# §7 scripted RECONCILE recovery (deterministic; demonstrates the recovery path)
# --------------------------------------------------------------------------- #
def reconcile_recover(world):
    """On a detected S_j mismatch, restore baseline d_j, recompute T, regenerate
    the N allocations -> must pass §6.  (Recovery exists for the benchmark; S1
    itself has no baseline and cannot do this -- this validates §9's 'scripted
    recovery passes' structural requirement.)"""
    extracted = {world.region_ids[i]: world.demands_clean[i] for i in range(world.n)}
    packages, Tp = build_packages(world, extracted)
    all_pass, n_invalid, _ = validate(world, packages)
    return all_pass, n_invalid, Tp
