"""Sentinel judge wrapper: escalation -> GENUINE/NOISE verdict.

Renders the FROZEN prompts/sentinel_judge.md by exact placeholder replacement,
runs a single-turn no-tools claude -p call on the judge model (Haiku — the
cheap-judge economics are part of what the pilot tests), validates the output
against the verdict shape fixed in the frozen prompt, and retries exactly once
on schema-invalid output, with every attempt counted in the trace as a
`judge_verdict` event.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from conductor.sessions import JUDGE_MODEL, SessionResult, run_claude
from sentinel.compile import strip_markdown_fence
from trace import TraceWriter

JUDGE_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "sentinel_judge.md"
MAX_ATTEMPTS = 2  # pre-registered: one retry on schema-invalid output


class JudgeVerdict(BaseModel):
    """Mirrors the output object fixed in the frozen judge prompt verbatim."""
    verdict: Literal["GENUINE", "NOISE"]
    confidence: float = Field(ge=0.0, le=1.0)
    scope_confirmed: Literal["global", "local"]
    affected_subplans: list[str]
    replan_hint: str
    reason: str


def render_judge_prompt(tripwire: dict, evidence: dict, plan_summary: str) -> str:
    template = JUDGE_PROMPT_PATH.read_text(encoding="utf-8")
    return (template
            .replace("{tripwire}", json.dumps(tripwire, separators=(",", ":")))
            .replace("{evidence}", json.dumps(evidence, separators=(",", ":")))
            .replace("{plan_summary}", plan_summary))


def parse_verdict(text: str) -> tuple[JudgeVerdict, bool]:
    """Parse and validate; whole-payload markdown fences are stripped as a
    transport repair (recorded in the trace), same policy as compile."""
    body, fences_stripped = strip_markdown_fence(text)
    return JudgeVerdict.model_validate_json(body.strip()), fences_stripped


def judge_escalation(tripwire: dict, evidence: dict, plan_summary: str,
                     trace: TraceWriter, runner=run_claude, **runner_kwargs,
                     ) -> tuple[Optional[JudgeVerdict], list[SessionResult]]:
    system_prompt = render_judge_prompt(tripwire, evidence, plan_summary)
    stdin_text = json.dumps({"tripwire": tripwire, "evidence": evidence,
                             "plan_summary": plan_summary},
                            separators=(",", ":"))
    results: list[SessionResult] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = runner(model=JUDGE_MODEL, system_prompt=system_prompt,
                        stdin_text=stdin_text, max_turns=1, no_tools=True,
                        **runner_kwargs)
        results.append(result)
        verdict: Optional[JudgeVerdict] = None
        error: Optional[str] = None
        fences_stripped = False
        if result.exit_code == 0 and not result.is_error and result.result_text:
            try:
                verdict, fences_stripped = parse_verdict(result.result_text)
            except (ValidationError, ValueError) as exc:
                error = f"schema-invalid output: {str(exc)[:500]}"
        else:
            error = (f"invocation failed: exit={result.exit_code} "
                     f"is_error={result.is_error} timed_out={result.timed_out}")
        trace.emit(
            actor="judge",
            event_type="judge_verdict",
            payload={"attempt": attempt, "valid": verdict is not None,
                     "fences_stripped": fences_stripped,
                     "error": error,
                     "verdict": verdict.model_dump() if verdict else None,
                     "tripwire_id": tripwire.get("id"),
                     **result.trace_payload()},
            usage=result.trace_usage(),
        )
        if verdict is not None:
            return verdict, results
    return None, results
