"""M5 acceptance: the queue survives throttles and resumes; a kill -9 of the
supervisor mid-run neither duplicates nor loses jobs; the CLI version pin
halts the matrix on change."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from conductor.queue import (claim_next, connect, enqueue, night0_jobs,
                             recover_stale, supervise, trace_shows_throttle)


def make_db(tmp_path) -> Path:
    return tmp_path / "queue.sqlite"


def three_jobs() -> list[dict]:
    return [{"task": "a1", "system": "S1", "injection": None, "seed": s}
            for s in (1, 2, 3)]


def test_throttle_backoff_and_resume(tmp_path):
    db = make_db(tmp_path)
    enqueue(connect(db), three_jobs())
    executions: list[tuple[int, int]] = []
    throttle_once = {"left": 1}

    def runner(job):
        executions.append((job["id"], job["attempts"]))
        if job["seed"] == 1 and throttle_once["left"]:
            throttle_once["left"] -= 1
            raise RuntimeError("Error: rate limit exceeded (429)")
        return {"success": True, "reason": None, "run_dir": None,
                "cost_usd": 0.0}

    counts = supervise(db, runner=runner, poll_s=0.05, backoff_base_s=0.05)
    assert counts == {"done": 3}
    conn = connect(db)
    job1 = conn.execute("SELECT * FROM jobs WHERE seed=1").fetchone()
    assert job1["state"] == "done"
    assert job1["attempts"] == 1  # exactly one throttle backoff
    # the throttled job ran twice, the others once: nothing lost, no extras
    assert len(executions) == 4


def test_kill9_recovery_no_duplicate_no_loss(tmp_path):
    db = make_db(tmp_path)
    conn = connect(db)
    enqueue(conn, three_jobs())
    # simulate a supervisor killed mid-run: job claimed by a dead token
    conn.execute("UPDATE jobs SET state='running', claim_token='dead-supervisor'"
                 " WHERE seed=2")
    executions = []

    def runner(job):
        executions.append(job["seed"])
        return {"success": True, "reason": None, "run_dir": None,
                "cost_usd": 0.0}

    counts = supervise(db, runner=runner, poll_s=0.05)
    assert counts == {"done": 3}
    assert sorted(executions) == [1, 2, 3], "each job exactly once"


def test_cli_version_change_halts(tmp_path):
    db = make_db(tmp_path)
    conn = connect(db)
    enqueue(conn, three_jobs())
    conn.execute("INSERT INTO meta (key, value) VALUES ('cli_version',"
                 " 'pinned-other-version')")
    with pytest.raises(RuntimeError, match="HALT.*version"):
        supervise(db, runner=lambda job: {"success": True, "run_dir": None})
    # nothing ran; jobs intact
    states = [r["state"] for r in connect(db).execute("SELECT state FROM jobs")]
    assert states == ["pending"] * 3


def test_trace_throttle_detection(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    from trace import TraceWriter
    writer = TraceWriter(run_dir / "trace.jsonl", run_id="r", seed=1,
                         system="S1", task_id="a1")
    writer.emit(actor="w1", event_type="worker_end",
                payload={"status": "failed",
                         "stderr": "Error: usage limit reached for this window"})
    writer.close()
    assert trace_shows_throttle(run_dir) is True

    clean_dir = tmp_path / "clean"
    clean_dir.mkdir()
    writer = TraceWriter(clean_dir / "trace.jsonl", run_id="r", seed=1,
                         system="S1", task_id="a1")
    writer.emit(actor="w1", event_type="worker_end",
                payload={"status": "done", "stderr": ""})
    writer.close()
    assert trace_shows_throttle(clean_dir) is False


def test_claim_is_exclusive(tmp_path):
    db = make_db(tmp_path)
    conn = connect(db)
    enqueue(conn, three_jobs())
    a = claim_next(conn, "tok-a")
    b = claim_next(conn, "tok-b")
    assert a["id"] != b["id"]
    # recover_stale with token a's perspective frees ONLY b's claim
    freed = recover_stale(conn, "tok-a")
    assert freed == 1


def test_night0_enqueue_shape():
    jobs = night0_jobs()
    clean = [j for j in jobs if j["injection"] is None]
    injected = [j for j in jobs if j["injection"] is not None]
    assert len(clean) == 4          # one calibration run per archetype task
    assert len(injected) == 9       # every planned (task, injection) pair
    assert all(j["system"] == "S1" and j["seed"] == 1 for j in jobs)
    assert all(j["n_inject"] for j in injected)
