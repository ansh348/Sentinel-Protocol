"""Kill-gate table (protocol Section 6.2). REFUSES to run unless the planned
matrix is complete — completeness is checked against the COMMITTED manifest
(analysis/matrix_manifest.json, generated once before Phase 1 by
`make manifest`), never inferred from whatever runs happen to exist. There is
no override flag: peeking at half-collected gates voids the pre-registration
(protocol 8.1).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Optional

import yaml

from analysis.metrics import run_metrics

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "analysis" / "matrix_manifest.json"
SYSTEMS = ("S1", "S2", "S3", "S4", "S5")
SEEDS = (1, 2, 3)

INJECTION_CATEGORY = {
    "endpoint_404": "API_SURFACE",
    "schema_drift": "SCHEMA_DRIFT",
    "token_expiry": "PERMISSION_AUTH",
    "doc_contradiction": "RETRIEVAL_INTEGRITY",
    "gate_skip_trap": "TOOL_CONTRACT",
}


def generate_manifest(tasks_dir: Path = REPO_ROOT / "tasks") -> list[dict]:
    """Every planned (task, system, injection, seed) cell, from the task specs
    and the protocol 5.2 design: each qualified injected pair plus one clean
    variant per task, across all five systems and three seeds."""
    cells = []
    for yaml_path in sorted(tasks_dir.glob("[abcd][0-9].yaml")):
        task = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        variants = [None] + [i["type"] for i in task.get("injections", [])]
        for injection in variants:
            for system in SYSTEMS:
                for seed in SEEDS:
                    cells.append({"task": task["id"], "system": system,
                                  "injection": injection, "seed": seed})
    return cells


def cell_run_dir(runs_root: Path, cell: dict) -> Optional[Path]:
    label = cell["injection"] or "clean"
    base = f"{cell['task']}-{cell['system']}-{label}-s{cell['seed']}"
    candidates = sorted(runs_root.glob(base + "*"))
    for candidate in reversed(candidates):  # latest suffix wins
        if any(candidate.glob("*.jsonl")):
            return candidate
    return None


def check_complete(runs_root: Path,
                   manifest_path: Path = MANIFEST_PATH) -> tuple[list, list]:
    if not manifest_path.exists():
        raise SystemExit("REFUSING: no committed matrix manifest "
                         f"({manifest_path}); generate it ONCE before Phase 1 "
                         "with `make manifest`")
    cells = json.loads(manifest_path.read_text(encoding="utf-8"))
    found, missing = [], []
    for cell in cells:
        run_dir = cell_run_dir(runs_root, cell)
        (found if run_dir else missing).append((cell, run_dir))
    return found, missing


def _median(values: list) -> Optional[float]:
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def kill_gate_table(runs_root: Path,
                    manifest_path: Path = MANIFEST_PATH) -> str:
    found, missing = check_complete(runs_root, manifest_path)
    if missing:
        lines = [f"REFUSING: planned matrix incomplete — {len(missing)} of "
                 f"{len(missing) + len(found)} cells missing (no override):"]
        for cell, _ in missing[:20]:
            lines.append(f"  {cell['task']}/{cell['system']}/"
                         f"{cell['injection'] or 'clean'}/s{cell['seed']}")
        if len(missing) > 20:
            lines.append(f"  ... and {len(missing) - 20} more")
        raise SystemExit("\n".join(lines))

    metrics = [run_metrics(run_dir) for _, run_dir in found]

    def sel(system=None, injected=None):
        return [m for m in metrics
                if (system is None or m["system"] == system)
                and (injected is None or m["injected"] == injected)]

    lines = ["=== KILL GATES (computed once, on the complete planned matrix) ==="]

    # KG1: detection recall (S5)
    s5_inj = sel("S5", True)
    recall = (sum(m["detected"] for m in s5_inj) / len(s5_inj)) if s5_inj else 0
    per_cat: dict[str, list] = {}
    for m in s5_inj:
        per_cat.setdefault(INJECTION_CATEGORY[m["injection"]], []).append(
            m["detected"])
    cat_ok = sum(1 for vals in per_cat.values()
                 if sum(vals) / len(vals) >= 0.5)
    kg1 = recall >= 0.6 and cat_ok >= min(4, len(per_cat))
    lines.append(f"KG1 recall: {recall:.0%} (>=60%) | categories >=50%: "
                 f"{cat_ok}/{len(per_cat)} (>=4) -> "
                 f"{'PASS' if kg1 else 'FAIL'}")

    # KG2: judge earns its cost (FIR ratios)
    def fir(system):
        firs = [m["interrupts"]["fir"] for m in sel(system)
                if m["interrupts"]["fir"] is not None]
        return _median(firs)
    f5, f2, f4 = fir("S5"), fir("S2"), fir("S4")
    kg2 = (f5 is not None and f2 is not None and f4 is not None
           and f5 <= 0.5 * f2 and f5 <= 0.7 * f4)
    lines.append(f"KG2 FIR: S5={f5} S2={f2} S4={f4} "
                 f"(S5<=0.5*S2 and S5<=0.7*S4) -> "
                 f"{'PASS' if kg2 else 'FAIL'}")

    # KG3: pays for itself
    cost5 = _median([m["total_cost_usd"] for m in sel("S5", True)])
    cost1 = _median([m["total_cost_usd"] for m in sel("S1", True)])
    succ5 = (sum(bool(m["success"]) for m in sel("S5", True))
             / max(1, len(sel("S5", True))))
    succ1 = (sum(bool(m["success"]) for m in sel("S1", True))
             / max(1, len(sel("S1", True))))
    clean5 = _median([m["total_cost_usd"] for m in sel("S5", False)])
    clean1 = _median([m["total_cost_usd"] for m in sel("S1", False)])
    overhead_ok = (clean5 is not None and clean1 not in (None, 0)
                   and (clean5 - clean1) / clean1 <= 0.12)
    kg3 = ((cost5 is not None and cost1 is not None)
           and (cost5 < cost1
                or (cost5 <= 1.15 * cost1 and succ5 >= succ1 + 0.15))
           and overhead_ok)
    lines.append(f"KG3 cost: S5 med ${cost5} vs S1 med ${cost1}; success "
                 f"S5={succ5:.0%} S1={succ1:.0%}; clean overhead "
                 f"{'OK' if overhead_ok else 'OVER'} (<=12%) -> "
                 f"{'PASS' if kg3 else 'FAIL'}")

    # KG4: beats cost-matched heartbeat
    w5 = _median([m["wasted"]["tokens"] for m in sel("S5", True)])
    w3 = _median([m["wasted"]["tokens"] for m in sel("S3", True)])
    t5 = _median([m["ttd_tool_calls"] for m in sel("S5", True)])
    t3 = _median([m["ttd_tool_calls"] for m in sel("S3", True)])
    waste_ok = (w5 is not None and w3 not in (None, 0)
                and w5 <= 0.8 * w3)
    ttd_ok = (t5 is not None and t3 is not None and t5 > 0
              and t3 / t5 >= 2)
    kg4 = waste_ok or ttd_ok
    lines.append(f"KG4 vs heartbeat: wasted med S5={w5} S3={w3} (>=20% better)"
                 f" | TTD med S5={t5} S3={t3} (>=2x) -> "
                 f"{'PASS' if kg4 else 'FAIL'}")
    lines.append("Decide within 48 hours of seeing this table; do not "
                 "negotiate with the data (protocol 6.2).")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="kill gates / matrix manifest")
    parser.add_argument("command", choices=["manifest", "gates"])
    parser.add_argument("--runs-root", default=str(REPO_ROOT / "runs"))
    args = parser.parse_args(argv)
    if args.command == "manifest":
        if MANIFEST_PATH.exists():
            raise SystemExit(f"REFUSING: {MANIFEST_PATH} already exists; the "
                             "manifest is generated ONCE before Phase 1")
        cells = generate_manifest()
        MANIFEST_PATH.write_text(json.dumps(cells, indent=1), encoding="utf-8")
        print(f"wrote {MANIFEST_PATH} ({len(cells)} cells); commit it")
    elif args.command == "gates":
        print(kill_gate_table(Path(args.runs_root)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
