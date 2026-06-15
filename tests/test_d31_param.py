"""D31 C1: the under-parameterized compile fix + counter-neutral §4 read.

compile_and_arm now passes world / auth_token / planned_write_set to
compile_pipeline. These tests pin the three C1 acceptance points:
  - the §4 gate probe ARMS when a world is supplied, and does NOT without one;
  - planned_write_set is derived from the plan (category-blind) and reaches the
    compiler;
  - the gate-probe compile is COUNTER-NEUTRAL — it advances no injection-counting
    channel (the fence), so the injection call-index is unchanged with vs without it.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from conftest import get_token
from sentinel_v2.compile_probes import (SoftAssumption, SoftAssumptionSet,
                                        compile_pipeline)
from sentinel_v2.gate_route import REPO_GATE_SHADOW, check_non_perturbation
from sentinel_v2.probes import ProbeExecutor
from sentinel_v2.write_footprint import planned_write_patterns

REPO = Path(__file__).resolve().parent.parent


def _soft() -> SoftAssumptionSet:
    return SoftAssumptionSet(plan_id="b1", assumptions=[
        SoftAssumption(plan_step="POST /repo/validate and record the report",
                       world_fact="the validate gate actually runs its checks",
                       surface="/repo/validate",
                       recovery_hint="replan via the gate if it stops enforcing"),
        SoftAssumption(plan_step="GET /repo/files/config/settings.yaml",
                       world_fact="settings.yaml carries the pricing key",
                       surface="/repo/files/config/settings.yaml",
                       recovery_hint="re-read settings on drift"),
    ])


@pytest.fixture
def world(make_world):
    return make_world(probe_channel=True, world_rev=2)


def test_gate_probe_arms_with_world_not_without(world):
    soft = _soft()
    token = get_token(world.client)
    # WITHOUT a world: the gate assumption -> UNCOVERED -> caution, no gate probe
    cr0 = compile_pipeline(soft, world_rev=2)
    assert not any(p.target == REPO_GATE_SHADOW for p in cr0.probes)
    assert any(u["surface"] == "/repo/validate" for u in cr0.uncovered)
    # WITH a world: the §4 gate probe arms (the C1 fix)
    cr1 = compile_pipeline(soft, world_rev=2, world=world, auth_token=token)
    gate = [p for p in cr1.probes if p.target == REPO_GATE_SHADOW]
    assert len(gate) == 1
    assert gate[0].lens.op.value == "gate_shadow"
    assert not cr1.uncovered          # the gate assumption is now covered


def test_planned_write_patterns_reach_from_the_plan():
    b1 = yaml.safe_load((REPO / "tasks" / "b1.yaml").read_text(encoding="utf-8"))["plan"]
    pats = planned_write_patterns(b1)
    assert any("settings.yaml" in p for p in pats)         # PUT settings.yaml (w1)
    assert any("src" in p and ".py" in p for p in pats)     # PUT src/*.py (w2)
    # a read-only task declares no writes (category-blind: nothing to scope)
    a1 = yaml.safe_load((REPO / "tasks" / "a1.yaml").read_text(encoding="utf-8"))["plan"]
    assert planned_write_patterns(a1) == ()


def test_planned_write_set_reaches_the_compiler(world):
    """The write surface must be recognized by the compiler as in the write-set
    (a probe target matching a write pattern is treated specially, not as an
    ordinary monitored surface)."""
    soft = _soft()
    token = get_token(world.client)
    pats = ("/repo/files/config/settings.yaml",)
    cr = compile_pipeline(soft, world_rev=2, world=world, auth_token=token,
                          planned_write_set=pats)
    # the write surface is NOT compiled as an ordinary active drift probe
    assert not any(p.target == "/repo/files/config/settings.yaml" for p in cr.probes)


def test_gate_compile_is_counter_neutral(world):
    """The fence: the §4 gate-probe compile must advance NO injection-counting
    channel. The world counter (the injection clock) is unchanged across the
    compile -> the injection call-index is identical with vs without it."""
    soft = _soft()
    token = get_token(world.client)                       # this POST counts; excluded below
    before = world.client.get("/admin/state").json()["counter"]
    compile_pipeline(soft, world_rev=2, world=world, auth_token=token)
    after = world.client.get("/admin/state").json()["counter"]
    assert after == before


def test_check_non_perturbation_is_counter_neutral(world):
    token = get_token(world.client)
    ex = ProbeExecutor(world.client, auth_token=token)
    before = world.client.get("/admin/state").json()["counter"]
    rep = check_non_perturbation(world, lambda: ex.get(REPO_GATE_SHADOW),
                                 auth_token=token)
    after = world.client.get("/admin/state").json()["counter"]
    assert rep.ok                       # all three vectors hold for the real route
    assert after == before              # measured entirely via excluded /admin reads
