"""Matrix escrow draw for the Phase 1b ORIGINAL five categories
(prereg_1b.md AUTHOR-5 ruling; benchmark/matrix_draw_spec.md — the spec is
committed in the ratification commit, before this script runs).

Draws the sealed per-cell values for the non-holdout matrix slice — 27
original-injected cells (9 qualified pairs x 3 seed slots) + 12 clean cells
(4 tasks x 3 seed slots) — and writes escrow/matrix_escrow.json (gitignored;
the repo is public). Values are drawn with the `secrets` module
(cryptographic, non-reproducible). NOTHING from the drawn set is ever
printed; the only console output is the file's SHA-256, its shape, and the
non-secret draw basis.

Draw rules (verbatim from benchmark/matrix_draw_spec.md):
- run seed: unique per cell, uniform [10000, 99999] (disjoint from Phase 1
  matrix seeds {1,2,3}, qualification seeds 901-912, and the holdout-escrow
  namespace 1000-9999)
- n_inject (injected cells): uniform integer in [floor(0.40*m),
  floor(0.60*m)] of the task's clean median m — a1 24, c1 12, d1 21
  (Phase 1 finals), b1 14 (rev-4 re-qualification)
- payload parameters: NONE varied — the wound-preserving variation set is
  empty (spec Section 2); injection params stay exactly as qualified in the
  task yamls
- a cell's drawn values are shared across all five arms

Custody (decisions/matrix_escrow_record.md after the draw): transmitted to
the escrow holder; the 1b harness consumes it programmatically at launch
after SHA-256 verification; the author does not open it.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "escrow" / "matrix_escrow.json"

SEED_SLOTS = 3
SEED_RANGE = (10000, 99999)
CLEAN_MEDIANS = {"a1": 24, "b1": 14, "c1": 12, "d1": 21}

# The nine qualified pairs (decisions/manipulation_table_s1_seed1.md;
# prereg_1b Section 3), params exactly as qualified in the task yamls.
PAIRS = (
    ("a1", "endpoint_404"),
    ("a1", "schema_drift"),
    ("a1", "token_expiry"),
    ("b1", "schema_drift"),
    ("b1", "gate_skip_trap"),
    ("c1", "doc_contradiction"),
    ("c1", "token_expiry"),
    ("d1", "gate_skip_trap"),
    ("d1", "endpoint_404"),
)
TASKS = ("a1", "b1", "c1", "d1")


def _uniform(lo: int, hi: int) -> int:
    return lo + secrets.randbelow(hi - lo + 1)


def main() -> int:
    if OUT_PATH.exists():
        raise SystemExit(f"REFUSING: {OUT_PATH} already exists; the draw "
                         "happens exactly once. Delete it only with the "
                         "escrow holder's involvement.")

    used_seeds: set[int] = set()

    def draw_seed() -> int:
        while True:
            seed = _uniform(*SEED_RANGE)
            if seed not in used_seeds:
                used_seeds.add(seed)
                return seed

    n_ranges = {task: (int(m * 0.4), int(m * 0.6))
                for task, m in CLEAN_MEDIANS.items()}

    injected = []
    for task, injection in PAIRS:
        lo, hi = n_ranges[task]
        for slot in range(1, SEED_SLOTS + 1):
            injected.append({
                "task": task, "injection": injection, "slot": slot,
                "seed": draw_seed(), "n_inject": _uniform(lo, hi),
            })

    clean = []
    for task in TASKS:
        for slot in range(1, SEED_SLOTS + 1):
            clean.append({"task": task, "slot": slot, "seed": draw_seed()})

    payload = {
        "drawn": "2026-06-12",
        "shape": "27 injected (9 pairs x 3 slots) + 12 clean (4 tasks x 3 "
                 "slots) = 39 cells; values shared across all five arms",
        "draw_basis": {"clean_medians": CLEAN_MEDIANS,
                       "n_inject_ranges": {t: list(r)
                                           for t, r in n_ranges.items()},
                       "seed_range": list(SEED_RANGE),
                       "payload_variation": "none (matrix_draw_spec.md S2: "
                                            "wound-preserving set is empty)"},
        "injected_cells": injected,
        "clean_cells": clean,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, indent=1, sort_keys=True).encode("utf-8")
    OUT_PATH.write_bytes(raw)

    digest = hashlib.sha256(raw).hexdigest()
    print(f"escrow file written: {OUT_PATH} "
          f"({len(injected)} injected + {len(clean)} clean cells)")
    print("draw basis (non-secret): clean medians "
          f"{CLEAN_MEDIANS} | n_inject ranges {n_ranges} | "
          f"seed range {SEED_RANGE} | payload variation: none")
    print(f"SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
