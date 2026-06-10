"""Morning operations report (protocol 8.1, ops-vs-science rule): completions,
throttle events, failure rate, malformed traces — and NOTHING else. Gate
metrics are computed exactly once, by analysis/gates.py, when the planned
matrix completes."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from conductor.queue import DEFAULT_DB, connect


def malformed_trace_lines(run_dir: str | Path) -> int:
    count = 0
    for path in Path(run_dir).glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                json.loads(line)
            except ValueError:
                count += 1
    return count


def report(db_path: str | Path = DEFAULT_DB) -> str:
    conn = connect(db_path)
    lines = ["=== morning ops report (operations ONLY; gates compute once,",
             "    when the planned matrix is complete) ==="]
    counts = {r["state"]: r["n"] for r in conn.execute(
        "SELECT state, COUNT(*) AS n FROM jobs GROUP BY state")}
    total = sum(counts.values())
    lines.append(f"jobs: {total} total | " + " | ".join(
        f"{state}: {counts.get(state, 0)}"
        for state in ("done", "pending", "running", "throttled", "failed")))
    throttle_events = conn.execute(
        "SELECT COALESCE(SUM(attempts), 0) AS n FROM jobs").fetchone()["n"]
    lines.append(f"throttle events (total backoffs): {throttle_events}")
    finished = counts.get("done", 0) + counts.get("failed", 0)
    if finished:
        rate = counts.get("failed", 0) / finished
        lines.append(f"failure rate: {counts.get('failed', 0)}/{finished} "
                     f"({rate:.0%})")
    for row in conn.execute("SELECT id, task, system, injection, error FROM jobs"
                            " WHERE state='failed' ORDER BY id"):
        lines.append(f"  failed job {row['id']} {row['task']}/{row['system']}/"
                     f"{row['injection'] or 'clean'}: {(row['error'] or '')[:100]}")
    malformed_total = 0
    for row in conn.execute("SELECT run_dir FROM jobs WHERE run_dir IS NOT NULL"):
        if row["run_dir"] and Path(row["run_dir"]).exists():
            malformed_total += malformed_trace_lines(row["run_dir"])
    lines.append(f"malformed trace lines: {malformed_total}")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="morning ops report")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args(argv)
    print(report(args.db))
    return 0


if __name__ == "__main__":
    sys.exit(main())
