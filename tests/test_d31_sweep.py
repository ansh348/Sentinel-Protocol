"""D31 C2: the guaranteed pre-completion sweep (D29 §3.1).

A load-bearing surface no worker barrier re-observed — above all the side-channel
§4 gate shadow, which a worker can never touch — must still get a guaranteed final
re-look before run end. These tests pin the three acceptance points: the
never-touched gate shadow IS swept; a fresh surface is NOT redundantly swept; an
unreachable surface routes to the uncovered valve.
"""
from __future__ import annotations

from collections import namedtuple

import pytest

from conftest import get_token
from sentinel_v2.cadence.sweep import (pending_sweep_targets,
                                       run_pre_completion_sweep)
from sentinel_v2.gate_route import REPO_GATE_SHADOW, compile_gate_probe
from sentinel_v2.probe_spec import Provenance

P = namedtuple("P", "target")


def _prov() -> Provenance:
    return Provenance(plan_step="package behind the gate",
                      world_fact="the gate enforces", surface="/repo/validate",
                      read="gate_status enforcing", predicate="enforcing == True",
                      recovery_hint="replan via gate")


@pytest.fixture
def world(make_world):
    return make_world(probe_channel=True, world_rev=2)


def test_fresh_surface_not_redundantly_swept():
    probes = [P("/repo/gate_status"), P("/pricing/quote/WID-001"), P("/inventory/items")]
    observed = {"/pricing/quote/WID-001"}        # re-observed at a barrier => FRESH
    interrupted = {"/inventory/items"}           # an open incident => coalesced, not swept
    owed = [p.target for p in pending_sweep_targets(probes, observed, interrupted)]
    assert owed == ["/repo/gate_status"]         # only the never-touched shadow is owed


def test_never_touched_gate_shadow_is_swept(world):
    token = get_token(world.client)
    gate = compile_gate_probe(world, shadow_path=REPO_GATE_SHADOW, provenance=_prov(),
                              auth_token=token).probe
    events = []
    res = run_pre_completion_sweep(
        [gate], observed=set(), interrupted=set(), client=world.client,
        auth_token=token, baselines={}, queries={}, judge=False,
        emit=lambda et, p: events.append((et, p)))
    assert res["swept"] == [REPO_GATE_SHADOW]
    assert res["reachable"] == [REPO_GATE_SHADOW]   # the shadow got its final re-look
    assert res["uncovered"] == []


def test_unreachable_surface_routes_to_uncovered():
    class _BoomClient:
        def get(self, path, params=None, headers=None):
            raise ConnectionError("side channel unreachable")
        def head(self, path, headers=None):
            raise ConnectionError("side channel unreachable")

    events = []
    res = run_pre_completion_sweep(
        [P("/dead/surface")], observed=set(), interrupted=set(), client=_BoomClient(),
        auth_token=None, baselines={}, queries={}, judge=False,
        emit=lambda et, p: events.append((et, p)))
    assert res["uncovered"] == ["/dead/surface"]
    assert res["reachable"] == []
    assert res["invalidations"] == []               # nothing reachable -> no detection
    assert events and events[0][0] == "uncovered"   # the valve fired, never silent
