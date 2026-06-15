"""D32 acceptance: family-template grounding (under-coverage fix).

A family-level template ({param}) is a FAMILY reference spanning every member; the
substrate grounds it to the plan-named ids where the plan provides them, else to ALL
bounded family members (each routed through its existing per-surface policy), else to
UNCOVERED_CAUTION — replacing the old `sorted(glob)[0]` single lexicographically-first
pick that under-covered the family. Deterministic, category-blind, injection-blind.
"""
from __future__ import annotations

import inspect

import pytest

from sentinel_v2.compile_probes import (FAMILY_MEMBER_CAP, SoftAssumption,
                                        SoftAssumptionSet, compile_pipeline,
                                        ground_surface)
from sentinel_v2.pattern_liveness import path_samples_for_rev

# the full bounded passage family at rev 4 (derived mechanically from the corpus).
PASSAGE_FAMILY = tuple(sorted(
    p for p in path_samples_for_rev(4) if p.startswith("/docs/passages/")))
INJECTED_PASSAGE = "/docs/passages/pol-returns"   # the SEEN-cell injected member


def _set(*assumptions) -> SoftAssumptionSet:
    return SoftAssumptionSet(plan_id="a1", assumptions=list(assumptions))


def _a(surface, *, pointer=None, recovery_hint="replan via this surface") -> SoftAssumption:
    return SoftAssumption(plan_step="s1", world_fact="the step trusts this surface",
                          surface=surface, pointer=pointer, recovery_hint=recovery_hint)


# -- (1) plan-named ids: a family template grounds to EXACTLY those ------------

def test_family_template_grounds_to_plan_named_ids_when_present():
    # the plan names pol-returns concretely AND emits the family template; the template
    # grounds to {pol-returns} (the plan-named id), NOT the lexicographic-first member.
    soft = _set(_a("/docs/passages/pol-returns", pointer="/content"),
                _a("/docs/passages/{passage_id}"))
    result = compile_pipeline(soft, world_rev=4)
    passage_targets = {p.target for p in result.probes
                       if p.target.startswith("/docs/passages/")}
    assert passage_targets == {"/docs/passages/pol-returns"}
    # the lexicographically-first member is NOT armed (the old bug armed exactly it)
    assert "/docs/passages/ops-shipping" not in passage_targets


# -- (2) no plan-named id: arm the FULL bounded family (not a representative) --

def test_family_template_arms_all_bounded_members_without_plan_named_ids():
    # a generic-naming plan emits ONLY the template (no concrete passage id bound); the
    # substrate arms EVERY bounded family member — the decisive generic case.
    soft = _set(_a("/docs/passages/{passage_id}"))
    result = compile_pipeline(soft, world_rev=4)
    passage_targets = {p.target for p in result.probes
                       if p.target.startswith("/docs/passages/")}
    # the FULL member set, NOT a single lexicographically-first representative
    assert passage_targets == set(PASSAGE_FAMILY)
    assert len(passage_targets) > 1
    # pol-returns is covered ONLY because it is a family member (never named/singled out)
    assert INJECTED_PASSAGE in passage_targets


def test_rule_references_no_injected_or_target_identity():
    # structural injection-blindness: the grounding API carries NO injected/target
    # parameter, so the rule cannot reference, prefer, or single out the injected member.
    params = set(inspect.signature(ground_surface).parameters)
    assert {"injected", "target", "injection", "category"} & params == set()
    params_cp = set(inspect.signature(compile_pipeline).parameters)
    assert {"injected", "target", "injection", "category"} & params_cp == set()
    # behavioural symmetry: the armed family is the whole bounded set — no member is
    # preferred, so the result is identical whichever member happens to be injected.
    g = ground_surface("/docs/passages/{passage_id}", path_samples_for_rev(4))
    assert set(g.members) == set(PASSAGE_FAMILY) and g.mode == "all_bounded"


# -- (3) an unbounded family routes to UNCOVERED_CAUTION (loud) ----------------

def test_unbounded_family_template_routes_to_uncovered():
    # a template the sample set cannot bound (no member globs out) → UNCOVERED_CAUTION,
    # never a silent drop and never a single arbitrary pick. It is NOT a hallucination.
    soft = _set(_a("/widgets/{widget_id}"))
    result = compile_pipeline(soft, world_rev=4)
    assert result.probes == []
    assert len(result.uncovered) == 1
    assert "no bounded membership" in result.uncovered[0]["reason"]
    # ground_surface flags it directly
    g = ground_surface("/widgets/{widget_id}", path_samples_for_rev(4))
    assert g.unbounded and g.members == () and g.mode == "unbounded"


# -- (4) a planned-write family member routes through D31 (no naive drift) -----

def test_planned_write_family_member_routes_through_d31_footprint():
    # every member of /repo/files/{path} is a planned-write surface → footprint-scoped
    # (D31), NOT a naive active drift probe (which would false-positive on the legit
    # write) and NOT silently passive.
    soft = _set(_a("/repo/files/{path}", pointer="/content"))
    result = compile_pipeline(soft, world_rev=4, planned_write_set=("/repo/files/*",))
    repo_family = sorted(p for p in path_samples_for_rev(4)
                         if p.startswith("/repo/files/"))
    assert result.probes == [] and result.passive == []   # no naive drift probe
    assert sorted(f.surface for f in result.write_footprints) == repo_family


# -- (5) budget: within the cap arms all; the overflow goes UNCOVERED ----------

def test_within_cap_arms_all_members():
    # the real seen families are small (6) and fit entirely within the cap.
    assert len(PASSAGE_FAMILY) <= FAMILY_MEMBER_CAP
    g = ground_surface("/docs/passages/{passage_id}", path_samples_for_rev(4))
    assert g.overflow == () and set(g.members) == set(PASSAGE_FAMILY)


def test_budget_overflow_routes_remainder_to_uncovered():
    # a synthetic family of 30 members against a cap of 24: arm the first 24
    # (deterministic, lexicographic), route the remaining 6 to UNCOVERED_CAUTION.
    samples = tuple(f"/big/{i:03d}" for i in range(30))
    g = ground_surface("/big/{id}", samples)
    assert len(g.members) == FAMILY_MEMBER_CAP
    assert len(g.overflow) == 30 - FAMILY_MEMBER_CAP
    assert set(g.members) | set(g.overflow) == set(samples)        # nothing lost
    assert g.members == samples[:FAMILY_MEMBER_CAP]                # deterministic


def test_compile_pipeline_routes_overflow_to_uncovered(monkeypatch):
    # shrink the cap so a real family (6 passages) overflows: 2 arm, 4 → uncovered.
    monkeypatch.setattr("sentinel_v2.compile_probes.FAMILY_MEMBER_CAP", 2)
    soft = _set(_a("/docs/passages/{passage_id}"))
    result = compile_pipeline(soft, world_rev=4)
    armed = {p.target for p in result.probes if p.target.startswith("/docs/passages/")}
    over = {u["surface"] for u in result.uncovered}
    assert len(armed) == 2
    assert armed | over == set(PASSAGE_FAMILY)                     # full family covered
    assert all("budget cap" in u["reason"] for u in result.uncovered)


# -- invariants preserved: invented id (single rep) + concrete hallucination ---

def test_invented_concrete_id_still_grounds_to_single_representative():
    # D5/D8 path unchanged: an invented concrete id (not a template) grounds to ONE real
    # representative, not the whole family (it is a single intended member).
    g = ground_surface("/pricing/quote/SKU-001", path_samples_for_rev(4),
                       routes=("/pricing/quote/{sku}",))
    assert g.mode == "invented_id" and len(g.members) == 1
    assert g.members[0].startswith("/pricing/quote/") and "SKU-001" not in g.members[0]
