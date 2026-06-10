"""Offline end-to-end conductor tests: real world server subprocess, fake
claude binary in conductor mode. Live S1/S5 acceptance runs are executed
manually (they bill the subscription); these tests pin the control flow."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from conductor.run_one import run_one
from trace import read_run

REPO_ROOT = Path(__file__).resolve().parent.parent
FAKE = str(Path(__file__).parent / "fake_claude.py")


@pytest.fixture
def conductor_env(monkeypatch):
    def _set(escalate: bool = False):
        monkeypatch.setenv("TRIPWIRE_CLAUDE_BIN", f"{sys.executable};{FAKE}")
        monkeypatch.setenv("FAKE_CLAUDE_MODE", "conductor")
        if escalate:
            monkeypatch.setenv("FAKE_WORKER_ESCALATE", "1")
        else:
            monkeypatch.delenv("FAKE_WORKER_ESCALATE", raising=False)
    return _set


def test_parse_worker_message_extraction_modes():
    import json
    import pytest
    from conductor.run_one import parse_worker_message

    esc = {"status": "escalated", "tripwire_id": "tw_x", "evidence": {"s": 404}}
    assert parse_worker_message(json.dumps(esc)) == (esc, "exact")
    assert parse_worker_message("```json\n" + json.dumps(esc) + "\n```")[1] == "fence"
    # the exact live shape from S5 attempt 5: prose, then a fenced block
    prose = ("I've detected a tripwire_control that requires escalation. "
             "Following the control protocol, I must stop all work.\n\n"
             "```json\n" + json.dumps(esc) + "\n```")
    parsed, mode = parse_worker_message(prose)
    assert parsed == esc and mode == "embedded_fence"
    parsed, mode = parse_worker_message("Done. Result: " + json.dumps(esc))
    assert parsed == esc and mode == "trailing_json"
    with pytest.raises(ValueError):
        parse_worker_message("no json here at all")


def test_s1_batch_flow(tmp_path, conductor_env):
    conductor_env(escalate=False)
    summary = run_one(task_path=REPO_ROOT / "tasks" / "a1.yaml",
                      system_id="S1", runs_root=tmp_path)
    events = read_run(summary["run_dir"])
    types = [e["event_type"] for e in events]

    assert types.count("run_start") == 1 and types.count("run_end") == 1
    assert types.count("plan") == 1
    assert types.count("worker_start") == 3 and types.count("worker_end") == 3
    assert types.count("success_check") == 1
    # S1 has no sentinel machinery
    for absent in ("compile", "tripwire_set", "escalation", "judge_verdict",
                   "interrupt", "pause", "replan"):
        assert types.count(absent) == 0, absent
    # fake final report cannot match ground truth
    assert summary["success"] is False and summary["reason"] is None

    # amendment 5: the final aggregate event records used vs discarded
    agg = [e for e in events if e["event_type"] == "aggregate"][-1]
    assert set(agg["payload"]["used"]) == {"w1", "w2", "w3"}
    assert agg["payload"]["discarded"] == []


def test_s5_escalation_judge_pause_replan_recompile(tmp_path, conductor_env):
    conductor_env(escalate=True)
    summary = run_one(task_path=REPO_ROOT / "tasks" / "a1.yaml",
                      system_id="S5", runs_root=tmp_path)
    events = read_run(summary["run_dir"])
    types = [e["event_type"] for e in events]

    assert summary["replans"] == 1
    assert types.count("escalation") == 1
    assert types.count("judge_verdict") == 1
    assert types.count("interrupt") == 1
    assert types.count("pause") == 1
    assert types.count("replan") == 1
    assert types.count("redispatch") == 1
    # amendment 1: recompile on replan — two compiles, two armed sets
    assert types.count("compile") == 2
    assert types.count("tripwire_set") == 2
    # escalating worker w2 plus redispatched w2r1
    worker_ends = [e for e in events if e["event_type"] == "worker_end"]
    by_actor = {e["actor"]: e["payload"]["status"] for e in worker_ends}
    assert by_actor["w2"] == "escalated"
    assert by_actor["w2r1"] == "done"
    # event ordering: escalation -> judge -> interrupt -> replan -> recompile
    order = [t for t in types if t in
             ("escalation", "judge_verdict", "interrupt", "replan", "redispatch")]
    assert order == ["escalation", "judge_verdict", "interrupt", "replan",
                     "redispatch"]


def test_noise_dedup_by_evidence_hash(tmp_path, conductor_env, monkeypatch):
    """D7: identical (tripwire, evidence) is judged once; every further
    escalation of the pair is a suppressed_refire, not a judge call."""
    conductor_env(escalate=False)
    monkeypatch.setenv("FAKE_WORKER_ESCALATE", "always_w2")
    monkeypatch.setenv("FAKE_JUDGE", "NOISE")
    summary = run_one(task_path=REPO_ROOT / "tasks" / "a1.yaml",
                      system_id="S5", runs_root=tmp_path, max_escalations=4)
    assert summary["success"] is False
    assert summary["reason"] == "escalation_loop"
    events = read_run(summary["run_dir"])
    judge_calls = [e for e in events if e["event_type"] == "judge_verdict"]
    assert len(judge_calls) == 1, "identical evidence must be judged exactly once"
    refires = [e for e in events if e["event_type"] == "suppressed_refire"
               and e["payload"]["where"] == "conductor"]
    assert len(refires) >= 2
    assert all(r["payload"]["tripwire_id"] == "tw_pricing_endpoint_404"
               for r in refires)
    # all refires share the single adjudicated evidence hash
    assert len({r["payload"]["evidence_hash"] for r in refires}) == 1


def test_replan_cap_marks_failed(tmp_path, conductor_env):
    conductor_env(escalate=True)
    summary = run_one(task_path=REPO_ROOT / "tasks" / "a1.yaml",
                      system_id="S5", runs_root=tmp_path, max_replans=0)
    assert summary["success"] is False
    assert summary["reason"] == "replan_loop"
    events = read_run(summary["run_dir"])
    run_end = [e for e in events if e["event_type"] == "run_end"][0]
    assert run_end["payload"]["reason"] == "replan_loop"
