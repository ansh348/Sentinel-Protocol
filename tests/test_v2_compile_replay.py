"""C4 acceptance: compile-output recording + byte-identical replay.
The LLM call happens once; the soft assumptions are recorded; replay reconstructs
the compiled probes deterministically with NO model call.
"""
from __future__ import annotations

import json

from conductor.sessions import SessionResult
from conftest import get_token
from sentinel_v2.compile_probes import (SoftAssumption, SoftAssumptionSet,
                                        compile_assumptions, compile_pipeline,
                                        compile_result_summary, record_compile,
                                        replay_compile)
from trace import TraceWriter, read_trace


def _set(*a) -> SoftAssumptionSet:
    return SoftAssumptionSet(plan_id="a1", assumptions=list(a))


def _a(surface, *, plan_step="s1", world_fact="trusts surface", pointer=None,
       recovery_hint="replan") -> SoftAssumption:
    return SoftAssumption(plan_step=plan_step, world_fact=world_fact, surface=surface,
                          pointer=pointer, recovery_hint=recovery_hint)


def _summary_json(cr) -> str:
    return json.dumps(compile_result_summary(cr), sort_keys=True)


def test_replay_reconstructs_byte_identical(tmp_path):
    soft = _set(_a("/pricing/quote/WID-001"),
                _a("/docs/passages/pol-returns", pointer="/content"),
                _a("/inventory/items", recovery_hint=None))  # → telemetry
    live = compile_pipeline(soft, world_rev=4)

    trace = TraceWriter(tmp_path / "t.jsonl", run_id="r", seed=0, system="test",
                        task_id="a1")
    record_compile(trace, live, cost_usd=0.21)
    trace.close()

    events = read_trace(tmp_path / "t.jsonl")
    replayed = replay_compile(events, world_rev=4)  # NO runner, NO LLM call
    assert _summary_json(live) == _summary_json(replayed)
    # the recorded soft assumptions round-trip exactly
    assert replayed.soft_assumptions.model_dump() == soft.model_dump()


def test_end_to_end_compile_record_replay(tmp_path):
    """LLM (fake runner) → compile_assumptions → pipeline → record → replay."""
    payload = {"plan_id": "a1", "assumptions": [
        {"plan_step": "s3", "world_fact": "pricing shape holds",
         "surface": "/pricing/quote/WID-001", "recovery_hint": "replan pricing"},
        {"plan_step": "s1", "world_fact": "content stable",
         "surface": "/docs/passages/pol-returns", "pointer": "/content",
         "recovery_hint": "re-fetch"}]}

    def runner(**kw):
        r = SessionResult(model="claude-sonnet-4-6", exit_code=0, stdout="",
                          stderr="", timed_out=False, duration_s=0.0)
        r.result_text = json.dumps(payload)
        r.session_id = "fake"
        r.num_turns = 1
        r.usage = {"input_tokens": 100, "output_tokens": 50}
        r.total_cost_usd_reported = 0.2
        return r

    trace = TraceWriter(tmp_path / "t.jsonl", run_id="r", seed=0, system="test",
                        task_id="a1")
    soft, results = compile_assumptions("plan", "appendix", trace, runner=runner)
    live = compile_pipeline(soft, world_rev=4)
    record_compile(trace, live, cost_usd=sum(r.cost_usd for r in results))
    trace.close()

    events = read_trace(tmp_path / "t.jsonl")
    replayed = replay_compile(events, world_rev=4)
    assert _summary_json(live) == _summary_json(replayed)
    assert len(replayed.probes) == 2


def test_replay_is_deterministic_for_gate_probes(make_world, tmp_path):
    """The §4 gate probe replays identically against a re-instantiated world (the
    world is seed-deterministic; the trapdoor verdict is stable)."""
    soft = _set(_a("/repo/validate", world_fact="repo gate enforces",
                   recovery_hint="replan via gate"))
    w1 = make_world(probe_channel=True, world_rev=4, seed=1)
    live = compile_pipeline(soft, world_rev=4, world=w1, auth_token=get_token(w1.client))

    trace = TraceWriter(tmp_path / "t.jsonl", run_id="r", seed=0, system="test",
                        task_id="b1")
    record_compile(trace, live, cost_usd=0.2)
    trace.close()

    events = read_trace(tmp_path / "t.jsonl")
    w2 = make_world(probe_channel=True, world_rev=4, seed=1)  # re-instantiated
    replayed = replay_compile(events, world_rev=4, world=w2,
                              auth_token=get_token(w2.client))
    assert _summary_json(live) == _summary_json(replayed)
    assert replayed.probes[0].target == "/repo/gate_status"
