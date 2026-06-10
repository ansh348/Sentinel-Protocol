"""M6 acceptance: metrics unit-tested against four hand-constructed synthetic
traces with known answers (amendment 1):
  (a) batch with redo, (b) sentinel clean detect-judge-replan,
  (c) no-detection run (wasted work runs injection-to-end),
  (d) worker_noncompliance + suppressed_refire — suppression savings and
      noncompliance costs counted exactly once, in the right buckets."""
from __future__ import annotations

from pathlib import Path

from analysis.metrics import run_metrics
from trace import TraceWriter


def usage(tokens_in: int, tokens_out: int, cost: float) -> dict:
    return {"input_tokens": tokens_in, "output_tokens": tokens_out,
            "cost_usd": cost, "model": "claude-haiku-4-5-20251001",
            "session_id": "syn"}


def writer_for(tmp_path: Path, system: str) -> tuple[TraceWriter, Path]:
    run_dir = tmp_path / f"syn-{system}"
    run_dir.mkdir()
    w = TraceWriter(run_dir / "trace.jsonl", run_id=f"syn-{system}", seed=1,
                    system=system, task_id="a1")
    return w, run_dir


def call(w, actor, counter, path, status, method="GET"):
    w.emit(actor=actor, event_type="tool_call",
           payload={"counter": counter, "method": method, "path": path,
                    "query": "", "body": None})
    w.emit(actor=actor, event_type="tool_response",
           payload={"counter": counter, "status": status, "body": {}})


def test_a_batch_with_redo(tmp_path):
    w, run_dir = writer_for(tmp_path, "S1")
    w.emit(actor="conductor", event_type="run_start", payload={})
    w.emit(actor="orchestrator", event_type="plan", payload={})
    w.emit(actor="w1", event_type="worker_start", payload={"subplan_id": "s2"})
    w.emit(actor="w2", event_type="worker_start", payload={"subplan_id": "s3"})
    for c, (actor, path) in enumerate(
            [("w1", "/inventory/items"), ("w1", "/inventory/items/WID-001"),
             ("w1", "/inventory/items/GAD-001"),
             ("w2", "/auth/token")], start=1):
        call(w, actor, c, path, 200)
    w.emit(actor="world", event_type="injection_fired",
           payload={"trigger": "counter", "counter": 5,
                    "injection": {"type": "endpoint_404",
                                  "path": "/pricing/quote/*"}})
    call(w, "w2", 5, "/pricing/quote/WID-001", 404)
    call(w, "w2", 6, "/pricing/quote/GAD-001", 404)
    w.emit(actor="w1", event_type="worker_end",
           payload={"status": "done"}, usage=usage(1000, 200, 0.010))
    w.emit(actor="w2", event_type="worker_end",
           payload={"status": "blocked"}, usage=usage(800, 100, 0.008))
    w.emit(actor="orchestrator", event_type="aggregate",
           payload={"mode": "aggregate", "reply": {"redo": ["..."]}})
    w.emit(actor="conductor", event_type="redispatch", payload={"after": "redo"})
    w.emit(actor="w2r1", event_type="worker_start", payload={"subplan_id": "s3"})
    call(w, "w2r1", 7, "/pricing/quote/WID-001", 404)
    w.emit(actor="w2r1", event_type="worker_end",
           payload={"status": "blocked"}, usage=usage(500, 50, 0.005))
    w.emit(actor="orchestrator", event_type="aggregate",
           payload={"used": ["w1"], "discarded": ["w2", "w2r1"],
                    "final_report": {}})
    w.emit(actor="conductor", event_type="success_check",
           payload={"success": False, "detail": "prices missing"})
    w.emit(actor="conductor", event_type="run_end", payload={"success": False})
    w.close()

    m = run_metrics(run_dir)
    assert m["injected"] and m["injection"] == "endpoint_404"
    assert m["detected"] is False and m["ttd_tool_calls"] is None
    # S1 window: injection -> FIRST aggregate. calls 5 and 6 inside.
    assert m["wasted"]["tool_calls"] == 2
    # w1+w2 sessions end inside the window (1200 + 900); w2r1 ends after it
    # but is aggregate-marked discarded -> counted ONCE in the discarded bucket
    assert m["wasted"]["window_workers"] == ["w1", "w2"]
    assert m["wasted"]["discarded_workers"] == ["w2r1"]
    assert m["wasted"]["tokens"] == 1200 + 900 + 550
    assert abs(m["wasted"]["usd"] - 0.023) < 1e-9
    assert m["interrupts"] == {"total": 0, "false": 0, "fir": None}
    assert m["success"] is False


def test_b_sentinel_detect_judge_replan(tmp_path):
    w, run_dir = writer_for(tmp_path, "S5")
    w.emit(actor="conductor", event_type="run_start", payload={})
    w.emit(actor="orchestrator", event_type="plan", payload={})
    w.emit(actor="sentinel", event_type="compile", payload={"valid": True},
           usage=usage(4000, 1500, 0.05))
    w.emit(actor="sentinel", event_type="tripwire_set", payload={"count": 1})
    w.emit(actor="w2", event_type="worker_start", payload={"subplan_id": "s3"})
    for c in (1, 2, 3):
        call(w, "w2", c, "/auth/token" if c == 1 else "/inventory/items", 200)
    w.emit(actor="world", event_type="injection_fired",
           payload={"trigger": "counter", "counter": 4,
                    "injection": {"type": "endpoint_404",
                                  "path": "/pricing/quote/*"}})
    w.emit(actor="w2", event_type="tool_call",
           payload={"counter": 4, "method": "GET",
                    "path": "/pricing/quote/WID-001", "query": "", "body": None})
    w.emit(actor="world", event_type="tripwire_fire",
           payload={"counter": 4, "tripwire_id": "tw_p", "severity": "CRITICAL",
                    "on_trigger": "PAUSE_AND_REPLAN", "log_only": False,
                    "path": "/pricing/quote/WID-001", "status": 404,
                    "worker_id": "w2"})
    w.emit(actor="w2", event_type="tool_response",
           payload={"counter": 4, "status": 404, "body": {}})
    w.emit(actor="w2", event_type="worker_end",
           payload={"status": "escalated"}, usage=usage(600, 60, 0.006))
    w.emit(actor="w2", event_type="escalation",
           payload={"tripwire_id": "tw_p",
                    "evidence": {"_path": "/pricing/quote/WID-001",
                                 "_status": 404}, "subplan_id": "s3"})
    w.emit(actor="judge", event_type="judge_verdict",
           payload={"valid": True, "verdict": {"verdict": "GENUINE"}},
           usage=usage(800, 80, 0.002))
    w.emit(actor="conductor", event_type="pause",
           payload={"scope": "local", "affected_subplans": ["s3"],
                    "paused_workers": [], "escalating_worker": "w2"})
    w.emit(actor="conductor", event_type="interrupt",
           payload={"tripwire": {"id": "tw_p"}})
    w.emit(actor="orchestrator", event_type="replan",
           payload={"valid": True, "reply": {"revision": 1}})
    w.emit(actor="conductor", event_type="redispatch", payload={"after": "replan"})
    w.emit(actor="w2r1", event_type="worker_start", payload={"subplan_id": "s3"})
    call(w, "w2r1", 5, "/pricing/quotes", 200)
    w.emit(actor="w2r1", event_type="worker_end",
           payload={"status": "done"}, usage=usage(400, 40, 0.004))
    w.emit(actor="orchestrator", event_type="aggregate",
           payload={"used": ["w2r1"], "discarded": ["w2"], "final_report": {}})
    w.emit(actor="conductor", event_type="success_check",
           payload={"success": True, "detail": "ok"})
    w.emit(actor="conductor", event_type="run_end", payload={"success": True})
    w.close()

    m = run_metrics(run_dir)
    assert m["detected"] is True
    assert m["ttd_tool_calls"] == 0          # pause at counter 4 == injection
    assert m["wasted"]["tool_calls"] == 1    # only call 4 inside the window
    # w2 ends inside the window; its aggregate-discard must NOT double count
    assert m["wasted"]["window_workers"] == ["w2"]
    assert m["wasted"]["discarded_workers"] == []
    assert m["wasted"]["tokens"] == 660
    assert m["interrupts"] == {"total": 1, "false": 0, "fir": 0.0}
    assert m["success"] is True


def test_c_no_detection_runs_to_end(tmp_path):
    w, run_dir = writer_for(tmp_path, "S5")
    w.emit(actor="conductor", event_type="run_start", payload={})
    w.emit(actor="w1", event_type="worker_start", payload={"subplan_id": "s2"})
    call(w, "w1", 1, "/auth/token", 200, method="POST")
    call(w, "w1", 2, "/inventory/items", 200)
    w.emit(actor="world", event_type="injection_fired",
           payload={"trigger": "counter", "counter": 3,
                    "injection": {"type": "schema_drift", "target": "pricing"}})
    call(w, "w1", 3, "/pricing/quote/WID-001", 200)
    call(w, "w1", 4, "/pricing/quote/GAD-001", 200)
    call(w, "w1", 5, "/shipping/rates/WID-001", 200)
    w.emit(actor="w1", event_type="worker_end",
           payload={"status": "blocked"}, usage=usage(700, 300, 0.009))
    w.emit(actor="orchestrator", event_type="aggregate",
           payload={"used": [], "discarded": ["w1"], "final_report": {}})
    w.emit(actor="conductor", event_type="success_check",
           payload={"success": False, "detail": "bad"})
    w.emit(actor="conductor", event_type="run_end", payload={"success": False})
    w.close()

    m = run_metrics(run_dir)
    assert m["detected"] is False
    # amendment 1c: no detection and not S1 -> window runs injection-to-END
    assert m["wasted"]["tool_calls"] == 3    # calls 3, 4, 5
    assert m["wasted"]["window_workers"] == ["w1"]
    assert m["wasted"]["discarded_workers"] == []  # already counted once
    assert m["wasted"]["tokens"] == 1000


def test_d_noncompliance_and_suppression_buckets(tmp_path):
    w, run_dir = writer_for(tmp_path, "S5")
    w.emit(actor="conductor", event_type="run_start", payload={})
    w.emit(actor="w2", event_type="worker_start", payload={"subplan_id": "s3"})
    call(w, "w2", 1, "/auth/token", 200, method="POST")
    w.emit(actor="world", event_type="injection_fired",
           payload={"trigger": "counter", "counter": 2,
                    "injection": {"type": "endpoint_404",
                                  "path": "/pricing/quote/*"}})
    call(w, "w2", 2, "/pricing/quote/WID-001", 404)
    w.emit(actor="w2", event_type="worker_end",
           payload={"status": "escalated"}, usage=usage(500, 50, 0.005))
    w.emit(actor="w2", event_type="escalation",
           payload={"tripwire_id": "tw_p",
                    "evidence": {"_path": "/pricing/quote/WID-001",
                                 "_status": 404}, "subplan_id": "s3"})
    w.emit(actor="judge", event_type="judge_verdict",
           payload={"valid": True, "verdict": {"verdict": "NOISE"}},
           usage=usage(800, 80, 0.002))
    w.emit(actor="conductor", event_type="redispatch", payload={"after": "noise"})
    w.emit(actor="w2r1", event_type="worker_start", payload={"subplan_id": "s3"})
    # a tripped worker keeps calling: ONE tool_call + the noncompliance marker
    w.emit(actor="w2r1", event_type="tool_call",
           payload={"counter": 3, "method": "GET", "path": "/inventory/items",
                    "query": "", "body": None})
    w.emit(actor="w2r1", event_type="worker_noncompliance",
           payload={"counter": 3, "path": "/inventory/items",
                    "tripwire_id": "tw_p"})
    w.emit(actor="w2r1", event_type="tool_response",
           payload={"counter": 3, "status": 409, "body": {}})
    # policy savings: one conductor dedup, one matcher suppression
    w.emit(actor="conductor", event_type="suppressed_refire",
           payload={"where": "conductor", "tripwire_id": "tw_p",
                    "evidence_hash": "x", "worker_id": "w2r1",
                    "subplan_id": "s3"})
    w.emit(actor="world", event_type="suppressed_refire",
           payload={"where": "matcher", "counter": 3, "tripwire_id": "tw_p",
                    "path": "/inventory/items", "status": 200,
                    "worker_id": "w2r1"})
    w.emit(actor="w2r1", event_type="worker_end",
           payload={"status": "escalated"}, usage=usage(300, 30, 0.003))
    w.emit(actor="orchestrator", event_type="aggregate",
           payload={"used": [], "discarded": ["w2", "w2r1"],
                    "final_report": {}})
    w.emit(actor="conductor", event_type="success_check",
           payload={"success": False, "detail": "bad"})
    w.emit(actor="conductor", event_type="run_end", payload={"success": False})
    w.close()

    m = run_metrics(run_dir)
    # noncompliance 409s carry exactly one tool_call each: calls 2 and 3 only;
    # suppressed_refire events add NO tool calls
    assert m["wasted"]["tool_calls"] == 2
    # both workers in the window; the discarded marking adds nothing twice
    assert m["wasted"]["window_workers"] == ["w2", "w2r1"]
    assert m["wasted"]["discarded_workers"] == []
    assert m["wasted"]["tokens"] == 550 + 330
    # savings and costs in their own buckets, counted exactly once
    assert m["policy"]["suppressed_refires"] == {"conductor": 1, "matcher": 1}
    assert m["policy"]["worker_noncompliance"] == 1
    assert m["interrupts"]["total"] == 0     # NOISE never interrupted
    assert m["detected"] is False
