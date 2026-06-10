"""Offline tests for sentinel compile/judge wrappers: rendering, validation,
and the pre-registered one-retry-on-schema-invalid behavior (M2 acceptance)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from fake_claude import VALID_TRIPWIRE_SET
from sentinel.compile import (compile_tripwires, parse_tripwire_set,
                              plan_text_from_task, render_compile_prompt)
from sentinel.judge import judge_escalation, render_judge_prompt
from trace import TraceWriter, read_trace

FAKE_ARGV = [sys.executable, str(Path(__file__).parent / "fake_claude.py")]


def make_trace(tmp_path) -> TraceWriter:
    return TraceWriter(tmp_path / "trace.jsonl", run_id="t", seed=0,
                       system="test", task_id="a1")


def fake_kwargs() -> dict:
    return dict(claude_argv=FAKE_ARGV, token="offline")


# -- rendering ---------------------------------------------------------------

def test_render_compile_prompt_replaces_placeholders_only():
    rendered = render_compile_prompt("PLAN BODY HERE", "CONTEXT BODY HERE")
    for placeholder in ("{schema_json}", "{plan}", "{task_context}"):
        assert placeholder not in rendered
    assert "PLAN BODY HERE" in rendered
    assert "CONTEXT BODY HERE" in rendered
    assert '"title":"TripwireSet"' in rendered  # schema embedded
    # frozen template's literal JSON braces survive (str.format would mangle them)
    assert '"status_in": [404, 410]' in rendered


def test_render_judge_prompt():
    rendered = render_judge_prompt({"id": "tw_x"}, {"status": 404}, "the plan")
    for placeholder in ("{tripwire}", "{evidence}", "{plan_summary}"):
        assert placeholder not in rendered
    assert '{"id":"tw_x"}' in rendered
    assert '"verdict": "GENUINE" | "NOISE"' in rendered  # frozen output spec intact


def test_plan_text_from_task():
    task = {"goal": "Do the thing.", "plan": [
        {"subplan_id": "s1", "step": "First."},
        {"subplan_id": "s2", "step": "Second."}]}
    text = plan_text_from_task(task)
    assert "1. [s1] First." in text and "2. [s2] Second." in text


# -- validation --------------------------------------------------------------

def test_parse_tripwire_set():
    import json
    parsed, stripped = parse_tripwire_set(json.dumps(VALID_TRIPWIRE_SET))
    assert parsed.plan_id == "a1" and len(parsed.tripwires) == 1
    assert stripped is False
    # whole-payload fence: transport repair, recorded via the stripped flag
    fenced = "```json\n" + json.dumps(VALID_TRIPWIRE_SET) + "\n```"
    parsed2, stripped2 = parse_tripwire_set(fenced)
    assert parsed2.plan_id == "a1" and stripped2 is True
    # prose around the JSON stays schema-invalid (consumes the one retry)
    with pytest.raises((ValidationError, ValueError)):
        parse_tripwire_set("Here are your tripwires: " + json.dumps(VALID_TRIPWIRE_SET))
    # fenced-but-invalid content still fails the DSL bar
    with pytest.raises((ValidationError, ValueError)):
        parse_tripwire_set("```json\n{}\n```")


# -- compile retry behavior ---------------------------------------------------

def test_compile_first_try_valid(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")
    trace = make_trace(tmp_path)
    tripwires, results = compile_tripwires("plan", "ctx", trace, **fake_kwargs())
    assert tripwires is not None and len(results) == 1
    events = read_trace(tmp_path / "trace.jsonl")
    assert [e["event_type"] for e in events] == ["compile"]
    assert events[0]["payload"]["attempt"] == 1
    assert events[0]["payload"]["valid"] is True
    assert events[0]["usage"]["model"] == "claude-sonnet-4-6"


def test_compile_retries_once_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "malformed_then_ok")
    monkeypatch.setenv("FAKE_CLAUDE_COUNTER", str(tmp_path / "counter"))
    trace = make_trace(tmp_path)
    tripwires, results = compile_tripwires("plan", "ctx", trace, **fake_kwargs())
    assert tripwires is not None and len(results) == 2
    events = read_trace(tmp_path / "trace.jsonl")
    assert [e["payload"]["attempt"] for e in events] == [1, 2]
    assert [e["payload"]["valid"] for e in events] == [False, True]
    assert "schema-invalid" in events[0]["payload"]["error"]


def test_compile_gives_up_after_one_retry(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "malformed_always")
    trace = make_trace(tmp_path)
    tripwires, results = compile_tripwires("plan", "ctx", trace, **fake_kwargs())
    assert tripwires is None and len(results) == 2
    events = read_trace(tmp_path / "trace.jsonl")
    assert [e["payload"]["valid"] for e in events] == [False, False]


# -- judge --------------------------------------------------------------------

def test_judge_valid_verdict(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "judge_ok")
    trace = make_trace(tmp_path)
    verdict, results = judge_escalation(
        {"id": "tw_pricing_endpoint_404"}, {"status": 404}, "plan summary",
        trace, **fake_kwargs())
    assert verdict is not None and verdict.verdict == "GENUINE"
    assert verdict.affected_subplans == ["s3"]
    events = read_trace(tmp_path / "trace.jsonl")
    assert [e["event_type"] for e in events] == ["judge_verdict"]
    assert events[0]["payload"]["verdict"]["verdict"] == "GENUINE"
    assert events[0]["payload"]["tripwire_id"] == "tw_pricing_endpoint_404"
    assert events[0]["usage"]["model"] == "claude-haiku-4-5-20251001"


def test_judge_rejects_tripwire_set_shaped_output(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")  # returns a TripwireSet, not a verdict
    trace = make_trace(tmp_path)
    verdict, results = judge_escalation({"id": "tw_x"}, {}, "plan", trace,
                                        **fake_kwargs())
    assert verdict is None and len(results) == 2
