"""M5 acceptance: the queue survives throttles and resumes; a kill -9 of the
supervisor mid-run neither duplicates nor loses jobs; the CLI version pin
halts the matrix on change."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

from conductor.queue import (claim_next, connect, enqueue, night0_jobs,
                             recover_stale, supervise, trace_shows_throttle,
                             void_run)

FAKE = str(Path(__file__).parent / "fake_claude.py")


@pytest.fixture(autouse=True)
def offline_launcher(monkeypatch):
    """D21: supervise() fires a live launcher probe at startup; route every
    queue test's probe to the offline fake."""
    monkeypatch.setenv("TRIPWIRE_CLAUDE_BIN", f"{sys.executable};{FAKE}")
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "conductor")


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


def test_failed_job_persists_run_context(tmp_path):
    """CD-3 (author ruling 2026-06-10): a crash carrying run context must
    leave run_dir + accumulated cost on the failed row, so the morning ops
    scan sees the trace and the spend."""
    db = make_db(tmp_path)
    enqueue(connect(db), three_jobs()[:1])

    class ContextCrash(RuntimeError):
        def __init__(self, message, run_dir, cost_usd):
            super().__init__(message)
            self.run_dir = run_dir
            self.cost_usd = cost_usd

    def runner(job):
        raise ContextCrash("FileNotFoundError: [Errno 2] missing checker",
                           run_dir="runs/x-S1-clean-s1", cost_usd=0.1535)

    counts = supervise(db, runner=runner, poll_s=0.05)
    assert counts == {"failed": 1}
    row = connect(db).execute("SELECT * FROM jobs").fetchone()
    assert row["state"] == "failed"
    assert row["run_dir"] == "runs/x-S1-clean-s1"
    assert json.loads(row["note"])["cost_usd"] == 0.1535
    assert "FileNotFoundError" in row["error"]


def test_failed_job_without_context_keeps_old_shape(tmp_path):
    db = make_db(tmp_path)
    enqueue(connect(db), three_jobs()[:1])

    def runner(job):
        raise ValueError("boom")

    counts = supervise(db, runner=runner, poll_s=0.05)
    assert counts == {"failed": 1}
    row = connect(db).execute("SELECT * FROM jobs").fetchone()
    assert row["state"] == "failed"
    assert row["run_dir"] is None and row["note"] is None
    assert row["error"] == "ValueError: boom"


def test_launcher_guard_halts_on_multiline_mangling(tmp_path, monkeypatch):
    """D21: a launcher that eats flags (prose, exit 0, no envelope) must halt
    the supervisor before any claim — the version guard alone is blind."""
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "prose")
    db = make_db(tmp_path)
    enqueue(connect(db), three_jobs()[:1])
    with pytest.raises(RuntimeError, match="HALT: launcher mangles"):
        supervise(db, runner=lambda job: {"success": True, "run_dir": None})
    states = [r["state"] for r in connect(db).execute("SELECT state FROM jobs")]
    assert states == ["pending"], "nothing may be claimed past a failed guard"


def _write_trace(run_dir: Path, event_types: list[str]) -> None:
    from trace import TraceWriter
    run_dir.mkdir()
    writer = TraceWriter(run_dir / "trace.jsonl", run_id="r", seed=1,
                         system="S1", task_id="a1")
    for et in event_types:
        writer.emit(actor="x", event_type=et, payload={})
    writer.close()


def test_void_run_invariant_rejects_zero_call_done(tmp_path):
    """D21 permanent invariant: zero tool calls + no checker event is never
    accepted as done, whatever the runner summary claims."""
    db = make_db(tmp_path)
    enqueue(connect(db), three_jobs()[:1])
    run_dir = tmp_path / "void-run"
    _write_trace(run_dir, ["run_start", "plan", "error", "run_end"])

    counts = supervise(db, runner=lambda job: {
        "success": False, "reason": "orchestrator_invalid",
        "run_dir": str(run_dir), "cost_usd": 0.0}, poll_s=0.05)
    assert counts == {"failed": 1}
    row = connect(db).execute("SELECT * FROM jobs").fetchone()
    assert "void_run" in row["error"]
    assert row["run_dir"] == str(run_dir)


def test_real_work_run_is_still_done(tmp_path):
    db = make_db(tmp_path)
    enqueue(connect(db), three_jobs()[:1])
    run_dir = tmp_path / "real-run"
    _write_trace(run_dir, ["run_start", "plan", "tool_call", "tool_response",
                           "success_check", "run_end"])

    counts = supervise(db, runner=lambda job: {
        "success": True, "reason": None,
        "run_dir": str(run_dir), "cost_usd": 0.2}, poll_s=0.05)
    assert counts == {"done": 1}
    assert void_run({"run_dir": str(run_dir)}) is False
    assert void_run({"run_dir": None}) is False


def test_night0_enqueue_shape():
    jobs = night0_jobs()
    clean = [j for j in jobs if j["injection"] is None]
    injected = [j for j in jobs if j["injection"] is not None]
    assert len(clean) == 4          # one calibration run per archetype task
    assert len(injected) == 9       # every planned (task, injection) pair
    assert all(j["system"] == "S1" and j["seed"] == 1 for j in jobs)
    assert all(j["n_inject"] for j in injected)
