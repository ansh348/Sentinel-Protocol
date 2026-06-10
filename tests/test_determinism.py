"""M1 acceptance: pre-injection behavior is byte-identical across two runs with
the same seed — full bodies, no exclusion lists (amendment 2)."""
from __future__ import annotations

from conftest import auth_headers, get_token

VALID_DOC = {
    "title": "Returns brief",
    "body": "Customers may return items within the published returns window; "
            "see the cited policy passage for the authoritative wording.",
    "citations": ["pol-returns"],
}


def run_script(world) -> list[tuple[int, str, bytes]]:
    """One fixed request sequence touching every service, including 404/409/401
    paths. Returns (status, content-type, raw body) per step."""
    client = world.client
    results: list[tuple[int, str, bytes]] = []

    def record(response):
        results.append((response.status_code,
                        response.headers.get("content-type", ""),
                        response.content))
        return response

    token = record(client.post("/auth/token", headers={"X-Worker-Id": "w1"})).json()["token"]
    h = auth_headers(token)

    record(client.get("/auth/validate", headers=h))
    record(client.get("/inventory/items", headers=h))
    record(client.get("/inventory/items/WID-001", headers=h))
    record(client.get("/inventory/items/NOPE-999", headers=h))          # 404
    record(client.get("/pricing/quote/WID-001", headers=h))
    record(client.get("/pricing/quote/THM-002", headers=h))
    record(client.get("/shipping/destinations", headers=h))
    record(client.get("/shipping/rates/GAD-001", params={"dest": "eu"}, headers=h))
    record(client.get("/shipping/rates/GAD-001", params={"dest": "moon"}, headers=h))  # 404
    record(client.get("/docs/passages", headers=h))
    record(client.get("/docs/passages/pol-returns", headers=h))
    record(client.get("/docs/search", params={"q": "warehouse"}, headers=h))
    record(client.post("/docs/package", json=VALID_DOC, headers=h))     # 409: not validated yet
    record(client.post("/docs/validate", json=VALID_DOC, headers=h))
    record(client.post("/docs/package", json=VALID_DOC, headers=h))
    record(client.get("/repo/files"))
    record(client.get("/repo/files/config/settings.yaml"))
    record(client.put("/repo/files/src/new_module.py",
                      json={"content": "# requires-setting: report.format\n"}))
    record(client.post("/repo/validate"))
    record(client.get("/inventory/items", headers={"X-Worker-Id": "w1"}))  # 401: no token
    return results


def test_same_seed_byte_identical(make_world):
    a = run_script(make_world(seed=11))
    b = run_script(make_world(seed=11))
    assert len(a) == len(b)
    for i, (ra, rb) in enumerate(zip(a, b)):
        assert ra == rb, f"step {i} differs between same-seed runs"


def test_different_seed_differs(make_world):
    a = run_script(make_world(seed=11))
    b = run_script(make_world(seed=12))
    assert [r[2] for r in a] != [r[2] for r in b]


def test_openapi_covers_all_services(make_world):
    world = make_world()
    spec = world.client.get("/openapi.json").json()
    paths = spec["paths"]
    for expected in ("/auth/token", "/inventory/items", "/pricing/quote/{sku}",
                     "/shipping/rates/{sku}", "/docs/passages", "/docs/validate",
                     "/repo/validate", "/repo/files/{path}"):
        assert expected in paths, f"{expected} missing from OpenAPI spec"
    # spec fetches are not tool calls
    assert world.client.get("/admin/state").json()["counter"] == 0
