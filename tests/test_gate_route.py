"""B5 acceptance: the §4 gate route + equivalence + non-perturbation trapdoor
(probe_compiler_design_v0.4.md §4/§5.1; author ruling D1).
"""
from __future__ import annotations

import pytest

from conftest import get_token
from sentinel_v2.gate_route import (DOCS_GATE_SHADOW, REPO_GATE_SHADOW,
                                    check_non_perturbation, compile_gate_probe,
                                    evaluate_gate_probe)
from sentinel_v2.probes import ProbeExecutor
from sentinel_v2.probe_spec import Provenance
from sentinel_v2.typing_engine import Verdict


def _prov() -> Provenance:
    return Provenance(plan_step="package report behind the gate",
                      world_fact="the gate actually enforces its checks",
                      surface="/repo/validate", read="gate_status enforcing",
                      predicate="enforcing == True", recovery_hint="replan via gate")


@pytest.fixture
def world(make_world):
    return make_world(probe_channel=True, world_rev=2)


def _trap(world, path):
    r = world.client.post("/admin/inject",
                          json={"type": "gate_skip_trap", "params": {"path": path}})
    assert r.status_code == 200


# -- repo gate: enforcing -> CLEAN; trapped -> INTERRUPT (fires on its own) -----

def test_repo_gate_enforcing_then_trapped(world):
    token = get_token(world.client)
    res = compile_gate_probe(world, shadow_path=REPO_GATE_SHADOW,
                             provenance=_prov(), auth_token=token)
    assert res.enabled and res.probe is not None and res.report.ok

    ex = ProbeExecutor(world.client, auth_token=token)
    clean = evaluate_gate_probe(res.probe, ex, requires_auth=False)
    assert clean.verdict is Verdict.CLEAN  # enforcing, with NO baseline (Break-A)

    _trap(world, "/repo/validate")
    fired = evaluate_gate_probe(res.probe, ex, requires_auth=False)
    assert fired.verdict is Verdict.INTERRUPT and fired.witness is False


# -- docs gate: equivalence (worker auth required) -----------------------------

def test_docs_gate_requires_worker_auth_context(world):
    token = get_token(world.client)
    res = compile_gate_probe(world, shadow_path=DOCS_GATE_SHADOW,
                             provenance=_prov(), auth_token=token)
    assert res.enabled

    # a probe WITHOUT worker context is DISQUALIFIED to telemetry, never root
    no_auth = ProbeExecutor(world.client, auth_token=None)
    dq = evaluate_gate_probe(res.probe, no_auth, requires_auth=True)
    assert dq.verdict is Verdict.DISQUALIFIED and "never fired under a privileged" in dq.reason

    # with the worker's own token: enforcing -> CLEAN, trapped -> INTERRUPT
    ex = ProbeExecutor(world.client, auth_token=token)
    assert evaluate_gate_probe(res.probe, ex, requires_auth=True).verdict is Verdict.CLEAN
    _trap(world, "/docs/validate")
    assert evaluate_gate_probe(res.probe, ex, requires_auth=True).verdict is Verdict.INTERRUPT


# -- the non-perturbation trapdoor ---------------------------------------------

def test_trapdoor_passes_for_the_real_route(world):
    token = get_token(world.client)
    ex = ProbeExecutor(world.client, auth_token=token)
    report = check_non_perturbation(
        world, lambda: ex.get(DOCS_GATE_SHADOW), auth_token=token)
    assert report.ok
    assert report.counter_ok and report.token_stream_ok and report.sentinel_ok


def test_disable_and_flag_fallback_on_a_perturbing_route(world):
    """Ruling D1: a §4 action that perturbs (here, a probe that rides the MAIN
    channel and advances the counter) trips the trapdoor — route DISABLED,
    assumption flagged UNCOVERED, routed to caution. No probe is armed."""
    token = get_token(world.client)
    auth = {"Authorization": f"Bearer {token}", "X-Worker-Id": "w1"}
    perturbing = lambda: world.client.get("/inventory/items", headers=auth)  # counts!

    res = compile_gate_probe(world, shadow_path=REPO_GATE_SHADOW, provenance=_prov(),
                             auth_token=token, probe_action=perturbing)
    assert res.enabled is False and res.uncovered is True and res.probe is None
    assert "counter" in res.report.failed_vectors()
    assert "UNCOVERED" in res.reason and "caution" in res.reason


def test_shadow_is_no_write(world):
    """Probing the docs shadow (which runs the real predicate against a canary)
    admits nothing and perturbs nothing: counter, token stream, and the
    validated_docs sentinel all hold across repeated reads."""
    token = get_token(world.client)
    ex = ProbeExecutor(world.client, auth_token=token)

    def repeated():
        for _ in range(4):
            ex.get(DOCS_GATE_SHADOW)
    report = check_non_perturbation(world, repeated, auth_token=token)
    assert report.ok


# -- probe and predicate can never disagree ------------------------------------

def test_shadow_agrees_with_the_real_gate(world):
    token = get_token(world.client)
    ex = ProbeExecutor(world.client, auth_token=token)
    auth = {"Authorization": f"Bearer {token}", "X-Worker-Id": "w1"}

    # clean: shadow checks_run == the real POST gate's checks_run
    shadow = ex.get(REPO_GATE_SHADOW).body
    real = world.client.post("/repo/validate", headers=auth).json()
    assert shadow["checks_run"] == real["checks_run"] > 0
    assert shadow["enforcing"] is True

    # trapped: the POST gate is fooled (status passed, 0 checks) but the shadow
    # reports non-enforcement — exactly the §4 point
    _trap(world, "/repo/validate")
    shadow2 = ex.get(REPO_GATE_SHADOW).body
    real2 = world.client.post("/repo/validate", headers=auth).json()
    assert real2["status"] == "passed" and real2["checks_run"] == 0
    assert shadow2["checks_run"] == 0 and shadow2["enforcing"] is False


# -- byte-identity: the shadow routes exist ONLY on probe-channel worlds --------

def test_gate_shadow_absent_when_flag_off(make_world):
    off = make_world(world_rev=2)  # probe_channel defaults False (banked configs)
    token = get_token(off.client)
    auth = {"Authorization": f"Bearer {token}", "X-Worker-Id": "w1"}
    assert off.client.get("/repo/gate_status").status_code == 404
    assert off.client.get("/docs/gate_status", headers=auth).status_code == 404
    # the real gate is unchanged by the refactor
    assert off.client.post("/repo/validate", headers=auth).json()["status"] == "passed"

    on = make_world(world_rev=2, probe_channel=True)
    assert on.client.get("/repo/gate_status").status_code == 200


def test_refactored_doc_gate_still_admits_and_packages(world):
    token = get_token(world.client)
    auth = {"Authorization": f"Bearer {token}", "X-Worker-Id": "w1"}
    doc = {"title": "t", "body": "b" * 60, "citations": ["pol-returns"]}
    assert world.client.post("/docs/validate", json=doc, headers=auth).json()["status"] \
        == "passed"
    assert world.client.post("/docs/package", json=doc, headers=auth).status_code == 200
