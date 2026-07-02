"""A7 benign-noise smoke runner (foreground-chunked, resumable).

Executes the A7 matrix under the ratified addendum + D36:
  - arms V2 + S2 (FIR), S1 (qualification anchor); 3 frozen classes; seeds 4-15.
  - FROZEN run order (plan §6.1): S1 qualification (all 12) -> transient_500 (V2 then S2)
    -> additive_field (V2 then S2) -> latency_spike (V2 then S2).
  - PER-CELL M6 qualification gate: a (task x class) cell's V2/S2 run only if S1 PASSED
    its checker under that noise at the frozen seed; an S1 failure DISQUALIFIES that cell
    (V2/S2 excluded + logged); the class survives on tasks where S1 passes.
  - HARD $15 cap on cumulative MODELED total_cost_usd (list price): stop before starting a
    job once the cap is reached; report partial; NO verdict on a truncated matrix.
  - Resumable: an append-only ledger (a7_results.jsonl) records every completed job; a new
    invocation skips completed keys and carries cumulative cost (D-V3-1 chunking pattern).
  - Per transient_500 cell, the WORLD trace carries a `noise_fired` event (which call the
    500 landed on: token vs first surface call); the runner mirrors it into the ledger.

The executor is injectable so the control logic (order / M6 gate / cap / resume) is
dry-testable offline; execute_live() is the real Phase-3 dispatch. This module runs NO
live cell on import or in --preflight; the metered run is gated on explicit author go.
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

TASKS = ("a1", "b1", "c1", "d1")
# Run-order over classes (plan §6.1): transient_500 first (load-bearing M3 prediction),
# then additive_field, then latency_spike.
CLASS_ORDER = ("transient_500", "additive_field", "latency_spike")
FIR_ARMS = ("V2", "S2")

# Frozen seed block (addendum M4): one seed per (task x class), shared across arms.
SEED_MAP = {
    ("a1", "transient_500"): 4,  ("a1", "latency_spike"): 5,  ("a1", "additive_field"): 6,
    ("b1", "transient_500"): 7,  ("b1", "latency_spike"): 8,  ("b1", "additive_field"): 9,
    ("c1", "transient_500"): 10, ("c1", "latency_spike"): 11, ("c1", "additive_field"): 12,
    ("d1", "transient_500"): 13, ("d1", "latency_spike"): 14, ("d1", "additive_field"): 15,
}

CAP_USD = 15.0                 # frozen modeled total_cost_usd cap (addendum M2)
DEFAULT_TIME_BUDGET_S = 520.0  # per-invocation chunk (D-V3-1)
# Conservative per-run modeled-cost reserve: never START a job that could carry cumulative
# past the cap (so the hard ceiling holds even though a job's cost is unknown until it runs).
PER_RUN_RESERVE_USD = 0.60


@dataclass(frozen=True)
class Job:
    phase: str    # "qual" (S1 anchor) | "fir" (V2/S2)
    task: str
    noise_class: str
    arm: str      # S1 | V2 | S2
    seed: int

    @property
    def key(self) -> str:
        return f"{self.phase}:{self.task}:{self.noise_class}:{self.arm}:s{self.seed}"


def build_jobs() -> list[Job]:
    """The full A7 job list in FROZEN execution order (plan §6.1)."""
    jobs: list[Job] = []
    # 1. S1 qualification first — all 12 (task x class) cells.
    for cls in CLASS_ORDER:
        for task in TASKS:
            jobs.append(Job("qual", task, cls, "S1", SEED_MAP[(task, cls)]))
    # 2-4. FIR arms, by class (transient -> additive -> latency), V2 then S2, over tasks.
    for cls in CLASS_ORDER:
        for arm in FIR_ARMS:
            for task in TASKS:
                jobs.append(Job("fir", task, cls, arm, SEED_MAP[(task, cls)]))
    return jobs


# --------------------------------------------------------------------------- ledger

def load_ledger(ledger_path: Path) -> list[dict]:
    if not ledger_path.exists():
        return []
    rows = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def append_ledger(ledger_path: Path, entry: dict) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
        fh.flush()


# ----------------------------------------------------------------------- executors

def read_noise_landing(run_dir: Path) -> Optional[dict]:
    """The transient_500 `noise_fired` record from the banked world trace: which call
    the 500 landed on (token vs first surface call), its counter and path."""
    wt = Path(run_dir) / "trace_world.jsonl"
    if not wt.exists():
        return None
    from trace import read_trace
    for e in read_trace(wt):
        if (e.get("event_type") == "noise_fired"
                and (e.get("payload") or {}).get("noise_class") == "transient_500"):
            p = e["payload"]
            return {"landed_on": p.get("landed_on"), "counter": p.get("counter"),
                    "path": p.get("path")}
    return None


def execute_live(job: Job, runs_root: str) -> dict:
    """Phase-3 dispatch of one cell through the real arm. NOT invoked offline."""
    from world.state import NoiseProfile
    np_ = NoiseProfile(noise_class=job.noise_class)
    task_path = str(REPO_ROOT / "tasks" / f"{job.task}.yaml")
    if job.arm in ("S1", "S2"):
        from conductor.run_one import run_one
        summary = run_one(task_path=task_path, system_id=job.arm, injection=None,
                          n_inject=None, seed=job.seed, runs_root=runs_root,
                          noise_profile=np_)
    elif job.arm == "V2":
        from conductor.run_v2_loop import run_v2_loop
        summary = run_v2_loop(task_path=task_path, injection=None, seed=job.seed,
                              runs_root=runs_root, noise_profile=np_)
    else:
        raise ValueError(f"unknown arm {job.arm!r}")
    landing = (read_noise_landing(Path(summary["run_dir"]))
               if job.noise_class == "transient_500" else None)
    return {"success": bool(summary.get("success")),
            "cost_usd": float(summary.get("cost_usd", 0.0)),
            "run_dir": summary.get("run_dir"),
            "reason": summary.get("reason"),
            "noise_landed_on": landing}


# ---------------------------------------------------------------------- matrix loop

def run_matrix(execute: Callable[[Job], dict], *, ledger_path: Path,
               cap: float = CAP_USD, time_budget_s: float = DEFAULT_TIME_BUDGET_S,
               clock: Callable[[], float] = time.monotonic) -> dict:
    """Iterate the frozen job order, honouring resume, the per-cell M6 gate, the hard
    cap, and the chunk time budget. Returns a status dict; never computes the verdict."""
    ledger = load_ledger(ledger_path)
    done = {e["key"] for e in ledger}
    cost = sum(float(e.get("cost_usd", 0.0)) for e in ledger)
    qual = {(e["task"], e["noise_class"]): bool(e["success"])
            for e in ledger if e["phase"] == "qual" and "success" in e}
    jobs = build_jobs()
    start = clock()
    ran = 0
    reason = "complete"

    for job in jobs:
        if job.key in done:
            continue
        # HARD cap: never start a job that could carry cumulative past the ceiling.
        if cost + PER_RUN_RESERVE_USD > cap:
            reason = "cap"
            break
        # Chunk boundary: exit gracefully after the time budget (resume next invocation).
        if ran > 0 and clock() - start >= time_budget_s:
            reason = "chunk_time"
            break
        # Per-cell M6 gate for FIR jobs.
        if job.phase == "fir":
            q = qual.get((job.task, job.noise_class))
            if q is None:
                # S1 qualification for this cell hasn't run yet (cap/chunk stopped in the
                # qual phase). Leave the FIR job for a later invocation; do not run blind.
                continue
            if q is False:
                entry = {"key": job.key, **asdict(job), "status": "disqualified",
                         "success": False, "cost_usd": 0.0, "run_dir": None,
                         "noise_landed_on": None}
                append_ledger(ledger_path, entry)
                done.add(job.key)
                continue
        # Execute + bank.
        result = execute(job)
        entry = {"key": job.key, **asdict(job), "status": "ran",
                 "success": bool(result.get("success")),
                 "cost_usd": float(result.get("cost_usd", 0.0)),
                 "run_dir": result.get("run_dir"),
                 "reason": result.get("reason"),
                 "noise_landed_on": result.get("noise_landed_on")}
        append_ledger(ledger_path, entry)
        done.add(job.key)
        cost += entry["cost_usd"]
        ran += 1
        if job.phase == "qual":
            qual[(job.task, job.noise_class)] = entry["success"]

    total = len(jobs)
    matrix_complete = all(j.key in done for j in jobs)
    return {"reason": reason, "cost_usd": round(cost, 6), "cap": cap,
            "ran_this_chunk": ran, "completed": len(done & {j.key for j in jobs}),
            "total_jobs": total, "matrix_complete": matrix_complete,
            "disqualified": [e["key"] for e in load_ledger(ledger_path)
                             if e.get("status") == "disqualified"]}


# ------------------------------------------------------------------- pre-flight text

def preflight_summary() -> str:
    jobs = build_jobs()
    quals = [j for j in jobs if j.phase == "qual"]
    firs = [j for j in jobs if j.phase == "fir"]
    lines = ["A7 PRE-FLIGHT (no runs; --preflight)", ""]
    lines.append(f"Matrix: {len(jobs)} jobs max = {len(quals)} S1-qual + {len(firs)} FIR "
                 f"(V2/S2 on qualified cells).")
    lines.append(f"Seeds: {min(SEED_MAP.values())}-{max(SEED_MAP.values())} "
                 "(one per task x class, shared across arms).")
    lines.append("")
    lines.append("FROZEN run order (plan §6.1):")
    lines.append(f"  1. S1 qualification, all {len(quals)} cells "
                 f"[order: {' , '.join(f'{j.task}/{j.noise_class}' for j in quals)}]")
    step = 2
    for cls in CLASS_ORDER:
        block = [j for j in firs if j.noise_class == cls]
        lines.append(f"  {step}. {cls}: "
                     + " , ".join(f"{j.arm}:{j.task}(s{j.seed})" for j in block))
        step += 1
    lines.append("")
    lines.append(f"Cap accounting: HARD ${CAP_USD:.0f} on cumulative MODELED total_cost_usd "
                 f"(list price); reserve ${PER_RUN_RESERVE_USD:.2f}/run so no job starts that "
                 "could exceed the ceiling.")
    lines.append("  estimate: S1 12x~$0.234 (~$2.8) + S2 12x~$0.30-0.50 (~$3.6-6.0) + "
                 "V2 12x~$0.40-0.60 (~$4.8-7.2) = ~$11-16 modeled; cap can bind on the high "
                 "side -> partial report, NO verdict on a truncated matrix.")
    lines.append("")
    lines.append("Resume/abort behaviour:")
    lines.append("  - resume: append-only a7_results.jsonl; a new invocation skips completed "
                 "keys and carries cumulative cost.")
    lines.append("  - chunk: each invocation runs until the ~520s time budget, then exits "
                 "(D-V3-1); resume continues the frozen order.")
    lines.append("  - cap: stop BEFORE starting a job once cumulative + reserve > cap; "
                 "reason='cap'; partial; verdict NOT computed.")
    lines.append("  - M6 gate: an S1-qual failure disqualifies that (task x class) cell only "
                 "(V2/S2 skipped + logged); the class survives on tasks where S1 passes.")
    lines.append("  - transient_500 landing (token vs first surface call) is banked in the "
                 "world trace (noise_fired) and mirrored into the ledger.")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="A7 benign-noise runner")
    parser.add_argument("--preflight", action="store_true",
                        help="print the pre-flight summary and exit (no runs)")
    parser.add_argument("--runs-root", default="runs/a7")
    parser.add_argument("--ledger", default="runs/a7/a7_results.jsonl")
    parser.add_argument("--cap", type=float, default=CAP_USD)
    parser.add_argument("--time-budget", type=float, default=DEFAULT_TIME_BUDGET_S)
    args = parser.parse_args(argv)

    if args.preflight:
        print(preflight_summary())
        return 0

    ledger_path = Path(args.ledger)
    status = run_matrix(lambda job: execute_live(job, args.runs_root),
                        ledger_path=ledger_path, cap=args.cap,
                        time_budget_s=args.time_budget)
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
