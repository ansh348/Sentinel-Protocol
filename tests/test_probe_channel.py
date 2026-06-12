"""N4 acceptance: the probe side-channel transport (v6.1 §11.9 amendment #1).

Deterministic verification against the three measured perturbation vectors
(archaeology_v2 G7): (1) probe traffic never advances the injection-clock
counter; (2) it cannot enter the token stream; (3) it cannot touch the
validated_docs sentinel — plus: no world-state mutation of any kind, no
matcher interaction, separate metering, and flag-off inertness (the
byte-identity guarantee for banked configs).
"""
from __future__ import annotations

from conftest import auth_headers, get_token
from trace import read_trace

PROBE = {"X-Probe-Channel": "1"}


def _admin(world) -> dict:
    return world.client.get("/admin/state").json()


# -- vector 1: the injection clock ---------------------------------------------

def test_probe_calls_never_advance_the_counter(make_world):
    world = make_world(probe_channel=True)
    h = auth_headers(get_token(world.client))          # worker call 1
    for _ in range(3):
        r = world.client.get("/inventory/items", headers={**h, **PROBE})
        assert r.status_code == 200
    assert _admin(world)["counter"] == 1
    world.client.get("/inventory/items", headers=h)    # worker call 2
    assert _admin(world)["counter"] == 2


def test_probe_calls_never_fire_the_injection(make_world):
    world = make_world(
        probe_channel=True, n_inject=2,
        injection={"type": "endpoint_404", "params": {"path": "/pricing/quote/*"}})
    h = auth_headers(get_token(world.client))          # worker call 1
    for _ in range(5):                                 # would cross n_inject=2
        world.client.get("/pricing/quote/WID-001", headers={**h, **PROBE})
    admin = _admin(world)
    assert admin["counter"] == 1
    assert admin["injection_fired"] is False
    # the SECOND worker call fires it, exactly as without any probe traffic
    world.client.get("/pricing/quote/WID-001", headers=h)
    admin = _admin(world)
    assert admin["injection_fired"] is True
    assert admin["injection_fired_at"] == 2


def test_probe_observes_the_broken_world_read_only(make_world):
    world = make_world(
        probe_channel=True, n_inject=2,
        injection={"type": "endpoint_404", "params": {"path": "/pricing/quote/*"}})
    h = auth_headers(get_token(world.client))
    world.client.get("/pricing/quote/WID-001", headers=h)   # call 2: fires
    r = world.client.get("/pricing/quote/WID-001", headers={**h, **PROBE})
    assert r.status_code == 404                              # probe sees it
    assert _admin(world)["counter"] == 2                     # without counting


# -- vector 2: the token stream -------------------------------------------------

def test_probe_channel_refuses_token_issuance(make_world):
    world = make_world(probe_channel=True)
    r = world.client.post("/auth/token",
                          headers={"X-Worker-Id": "probe", **PROBE})
    assert r.status_code == 405
    assert r.json()["error"] == "probe_channel_read_only"
    assert _admin(world)["active_tokens"] == 0


def test_token_stream_identical_with_and_without_probe_traffic(make_world):
    control = make_world(seed=7)
    t1c = get_token(control.client)
    t2c = get_token(control.client)

    probed = make_world(seed=7, probe_channel=True)
    t1p = get_token(probed.client)
    h = auth_headers(t1p)
    probed.client.get("/auth/validate", headers={**h, **PROBE})  # E.2 auth probe
    probed.client.get("/inventory/items", headers={**h, **PROBE})
    probed.client.post("/auth/token", headers={**PROBE})         # refused 405
    t2p = get_token(probed.client)

    assert (t1c, t2c) == (t1p, t2p)


# -- vector 3: the validated_docs sentinel --------------------------------------

def test_probe_channel_cannot_admit_documents(make_world):
    world = make_world(probe_channel=True)
    h = auth_headers(get_token(world.client))
    doc = {"title": "t", "body": "b" * 60, "citations": ["pol-returns"]}
    r = world.client.post("/docs/validate", json=doc, headers={**h, **PROBE})
    assert r.status_code == 405          # never reaches the handler
    # the worker-path proof: packaging the never-validated doc is refused
    r = world.client.post("/docs/package", json=doc, headers=h)
    assert r.status_code == 409


# -- no mutation of any kind / no matcher interaction ---------------------------

def test_probe_traffic_leaves_admin_state_identical(make_world):
    world = make_world(probe_channel=True)
    h = auth_headers(get_token(world.client))
    before = _admin(world)
    for path in ("/inventory/items", "/pricing/quote/WID-001",
                 "/docs/passages/pol-returns", "/repo/files", "/auth/validate"):
        world.client.get(path, headers={**h, **PROBE})
    world.client.post("/repo/validate", json={}, headers={**h, **PROBE})  # 405
    assert _admin(world) == before


def test_probe_traffic_never_meets_the_matcher(make_world):
    world = make_world(probe_channel=True)
    h = auth_headers(get_token(world.client))
    world.client.post("/admin/arm_tripwires", json={
        "plan_id": "p1",
        "tripwires": [{
            "id": "tw_inventory_status", "severity": "WARNING",
            "scope": "global",
            "assumption": "inventory stays reachable all run",
            "assumption_id": "a3",
            "category_weights": {"API_SURFACE": 1.0},
            "signal": {"type": "http_response",
                       "url_pattern": "/inventory/items",
                       "status_in": [200]},
            "action": {"on_trigger": "ESCALATE_TO_SENTINEL",
                       "hint": "check the inventory surface"},
            "evidence_fields": ["status"],
        }]})
    r = world.client.get("/inventory/items", headers={**h, **PROBE})
    assert r.status_code == 200
    assert "tripwire_control" not in r.json()
    events = read_trace(world.trace_path)
    assert not [e for e in events if e["event_type"] == "tripwire_fire"]
    # the same surface fires for an ordinary worker call
    world.client.get("/inventory/items", headers=h)
    assert [e for e in read_trace(world.trace_path)
            if e["event_type"] == "tripwire_fire"]


# -- separate metering -----------------------------------------------------------

def test_probe_traffic_is_separately_metered(make_world):
    world = make_world(probe_channel=True)
    h = auth_headers(get_token(world.client))
    world.client.get("/inventory/items", headers={**h, **PROBE})
    world.client.get("/inventory/items", headers={**h, **PROBE})
    events = read_trace(world.trace_path)
    calls = [e for e in events if e["event_type"] == "probe_call"]
    responses = [e for e in events if e["event_type"] == "probe_response"]
    assert [c["payload"]["probe_seq"] for c in calls] == [1, 2]
    assert [r["payload"]["status"] for r in responses] == [200, 200]
    assert all(e["actor"] == "probe" for e in calls + responses)
    # probe traffic emits NO tool_call/tool_response rows
    tool_calls = [e for e in events if e["event_type"] == "tool_call"]
    assert len(tool_calls) == 1  # the token issuance only


# -- flag-off inertness (the byte-identity guarantee) ----------------------------

def test_flag_off_marker_is_inert(make_world):
    world = make_world()  # probe_channel defaults False, like banked configs
    h = auth_headers(get_token(world.client))                 # call 1
    r = world.client.get("/inventory/items", headers={**h, **PROBE})  # call 2
    assert r.status_code == 200
    assert _admin(world)["counter"] == 2                      # it counted
    events = read_trace(world.trace_path)
    assert not [e for e in events if e["event_type"].startswith("probe_")]
    assert len([e for e in events if e["event_type"] == "tool_call"]) == 2
