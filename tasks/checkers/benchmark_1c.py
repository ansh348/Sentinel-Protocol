"""Checker for benchmark_1c (demand-normalized regional allocation).

The deterministic reducer (T = Σ normalized_verified_demand; share = demand/T as an
EXACT RATIONAL, no float) + the §6 exact-rational validator. Single source of truth =
analysis.benchmark_1c_world (the same oracle the S1 qualification used). World/checker-
side only; no treatment code.

  check(final_report, ground_truth) -> (bool, str)   # conductor success interface
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any

from analysis.benchmark_1c_world import (build_world, build_packages, validate,
                                         reconcile_recover)


# ---- deterministic reduce + exact-rational packaging (Stage-2; no LLM) ----------
def reduce_and_package(n: int, seed: int, extracted: dict[str, int]):
    """Reduce the per-region extracted demands to T' and emit one exact-rational
    allocation package per region. Reuses build_packages (exact Fraction shares)."""
    world = build_world(n, seed, inject=False)
    packages, t_prime = build_packages(world, {r: int(extracted[r]) for r in world.region_ids})
    return packages, t_prime


# ---- §6 exact-rational validation against the canonical (clean) world ----------
def validate_against_canonical(n: int, seed: int, packages: list):
    """all_pass, n_invalid, reasons — validates the package set against the canonical
    clean demands and true T (oracle retains d_i; exact rational)."""
    world = build_world(n, seed, inject=False)
    return validate(world, packages)


def reconcile(n: int, seed: int):
    """§7 scripted RECONCILE recovery: restore baseline, recompute T, regenerate -> §6 pass."""
    inj = build_world(n, seed, inject=True)
    return reconcile_recover(inj)


# ---- conductor success interface ----------------------------------------------
def _parse_share(s: Any) -> Fraction:
    if isinstance(s, Fraction):
        return s
    if isinstance(s, (list, tuple)) and len(s) == 2:
        return Fraction(int(s[0]), int(s[1]))
    if isinstance(s, str) and "/" in s:
        num, den = s.split("/", 1)
        return Fraction(int(num), int(den))
    return Fraction(s)  # last resort; exact only for ints/Fractions


def check(final_report: Any, ground_truth: dict) -> tuple[bool, str]:
    """final_report: the COLLECTED per-region records the orchestrator aggregated —
    a list (or {"packages": [...]}) of {region_id, verified_demand (==the worker's
    normalized_verified_demand), provenance_id}. ground_truth: {n, seed}.

    The reduce is DETERMINISTIC and done HERE (spec §1: 'reduce + exact-rational share
    are deterministic, no float' — the LLM only reads/extracts): sum the collected
    demands to T', build exact-rational packages, and §6-validate them against the
    canonical CLEAN world. Clean demands -> T'=T -> every package valid. A single
    silently-mutated shard -> T'!=T -> the shared denominator wounds EVERY package
    (GLOBAL_TOTAL_MISMATCH/SHARE_MISMATCH on all N)."""
    n, seed = int(ground_truth["n"]), int(ground_truth["seed"])
    pkgs_in = final_report.get("packages", final_report) if isinstance(final_report, dict) else final_report
    if not isinstance(pkgs_in, list):
        return False, "final_report has no package list"
    extracted: dict[str, int] = {}
    for p in pkgs_in:
        if not isinstance(p, dict):
            continue
        rid = p.get("region_id")
        dem = p.get("verified_demand", p.get("normalized_verified_demand"))
        if rid is None or dem is None:
            continue
        try:
            extracted[str(rid)] = int(dem)
        except (TypeError, ValueError):
            continue
    world = build_world(n, seed, inject=False)
    missing = [r for r in world.region_ids if r not in extracted]
    if missing:
        return False, f"incomplete collection: {len(missing)}/{n} region demand(s) missing {missing[:3]}"
    extra = [r for r in extracted if r not in set(world.region_ids)]
    if extra:
        return False, f"unknown region(s) in collection: {extra[:3]}"
    packages, t_prime = reduce_and_package(n, seed, extracted)   # deterministic reduce
    all_pass, n_invalid, reasons = validate(world, packages)     # §6 vs canonical clean
    if all_pass:
        return True, f"all {n} allocation packages valid (exact §6); T={world.T}"
    return False, (f"{n_invalid}/{n} invalid (T'={t_prime} vs canonical T={world.T}): "
                   f"{reasons[:2]}")
