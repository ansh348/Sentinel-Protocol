"""D31 C3: GATE_SHADOW probes route through evaluate_gate_probe in run_v2_detection.

Before this fix the detection seam built an empty Invariant() for a
HARD_INVARIANT + VALUE_CHANGED probe (the gate-shadow case), so a trapped gate
read CLEAN. Now a §4 gate probe is evaluated as the hard invariant
`enforcing == True`: a trapped gate fires an interrupt, a healthy gate stays clean,
and a probe lacking worker auth context on an authed gate is DISQUALIFIED (never a
fast-path 401).
"""
from __future__ import annotations

import pytest

from conftest import get_token
from sentinel_v2.arms import run_v2_detection
from sentinel_v2.gate_route import (DOCS_GATE_SHADOW, REPO_GATE_SHADOW,
                                    compile_gate_probe)
from sentinel_v2.probe_spec import Provenance


def _prov() -> Provenance:
    return Provenance(plan_step="package behind the gate",
                      world_fact="the gate enforces", surface="/repo/validate",
                      read="gate_status enforcing", predicate="enforcing == True",
                      recovery_hint="replan via gate")


@pytest.fixture
def world(make_world):
    return make_world(probe_channel=True, world_rev=2)


def _trap(world, path):
    world.client.post("/admin/inject",
                      json={"type": "gate_skip_trap", "params": {"path": path}})


def test_repo_gate_clean_then_trapped_via_detection(world):
    token = get_token(world.client)
    gate = compile_gate_probe(world, shadow_path=REPO_GATE_SHADOW, provenance=_prov(),
                              auth_token=token).probe
    healthy = run_v2_detection([gate], world.client, auth_token=token)
    assert healthy["detected"] is False           # enforcing == True -> CLEAN

    _trap(world, "/repo/validate")
    fired = run_v2_detection([gate], world.client, auth_token=token)
    assert fired["detected"] and fired["grades"] == ["interrupt"]
    inv = fired["invalidations"][0]
    assert inv.target == REPO_GATE_SHADOW
    assert inv.witness is False                   # enforcing observed False
    assert "stopped enforcing" in inv.reason


def test_docs_gate_trapped_interrupts_with_worker_auth(world):
    token = get_token(world.client)
    gate = compile_gate_probe(world, shadow_path=DOCS_GATE_SHADOW, provenance=_prov(),
                              auth_token=token).probe
    _trap(world, "/docs/validate")
    fired = run_v2_detection([gate], world.client, auth_token=token)
    assert fired["detected"] and fired["grades"] == ["interrupt"]


def test_authed_gate_without_token_is_disqualified_not_interrupt(world):
    token = get_token(world.client)
    gate = compile_gate_probe(world, shadow_path=DOCS_GATE_SHADOW, provenance=_prov(),
                              auth_token=token).probe
    _trap(world, "/docs/validate")
    # no token -> the §4 probe lacks worker auth context (401) -> DISQUALIFIED,
    # never a fast-path 401 interrupt
    out = run_v2_detection([gate], world.client, auth_token=None)
    assert out["detected"] is False
