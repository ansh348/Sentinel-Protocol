"""C2 acceptance: the v2 compile prompt + the bounded LLM wrapper.
Category-blind rendering, soft-only schema (extra-forbid), and the one-retry
behavior — exercised with an injected fake runner (no live model, $0)."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from conductor.sessions import SessionResult
from sentinel_v2.compile_probes import (SoftAssumption, SoftAssumptionSet,
                                        compile_assumptions, parse_soft_assumptions,
                                        render_compile_prompt)
from trace import TraceWriter, read_trace

CATEGORY_LABELS = ("API_SURFACE", "SCHEMA_DRIFT", "PERMISSION_AUTH",
                   "RETRIEVAL_INTEGRITY", "TOOL_CONTRACT")
SIX_SHAPES = ("vanished", "status-moved", "structure-changed", "value-moved",
              "order-scrambled", "relationship-broke")

VALID = {"plan_id": "a1", "assumptions": [
    {"plan_step": "s3", "world_fact": "pricing returns unit_price",
     "surface": "/pricing/quote/WID-001"}]}


def _trace(tmp_path) -> TraceWriter:
    return TraceWriter(tmp_path / "trace.jsonl", run_id="t", seed=0,
                       system="test", task_id="a1")


def _result(text, *, exit_code=0, is_error=False, cost=0.01) -> SessionResult:
    r = SessionResult(model="claude-sonnet-4-6", exit_code=exit_code, stdout="",
                      stderr="", timed_out=False, duration_s=0.0)
    r.result_text = text
    r.is_error = is_error
    r.session_id = "fake-session"
    r.num_turns = 1
    r.usage = {"input_tokens": 100, "output_tokens": 50}
    r.total_cost_usd_reported = cost
    return r


def _runner(*texts):
    it = iter(texts)
    return lambda **kw: _result(next(it))


# -- rendering: category-blind, six-shape, soft -------------------------------

def test_render_compile_prompt_is_category_blind():
    rendered = render_compile_prompt("PLAN HERE", "APPENDIX HERE")
    for placeholder in ("{output_schema}", "{fewshot}", "{plan}", "{surface_appendix}"):
        assert placeholder not in rendered
    assert "PLAN HERE" in rendered and "APPENDIX HERE" in rendered
    # Rule Zero: NO failure-category label anywhere in the prompt
    for label in CATEGORY_LABELS:
        assert label not in rendered, f"category label {label} leaked into the prompt"
    # the six general shapes ARE the vocabulary
    for shape in SIX_SHAPES:
        assert shape in rendered
    # the soft schema is embedded; lens/firing fields are not part of it
    assert '"SoftAssumptionSet"' in rendered
    assert "fault_shape" not in rendered and "on_trigger" not in rendered


def test_soft_assumption_forbids_lens_and_firing_fields():
    SoftAssumption(plan_step="s1", world_fact="f", surface="/x")  # ok
    with pytest.raises(ValidationError):
        SoftAssumption(plan_step="s1", world_fact="f", surface="/x", lens="field_read")
    with pytest.raises(ValidationError):
        SoftAssumption(plan_step="s1", world_fact="f", surface="/x",
                       on_trigger="PAUSE")


def test_parse_soft_assumptions():
    parsed, stripped = parse_soft_assumptions(json.dumps(VALID))
    assert parsed.plan_id == "a1" and len(parsed.assumptions) == 1 and stripped is False
    fenced = "```json\n" + json.dumps(VALID) + "\n```"
    parsed2, stripped2 = parse_soft_assumptions(fenced)
    assert stripped2 is True and parsed2.assumptions[0].surface == "/pricing/quote/WID-001"
    with pytest.raises((ValidationError, ValueError)):
        parse_soft_assumptions("here are the assumptions: " + json.dumps(VALID))


# -- the bounded call + one-retry behavior ------------------------------------

def test_compile_first_try_valid(tmp_path):
    trace = _trace(tmp_path)
    soft, results = compile_assumptions("plan", "appendix", trace,
                                        runner=_runner(json.dumps(VALID)))
    assert soft is not None and len(results) == 1
    events = read_trace(tmp_path / "trace.jsonl")
    assert [e["event_type"] for e in events] == ["compile"]
    assert events[0]["payload"]["valid"] is True
    assert events[0]["payload"]["n_assumptions"] == 1
    assert events[0]["payload"]["layer"] == "v2_assumptions"
    assert events[0]["usage"]["model"] == "claude-sonnet-4-6"


def test_compile_retries_once_then_succeeds(tmp_path):
    trace = _trace(tmp_path)
    soft, results = compile_assumptions(
        "plan", "appendix", trace,
        runner=_runner("not json at all", json.dumps(VALID)))
    assert soft is not None and len(results) == 2
    events = read_trace(tmp_path / "trace.jsonl")
    assert [e["payload"]["valid"] for e in events] == [False, True]
    assert "schema-invalid" in events[0]["payload"]["error"]


def test_compile_gives_up_after_one_retry(tmp_path):
    trace = _trace(tmp_path)
    soft, results = compile_assumptions("plan", "appendix", trace,
                                        runner=_runner("nope", "still nope"))
    assert soft is None and len(results) == 2
    events = read_trace(tmp_path / "trace.jsonl")
    assert [e["payload"]["valid"] for e in events] == [False, False]
