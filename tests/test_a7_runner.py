"""Offline validation of the A7 runner control logic (analysis/a7_runner.py): frozen run
order, per-cell M6 qualification gate, hard $15 cap, resume, and chunk boundary. Uses a
mock executor -- no live cell, no spend."""
from __future__ import annotations

import analysis.a7_runner as R


def _mock_exec(sink, *, cost=0.01, qual_fail=(), fir_success=True):
    def _exec(job):
        sink.append(job.key)
        success = ((job.task, job.noise_class) not in qual_fail
                   if job.phase == "qual" else fir_success)
        return {"success": success, "cost_usd": cost,
                "run_dir": f"runs/a7/{job.key}", "reason": None,
                "noise_landed_on": ({"landed_on": "token"} if job.noise_class ==
                                    "transient_500" else None)}
    return _exec


# -- frozen order / shape ------------------------------------------------------------------

def test_build_jobs_shape_and_order():
    jobs = R.build_jobs()
    assert len(jobs) == 36
    assert sum(j.phase == "qual" for j in jobs) == 12
    assert sum(j.phase == "fir" for j in jobs) == 24
    assert all(j.phase == "qual" for j in jobs[:12])            # S1 qualification first
    fir = [j for j in jobs if j.phase == "fir"]
    assert [j.noise_class for j in fir[:8]] == ["transient_500"] * 8   # class order §6.1
    assert [j.noise_class for j in fir[8:16]] == ["additive_field"] * 8
    assert [j.noise_class for j in fir[16:24]] == ["latency_spike"] * 8
    tr = [j for j in fir if j.noise_class == "transient_500"]
    assert [j.arm for j in tr] == ["V2"] * 4 + ["S2"] * 4       # V2 then S2


def test_full_run_executes_in_frozen_order(tmp_path):
    order = []
    status = R.run_matrix(_mock_exec(order), ledger_path=tmp_path / "l.jsonl", cap=100.0)
    assert status["matrix_complete"]
    assert status["ran_this_chunk"] == 36
    assert order == [j.key for j in R.build_jobs()]


# -- per-cell M6 qualification gate --------------------------------------------------------

def test_disqualified_cell_skips_only_its_fir(tmp_path):
    order = []
    ledger = tmp_path / "l.jsonl"
    R.run_matrix(_mock_exec(order, qual_fail={("a1", "transient_500")}),
                 ledger_path=ledger, cap=100.0)
    # the disqualified cell's V2/S2 never execute...
    assert "fir:a1:transient_500:V2:s4" not in order
    assert "fir:a1:transient_500:S2:s4" not in order
    # ...but the same class survives on other tasks, and other classes on a1 are unaffected
    assert "fir:b1:transient_500:V2:s7" in order
    assert "fir:a1:additive_field:V2:s6" in order
    dq = {e["key"] for e in R.load_ledger(ledger) if e["status"] == "disqualified"}
    assert dq == {"fir:a1:transient_500:V2:s4", "fir:a1:transient_500:S2:s4"}


# -- hard cap ------------------------------------------------------------------------------

def test_cap_hard_stops_before_exceeding(tmp_path):
    order = []
    # per-job cost == reserve, so the ceiling holds exactly: no started job can exceed cap.
    status = R.run_matrix(_mock_exec(order, cost=R.PER_RUN_RESERVE_USD),
                          ledger_path=tmp_path / "l.jsonl", cap=3.0)
    assert status["reason"] == "cap"
    assert not status["matrix_complete"]
    assert status["cost_usd"] <= 3.0                 # never exceeded the ceiling
    assert 0 < status["ran_this_chunk"] < 36         # partial


# -- resume --------------------------------------------------------------------------------

def test_resume_skips_completed_and_carries_cost(tmp_path):
    ledger = tmp_path / "l.jsonl"
    order1 = []
    R.run_matrix(_mock_exec(order1, cost=R.PER_RUN_RESERVE_USD), ledger_path=ledger, cap=3.0)
    order2 = []
    status = R.run_matrix(_mock_exec(order2), ledger_path=ledger, cap=100.0)
    assert set(order1) & set(order2) == set()        # nothing re-run
    assert status["matrix_complete"]                 # resume finishes the matrix
    # cumulative cost carried across chunks (chunk-1 jobs + chunk-2 jobs)
    assert status["cost_usd"] > 0


# -- chunk time budget ---------------------------------------------------------------------

def test_chunk_time_budget_exits_and_is_resumable(tmp_path):
    ledger = tmp_path / "l.jsonl"
    t = {"v": 0.0}

    def clk():
        v = t["v"]
        t["v"] += 300.0
        return v

    order = []
    status = R.run_matrix(_mock_exec(order), ledger_path=ledger, cap=100.0,
                          time_budget_s=500.0, clock=clk)
    assert status["reason"] == "chunk_time"
    assert not status["matrix_complete"]
    assert status["ran_this_chunk"] >= 1
    # resume completes with a fresh (large) time budget
    status2 = R.run_matrix(_mock_exec([]), ledger_path=ledger, cap=100.0)
    assert status2["matrix_complete"]
