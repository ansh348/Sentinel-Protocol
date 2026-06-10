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


def test_evidence_hash_all_null_fallback():
    """D9(c): a pre-injection all-null NOISE must NOT suppress a
    post-injection all-null GENUINE — when every declared field is null the
    whole evidence object (including the floor) is hashed instead."""
    from conductor.run_one import Conductor

    tripwire = {"id": "tw_x", "evidence_fields": ["status_code", "sku"]}
    pre = {"status_code": None, "sku": None,
           "_status": 200, "_path": "/pricing/quote/WID-001",
           "_response_excerpt": '{"unit_price": 19.68}'}
    post = {"status_code": None, "sku": None,
            "_status": 404, "_path": "/pricing/quote/WID-001",
            "_response_excerpt": '{"error": "endpoint_deprecated"}'}
    assert Conductor._evidence_hash(tripwire, pre) != \
        Conductor._evidence_hash(tripwire, post)
    # identical evidence still dedupes
    assert Conductor._evidence_hash(tripwire, pre) == \
        Conductor._evidence_hash(tripwire, dict(pre))
    # and resolved declared fields keep governing materiality: floor noise
    # does not split otherwise-identical evidence
    resolved_a = {"status_code": 404, "sku": "WID-001", "_response_excerpt": "A"}
    resolved_b = {"status_code": 404, "sku": "WID-001", "_response_excerpt": "B"}
    assert Conductor._evidence_hash(tripwire, resolved_a) == \
        Conductor._evidence_hash(tripwire, resolved_b)


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
    assert parsed == esc and mode == "embedded_object"
    # a non-payload JSON object quoted in prose does not confuse the reader
    quoted = ('The response was {"error": "endpoint_deprecated"} so I stop.\n'
              + json.dumps(esc))
    assert parse_worker_message(quoted) == (esc, "embedded_object")
    # the same payload appearing twice (fenced and quoted) is one candidate
    twice = "```json\n" + json.dumps(esc) + "\n```\nAs stated: " + json.dumps(esc)
    assert parse_worker_message(twice)[0] == esc
    with pytest.raises(ValueError):
        parse_worker_message("no json here at all")


def test_parse_worker_message_rejects_distinct_candidates():
    """D10 tightening: two distinct schema-validating objects in one message
    is invalid_output — never pick one by tier order."""
    import json
    import pytest
    from conductor.run_one import parse_worker_message

    done = {"status": "done", "result": {"x": 1}}
    esc = {"status": "escalated", "tripwire_id": "tw_y", "evidence": {}}
    message = ("Earlier I produced " + json.dumps(done)
               + " but then:\n```json\n" + json.dumps(esc) + "\n```")
    with pytest.raises(ValueError, match="2 distinct"):
        parse_worker_message(message)


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


def _counts(events):
    from collections import Counter
    return Counter(e["event_type"] for e in events)


def test_s2_naive_interrupt_reaches_orchestrator_unjudged(tmp_path, conductor_env,
                                                          monkeypatch):
    conductor_env(escalate=False)
    monkeypatch.setenv("FAKE_WORKER_ESCALATE", "s2")
    summary = run_one(task_path=REPO_ROOT / "tasks" / "a1.yaml",
                      system_id="S2", runs_root=tmp_path)
    events = read_run(summary["run_dir"])
    counts = _counts(events)
    assert counts["judge_verdict"] == 0      # no filter tier
    assert counts["compile"] == 0            # no tripwires
    assert counts["tripwire_set"] == 0
    assert counts["escalation"] == 1
    assert counts["interrupt"] == 1          # straight to the orchestrator
    assert summary["replans"] == 1
    # the S2 anomaly clause is appended to every dispatched subtask
    starts = [e for e in events if e["event_type"] == "worker_start"]
    assert all("ANOMALY PROTOCOL" in e["payload"]["subtask"] for e in starts)


def test_s2_orchestrator_can_dismiss(tmp_path, conductor_env, monkeypatch):
    """M4 condition 1: dismiss/continue is a first-class interrupt verdict."""
    conductor_env(escalate=False)
    monkeypatch.setenv("FAKE_WORKER_ESCALATE", "s2")
    monkeypatch.setenv("FAKE_ORCH_INTERRUPT", "dismiss")
    summary = run_one(task_path=REPO_ROOT / "tasks" / "a1.yaml",
                      system_id="S2", runs_root=tmp_path)
    events = read_run(summary["run_dir"])
    counts = _counts(events)
    assert counts["dismissal"] == 1
    assert summary["replans"] == 0
    redispatches = [e["payload"] for e in events
                    if e["event_type"] == "redispatch"]
    assert any(r.get("after") == "dismissal" for r in redispatches)
    assert summary["reason"] is None         # the run ran to completion


def test_s4_fires_reach_orchestrator_unjudged(tmp_path, conductor_env,
                                              monkeypatch):
    conductor_env(escalate=True)
    summary = run_one(task_path=REPO_ROOT / "tasks" / "a1.yaml",
                      system_id="S4", runs_root=tmp_path)
    events = read_run(summary["run_dir"])
    counts = _counts(events)
    assert counts["judge_verdict"] == 0      # judge bypassed
    assert counts["escalation"] == 1
    assert counts["interrupt"] == 1
    assert counts["compile"] == 2            # recompile-on-replan applies to S4
    assert counts["tripwire_set"] == 2
    assert summary["replans"] == 1


def test_s3_heartbeat_tick_unit(tmp_path, conductor_env):
    """Unit-level: revalidation fires once per k-mark crossed; live S3 covers
    the integrated loop."""
    conductor_env(escalate=False)
    from conductor.run_one import Conductor
    conductor = Conductor(task_path=REPO_ROOT / "tasks" / "a1.yaml",
                          system_id="S3", runs_root=tmp_path, heartbeat_k=2)
    calls = []

    class FakeResponse:
        @staticmethod
        def json():
            return {"counter": 5}

    conductor._admin = lambda *a, **k: FakeResponse()
    conductor._orchestrator_turn = lambda msg, et: (
        calls.append((msg["mode"], et)) or {"verdict": "continue"})
    conductor._heartbeat_tick(None, {})
    assert calls == [("revalidate", "revalidation"), ("revalidate", "revalidation")]
    assert conductor._next_reval_mark == 6
    conductor._heartbeat_tick(None, {})  # counter unchanged: no new marks
    assert len(calls) == 2
    conductor.trace.close()


def test_noise_streak_installs_cooldown(tmp_path, conductor_env, monkeypatch):
    """D11: two consecutive NOISE-class instances on one tripwire install the
    world-side cooldown (visible as cooldown_installed on the redispatch)."""
    conductor_env(escalate=False)
    monkeypatch.setenv("FAKE_WORKER_ESCALATE", "always_w2_vary")
    monkeypatch.setenv("FAKE_JUDGE", "NOISE")
    summary = run_one(task_path=REPO_ROOT / "tasks" / "a1.yaml",
                      system_id="S5", runs_root=tmp_path, max_escalations=5)
    assert summary["reason"] == "escalation_loop"
    events = read_run(summary["run_dir"])
    noise_redispatches = [e["payload"] for e in events
                          if e["event_type"] == "redispatch"
                          and e["payload"].get("after") == "noise"]
    installed_flags = [r["cooldown_installed"] for r in noise_redispatches]
    assert installed_flags[0] is False, "K=1 must not cool down"
    assert any(installed_flags), "K=2 must install the cooldown"
    assert installed_flags.index(True) == 1, "cooldown installs exactly at K=2"
    judges = [e for e in events if e["event_type"] == "judge_verdict"]
    assert len(judges) >= 2  # varied evidence is judged fresh per D7


def test_replan_cap_marks_failed(tmp_path, conductor_env):
    conductor_env(escalate=True)
    summary = run_one(task_path=REPO_ROOT / "tasks" / "a1.yaml",
                      system_id="S5", runs_root=tmp_path, max_replans=0)
    assert summary["success"] is False
    assert summary["reason"] == "replan_loop"
    events = read_run(summary["run_dir"])
    run_end = [e for e in events if e["event_type"] == "run_end"][0]
    assert run_end["payload"]["reason"] == "replan_loop"
