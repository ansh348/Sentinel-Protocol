"""D20 acceptance: strict orchestrator reply validation. The night-0 failure
class — plan-shaped aggregate replies silently coerced to empty — must be
REJECTED, re-prompted with the fixed template (max 2), logged as first-class
reply_rejected events, never semantically translated; persistent violation
fails the run loudly with reason reply_schema_violation."""
from __future__ import annotations

from pathlib import Path

import pytest

from conductor.run_one import (AggregateReply, Conductor, Continue, Dismiss,
                               Plan, ReplyRejected, RunAbort,
                               validate_aggregate_reply,
                               validate_interrupt_reply, validate_plan_reply,
                               validate_revalidation_reply)
from trace import read_trace

REPO_ROOT = Path(__file__).resolve().parent.parent

# the literal night-0 dialect error: a redo request expressed as a plan
PLAN_SHAPED = {
    "plan_id": "price-avail-001", "revision": 1,
    "steps": [{"subplan_id": "s3a", "worker_id": "w4", "subtask": "redo"}],
    "aggregation": "combine",
}
GOOD_AGG = {"final_report": {"ok": True}, "used": ["w1"], "discarded": [],
            "redo": []}


def test_plan_shaped_aggregate_reply_is_rejected_not_coerced():
    with pytest.raises(ReplyRejected, match="aggregate schema"):
        validate_aggregate_reply(PLAN_SHAPED, redo_permitted=True)


def test_empty_aggregate_reply_is_rejected():
    for empty in ({}, {"used": ["w1"]}, {"final_report": None, "redo": []}):
        with pytest.raises(ReplyRejected, match="empty"):
            validate_aggregate_reply(empty, redo_permitted=True)


def test_redo_only_aggregate_requires_permission():
    redo_only = {"final_report": None,
                 "redo": [{"subplan_id": "s1", "worker_id": "w1",
                           "subtask": "x"}]}
    reply = validate_aggregate_reply(redo_only, redo_permitted=True)
    assert len(reply.redo) == 1
    with pytest.raises(ReplyRejected, match="not permitted"):
        validate_aggregate_reply(redo_only, redo_permitted=False)


def test_reply_schemas_forbid_extras():
    with pytest.raises(ReplyRejected):
        validate_aggregate_reply({**GOOD_AGG, "note": "hi"},
                                 redo_permitted=False)
    with pytest.raises(ReplyRejected):
        validate_plan_reply({**PLAN_SHAPED, "confidence": 0.9})


def test_interrupt_reply_exactly_one_sanctioned_shape():
    assert isinstance(validate_interrupt_reply(
        {"verdict": "dismiss", "reason": "noise"}), Dismiss)
    assert isinstance(validate_interrupt_reply(PLAN_SHAPED), Plan)
    with pytest.raises(ReplyRejected, match="no sanctioned shape"):
        validate_interrupt_reply({"verdict": "dismiss", "confidence": 0.9})
    with pytest.raises(ReplyRejected):
        validate_interrupt_reply({"verdict": "continue"})


def test_revalidation_reply_shapes():
    assert isinstance(validate_revalidation_reply({"verdict": "continue"}),
                      Continue)
    assert isinstance(validate_revalidation_reply(PLAN_SHAPED), Plan)
    with pytest.raises(ReplyRejected):
        validate_revalidation_reply({"verdict": "continue", "extra": 1})


def _conductor(tmp_path):
    return Conductor(task_path=REPO_ROOT / "tasks" / "a1.yaml",
                     system_id="S1", runs_root=tmp_path)


def test_reprompt_recovers_and_logs(tmp_path):
    conductor = _conductor(tmp_path)
    replies = [dict(PLAN_SHAPED), dict(GOOD_AGG)]
    seen = []

    def fake_turn(msg, et, schema_reprompt=None):
        seen.append((msg.get("mode"), msg.get("schema_error"), schema_reprompt))
        return replies.pop(0)

    conductor._orchestrator_turn = fake_turn
    reply = conductor.aggregate(redo_permitted=True)
    assert isinstance(reply, AggregateReply)
    assert reply.final_report == {"ok": True}
    # the re-prompt carries the fixed template, same mode, attempt marker
    assert seen[0] == ("aggregate", None, None)
    assert seen[1][0] == "aggregate" and seen[1][2] == 1
    assert seen[1][1].startswith("SCHEMA ERROR")
    assert "final_report" in seen[1][1]  # the restated schema

    events = list(read_trace(conductor.run_dir / "trace.jsonl"))
    rejected = [e for e in events if e["event_type"] == "reply_rejected"]
    assert len(rejected) == 1
    assert rejected[0]["payload"]["mode"] == "aggregate"
    assert rejected[0]["payload"]["attempt"] == 1
    assert "plan_id" in rejected[0]["payload"]["reply_keys"]
    conductor.trace.close()


def test_persistent_violation_fails_loudly(tmp_path):
    conductor = _conductor(tmp_path)
    conductor._orchestrator_turn = lambda msg, et, **kw: dict(PLAN_SHAPED)
    with pytest.raises(RunAbort) as excinfo:
        conductor.aggregate(redo_permitted=True)
    assert excinfo.value.reason == "reply_schema_violation"

    events = list(read_trace(conductor.run_dir / "trace.jsonl"))
    rejections = [e for e in events if e["event_type"] == "reply_rejected"]
    assert [e["payload"]["attempt"] for e in rejections] == [1, 2, 3]
    conductor.trace.close()
