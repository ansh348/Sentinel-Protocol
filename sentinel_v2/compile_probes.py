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

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from conductor.sessions import COMPILE_MODEL, SessionResult, run_claude
from sentinel.compile import strip_markdown_fence
from sentinel_v2.attachment import (Assumption, AssumptionKind, Disposition,
                                    evaluate_attachment)
from sentinel_v2.gate_route import (DOCS_GATE_SHADOW, REPO_GATE_SHADOW,
                                    compile_gate_probe)
from sentinel_v2.pattern_liveness import path_samples_for_rev
from sentinel_v2.probe_spec import Probe, Provenance
from trace import TraceWriter
from world.server import classify_url_pattern

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


# -- C3: wire the soft assumptions into the substrate --------------------------

# Enforcement gates → their §4 read-only shadow routes (build B5).
GATE_SHADOWS = {"/repo/validate": REPO_GATE_SHADOW, "/docs/validate": DOCS_GATE_SHADOW}


class GroundingError(ValueError):
    """Raised when a soft assumption names a surface that does not ground against
    the rev's appendix — a hallucinated surface, rejected LOUDLY (reuse N2)."""

    def __init__(self, surfaces: list, world_rev: int) -> None:
        self.surfaces = surfaces
        super().__init__(
            f"compile grounding FAILED (world_rev {world_rev}): "
            f"{len(surfaces)} assumption surface(s) do not match any real world "
            f"path and must not compile: {surfaces}")


@dataclass
class CompileResult:
    plan_id: str
    probes: list                  # list[Probe] — the compiled active probes
    telemetry_only: list          # demoted: incomplete provenance (§3.3)
    passive: list                 # left passive (self-revealing / planned write-set)
    uncovered: list               # §4 trapdoor failed / unverifiable → caution (D1)
    soft_assumptions: SoftAssumptionSet
    cost_usd: float = 0.0


def _to_attachment_assumption(soft: SoftAssumption, aid: str) -> Assumption:
    """Bridge a soft assumption to a substrate Assumption. Surface STRUCTURE picks
    the kind: a pointer (a value on a stable shape) → VALUE; a bare surface →
    STRUCTURE (a vanished field / changed shape / moved status all change the
    {key:type} shape). read/predicate are substrate-filled; recovery_hint passes
    through (empty ⇒ incomplete chain ⇒ telemetry, §3.3)."""
    if soft.pointer:
        kind = AssumptionKind.VALUE
        read = f"field_read {soft.pointer}"
        predicate = f"value at {soft.pointer} unchanged vs clean baseline"
    else:
        kind = AssumptionKind.STRUCTURE
        read = "schema_fingerprint of the surface"
        predicate = "{key:type} shape unchanged vs clean baseline"
    prov = Provenance(plan_step=soft.plan_step, world_fact=soft.world_fact,
                      surface=soft.surface, read=read, predicate=predicate,
                      recovery_hint=(soft.recovery_hint or "").strip())
    return Assumption(assumption_id=aid, kind=kind, surface=soft.surface,
                      provenance=prov, truth_carried_by_ordinary_traffic=False,
                      pointer=soft.pointer)


def compile_pipeline(soft_set: SoftAssumptionSet, *, world_rev: int = 1,
                     world=None, auth_token: Optional[str] = None,
                     planned_write_set=()) -> CompileResult:
    """Ground → provenance-gate → attachment+lens+typing. Deterministic given the
    soft set; the LLM call already happened (compile_assumptions)."""
    samples = path_samples_for_rev(world_rev)
    # 1. appendix grounding — hallucinated surfaces fail LOUDLY (reuse N2 liveness)
    hallucinated = sorted({a.surface for a in soft_set.assumptions
                           if classify_url_pattern(a.surface, samples) is None})
    if hallucinated:
        raise GroundingError(hallucinated, world_rev)

    probes, telemetry, passive, uncovered = [], [], [], []
    for idx, soft in enumerate(soft_set.assumptions, start=1):
        aid = f"a{idx}"
        # 2. provenance gate (§3.3): the recovery-hint chain link is required;
        #    a missing link is interrupt-DISqualified → telemetry, never an interrupt
        if not (soft.recovery_hint and soft.recovery_hint.strip()):
            telemetry.append({"assumption_id": aid, "surface": soft.surface,
                              "reason": "incomplete provenance: no recovery hint (§3.3)"})
            continue

        if soft.surface in GATE_SHADOWS:
            # §4 enforcement gate → shadow route behind the non-perturbation trapdoor
            prov = Provenance(plan_step=soft.plan_step, world_fact=soft.world_fact,
                              surface=soft.surface, read="gate_status enforcing",
                              predicate="enforcing == True",
                              recovery_hint=soft.recovery_hint)
            if world is None:
                uncovered.append({"assumption_id": aid, "surface": soft.surface,
                                  "reason": "§4 non-perturbation trapdoor cannot run "
                                            "(no world); UNCOVERED → caution (D1)"})
                continue
            res = compile_gate_probe(world, shadow_path=GATE_SHADOWS[soft.surface],
                                     provenance=prov, auth_token=auth_token)
            if res.enabled:
                probes.append(res.probe)
            else:
                uncovered.append({"assumption_id": aid, "surface": soft.surface,
                                  "reason": res.reason})
            continue

        # 3. attachment + lens + typing (non-gate surfaces)
        decision = evaluate_attachment(_to_attachment_assumption(soft, aid),
                                       planned_write_set=planned_write_set)
        if decision.disposition is Disposition.ATTACH:
            probes.append(decision.probe)
        elif decision.disposition is Disposition.TELEMETRY_ONLY:
            telemetry.append({"assumption_id": aid, "surface": soft.surface,
                              "reason": decision.reason})
        else:  # PASSIVE
            passive.append({"assumption_id": aid, "surface": soft.surface,
                            "reason": decision.reason})

    return CompileResult(plan_id=soft_set.plan_id, probes=probes,
                         telemetry_only=telemetry, passive=passive,
                         uncovered=uncovered, soft_assumptions=soft_set)
