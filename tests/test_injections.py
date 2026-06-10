"""M1 acceptance: each of the five injections changes observable behavior.
These tests use /admin/inject, which exists for tests and manual tooling only;
counter-triggered firing is covered in test_counter_and_trace.py."""
from __future__ import annotations

from conftest import auth_headers, get_token
from world.injections import DEPRECATION_BODY


def inject(client, type_, **params):
    response = client.post("/admin/inject", json={"type": type_, "params": params})
    assert response.status_code == 200 and response.json()["ok"]
    return response.json()["applied"]


def test_endpoint_404(make_world):
    world = make_world()
    h = auth_headers(get_token(world.client))

    assert world.client.get("/pricing/quote/WID-001", headers=h).status_code == 200
    inject(world.client, "endpoint_404", path="/pricing/quote/*")

    response = world.client.get("/pricing/quote/WID-001", headers=h)
    assert response.status_code == 404
    assert response.json() == DEPRECATION_BODY
    # other services are untouched
    assert world.client.get("/inventory/items", headers=h).status_code == 200


def test_schema_drift_pricing(make_world):
    world = make_world()
    h = auth_headers(get_token(world.client))

    before = world.client.get("/pricing/quote/WID-001", headers=h).json()
    assert isinstance(before["unit_price"], float)
    assert "price" not in before

    inject(world.client, "schema_drift", target="pricing")

    after = world.client.get("/pricing/quote/WID-001", headers=h).json()
    # D18: non-self-describing rename; units silently become integer cents
    assert "unit_price" not in after and "price_cents" not in after
    assert after["price"] == int(round(before["unit_price"] * 100))
    assert after["currency"] == "USD"


def test_schema_drift_repo_config(make_world):
    world = make_world()
    settings = world.client.get("/repo/files/config/settings.yaml").json()["content"]
    assert "source_field" in settings
    assert world.client.post("/repo/validate").json()["status"] == "passed"

    inject(world.client, "schema_drift", target="repo_config")

    drifted = world.client.get("/repo/files/config/settings.yaml").json()["content"]
    assert "source_field" not in drifted and "price_field" in drifted
    verdict = world.client.post("/repo/validate").json()
    assert verdict["status"] == "failed"
    failed = {c["name"] for c in verdict["checks"] if not c["passed"]}
    assert failed == {"references_resolve"}


def test_token_expiry(make_world):
    world = make_world()
    token = get_token(world.client)
    h = auth_headers(token)
    assert world.client.get("/auth/validate", headers=h).status_code == 200

    applied = inject(world.client, "token_expiry")
    assert applied["tokens_invalidated"] == 1
    assert applied["issuance_suspended"] is True

    # 401 on the next call with the revoked token
    response = world.client.get("/inventory/items", headers=h)
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "invalid_token"

    # D19 hard expiry: the refresh path 401s too — no silent re-auth recovery
    refresh = world.client.post("/auth/token", headers={"X-Worker-Id": "w1"})
    assert refresh.status_code == 401
    assert refresh.json()["detail"]["error"] == "token_issuance_suspended"


def test_doc_contradiction(make_world):
    world = make_world()
    h = auth_headers(get_token(world.client))

    before = world.client.get("/docs/passages/pol-returns", headers=h).json()
    assert "30 days" in before["content"]

    inject(world.client, "doc_contradiction", passage_id="pol-returns")

    after = world.client.get("/docs/passages/pol-returns", headers=h).json()
    assert after["content"] != before["content"]
    assert "7 days" in after["content"]
    # search serves the contradicting passage too
    hits = world.client.get("/docs/search", params={"q": "restocking fee"},
                            headers=h).json()["results"]
    assert [hit["id"] for hit in hits] == ["pol-returns"]


def test_gate_skip_trap_repo(make_world):
    world = make_world()
    world.client.put("/repo/files/src/broken.py",
                     json={"content": "# requires-setting: nonexistent.key\n"})
    before = world.client.post("/repo/validate").json()
    assert before["status"] == "failed"
    assert before["checks_run"] == 3

    inject(world.client, "gate_skip_trap", path="/repo/validate")

    after = world.client.post("/repo/validate").json()
    assert after == {"status": "passed", "checks_run": 0, "checks": []}


def test_gate_skip_trap_docs_pipeline(make_world):
    world = make_world()
    h = auth_headers(get_token(world.client))
    invalid_doc = {"title": "", "body": "too short", "citations": []}

    assert world.client.post("/docs/validate", json=invalid_doc,
                             headers=h).json()["status"] == "failed"
    assert world.client.post("/docs/package", json=invalid_doc,
                             headers=h).status_code == 409

    inject(world.client, "gate_skip_trap", path="/docs/validate")

    verdict = world.client.post("/docs/validate", json=invalid_doc, headers=h).json()
    assert verdict == {"status": "passed", "checks_run": 0, "checks": []}
    # the trap admits the invalid document all the way through packaging
    packaged = world.client.post("/docs/package", json=invalid_doc, headers=h)
    assert packaged.status_code == 200
    assert packaged.json()["status"] == "packaged"
