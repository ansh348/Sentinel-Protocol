"""Escrow draw for the Phase 1b held-out categories (memo Section 5(b);
benchmark/holdouts/*.md Section 6).

Draws the 1b value SUPERSET — 4 tasks x 5 seeds x both categories (40 cells)
— and writes it to escrow/holdout_escrow.json (gitignored: the repo is
public). Cell values are drawn with the `secrets` module (cryptographic,
non-reproducible: there is no seed from which the author could re-derive
them). NOTHING from the drawn set is ever printed; the only console output
is the file's SHA-256, its shape, and the draw rules applied.

Custody (decisions/holdout_escrow_record.md): the file is transmitted to the
non-implementer escrow holder; the 1b harness consumes it programmatically at
launch; the author does not open it.

Draw rules (verbatim from the specs; DV per spec rev 2, author ruling
2026-06-12):
- run seed: unique per cell, uniform 1000-9999 (distinct namespace from
  Phase 1 matrix seeds {1,2,3} and qualification seeds {901..906})
- RESOURCE_BUDGET (quota_cliff): N uniform in [40%, 60%] of the task's clean
  median (a1 24, c1 12, d1 21 — Phase 1 finals; b1 from the rev-3
  re-qualification clean median), floored bounds; Q0 uniform [8, 14]
- DEPENDENCY_VERSION (silent_minor_bump): N = 1 fixed (author ruling #2,
  2026-06-12: the category models deploy-time skew — the plan's v1.x
  assumption is documentary, formed from the task description and surface
  appendix regardless of N, and mid-run firing is structurally
  unsatisfiable on single-enumeration hosts, as the spec-rev-2
  re-qualification proved; the prior mid-run requirement is withdrawn by
  the author as a category-inappropriate import); post version from
  {2.0.0, 2.0.1}; post page size uniform [3, 6] for b1 (8-file repo),
  [3, 5] for a1/c1/d1 (6-item collections) — the author-ratified
  constraint that every drawn post size sits STRICTLY BELOW the host
  collection size is asserted here in code, not only in the spec; pre
  page size fixed 100, pre version fixed 1.4.0, parameter rename
  page_size -> page_limit fixed (ruling #2 R3)
- service family: FIXED per task by the specs, recorded per cell
"""
from __future__ import annotations

import hashlib
import json
import secrets
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "escrow" / "holdout_escrow.json"
QUAL_SUMMARY = (REPO_ROOT / "runs" / "holdout_requalification_dv2"
                / "summary.json")

TASKS = ("a1", "b1", "c1", "d1")
SEEDS_PER_CELL = 5

FAMILY = {
    "a1": ["/inventory", "/pricing", "/shipping"],
    "b1": ["/repo"],
    "c1": ["/docs"],
    "d1": ["/docs", "/inventory"],
}
PHASE1_CLEAN_MEDIANS = {"a1": 24, "c1": 12, "d1": 21}
# Host collection size on the task's wound surface (a1/d1: inventory items;
# b1: repo files at rev >= 2; c1: passages).
HOST_COLLECTION_SIZE = {"a1": 6, "b1": 8, "c1": 6, "d1": 6}
DV_POST_PAGE_RANGE = {"a1": (3, 5), "b1": (3, 6), "c1": (3, 5), "d1": (3, 5)}
DV_POST_VERSIONS = ("2.0.0", "2.0.1")
# Ruling #2 R2: deploy-time skew fires at N=1, uniformly — the v1.x
# assumption is documentary, and mid-run firing is structurally
# unsatisfiable on single-enumeration hosts (proven by the spec-rev-2
# re-qualification: enumeration was the run's first call in 3/3 seeds).
DV_N_CHOICES = (1,)
RB_Q0_RANGE = (8, 14)

# Author-ratified constraint (ruling 2026-06-12, item 5): drawn post sizes
# must sit strictly below the host collection size.
for _task, (_lo, _hi) in DV_POST_PAGE_RANGE.items():
    assert _hi < HOST_COLLECTION_SIZE[_task], (
        f"{_task}: post-size range {(_lo, _hi)} must stay strictly below "
        f"the host collection size {HOST_COLLECTION_SIZE[_task]}")


def _uniform(lo: int, hi: int) -> int:
    return lo + secrets.randbelow(hi - lo + 1)


def b1_rev3_clean_median() -> int:
    rows = json.loads(QUAL_SUMMARY.read_text(encoding="utf-8"))
    counts = sorted(r["tool_calls"] for r in rows
                    if r["task"] == "b1" and r["injection"] is None)
    if len(counts) != 3:
        raise SystemExit("REFUSING: need exactly 3 clean b1 re-qualification "
                         f"runs in {QUAL_SUMMARY}, found {len(counts)}")
    return int(statistics.median(counts))


def main() -> int:
    if OUT_PATH.exists():
        raise SystemExit(f"REFUSING: {OUT_PATH} already exists; the draw "
                         "happens exactly once. Delete it only with the "
                         "escrow holder's involvement.")
    medians = dict(PHASE1_CLEAN_MEDIANS)
    medians["b1"] = b1_rev3_clean_median()

    used_seeds: set[int] = set()

    def draw_seed() -> int:
        while True:
            seed = _uniform(1000, 9999)
            if seed not in used_seeds:
                used_seeds.add(seed)
                return seed

    cells = []
    for task in TASKS:
        median = medians[task]
        rb_n_lo, rb_n_hi = int(median * 0.4), int(median * 0.6)
        for _ in range(SEEDS_PER_CELL):
            cells.append({
                "category": "RESOURCE_BUDGET", "injection": "quota_cliff",
                "task": task, "seed": draw_seed(),
                "n_inject": _uniform(rb_n_lo, rb_n_hi),
                "q0": _uniform(*RB_Q0_RANGE),
                "family": FAMILY[task],
            })
        page_lo, page_hi = DV_POST_PAGE_RANGE[task]
        for _ in range(SEEDS_PER_CELL):
            cells.append({
                "category": "DEPENDENCY_VERSION",
                "injection": "silent_minor_bump",
                "task": task, "seed": draw_seed(),
                "n_inject": DV_N_CHOICES[secrets.randbelow(len(DV_N_CHOICES))],
                "version_to": DV_POST_VERSIONS[
                    secrets.randbelow(len(DV_POST_VERSIONS))],
                "page_size_to": _uniform(page_lo, page_hi),
                "family": FAMILY[task],
            })

    payload = {
        "drawn": "2026-06-12",
        "superset_shape": "4 tasks x 5 seeds x 2 categories = 40 cells "
                          "(SUPERSET: the 1b matrix uses the qualified "
                          "pairs drawn from within)",
        "draw_basis": {"clean_medians": medians,
                       "rb_q0_range": list(RB_Q0_RANGE),
                       "dv_n_choices": list(DV_N_CHOICES),
                       "dv_post_page_ranges": DV_POST_PAGE_RANGE},
        "cells": cells,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, indent=1, sort_keys=True).encode("utf-8")
    OUT_PATH.write_bytes(raw)

    digest = hashlib.sha256(raw).hexdigest()
    print(f"escrow file written: {OUT_PATH} ({len(cells)} cells)")
    print("draw basis (non-secret): clean medians "
          f"{medians} | Q0 range {RB_Q0_RANGE} | DV N {DV_N_CHOICES} | "
          f"DV post-page ranges {DV_POST_PAGE_RANGE}")
    print(f"SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
