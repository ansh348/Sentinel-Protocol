"""Phase 1b CONFIRMATORY MATRIX RUNNER — the glue the one-shot fires (C1).

GLUE ONLY. This module wires three already-frozen pieces together; it changes none of
them:
  - conductor/escrow_loader.py  — loads + hash-verifies both sealed files, yields
    seal-safe SealedCells (it never prints a drawn value);
  - sentinel_v2/arms.py dispatch — runs ONE cell on ONE arm through the frozen detection
    stack (the runner adds nothing to detection; it only forwards the cell's sealed seed
    and opaque injection-params, via dispatch's additive None-default pass-through);
  - the world/conductor — runs the cell.

What it does: enumerate the consumable 1b cells (27 original-injected + 12 clean from
matrix_escrow, the consumed held-out pairs from holdout_escrow, with the D23 skips
already honored inside the loader), and for the selected arms dispatch each cell and
persist a SEAL-SAFE per-cell-per-arm record (run-identity + outcome metrics only; NO
drawn seed/n_inject/param value is ever written or printed). It is a persistent, logged,
resumable launcher (append-as-you-go + skip-completed), so it survives session close and
runs to completion.

The 1bKG gates are a SEPARATE post-matrix step (analysis/matrix_gates.py); this runner
only produces the sealed result ledger.

SEAL DISCIPLINE (Rule Zero): the runner reads no drawn value (cells stay opaque); the
result ledger and every log line carry public run-identity (task / injection / category /
slot index / arm) and outcome metrics only. The drawn seed and n_inject are launch-only —
forwarded to dispatch, never recorded. The ledger lives under runs/ (gitignored).

THE FIRE IS A SEPARATE DELIBERATE STEP. Importing or smoking this module runs NO sealed
cell: run_matrix(...) is the fire entry; the seen smoke calls run_cell_arm on explicitly
constructed SEEN cells and exercises enumerate_cells() for hash-verification only.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis.gates import INJECTION_CATEGORY as _SEEN_CATEGORY
from conductor.escrow_loader import (load_holdout_cells, load_matrix_cells,
                                     SealedCell)
from sentinel_v2.arms import ArmResult, dispatch, resolve_arm

# The four confirmatory arms the fire passes (D33: V2J deferred — exploratory, later).
FIRE_ARMS = ("V2", "S1", "S2", "S3")

# injection -> category label. The five SEEN labels come verbatim from analysis/gates.py;
# the two held-out labels are PUBLIC category names (benchmark/holdouts/*.md, prereg §2),
# NOT drawn values — used only to bucket cells for the categorical/denominator counts.
INJECTION_CATEGORY = {**_SEEN_CATEGORY,
                      "quota_cliff": "RESOURCE_BUDGET",
                      "silent_minor_bump": "DEPENDENCY_VERSION"}

# Ex-ante recovery-class manifest, original nine pairs — prereg_1b.md §3a (AUTHOR-8,
# CONFIRMED 2026-06-12), governing the 1bKG1 recoverable-class denominator. Held-out
# labels are NOT in this map (set below): DEPENDENCY_VERSION always RECOVERABLE (retreat
# never justified, DEPENDENCY_VERSION.md §3); RESOURCE_BUDGET mechanical at the drawn
# N/Q0 (RESOURCE_BUDGET.md §3) — labeled at launch, surfaced as fire-time below.
RECOVERY_CLASS_3A = {
    ("a1", "endpoint_404"): "RECOVERABLE",      # pair 1 (REMAP)
    ("a1", "schema_drift"): "RECOVERABLE",      # pair 2 (REINTERPRET+REDO)
    ("a1", "token_expiry"): "RETREAT_CONDITION",  # pair 3 (justified RETREAT+salvage)
    ("b1", "schema_drift"): "RECOVERABLE",      # pair 4 (RECONCILE+REDO) — D23-retired
    ("b1", "gate_skip_trap"): "RECOVERABLE",    # pair 5 (REDO+verify)    — D23-retired
    ("c1", "doc_contradiction"): "RECOVERABLE",  # pair 6 (RECONCILE)
    ("c1", "token_expiry"): "RETREAT_CONDITION",  # pair 7
    ("d1", "gate_skip_trap"): "RETREAT_CONDITION",  # pair 8 (caveat recorded §3a)
    ("d1", "endpoint_404"): "RETREAT_CONDITION",  # pair 9
}

LEDGER_DIR = REPO_ROOT / "runs" / "matrix_1b"

# RESOURCE_BUDGET recoverable-class formula — RATIFIED by the author 2026-06-15 (rulings:
# "unique required" F-semantics + the a1-S1-clean-s1-3 profile). RESOURCE_BUDGET.md §3:
# REPLAN-recoverable iff Q0 >= expected_remaining_required(N), where
#   expected_remaining_required(N) = RB_T_A1 - F_uniq(N)
#   RB_T_A1 = 19 (§5 a1 row: 1 item list + 6 per-SKU item reads + 6 quotes + 6 us-east
#     rates; family /inventory /pricing /shipping, /auth excluded)
#   F_uniq(N) = count of DISTINCT REQUIRED family calls completed in the first N tool calls
#     of a1's S1 batch clean-median call ledger. "remaining REQUIRED" (§3) + recovery
#     "dedupe" (§2) => UNIQUE, not raw (the batch re-lists /inventory/items redundantly).
# RB_F_UNIQUE_A1 below is the cumulative F_uniq(N) for N=1..24, FROZEN from the canonical
# S1 clean-median run a1-S1-clean-s1-3 (24 tool calls = §6 a1 median 24; the seed-1 D20/D21
# re-run, manipulation_table_s1_seed1; a SEEN clean run). Consumed RB pair is (a1,
# quota_cliff) only; DEPENDENCY_VERSION (b1) is always recoverable (DV.md §3). The label is
# computed at FIRE from the sealed N/Q0 and never prints them. Cite RESOURCE_BUDGET.md
# §3/§5/§6; prereg_1b §3a; ratification decisions/v2_matrix_runner_gates_2026-06-15.md.
RB_T_A1 = 19
RB_F_UNIQUE_A1 = (0, 0, 0, 1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9,
                  10, 11, 12, 13, 14, 15, 16, 17, 18, 19)


def task_path(task: str) -> str:
    return str(REPO_ROOT / "tasks" / f"{task}.yaml")


def rb_recovery_class(n_inject: int, q0: int) -> str:
    """The RATIFIED RESOURCE_BUDGET recoverable-class label from the sealed N/Q0:
    RECOVERABLE (REPLAN-recoverable) iff Q0 >= RB_T_A1 - F_uniq(N), else RETREAT_CONDITION
    (RESOURCE_BUDGET.md §3). Returns only the label — never the drawn values."""
    if n_inject is None or q0 is None:
        return "RB_MECHANICAL_AT_LAUNCH"               # defensive: missing sealed inputs
    f = RB_F_UNIQUE_A1[min(max(int(n_inject), 1), len(RB_F_UNIQUE_A1)) - 1]
    expected_remaining_required = RB_T_A1 - f
    return "RECOVERABLE" if int(q0) >= expected_remaining_required else "RETREAT_CONDITION"


def recovery_class(cell: SealedCell) -> Optional[str]:
    """The 1bKG1 recoverable-class label for a cell (None for clean cells). Original pairs:
    §3a (AUTHOR-8) verbatim. Held-out: DEPENDENCY_VERSION always RECOVERABLE
    (DEPENDENCY_VERSION.md §3 binding asymmetry); RESOURCE_BUDGET labeled at launch from the
    sealed N/Q0 by the RATIFIED formula (rb_recovery_class), never printing the values."""
    if cell.injection is None:
        return None
    key = (cell.task, cell.injection)
    if key in RECOVERY_CLASS_3A:
        return RECOVERY_CLASS_3A[key]
    if cell.injection == "silent_minor_bump":          # DEPENDENCY_VERSION
        return "RECOVERABLE"
    if cell.injection == "quota_cliff":                # RESOURCE_BUDGET (RATIFIED)
        return rb_recovery_class(cell._n_inject, (cell._params or {}).get("q0"))
    return None


def enumerate_cells() -> tuple[list[SealedCell], list[SealedCell], int]:
    """Load + hash-verify BOTH escrow files and return (matrix_cells, holdout_cells,
    d23_skipped). The loader raises EscrowIntegrityError on a custody-pin mismatch and
    never surfaces a drawn value; the D23 retired b1 pairs are skipped inside it."""
    matrix_cells, skipped = load_matrix_cells()
    holdout_cells = load_holdout_cells()
    return matrix_cells, holdout_cells, skipped


def cell_identity(cell: SealedCell, slot_index: int) -> dict:
    """Seal-safe public identity for the ledger/log: NO drawn value. Held-out cells carry
    no public seed-slot, so a positional index (enumeration order) stands in."""
    return {
        "kind": cell.kind,
        "task": cell.task,
        "injection": cell.injection,                # public category injection name
        "category": INJECTION_CATEGORY.get(cell.injection) if cell.injection else None,
        "slot": cell.slot if cell.slot is not None else slot_index,  # public/positional
        "recovery_class": recovery_class(cell),
    }


def cell_key(identity: dict, arm_id: str) -> str:
    """Resumability key — seal-safe (no drawn value)."""
    return (f"{identity['kind']}|{identity['task']}|{identity['injection'] or 'clean'}"
            f"|slot{identity['slot']}|{arm_id}")


def _newest_run_dir(runs_root: str):
    """The most-recently-created top-level run dir under runs_root — the cell that just
    dispatched (the runner is sequential). Used transiently to read the wasted-work
    metric; the PATH (which carries the sealed seed) is never recorded."""
    root = Path(runs_root)
    dirs = [p for p in root.glob("*") if p.is_dir()]
    return max(dirs, key=lambda p: p.stat().st_mtime) if dirs else None


def _arm_result_record(res: ArmResult, runs_root: str) -> dict:
    """Outcome metrics for the ledger — drawn values excluded by construction. Adds the
    frozen M6 wasted-work measure (analysis.metrics, prereg.md 6.1) for the 1bKG4 column,
    read transiently from the just-created run dir (its path, which carries the sealed
    seed, is NOT recorded — only the metric values)."""
    rec = {"arm_id": res.arm_id, "detected": res.detected,
           "n_interrupts": res.n_interrupts, "total_cost_usd": res.total_cost_usd,
           "ttd_tool_calls": res.ttd_tool_calls, "false_interrupts": res.false_interrupts,
           "fir": res.fir, "replans": res.replans, "success": res.success,
           "grades": list(res.grades), "source": res.source}
    try:
        from analysis.metrics import run_metrics
        rd = _newest_run_dir(runs_root)
        rec["wasted"] = run_metrics(rd)["wasted"] if rd else None  # {tool_calls, tokens, usd}
    except Exception:
        rec["wasted"] = None
    return rec


def run_cell_arm(cell: SealedCell, arm_id: str, slot_index: int, *,
                 runs_root: str) -> dict:
    """Dispatch ONE cell on ONE arm through the frozen arms.dispatch and return a
    seal-safe record. The cell's sealed seed + opaque injection-params are forwarded to
    dispatch (and never recorded)."""
    resolve_arm(arm_id)                                     # validate (raises on unknown)
    kw = cell.launch_kwargs()                              # {task, injection, seed, n_inject, injection_params}
    res = dispatch(arm_id, task_path=task_path(kw["task"]),
                   injection=kw["injection"], n_inject=kw["n_inject"],
                   seed=kw["seed"], injection_params=kw["injection_params"],
                   runs_root=runs_root)
    identity = cell_identity(cell, slot_index)
    return {**identity, "arm": arm_id, "result": _arm_result_record(res, runs_root)}


def _load_done(ledger_path: Path) -> set[str]:
    done: set[str] = set()
    if ledger_path.exists():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            done.add(cell_key(row, row["arm"]))
    return done


def run_matrix(arms_scope=FIRE_ARMS, *, ledger_dir: Path = LEDGER_DIR,
               runs_root: Optional[str] = None, log=print) -> dict:
    """THE FIRE ENTRY (do not call on a smoke). Enumerate the sealed cells (hash-verified),
    dispatch each through the selected arms, and append each seal-safe record to the ledger
    as it completes (resumable: completed (cell,arm) are skipped). Persistent + logged:
    progress count + liveness only, NO per-cell outcome surfaced. Returns a summary count."""
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_dir / "results.jsonl"
    runs_root = runs_root or str(ledger_dir / "runs")
    matrix_cells, holdout_cells, skipped = enumerate_cells()
    cells = [(c, i) for i, c in enumerate(matrix_cells)]
    cells += [(c, i) for i, c in enumerate(holdout_cells)]
    total = len(cells) * len(arms_scope)
    done = _load_done(ledger_path)
    log(f"[matrix-1b] {len(cells)} cells x {len(arms_scope)} arms = {total} runs "
        f"(D23 skipped {skipped}); {len(done)} already done; arms={list(arms_scope)}")
    completed = len(done)
    with ledger_path.open("a", encoding="utf-8") as fh:
        for cell, slot_index in cells:
            identity = cell_identity(cell, slot_index)
            for arm_id in arms_scope:
                if cell_key(identity, arm_id) in done:
                    continue
                rec = run_cell_arm(cell, arm_id, slot_index, runs_root=runs_root)
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
                completed += 1
                log(f"[matrix-1b] progress {completed}/{total} "
                    f"({identity['kind']} {identity['task']}+"
                    f"{identity['injection'] or 'clean'}/slot{identity['slot']} :: {arm_id})")
    log(f"[matrix-1b] complete: {completed}/{total} records in {ledger_path}")
    return {"total": total, "completed": completed, "skipped_d23": skipped,
            "ledger": str(ledger_path)}


def verify_escrow_only() -> dict:
    """Exercise the escrow-load path for HASH-VERIFICATION ONLY: load + verify both files,
    count cells, dispatch NOTHING. Used by the seen smoke to prove the seal is intact
    without consuming a sealed cell."""
    matrix_cells, holdout_cells, skipped = enumerate_cells()
    return {"matrix_cells": len(matrix_cells), "holdout_cells": len(holdout_cells),
            "d23_skipped": skipped, "hash_verified": True}


if __name__ == "__main__":
    # Persistent fire entry. Default arm scope = the four confirmatory arms (D33).
    arms = tuple(a for a in sys.argv[1:] if not a.startswith("-")) or FIRE_ARMS
    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    print(f"[matrix-1b] FIRE start {started} arms={list(arms)} — this consumes the sealed "
          "escrow; abort now if this was not intended.")
    raise SystemExit(0 if run_matrix(arms) else 1)
