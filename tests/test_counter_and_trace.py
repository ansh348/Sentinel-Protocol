"""M1 acceptance: the middleware counts tool calls, fires the counter-triggered
injection at exactly N_inject, and writes Section 6 trace events from day one."""
from __future__ import annotations

import pytest

from conftest import auth_headers, get_token
from trace import EVENT_TYPES, TraceWriter, read_trace
from world.injections import DEPRECATION_BODY

REQUIRED_FIELDS = ("ts", "run_id", "seed", "system", "task_id", "actor",
                   "event_type", "payload")


def test_excluded_paths_do_not_count(make_world):
    world = make_world()
    world.client.get("/health")
    world.client.get("/openapi.json")
    assert world.client.get("/admin/state").json()["counter"] == 0

    get_token(world.client)
    assert world.client.get("/admin/state").json()["counter"] == 1


def test_injection_fires_at_exact_counter(make_world):
    world = make_world(
        n_inject=3,
        injection={"type": "endpoint_404", "params": {"path": "/pricing/quote/*"}},
    )
    h = auth_headers(get_token(world.client))                       # call 1

    pre = world.client.get("/pricing/quote/WID-001", headers=h)     # call 2
    assert pre.status_code == 200

    at = world.client.get("/pricing/quote/WID-001", headers=h)      # call 3: fires
    assert at.status_code == 404
    assert at.json() == DEPRECATION_BODY

    post = world.client.get("/pricing/quote/WID-001", headers=h)    # call 4
    assert post.status_code == 404

    admin = world.client.get("/admin/state").json()
    assert admin["injection_fired"] is True
    assert admin["injection_fired_at"] == 3

    events = read_trace(world.trace_path)
    fired = [e for e in events if e["event_type"] == "injection_fired"]
    assert len(fired) == 1
    assert fired[0]["payload"]["trigger"] == "counter"
    assert fired[0]["payload"]["counter"] == 3
    assert fired[0]["payload"]["injection"]["type"] == "endpoint_404"
    assert fired[0]["actor"] == "world"

    calls = [e for e in events if e["event_type"] == "tool_call"]
    responses = [e for e in events if e["event_type"] == "tool_response"]
    assert [c["payload"]["counter"] for c in calls] == [1, 2, 3, 4]
    assert [r["payload"]["status"] for r in responses] == [200, 200, 404, 404]


def test_trace_events_are_well_formed(make_world):
    world = make_world()
    h = auth_headers(get_token(world.client))
    world.client.get("/inventory/items", headers=h)
    world.client.put("/repo/files/src/x.py", json={"content": "pass\n"},
                     headers={"X-Worker-Id": "w2"})

    events = read_trace(world.trace_path)
    assert events, "trace must not be empty"
    for event in events:
        for field in REQUIRED_FIELDS:
            assert field in event, f"missing {field}: {event}"
        assert event["event_type"] in EVENT_TYPES
        assert event["run_id"] == world.config.run_id
        assert event["seed"] == world.config.seed
        assert event["system"] == "test"
        assert event["task_id"] == "t0"

    # actor is the X-Worker-Id header; request bodies are captured
    put_call = next(e for e in events if e["event_type"] == "tool_call"
                    and e["payload"]["method"] == "PUT")
    assert put_call["actor"] == "w2"
    assert put_call["payload"]["body"] == {"content": "pass\n"}


def test_admin_injection_records_trigger_and_counter(make_world):
    world = make_world()
    get_token(world.client)  # counter -> 1
    world.client.post("/admin/inject", json={"type": "token_expiry", "params": {}})

    events = read_trace(world.trace_path)
    fired = [e for e in events if e["event_type"] == "injection_fired"]
    assert len(fired) == 1
    assert fired[0]["payload"]["trigger"] == "admin"
    assert fired[0]["payload"]["counter"] == 1
    assert fired[0]["actor"] == "admin"


def test_trace_writer_validation(tmp_path):
    writer = TraceWriter(tmp_path / "t.jsonl", run_id="r", seed=1, system="S5",
                         task_id="a1")
    with pytest.raises(ValueError, match="unknown event_type"):
        writer.emit(actor="x", event_type="not_an_event", payload={})
    with pytest.raises(ValueError, match="usage payload missing"):
        writer.emit(actor="x", event_type="compile", payload={},
                    usage={"input_tokens": 1})
    writer.emit(actor="sentinel", event_type="compile", payload={"ok": True},
                usage={"input_tokens": 10, "output_tokens": 5, "cost_usd": 0.001,
                       "model": "claude-sonnet-4-6", "session_id": "s1"})
    writer.close()

    events = read_trace(tmp_path / "t.jsonl")
    assert len(events) == 1
    assert events[0]["usage"]["model"] == "claude-sonnet-4-6"
