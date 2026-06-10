"""Sentinel compile wrapper: plan + ontology + schema -> TripwireSet.

Renders the FROZEN prompts/sentinel_compile.md by exact placeholder replacement
(the frozen template contains literal JSON braces, so str.format would mangle
it), runs a single-turn no-tools claude -p call on the compile model, validates
the output against the frozen DSL, and retries exactly once on schema-invalid
output. Every attempt — including the retry — is counted in the trace as a
`compile` event (BUILD_BRIEF M2).

Doubles as the `make smoke` / phase-0 entry point:
    python -m sentinel.compile --task tasks/a1.yaml --outdir runs/smoke
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError

from conductor.sessions import (COMPILE_MODEL, SessionResult, get_cli_version,
                                run_claude)
from sentinel.dsl import TripwireSet
from trace import TraceWriter

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPILE_PROMPT_PATH = REPO_ROOT / "prompts" / "sentinel_compile.md"
MAX_ATTEMPTS = 2  # pre-registered: one retry on schema-invalid output


def render_compile_prompt(plan: str, task_context: str) -> str:
    template = COMPILE_PROMPT_PATH.read_text(encoding="utf-8")
    schema_json = json.dumps(TripwireSet.model_json_schema(),
                             separators=(",", ":"), sort_keys=True)
    return (template
            .replace("{schema_json}", schema_json)
            .replace("{plan}", plan)
            .replace("{task_context}", task_context))


_FENCE_RE = re.compile(r"\A```(?:json)?\s*\n(.*)\n```\s*\Z", re.DOTALL)


def strip_markdown_fence(text: str) -> tuple[str, bool]:
    """The frozen prompt forbids fences, but the compile model reliably wraps
    its (otherwise valid) JSON in a ```json fence anyway (observed on both
    smoke attempts, 2026-06-10). Stripping a single whole-payload fence is a
    transport repair, not a content repair: the DSL schema remains the
    validation bar, and the strip is recorded in the trace (fences_stripped)
    so Phase 0 scoring can track format compliance separately."""
    match = _FENCE_RE.match(text.strip())
    if match:
        return match.group(1), True
    return text, False


def parse_tripwire_set(text: str) -> tuple[TripwireSet, bool]:
    """Parse and DSL-validate; prose around the JSON is schema-invalid and
    consumes the one pre-registered retry."""
    body, fences_stripped = strip_markdown_fence(text)
    return TripwireSet.model_validate_json(body.strip()), fences_stripped


def compile_tripwires(plan: str, task_context: str, trace: TraceWriter,
                      runner=run_claude, **runner_kwargs,
                      ) -> tuple[Optional[TripwireSet], list[SessionResult]]:
    system_prompt = render_compile_prompt(plan, task_context)
    results: list[SessionResult] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = runner(model=COMPILE_MODEL, system_prompt=system_prompt,
                        stdin_text=plan, max_turns=1, no_tools=True,
                        **runner_kwargs)
        results.append(result)
        tripwire_set: Optional[TripwireSet] = None
        error: Optional[str] = None
        fences_stripped = False
        if result.exit_code == 0 and not result.is_error and result.result_text:
            try:
                tripwire_set, fences_stripped = parse_tripwire_set(result.result_text)
            except (ValidationError, ValueError) as exc:
                error = f"schema-invalid output: {str(exc)[:500]}"
        else:
            error = (f"invocation failed: exit={result.exit_code} "
                     f"is_error={result.is_error} timed_out={result.timed_out}")
        trace.emit(
            actor="sentinel",
            event_type="compile",
            payload={"attempt": attempt, "valid": tripwire_set is not None,
                     "fences_stripped": fences_stripped,
                     "error": error, **result.trace_payload()},
            usage=result.trace_usage(),
        )
        if tripwire_set is not None:
            return tripwire_set, results
    return None, results


def plan_text_from_task(task: dict) -> str:
    """Render a task spec's canonical plan (numbered steps with subplan_ids)."""
    lines = [f"Goal: {task['goal'].strip()}", "", "Plan:"]
    for i, step in enumerate(task["plan"], start=1):
        lines.append(f"{i}. [{step['subplan_id']}] {step['step']}")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="sentinel compile (smoke/phase0)")
    parser.add_argument("--task", required=True, help="task yaml path")
    parser.add_argument("--outdir", required=True, help="output directory")
    args = parser.parse_args(argv)

    task = yaml.safe_load(Path(args.task).read_text(encoding="utf-8"))
    plan = plan_text_from_task(task)
    task_context = task["task_context"].strip()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    trace = TraceWriter(outdir / "trace.jsonl", run_id=f"smoke-{task['id']}",
                        seed=0, system="smoke", task_id=task["id"])
    cli_version = get_cli_version()
    trace.emit(actor="conductor", event_type="run_start",
               payload={"mode": "smoke", "cli_version": cli_version,
                        "task": args.task})

    started = time.monotonic()
    tripwire_set, results = compile_tripwires(plan, task_context, trace)
    elapsed = time.monotonic() - started
    cost = sum(r.cost_usd for r in results)

    success = tripwire_set is not None
    if success:
        set_json = tripwire_set.model_dump_json(indent=2)
        out_path = outdir / f"tripwires_{task['id']}.json"
        out_path.write_text(set_json, encoding="utf-8")
        trace.emit(actor="sentinel", event_type="tripwire_set",
                   payload={"plan_id": tripwire_set.plan_id,
                            "count": len(tripwire_set.tripwires),
                            "tripwires": json.loads(set_json)})
        print(f"OK: {len(tripwire_set.tripwires)} schema-valid tripwires -> {out_path}")
    else:
        print("FAILED: no schema-valid tripwire set after "
              f"{len(results)} attempt(s)", file=sys.stderr)

    trace.emit(actor="conductor", event_type="run_end",
               payload={"success": success, "attempts": len(results),
                        "latency_s": round(elapsed, 2),
                        "cost_usd": round(cost, 6)})
    trace.close()
    print(f"attempts={len(results)} latency={elapsed:.1f}s cost=${cost:.4f} "
          f"cli={cli_version}")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
