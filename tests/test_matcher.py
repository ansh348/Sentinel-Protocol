"""Matcher + middleware tests: pure predicate evaluation, tripwire_control
embedding, hard-stop enforcement (M3 amendment 2), touch-trigger semantics
(deviations.md D3), suppression, and re-arm resets."""
from __future__ import annotations

import pytest

from conftest import auth_headers, get_token
from fake_claude import VALID_TRIPWIRE_SET
from trace import read_trace
from world.server import TripwireMatcher, _MISSING, _pointer_lookup
from sentinel.dsl import TripwireSet


def tw(id_="tw_test_wire", severity="CRITICAL", scope="global", signal=None,
       on_trigger="PAUSE_AND_REPLAN", evidence=("status", "path"), **extra):
    return {
        "id": id_, "severity": severity, "scope": scope,
        "assumption": "test assumption long enough to validate",
        "assumption_id": "a1",
        "category_weights": {"API_SURFACE": 1.0},
        "signal": signal,
        "action": {"on_trigger": on_trigger,
                   "hint": "do something specific about step s3"},
        "evidence_fields": list(evidence),
        **extra,
    }


def make_set(*tripwires) -> TripwireSet:
    return TripwireSet.model_validate({"plan_id": "t", "tripwires": list(tripwires)})


def arm(client, *tripwires):
    response = client.post(
        "/admin/arm_tripwires",
        json={"plan_id": "t", "tripwires": list(tripwires)})
    assert response.status_code == 200 and response.json()["ok"]


# -- pointer lookup -----------------------------------------------------------

def test_pointer_lookup():
    body = {"a": {"b": [10, {"c": 5}]}, "unit_price": 9.5}
    assert _pointer_lookup(body, "/unit_price") == 9.5
    assert _pointer_lookup(body, "unit_price") == 9.5
    assert _pointer_lookup(body, "/a/b/1/c") == 5
    assert _pointer_lookup(body, "a.b") == [10, {"c": 5}]
    assert _pointer_lookup(body, "/nope") is _MISSING
    assert _pointer_lookup(None, "/x") is _MISSING


# -- unit matcher -------------------------------------------------------------

def test_status_and_glob_predicates():
    matcher = TripwireMatcher()
    matcher.arm(make_set(tw(signal={"type": "http_response", "method": "GET",
                                    "url_pattern": "/pricing/quote/*",
                                    "status_in": [404, 410]})))
    assert matcher.evaluate(method="GET", path="/pricing/quote/X", status=200,
                            body={}) == []
    hits = matcher.evaluate(method="GET", path="/pricing/quote/X", status=404,
                            body={})
    assert [t.id for t in hits] == ["tw_test_wire"]
    # wrong path or method: no match
    assert matcher.evaluate(method="GET", path="/pricing/quotes", status=404,
                            body={}) == []
    assert matcher.evaluate(method="POST", path="/pricing/quote/X", status=404,
                            body={}) == []


def test_field_absent_and_regex_are_anded_with_gates():
    matcher = TripwireMatcher()
    matcher.arm(make_set(
        tw(id_="tw_drift", signal={"type": "http_response",
                                   "url_pattern": "/pricing/*",
                                   "field_absent": "/unit_price"})))
    assert matcher.evaluate(method="GET", path="/pricing/quote/X", status=200,
                            body={"unit_price": 4.2}) == []
    assert [t.id for t in matcher.evaluate(
        method="GET", path="/pricing/quote/X", status=200,
        body={"price_cents": 420})] == ["tw_drift"]

    matcher.arm(make_set(
        tw(id_="tw_regex", signal={"type": "http_response",
                                   "url_pattern": "/pricing/*",
                                   "field_regex": {"/currency": "cents"}})))
    assert matcher.evaluate(method="GET", path="/pricing/quote/X", status=200,
                            body={"currency": "USD"}) == []
    assert [t.id for t in matcher.evaluate(
        method="GET", path="/pricing/quote/X", status=200,
        body={"currency": "cents"})] == ["tw_regex"]


def test_touch_trigger_dedup_per_resource():
    matcher = TripwireMatcher()
    matcher.arm(make_set(
        tw(id_="tw_touch", severity="WARNING", on_trigger="ESCALATE_TO_SENTINEL",
           signal={"type": "retrieval_content",
                   "url_pattern": "/docs/passages/*",
                   "contradicts_assumption": "a1"})))
    first = matcher.evaluate(method="GET", path="/docs/passages/pol-returns",
                             status=200, body={"content": "x"})
    assert [t.id for t in first] == ["tw_touch"]
    # same resource: deduplicated
    assert matcher.evaluate(method="GET", path="/docs/passages/pol-returns",
                            status=200, body={"content": "x"}) == []
    # different resource: fires again
    assert len(matcher.evaluate(method="GET", path="/docs/passages/ven-terms",
                                status=200, body={})) == 1


def test_order_violation():
    matcher = TripwireMatcher()
    matcher.arm(make_set(
        tw(id_="tw_order", signal={"type": "tool_output",
                                   "order_violation": {
                                       "required_before": "/docs/validate",
                                       "observed": "/docs/package"}})))
    # package before validate: violation
    assert [t.id for t in matcher.evaluate(
        method="POST", path="/docs/package", status=200, body={})] == ["tw_order"]
    matcher.arm(make_set(
        tw(id_="tw_order", signal={"type": "tool_output",
                                   "order_violation": {
                                       "required_before": "/docs/validate",
                                       "observed": "/docs/package"}})))
    matcher.evaluate(method="POST", path="/docs/validate", status=200, body={})
    assert matcher.evaluate(method="POST", path="/docs/package", status=200,
                            body={}) == []


# -- middleware integration ---------------------------------------------------

def test_control_embedded_and_hard_stop(make_world):
    world = make_world()
    h = auth_headers(get_token(world.client))
    arm(world.client, VALID_TRIPWIRE_SET["tripwires"][0])

    # healthy world: no fire
    assert world.client.get("/pricing/quote/WID-001", headers=h).status_code == 200

    world.client.post("/admin/inject",
                      json={"type": "endpoint_404",
                            "params": {"path": "/pricing/quote/*"}})
    response = world.client.get("/pricing/quote/WID-001", headers=h)
    assert response.status_code == 404
    control = response.json()["tripwire_control"]
    assert control["action"] == "STOP_AND_ESCALATE"
    assert control["tripwire_id"] == "tw_pricing_endpoint_404"
    assert control["evidence"] == {"status": 404, "path": "/pricing/quote/WID-001"}

    # hard stop: the SAME worker's next call gets 409 + worker_noncompliance
    blocked = world.client.get("/inventory/items", headers=h)
    assert blocked.status_code == 409
    assert blocked.json()["tripwire_control"]["tripwire_id"] == control["tripwire_id"]
    # a different worker is unaffected (it must also authenticate as itself:
    # the tripped w1 cannot even fetch fresh tokens)
    h2 = auth_headers(get_token(world.client, worker="w9"), worker="w9")
    assert world.client.get("/inventory/items", headers=h2).status_code == 200

    events = read_trace(world.trace_path)
    fires = [e for e in events if e["event_type"] == "tripwire_fire"]
    assert len(fires) == 1 and fires[0]["payload"]["log_only"] is False
    noncompliance = [e for e in events if e["event_type"] == "worker_noncompliance"]
    assert len(noncompliance) == 1 and noncompliance[0]["actor"] == "w1"

    # re-arming clears tripped workers (fresh plan starts clean)
    arm(world.client, VALID_TRIPWIRE_SET["tripwires"][0])
    assert world.client.get("/inventory/items", headers=h).status_code == 200


def test_log_severity_never_embeds_control(make_world):
    world = make_world()
    h = auth_headers(get_token(world.client))
    arm(world.client, tw(id_="tw_log_only", severity="INFO", on_trigger="LOG",
                         signal={"type": "http_response",
                                 "url_pattern": "/inventory/*",
                                 "status_in": [200]}))
    response = world.client.get("/inventory/items", headers=h)
    assert response.status_code == 200
    assert "tripwire_control" not in response.json()
    events = read_trace(world.trace_path)
    fires = [e for e in events if e["event_type"] == "tripwire_fire"]
    assert len(fires) == 1 and fires[0]["payload"]["log_only"] is True
    assert world.client.get("/admin/state").json()["tripped_workers"] == []


def test_suppression(make_world):
    world = make_world()
    h = auth_headers(get_token(world.client))
    arm(world.client, VALID_TRIPWIRE_SET["tripwires"][0])
    world.client.post("/admin/inject",
                      json={"type": "endpoint_404",
                            "params": {"path": "/pricing/quote/*"}})
    world.client.post("/admin/suppress",
                      json={"tripwire_id": "tw_pricing_endpoint_404"})
    response = world.client.get("/pricing/quote/WID-001", headers=h)
    assert response.status_code == 404
    assert "tripwire_control" not in response.json()
