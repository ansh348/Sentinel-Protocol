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

import dataclasses
import json
import re
from fnmatch import fnmatchcase
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
from sentinel_v2.write_surface import WriteFootprint
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

# Tolerate the surface appendix's "METHOD /path/{template}" dialect (the model
# copies it verbatim) — a D5/D8-class transmission gap. The substrate normalizes
# rather than fighting it: strip a leading HTTP method, and ground a route
# template by globbing its {param} segments to a concrete representative.
_METHOD_RE = re.compile(r"^(GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS)\s+", re.IGNORECASE)


def _normalize_surface(surface: str) -> str:
    return _METHOD_RE.sub("", (surface or "").strip())


# D32 family-template budget (D29 uncovered valve). A family-level template arms ALL
# its bounded members; this caps how many a single template may arm before the overflow
# routes to UNCOVERED_CAUTION (loud, never a silent truncation). The real seen families
# are small (passages 6, SKUs 6, repo files 8); the cap is the matrix backstop.
FAMILY_MEMBER_CAP = 24


def _instantiate(glob: str, samples: tuple) -> tuple:
    """ALL concrete samples matching `glob`, lexicographically sorted (D32: the full
    bounded family — replacing the old `sorted(glob)[0]` single lexicographically-first
    pick that under-covered a family the integrity property spans). A caller that wants a
    single representative for an invented concrete id takes the first element."""
    return tuple(sorted(p for p in samples if fnmatchcase(p, glob)))


@dataclass(frozen=True)
class SurfaceGrounding:
    """The grounding of ONE soft-assumption surface against the rev's real surface (D32).

    A concrete / invented-id surface grounds to a single-element `members`. A
    family-level template ({param}) grounds to the plan-named ids if the soft set names
    any member of the family (mode 'plan_named'), else to every bounded family member
    within the budget cap (mode 'all_bounded'); `overflow` carries members beyond the cap.
    `unbounded` flags a template family the sample set cannot bound (mode 'unbounded') and
    `overflow` both route to UNCOVERED_CAUTION (loud). `hallucinated` flags a concrete
    surface that grounds to nothing (N2 loud whole-set failure)."""
    members: tuple = ()
    overflow: tuple = ()
    mode: str = "concrete"        # concrete|invented_id|plan_named|all_bounded|unbounded|hallucinated
    is_template: bool = False
    hallucinated: bool = False
    unbounded: bool = False


def ground_surface(surface: str, samples: tuple, routes: tuple = (),
                   *, plan_named: tuple = ()) -> SurfaceGrounding:
    """Ground a soft-assumption surface to the concrete surface(s) it watches. Tolerates
    the appendix dialect: strips a leading HTTP method.

    D32 family-template grounding (replaces the old single lexicographically-first pick):
    a route TEMPLATE ({param}) is a FAMILY-level reference spanning every member, so the
    substrate grounds it to (1) the plan-named ids where the plan provides them — the
    concrete members named directly elsewhere in the same soft set (`plan_named`); else
    (2) ALL bounded family members (capped, the overflow → UNCOVERED_CAUTION); else
    (3) UNCOVERED_CAUTION when the sample set cannot bound the family. The rule is
    deterministic, category-blind, and injection-blind — it names plan-provided ids or
    the whole bounded family, NEVER the injected member.

    A concrete surface grounds to itself; an invented concrete id on a real route (e.g.
    /pricing/quote/SKU-001) grounds to a single real representative (D5/D8 dialect
    tolerance, unchanged — a single intended member, not a family); anything else is
    hallucinated (loud)."""
    s = _normalize_surface(surface)
    if "{" in s:                                    # family-level template (D32)
        bounded = _instantiate(re.sub(r"\{[^}]+\}", "*", s), samples)
        if not bounded:                             # no bounded membership → uncovered
            return SurfaceGrounding(mode="unbounded", is_template=True, unbounded=True)
        named = tuple(m for m in bounded if m in set(plan_named))
        if named:                                   # ground to plan-named family ids
            return SurfaceGrounding(members=named, mode="plan_named", is_template=True)
        return SurfaceGrounding(members=bounded[:FAMILY_MEMBER_CAP],
                                overflow=bounded[FAMILY_MEMBER_CAP:],
                                mode="all_bounded", is_template=True)
    if classify_url_pattern(s, samples) is not None:  # already a real concrete path
        return SurfaceGrounding(members=(s,), mode="concrete")
    for route in routes:                            # invented id on a real route?
        if "{" in route:
            glob = re.sub(r"\{[^}]+\}", "*", route)
            if fnmatchcase(s, glob):
                rep = _instantiate(glob, samples)
                if rep:
                    return SurfaceGrounding(members=(rep[0],), mode="invented_id")
    return SurfaceGrounding(mode="hallucinated", hallucinated=True)


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
    passive: list                 # left passive (self-revealing)
    uncovered: list               # §4 trapdoor failed / unverifiable → caution (D1)
    soft_assumptions: SoftAssumptionSet
    cost_usd: float = 0.0
    write_footprints: list = field(default_factory=list)  # D31: planned-write surfaces, footprint-scoped


def _to_attachment_assumption(soft: SoftAssumption, aid: str,
                              surface: str) -> Assumption:
    """Bridge a soft assumption to a substrate Assumption (using the GROUNDED
    concrete surface). Surface STRUCTURE picks the kind: a pointer (a value on a
    stable shape) → VALUE; a bare surface → STRUCTURE (a vanished field / changed
    shape / moved status all change the {key:type} shape). read/predicate are
    substrate-filled; recovery_hint passes through (empty ⇒ telemetry, §3.3)."""
    if soft.pointer:
        kind = AssumptionKind.VALUE
        read = f"field_read {soft.pointer}"
        predicate = f"value at {soft.pointer} unchanged vs clean baseline"
    else:
        kind = AssumptionKind.STRUCTURE
        read = "schema_fingerprint of the surface"
        predicate = "{key:type} shape unchanged vs clean baseline"
    prov = Provenance(plan_step=soft.plan_step, world_fact=soft.world_fact,
                      surface=surface, read=read, predicate=predicate,
                      recovery_hint=(soft.recovery_hint or "").strip())
    return Assumption(assumption_id=aid, kind=kind, surface=surface,
                      provenance=prov, truth_carried_by_ordinary_traffic=False,
                      pointer=soft.pointer)


def compile_pipeline(soft_set: SoftAssumptionSet, *, world_rev: int = 1,
                     world=None, auth_token: Optional[str] = None,
                     planned_write_set=()) -> CompileResult:
    """Ground → provenance-gate → attachment+lens+typing. Deterministic given the
    soft set; the LLM call already happened (compile_assumptions)."""
    samples = path_samples_for_rev(world_rev)
    from sentinel_v2.surface_appendix import openapi_paths_for_rev
    routes = tuple(openapi_paths_for_rev(world_rev).keys())
    # D32: the plan-named concrete family ids = the real, groundable concrete paths the
    # soft set names DIRECTLY (a {param} family template grounds to these where present).
    # Drawn from the plan/soft-set only — injection-blind, never escrow.
    plan_named = tuple(
        norm for norm in (_normalize_surface(s.surface) for s in soft_set.assumptions)
        if "{" not in norm and classify_url_pattern(norm, samples) is not None)
    # 1. appendix grounding (dialect-tolerant; D32 family-template grounding). A concrete
    #    surface that cannot ground is a hallucination → LOUD whole-set failure (reuse N2
    #    liveness). A family template grounds to its plan-named ids / all bounded members /
    #    UNCOVERED_CAUTION; it is never a hallucination.
    groundings: dict[int, SurfaceGrounding] = {}
    hallucinated = []
    for idx, soft in enumerate(soft_set.assumptions, start=1):
        g = ground_surface(soft.surface, samples, routes, plan_named=plan_named)
        if g.hallucinated:
            hallucinated.append(soft.surface)
        else:
            groundings[idx] = g
    if hallucinated:
        raise GroundingError(sorted(set(hallucinated)), world_rev)

    probes, telemetry, passive, uncovered = [], [], [], []
    write_footprints = []
    for idx, soft in enumerate(soft_set.assumptions, start=1):
        g = groundings[idx]
        # D32: a template family with no bounded membership → loud UNCOVERED_CAUTION (D1).
        if g.unbounded:
            uncovered.append({"assumption_id": f"a{idx}",
                              "surface": _normalize_surface(soft.surface),
                              "reason": "family-level template with no bounded membership "
                                        "(D32) — UNCOVERED → caution (D1)"})
            continue
        # D32 budget valve (D29): bounded members beyond the cap → loud UNCOVERED_CAUTION,
        # never a silent truncation.
        for over in g.overflow:
            uncovered.append({"assumption_id": f"a{idx}", "surface": over,
                              "reason": f"family-template member beyond budget cap "
                                        f"{FAMILY_MEMBER_CAP} (D32) — UNCOVERED → caution (D1)"})
        # route EACH grounded family member through the EXISTING per-surface policy (D32
        # composes, never bypasses: a write member → D31 footprint, a gate member →
        # compile_gate_probe, a read member → D30 baseline + drift).
        multi = len(g.members) > 1
        for mno, surface in enumerate(g.members, start=1):
            aid = f"a{idx}m{mno}" if multi else f"a{idx}"
            # 2. provenance gate (§3.3): the recovery-hint chain link is required;
            #    a missing link is interrupt-DISqualified → telemetry, never an interrupt
            if not (soft.recovery_hint and soft.recovery_hint.strip()):
                telemetry.append({"assumption_id": aid, "surface": surface,
                                  "reason": "incomplete provenance: no recovery hint (§3.3)"})
                continue

            if surface in GATE_SHADOWS:
                # §4 enforcement gate → shadow route behind the non-perturbation trapdoor
                prov = Provenance(plan_step=soft.plan_step, world_fact=soft.world_fact,
                                  surface=surface, read="gate_status enforcing",
                                  predicate="enforcing == True",
                                  recovery_hint=soft.recovery_hint)
                if world is None:
                    uncovered.append({"assumption_id": aid, "surface": surface,
                                      "reason": "§4 non-perturbation trapdoor cannot run "
                                                "(no world); UNCOVERED → caution (D1)"})
                    continue
                res = compile_gate_probe(world, shadow_path=GATE_SHADOWS[surface],
                                         provenance=prov, auth_token=auth_token)
                if res.enabled:
                    probes.append(res.probe)
                else:
                    uncovered.append({"assumption_id": aid, "surface": surface,
                                      "reason": res.reason})
                continue

            # 3. attachment + lens + typing (non-gate surfaces)
            decision = evaluate_attachment(_to_attachment_assumption(soft, aid, surface),
                                           planned_write_set=planned_write_set)
            if decision.disposition is Disposition.ATTACH:
                probes.append(decision.probe)
            elif decision.disposition is Disposition.WRITE_FOOTPRINT:
                # D31: a planned-write surface is footprint-scoped, not an active drift
                # probe (a legitimate write would false-positive) and not silently
                # passive. The whole-surface footprint with no expected post-state is the
                # honest minimum (precise transition extraction is the item-3 residual) →
                # UNCOVERED_CAUTION at runtime, loud and scored by C7.
                write_footprints.append(WriteFootprint(surface=surface))
            elif decision.disposition is Disposition.TELEMETRY_ONLY:
                telemetry.append({"assumption_id": aid, "surface": surface,
                                  "reason": decision.reason})
            else:  # PASSIVE
                passive.append({"assumption_id": aid, "surface": surface,
                                "reason": decision.reason})

    return CompileResult(plan_id=soft_set.plan_id, probes=probes,
                         telemetry_only=telemetry, passive=passive,
                         uncovered=uncovered, soft_assumptions=soft_set,
                         write_footprints=write_footprints)


# -- C4: compile-output recording + byte-identical replay ----------------------
#
# The compile call is the one non-deterministic step. To keep a run byte-
# replayable, the SOFT ASSUMPTIONS (the LLM output) are recorded in the trace;
# replay reads them and re-runs the DETERMINISTIC compile_pipeline — no LLM call.
# The probe summary is recorded too, so replay can be checked against it.

def probe_to_dict(probe: Probe) -> dict:
    """A stable, JSON-serializable view of a compiled probe (str-enums serialize
    as their string values natively), for recording and byte-comparison."""
    return dataclasses.asdict(probe)


def compile_result_summary(cr: CompileResult) -> dict:
    return {"plan_id": cr.plan_id,
            "probes": [probe_to_dict(p) for p in cr.probes],
            "telemetry_only": cr.telemetry_only,
            "passive": cr.passive, "uncovered": cr.uncovered,
            "write_footprints": [{"surface": f.surface, "fields": list(f.fields),
                                  "expected": f.expected} for f in cr.write_footprints]}


def record_compile(trace: TraceWriter, cr: CompileResult, *, cost_usd: float = 0.0
                   ) -> dict:
    """Write the compiled set into the run trace as a `tripwire_set` event. The
    recorded soft assumptions are sufficient to reconstruct the probes on replay."""
    payload = {"layer": "v2_probes",
               "soft_assumptions": cr.soft_assumptions.model_dump(),
               "cost_usd": cost_usd, **compile_result_summary(cr)}
    trace.emit(actor="sentinel_v2", event_type="tripwire_set", payload=payload)
    return payload


def read_recorded_soft_set(events: list) -> Optional[SoftAssumptionSet]:
    """Recover the recorded SoftAssumptionSet from a trace (the last v2_probes
    tripwire_set event — keep-not-flush replans append later sets)."""
    recorded = [e for e in events if e["event_type"] == "tripwire_set"
                and (e.get("payload") or {}).get("layer") == "v2_probes"]
    if not recorded:
        return None
    return SoftAssumptionSet.model_validate(recorded[-1]["payload"]["soft_assumptions"])


def replay_compile(events: list, *, world_rev: int = 1, world=None,
                   auth_token: Optional[str] = None,
                   planned_write_set=()) -> Optional[CompileResult]:
    """Reconstruct the compiled set from the recorded trace WITHOUT an LLM call:
    read the recorded soft assumptions and re-run the deterministic pipeline."""
    soft = read_recorded_soft_set(events)
    if soft is None:
        return None
    return compile_pipeline(soft, world_rev=world_rev, world=world,
                            auth_token=auth_token, planned_write_set=planned_write_set)


# -- C5: cost discipline -------------------------------------------------------
#
# One bounded compile call per run, and one per replan (keep-not-flush, ruling
# D2). Compile cost is booked as OVERHEAD against the clean-run ≤12% cap (design
# §0; the replan recompile is booked on the run it occurs on, A5). The
# deterministic mock's probe traffic is effectively free (side-channel reads);
# probe_cost becomes load-bearing only in the real-suite study.

CLEAN_OVERHEAD_CAP = 0.12


@dataclass
class CompileEconomics:
    n_compiles: int            # bounded compile calls = 1 (run) + n_replans
    n_attempts: int            # total LLM attempts across all compiles (incl. retries)
    compile_cost_usd: float    # LLM cost of every compile + recompile
    probe_cost_usd: float = 0.0   # probe traffic booked as waste (mock ≈ 0)
    worker_cost_usd: float = 0.0  # the run's productive (worker) cost

    @property
    def overhead_usd(self) -> float:
        return self.compile_cost_usd + self.probe_cost_usd

    @property
    def overhead_fraction(self) -> float:
        return (self.overhead_usd / self.worker_cost_usd
                if self.worker_cost_usd > 0 else float("inf"))

    def within_clean_cap(self, cap: float = CLEAN_OVERHEAD_CAP) -> bool:
        return self.overhead_fraction <= cap

    @property
    def bounded(self) -> bool:
        """Every compile used at most one retry (no unbounded compile loop)."""
        return self.n_attempts <= self.n_compiles * MAX_ATTEMPTS


def account_compile(compile_runs: list, *, worker_cost_usd: float = 0.0,
                    probe_cost_usd: float = 0.0) -> CompileEconomics:
    """`compile_runs` is one list of SessionResults per compile call: the run
    compile first, then one per replan (keep-not-flush). Books all compile cost
    as overhead."""
    n_compiles = len(compile_runs)
    n_attempts = sum(len(r) for r in compile_runs)
    compile_cost = sum(s.cost_usd for r in compile_runs for s in r)
    return CompileEconomics(n_compiles=n_compiles, n_attempts=n_attempts,
                            compile_cost_usd=round(compile_cost, 6),
                            probe_cost_usd=probe_cost_usd,
                            worker_cost_usd=worker_cost_usd)
