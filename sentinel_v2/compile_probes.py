"""The v2 compile step (D4; probe_compiler_design_v0.4.md §9).

The ONE LLM call in the v2 path. It performs SOFT extraction: the model emits a list
of assumptions {plan_step, world_fact, surface, pointer?, recovery_hint?} and nothing
else — no probes, no lens choices, no firing decisions (the substrate compiles all of
it). The model is CATEGORY-BLIND: the prompt names no failure category, only the six
general change-shapes. Generous extraction; precision is the substrate's job.

This module:
  - SoftAssumption / SoftAssumptionSet — the substrate's compile-input format
    (extra='forbid', so a smuggled lens/firing field is a validation error);
  - render_compile_prompt — fills the frozen category-blind template + few-shot;
  - compile_assumptions — one bounded claude call, one retry on schema-invalid,
    a `compile` trace event per attempt;
  - (C3) compile_pipeline — grounds, gates provenance, and compiles survivors into
    substrate probes;
  - (C4) record/replay — byte-identical replay from the recorded compile;
  - (C5) compile_overhead — books compile cost against the 12% cap.

Rule Zero: the prompt and few-shot are tuned/validated on the five SEEN categories
only; no held-out category appears anywhere here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from conductor.sessions import COMPILE_MODEL, SessionResult, run_claude
from sentinel.compile import strip_markdown_fence
from trace import TraceWriter

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPILE_PROMPT_PATH = REPO_ROOT / "prompts" / "v2_compile.md"
FEWSHOT_PATH = REPO_ROOT / "prompts" / "v2_compile_fewshot.json"
MAX_ATTEMPTS = 2  # one retry on schema-invalid output (mirrors Phase-1 compile)


# -- the soft-assumption format (the substrate's compile input) ----------------

class SoftAssumption(BaseModel):
    """One extracted dependency. SOFT by construction: extra='forbid' rejects any
    probe/lens/firing field, so the model cannot smuggle substrate decisions in."""
    model_config = ConfigDict(extra="forbid")

    plan_step: str = Field(min_length=1)
    world_fact: str = Field(min_length=1)
    surface: str = Field(min_length=1)
    pointer: Optional[str] = None        # only for a value-on-a-stable-shape fact
    recovery_hint: Optional[str] = None


class SoftAssumptionSet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str
    assumptions: list[SoftAssumption] = Field(default_factory=list)


# -- prompt rendering ----------------------------------------------------------

def render_fewshot() -> str:
    data = json.loads(FEWSHOT_PATH.read_text(encoding="utf-8"))
    blocks = []
    for ex in data["examples"]:
        emit = json.dumps(ex["assumption"], separators=(",", ":"), ensure_ascii=False)
        blocks.append(
            f"[shape: {ex['change_shape']}]\n"
            f"reasoning: {ex['reasoning']}\n"
            f"emit: {emit}")
    return "\n\n".join(blocks)


def render_compile_prompt(plan: str, surface_appendix: str) -> str:
    """Exact-placeholder replacement (the schema + few-shot carry literal JSON
    braces, so str.format would mangle them — same discipline as Phase-1 compile)."""
    template = COMPILE_PROMPT_PATH.read_text(encoding="utf-8")
    schema_json = json.dumps(SoftAssumptionSet.model_json_schema(),
                             separators=(",", ":"), sort_keys=True)
    return (template
            .replace("{output_schema}", schema_json)
            .replace("{fewshot}", render_fewshot())
            .replace("{plan}", plan)
            .replace("{surface_appendix}", surface_appendix))


def parse_soft_assumptions(text: str) -> tuple[SoftAssumptionSet, bool]:
    body, fences_stripped = strip_markdown_fence(text)
    return SoftAssumptionSet.model_validate_json(body.strip()), fences_stripped


# -- the bounded compile call --------------------------------------------------

def compile_assumptions(plan: str, surface_appendix: str, trace: TraceWriter,
                        runner=run_claude, **runner_kwargs
                        ) -> tuple[Optional[SoftAssumptionSet], list[SessionResult]]:
    """One bounded claude call (per run, and per replan — keep-not-flush, D2), one
    retry on schema-invalid output. Every attempt is a `compile` trace event."""
    system_prompt = render_compile_prompt(plan, surface_appendix)
    results: list[SessionResult] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = runner(model=COMPILE_MODEL, system_prompt=system_prompt,
                        stdin_text=plan, max_turns=1, no_tools=True, **runner_kwargs)
        results.append(result)
        soft: Optional[SoftAssumptionSet] = None
        error: Optional[str] = None
        fences_stripped = False
        if result.exit_code == 0 and not result.is_error and result.result_text:
            try:
                soft, fences_stripped = parse_soft_assumptions(result.result_text)
            except (ValidationError, ValueError) as exc:
                error = f"schema-invalid output: {str(exc)[:500]}"
        else:
            error = (f"invocation failed: exit={result.exit_code} "
                     f"is_error={result.is_error} timed_out={result.timed_out}")
        trace.emit(
            actor="sentinel_v2", event_type="compile",
            payload={"layer": "v2_assumptions", "attempt": attempt,
                     "valid": soft is not None, "fences_stripped": fences_stripped,
                     "n_assumptions": len(soft.assumptions) if soft else 0,
                     "error": error, **result.trace_payload()},
            usage=result.trace_usage())
        if soft is not None:
            return soft, results
    return None, results
