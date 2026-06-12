"""SQLite job queue + overnight supervisor (protocol Section 8.1, M5).

States: pending -> running -> done | failed | throttled(-> pending via
backoff). The supervisor never crashes on a job: operational exceptions mark
the job failed; throttles (non-zero exits whose stderr matches the throttle
regex, surfaced either as exceptions or in the run's trace) back off
exponentially (capped 30 minutes) and requeue. Crash safety: claims carry a
per-supervisor token; on startup, stale 'running' rows from dead supervisors
reset to pending, so a kill -9 mid-run neither loses nor duplicates jobs.

The CLI version is pinned in the meta table: if `claude --version` changes
mid-matrix the queue halts and warns (BUILD_BRIEF Section 5).

Windows keep-awake (parked author note b): while supervising, the process
holds SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED); the
RUNBOOK documents the complementary powercfg settings.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO_ROOT / "runs" / "queue.sqlite"
THROTTLE_RE = re.compile(r"rate.?limit|usage limit|overloaded|429", re.IGNORECASE)
BACKOFF_BASE_S = 60.0
BACKOFF_CAP_S = 1800.0  # 30 minutes, per the brief
PROVISIONAL_N_INJECT = 8  # pending clean-median calibration (protocol 5.2)

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT NOT NULL,
    system TEXT NOT NULL,
    injection TEXT,
    n_inject INTEGER,
    seed INTEGER NOT NULL DEFAULT 1,
    heartbeat_k INTEGER,
    state TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    claim_token TEXT,
    claimed_at REAL,
    finished_at REAL,
    backoff_until REAL,
    run_dir TEXT,
    error TEXT,
    note TEXT
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def connect(db_path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def enqueue(conn: sqlite3.Connection, jobs: list[dict]) -> int:
    for job in jobs:
        conn.execute(
            "INSERT INTO jobs (task, system, injection, n_inject, seed, heartbeat_k)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (job["task"], job["system"], job.get("injection"),
             job.get("n_inject"), job.get("seed", 1), job.get("heartbeat_k")))
    return len(jobs)


def recover_stale(conn: sqlite3.Connection, token: str) -> int:
    """Kill -9 recovery: 'running' rows belonging to a dead supervisor go back
    to pending. Run exactly once at startup, before any claim."""
    cursor = conn.execute(
        "UPDATE jobs SET state='pending', claim_token=NULL, claimed_at=NULL"
        " WHERE state='running' AND (claim_token IS NULL OR claim_token != ?)",
        (token,))
    return cursor.rowcount


def claim_next(conn: sqlite3.Connection, token: str) -> Optional[dict]:
    now = time.time()
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT id FROM jobs WHERE state='pending'"
            " OR (state='throttled' AND backoff_until <= ?)"
            " ORDER BY id LIMIT 1", (now,)).fetchone()
        if row is None:
            conn.execute("COMMIT")
            return None
        conn.execute(
            "UPDATE jobs SET state='running', claim_token=?, claimed_at=?"
            " WHERE id=?", (token, now, row["id"]))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return dict(conn.execute("SELECT * FROM jobs WHERE id=?",
                             (row["id"],)).fetchone())


def trace_shows_throttle(run_dir: str | Path) -> bool:
    """Throttle detection over the run's trace: any event payload whose stderr
    (or error detail) matches the pre-registered throttle regex."""
    from trace import read_run
    try:
        events = read_run(run_dir)
    except OSError:
        return False
    for event in events:
        payload = event.get("payload") or {}
        for field in ("stderr", "detail", "error"):
            value = payload.get(field)
            if isinstance(value, str) and THROTTLE_RE.search(value):
                return True
    return False


def _keep_awake(enable: bool) -> None:
    if sys.platform != "win32":
        return
    import ctypes
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if enable else 0)
    ctypes.windll.kernel32.SetThreadExecutionState(flags)


def launcher_guard() -> None:
    """D21: the single-line canary is shim-transparent, so every supervisor
    start fires one orchestrator-shaped MULTILINE probe. A cmd shim truncates
    the command line at the first newline, destroying every flag after the
    multiline --system-prompt — detectable as a missing result envelope.
    HALT before claiming any job; never run a night on a mangling launcher."""
    from conductor.sessions import WORKER_MODEL, run_claude
    result = run_claude(
        model=WORKER_MODEL,
        system_prompt=("You are a test responder.\n"
                       "Follow the user instruction exactly.\n"
                       "Reply only with the requested word."),
        stdin_text="Reply with the single word: pong",
        max_turns=1, no_tools=True)
    if result.payload is None or result.exit_code != 0:
        raise RuntimeError(
            "HALT: launcher mangles multiline arguments (no result envelope "
            "from the orchestrator-shaped probe; D21). Point "
            "TRIPWIRE_CLAUDE_BIN at a real executable, never a .cmd shim, "
            f"then rerun. exit={result.exit_code} "
            f"stdout_head={result.stdout[:120]!r}")


def void_run(summary: Optional[dict]) -> bool:
    """D21 permanent invariant: a 'done' summary whose run directory shows
    zero tool calls AND no success_check event is a void run, never accepted
    as done. Summaries without an inspectable run_dir (unit-test runners)
    pass through."""
    run_dir = (summary or {}).get("run_dir")
    if not run_dir or not Path(run_dir).exists():
        return False
    from trace import read_run
    try:
        events = read_run(run_dir)
    except OSError:
        return False
    tool_calls = sum(1 for e in events if e.get("event_type") == "tool_call")
    checks = sum(1 for e in events if e.get("event_type") == "success_check")
    return tool_calls == 0 and checks == 0


def cli_version_guard(conn: sqlite3.Connection) -> str:
    """BUILD_BRIEF Section 5: halt and warn if the CLI version changes
    mid-matrix. The first supervisor run pins the baseline."""
    from conductor.sessions import get_cli_version
    current = get_cli_version()
    row = conn.execute("SELECT value FROM meta WHERE key='cli_version'").fetchone()
    if row is None:
        conn.execute("INSERT INTO meta (key, value) VALUES ('cli_version', ?)",
                     (current,))
        return current
    if row["value"] != current:
        raise RuntimeError(
            f"HALT: claude CLI version changed mid-matrix "
            f"(pinned {row['value']!r}, current {current!r}); the run matrix "
            "must complete on one version")
    return current


def default_runner(job: dict) -> dict:
    from conductor.run_one import run_one
    return run_one(task_path=REPO_ROOT / "tasks" / f"{job['task']}.yaml",
                   system_id=job["system"], injection=job["injection"],
                   n_inject=job["n_inject"], seed=job["seed"],
                   heartbeat_k=job["heartbeat_k"],
                   runs_root=REPO_ROOT / "runs")


def supervise(db_path: str | Path = DEFAULT_DB,
              runner: Optional[Callable[[dict], dict]] = None,
              poll_s: float = 5.0,
              backoff_base_s: float = BACKOFF_BASE_S) -> dict:
    """The single overnight supervisor loop. Returns counts by final state."""
    conn = connect(db_path)
    token = uuid.uuid4().hex
    cli_version_guard(conn)
    launcher_guard()  # D21: multiline probe beside the version guard
    recovered = recover_stale(conn, token)
    if recovered:
        print(f"recovered {recovered} stale running job(s) -> pending")
    runner = runner or default_runner
    _keep_awake(True)
    try:
        while True:
            job = claim_next(conn, token)
            if job is None:
                remaining = conn.execute(
                    "SELECT COUNT(*) AS n FROM jobs WHERE state IN "
                    "('pending', 'throttled')").fetchone()["n"]
                if remaining == 0:
                    break
                time.sleep(poll_s)
                continue
            throttled, error, summary = False, None, None
            crash_run_dir, crash_cost = None, None
            try:
                summary = runner(job)
                run_dir = (summary or {}).get("run_dir")
                if run_dir and trace_shows_throttle(run_dir):
                    throttled = True
            except Exception as exc:  # the queue never dies; it waits
                # CD-3 (2026-06-10): crashes that carry run context
                # (conductor.run_one.RunCrash) keep their run_dir and
                # accumulated cost on the failed row.
                crash_run_dir = getattr(exc, "run_dir", None)
                crash_cost = getattr(exc, "cost_usd", None)
                if THROTTLE_RE.search(str(exc)):
                    throttled = True
                else:
                    error = (str(exc) if crash_run_dir
                             else f"{type(exc).__name__}: {exc}")
            now = time.time()
            if throttled:
                backoff = min(backoff_base_s * (2 ** job["attempts"]),
                              BACKOFF_CAP_S)
                conn.execute(
                    "UPDATE jobs SET state='throttled', attempts=attempts+1,"
                    " backoff_until=?, run_dir=?, note=? WHERE id=?",
                    (now + backoff, (summary or {}).get("run_dir"),
                     f"throttled; backoff {backoff:.0f}s", job["id"]))
                print(f"job {job['id']} throttled; requeued in {backoff:.0f}s")
            elif error is not None:
                note = (json.dumps({"cost_usd": crash_cost})
                        if crash_cost is not None else None)
                conn.execute(
                    "UPDATE jobs SET state='failed', finished_at=?, error=?,"
                    " run_dir=?, note=? WHERE id=?",
                    (now, error, crash_run_dir, note, job["id"]))
                print(f"job {job['id']} FAILED: {error[:120]}")
            elif void_run(summary):
                # D21 invariant: zero tool calls + no checker event is never
                # accepted as done, whatever the summary claims
                conn.execute(
                    "UPDATE jobs SET state='failed', finished_at=?, error=?,"
                    " run_dir=?, note=? WHERE id=?",
                    (now, "void_run: zero tool calls and no checker event",
                     summary.get("run_dir"),
                     json.dumps({"cost_usd": summary.get("cost_usd")}),
                     job["id"]))
                print(f"job {job['id']} VOID (zero-call run) -> failed")
            else:
                conn.execute(
                    "UPDATE jobs SET state='done', finished_at=?, run_dir=?,"
                    " note=? WHERE id=?",
                    (now, summary.get("run_dir"),
                     json.dumps({"success": summary.get("success"),
                                 "reason": summary.get("reason"),
                                 "cost_usd": summary.get("cost_usd")}),
                     job["id"]))
                print(f"job {job['id']} done ({job['task']}/{job['system']}/"
                      f"{job['injection'] or 'clean'})")
    finally:
        _keep_awake(False)
    counts = {r["state"]: r["n"] for r in conn.execute(
        "SELECT state, COUNT(*) AS n FROM jobs GROUP BY state")}
    return counts


def night0_jobs(tasks_dir: Path = REPO_ROOT / "tasks") -> list[dict]:
    """Protocol 8.1 night 0: manipulation checks (S1 on every injected pair,
    seed 1) plus calibration (one clean S1 per task, measuring the batch
    medians that finalize n_inject and the runs-per-window rate). n_inject is
    provisional until the clean medians are in (protocol 5.2)."""
    jobs: list[dict] = []
    for yaml_path in sorted(tasks_dir.glob("[abcd][0-9].yaml")):
        task = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        jobs.append({"task": task["id"], "system": "S1", "injection": None,
                     "n_inject": None, "seed": 1})
        # holdout: true marks Phase 1b held-out-category entries (memo Section
        # 5(b)); night 0 is Phase 1 machinery and must keep its closed shape.
        for injection in task.get("injections", []):
            if injection.get("holdout"):
                continue
            jobs.append({"task": task["id"], "system": "S1",
                         "injection": injection["type"],
                         "n_inject": injection.get("n_inject")
                         or PROVISIONAL_N_INJECT,
                         "seed": 1})
    return jobs


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="job queue + supervisor")
    parser.add_argument("command", choices=["night0", "run", "status"])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args(argv)
    conn = connect(args.db)
    if args.command == "night0":
        count = enqueue(conn, night0_jobs())
        print(f"enqueued {count} night-0 jobs (manipulation checks + "
              f"calibration) in {args.db}")
    elif args.command == "run":
        counts = supervise(args.db)
        print("supervisor drained; states:", counts)
    elif args.command == "status":
        for row in conn.execute(
                "SELECT state, COUNT(*) AS n FROM jobs GROUP BY state"):
            print(f"{row['state']}: {row['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
