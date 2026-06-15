"""C3 — SEEN SMOKE for the 1b matrix runner + gates (wiring + compute; NO sealed cell).

Proves the plumbing on DEVELOPMENT SEEN cells only (the kind used in the seen sweep),
dispatched through the four confirmatory arms V2/S1/S2/S3, then scored by the 1bKG gate
computation. Separately confirms the escrow-load path HASH-VERIFIES both sealed files
WITHOUT dispatching any sealed cell.

NO sealed/matrix/holdout cell is executed here: the cells below are explicitly constructed
SEEN cells (public seed 1, no drawn param override). The smoke exists to show the wiring
computes — never to make a gate pass.

Usage: ../.venv/Scripts/python.exe -m analysis.matrix_smoke
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
os.environ["TRIPWIRE_V2"] = "1"
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from conductor.escrow_loader import SealedCell
from analysis import matrix_gates as MG
from analysis import matrix_runner as MR

SMOKE_DIR = REPO_ROOT / "runs" / "matrix_1b_smoke"

# Development SEEN cells (public seed 1, no drawn params) — NOT sealed cells.
SEEN_CELLS = [
    SealedCell(kind="matrix-injected", task="a1", injection="endpoint_404", slot=0,
               category=None, _seed=1, _n_inject=12, _params={}),   # API_SURFACE, RECOVERABLE
    SealedCell(kind="matrix-clean", task="a1", injection=None, slot=0,
               category=None, _seed=1, _n_inject=None, _params={}),  # clean
]


def main(argv) -> int:
    arms = MR.FIRE_ARMS
    SMOKE_DIR.mkdir(parents=True, exist_ok=True)
    ledger = SMOKE_DIR / "results.jsonl"
    if ledger.exists():
        ledger.unlink()
    runs_root = str(SMOKE_DIR / "runs")
    Path(runs_root).mkdir(parents=True, exist_ok=True)

    print(f"=== SEEN SMOKE: {len(SEEN_CELLS)} seen cells x {len(arms)} arms "
          f"({list(arms)}) — NO sealed cell ===")
    n = 0
    with ledger.open("a", encoding="utf-8") as fh:
        for cell in SEEN_CELLS:
            for arm in arms:
                rec = MR.run_cell_arm(cell, arm, slot_index=cell.slot, runs_root=runs_root)
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                n += 1
                r = rec["result"]
                print(f"  [{n:2d}/{len(SEEN_CELLS)*len(arms)}] {rec['task']}+"
                      f"{rec['injection'] or 'clean'} :: {arm}  detected={r['detected']} "
                      f"ttd={r['ttd_tool_calls']} fir={r['fir']} cost=${r['total_cost_usd']}")
    print(f"persisted {n} records -> {ledger}")

    print("\n=== gate computation over the seen-smoke ledger ===")
    rep = MG.compute_gates(ledger)
    print(MG.format_report(rep))
    (SMOKE_DIR / "gate_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")

    print("\n=== escrow-load HASH-VERIFY ONLY (no sealed cell dispatched) ===")
    v = MR.verify_escrow_only()
    print(f"  hash_verified={v['hash_verified']} matrix_cells={v['matrix_cells']} "
          f"holdout_cells={v['holdout_cells']} d23_skipped={v['d23_skipped']}")

    print("\nSMOKE CONFIRMATION:")
    print(f"  - dispatch+persistence across {len(arms)} arms: OK ({n} records)")
    print(f"  - gates compute + emit a verdict: {rep['verdict']}")
    print(f"  - sealed cells executed: 0 (seen cells only)")
    print(f"  - held-out values read: 0 (escrow path hash-verified, not dispatched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
