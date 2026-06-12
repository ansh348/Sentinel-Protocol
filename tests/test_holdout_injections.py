"""Held-out category mechanics (benchmark/holdouts/*.md): quota_cliff
(RESOURCE_BUDGET) and silent_minor_bump (DEPENDENCY_VERSION), plus the
world_rev gate that keeps rev-1 worlds byte-identical to Phase 1.

Deterministic throughout: no LLM, no clocks. Counter-path firing mirrors
test_counter_and_trace.py; /admin/inject usage mirrors test_injections.py
(tests and manual tooling only, M1 amendment 3)."""
from __future__ import annotations

import pytest

from conftest import auth_headers, get_token
from world.injections import QUOTA_EXHAUSTED_BODY
from world.state import REPO_FILES, REPO_FILES_V2


def inject(client, type_, **params):
    response = client.post("/admin/inject", json={"type": type_, "params": params})
    assert response.status_code == 200 and response.json()["ok"]
    return response.json()["applied"]


# ---------------------------------------------------------------- rev gate

def test_rev1_world_unchanged(make_world):
    """Rev-1 worlds carry none of the holdout surface: Phase 1 byte-shape."""
    world = make_world()
    h = auth_headers(get_token(world.client))

    assert world.client.get("/manifest").status_code == 404
    items = world.client.get("/inventory/items", headers=h)
    assert items.json() == {"items": list(items.json()["items"])}
    assert "total_count" not in items.json()
    assert "x-api-version" not in items.headers
    assert world.client.get("/repo/files").json() == {"files": sorted(REPO_FILES)}
    # explicit pagination params are ignored at rev 1 (whole collection)
    paged = world.client.get("/repo/files", params={"page_size": 2})
    assert paged.json() == {"files": sorted(REPO_FILES)}


def test_holdout_injections_refuse_rev1(make_world):
    world = make_world()
    with pytest.raises(ValueError, match="world_rev"):
        world.client.post("/admin/inject", json={
            "type": "quota_cliff",
            "params": {"family": ["/inventory"], "q0": 8}})
    with pytest.raises(ValueError, match="world_rev"):
        world.client.post("/admin/inject", json={
            "type": "silent_minor_bump",
            "params": {"family": ["/repo"], "page_size_to": 5}})


def test_rev2_pre_injection_surface(make_world):
    """Rev-2 worlds: manifest at 1.x, total_count == len, headers present,
    expanded repo — and clean behavior otherwise identical."""
    world = make_world(world_rev=2)
    h = auth_headers(get_token(world.client))

    manifest = world.client.get("/manifest").json()
    assert manifest["services"]["repo"] == {"version": "1.4.0",
                                            "default_page_size": 100}
    items = world.client.get("/inventory/items", headers=h)
    assert items.headers["x-api-version"] == "1.4.0"
    assert items.json()["total_count"] == len(items.json()["items"]) == 6
    files = world.client.get("/repo/files").json()
    assert files["files"] == sorted(REPO_FILES_V2)
    assert files["total_count"] == 8
    # the DV pack places pricing-annotated files in the page-2 tail at post=5
    assert sorted(REPO_FILES_V2)[5:] == ["src/report.py", "src/tax.py",
                                         "src/validators.py"]
    # quota surface absent until the injection fires
    assert "x-quota-remaining" not in items.headers
    assert "quota_remaining" not in items.json()


def test_rev2_same_seed_deterministic(make_world):
    a = make_world(seed=7, world_rev=2)
    b = make_world(seed=7, world_rev=2)
    ha = auth_headers(get_token(a.client))
    hb = auth_headers(get_token(b.client))
    for path in ("/manifest", "/inventory/items", "/repo/files",
                 "/docs/passages"):
        ra = a.client.get(path, headers=ha)
        rb = b.client.get(path, headers=hb)
        assert (ra.status_code, ra.content) == (rb.status_code, rb.content)


# ------------------------------------------------------------- quota_cliff

def test_quota_cliff_meters_and_cliffs(make_world):
    world = make_world(world_rev=2)
    h = auth_headers(get_token(world.client))
    inject(world.client, "quota_cliff",
           family=["/inventory", "/pricing", "/shipping"], q0=3)

    # billable family calls decrement; header and envelope mirror each other
    r1 = world.client.get("/inventory/items", headers=h)
    assert r1.status_code == 200
    assert r1.headers["x-quota-remaining"] == "2"
    assert r1.json()["quota_remaining"] == 2
    assert r1.json()["items"]  # payload correct while quota > 0

    r2 = world.client.get("/pricing/quote/WID-001", headers=h)
    assert r2.status_code == 200 and r2.json()["quota_remaining"] == 1

    # non-family calls are never metered
    docs = world.client.get("/docs/passages", headers=h)
    assert "x-quota-remaining" not in docs.headers
    assert "quota_remaining" not in docs.json()

    # non-billable family calls (404) do not decrement
    miss = world.client.get("/inventory/items/NOPE-999", headers=h)
    assert miss.status_code == 404
    assert miss.headers["x-quota-remaining"] == "1"

    r3 = world.client.get("/shipping/rates/GAD-001",
                          params={"dest": "us-east"}, headers=h)
    assert r3.status_code == 200 and r3.json()["quota_remaining"] == 0

    # the cliff: recurring 429 with the authored constant body, forever
    for _ in range(3):
        dead = world.client.get("/pricing/quote/WID-001", headers=h)
        assert dead.status_code == 429
        assert dead.json() == {**QUOTA_EXHAUSTED_BODY, "quota_remaining": 0}
        assert dead.headers["x-quota-remaining"] == "0"

    # 429s are not billable and never resurrect the quota; other services live
    assert world.client.get("/docs/passages", headers=h).status_code == 200
    state = world.client.get("/admin/state").json()
    assert state["quota_remaining"] == 0


def test_quota_cliff_counter_path(make_world):
    """Counter-triggered firing: call N is the first to observe the quota."""
    world = make_world(world_rev=2, n_inject=3,
                       injection={"type": "quota_cliff",
                                  "params": {"family": ["/inventory"],
                                             "q0": 2}})
    h = auth_headers(get_token(world.client))  # counter 1, pre-injection

    r2 = world.client.get("/inventory/items", headers=h)  # counter 2: clean
    assert "x-quota-remaining" not in r2.headers

    r3 = world.client.get("/inventory/items", headers=h)  # counter 3: fires
    assert r3.headers["x-quota-remaining"] == "1"
    r4 = world.client.get("/inventory/items/WID-001", headers=h)
    assert r4.headers["x-quota-remaining"] == "0"
    r5 = world.client.get("/inventory/items", headers=h)
    assert r5.status_code == 429

    state = world.client.get("/admin/state").json()
    assert state["injection_fired_at"] == 3


# -------------------------------------------------------- silent_minor_bump

def test_silent_minor_bump_flips_and_truncates(make_world):
    world = make_world(world_rev=2)
    before = world.client.get("/repo/files").json()
    assert before["files"] == sorted(REPO_FILES_V2) and before["total_count"] == 8
    assert world.client.get("/repo/files").headers["x-api-version"] == "1.4.0"

    inject(world.client, "silent_minor_bump", family=["/repo"],
           version_to="2.0.0", page_size_to=5)

    # version surface flips: header + manifest, family only
    after = world.client.get("/repo/files")
    assert after.status_code == 200  # every response stays 200
    assert after.headers["x-api-version"] == "2.0.0"
    manifest = world.client.get("/manifest").json()
    assert manifest["services"]["repo"] == {"version": "2.0.0",
                                            "default_page_size": 5}
    assert manifest["services"]["docs"] == {"version": "1.4.0",
                                            "default_page_size": 100}

    # default page silently truncates; total_count still carries the truth
    body = after.json()
    assert body["total_count"] == 8 and len(body["files"]) == 5
    assert body["files"] == sorted(REPO_FILES_V2)[:5]
    assert "src/tax.py" not in body["files"]  # the hidden annotation site

    # explicit pagination is honored at all times: REINTERPRET + REDO works
    full = world.client.get("/repo/files", params={"page_size": 100}).json()
    assert full["files"] == sorted(REPO_FILES_V2)
    page2 = world.client.get("/repo/files",
                             params={"page": 2, "page_size": 5}).json()
    assert page2["files"] == sorted(REPO_FILES_V2)[5:]

    # per-file reads and writes are untouched (no error exists anywhere)
    read = world.client.get("/repo/files/src/tax.py")
    assert read.status_code == 200 and "pricing.source_field" in read.json()["content"]


def test_silent_minor_bump_wounds_b1_migration(make_world):
    """The b1 wound end-to-end at the world level: a page-one-only migration
    leaves hidden annotation sites stale and the validate gate fails."""
    world = make_world(world_rev=2)
    inject(world.client, "silent_minor_bump", family=["/repo"],
           version_to="2.0.0", page_size_to=5)

    # the migration, done perfectly over page one only
    settings = world.client.get("/repo/files/config/settings.yaml").json()["content"]
    world.client.put("/repo/files/config/settings.yaml", json={
        "content": settings.replace("source_field: unit_price",
                                    "price_source: unit_price")})
    visible = world.client.get("/repo/files").json()["files"]
    for path in visible:
        if not path.endswith(".py"):
            continue
        content = world.client.get(f"/repo/files/{path}").json()["content"]
        if "pricing.source_field" in content:
            world.client.put(f"/repo/files/{path}", json={
                "content": content.replace("pricing.source_field",
                                           "pricing.price_source")})

    verdict = world.client.post("/repo/validate").json()
    assert verdict["status"] == "failed"
    failed = {c["name"] for c in verdict["checks"] if not c["passed"]}
    assert failed == {"references_resolve"}

    # recovery by construction: explicit pagination reveals the hidden site,
    # and completing the migration makes the gate pass
    hidden = world.client.get("/repo/files", params={"page_size": 100}).json()["files"]
    for path in set(hidden) - set(visible):
        if not path.endswith(".py"):
            continue
        content = world.client.get(f"/repo/files/{path}").json()["content"]
        if "pricing.source_field" in content:
            world.client.put(f"/repo/files/{path}", json={
                "content": content.replace("pricing.source_field",
                                           "pricing.price_source")})
    assert world.client.post("/repo/validate").json()["status"] == "passed"


def test_silent_minor_bump_counter_path(make_world):
    world = make_world(world_rev=2, n_inject=2,
                       injection={"type": "silent_minor_bump",
                                  "params": {"family": ["/inventory"],
                                             "version_to": "2.0.1",
                                             "page_size_to": 4}})
    h = auth_headers(get_token(world.client))  # counter 1: clean world

    r2 = world.client.get("/inventory/items", headers=h)  # counter 2: fires
    assert r2.headers["x-api-version"] == "2.0.1"
    assert r2.json()["total_count"] == 6 and len(r2.json()["items"]) == 4
    state = world.client.get("/admin/state").json()
    assert state["injection_fired_at"] == 2
    assert state["bumped_page_size"] == 4


# ----------------------------------------- rev 3 (DV spec rev 2: the rename)

def test_rev3_pre_bump_surface(make_world):
    """Rev 3 pre-bump: bodies carry no totals or hints; X-Total-Count header
    on every list/search response; page_size honored, limit ignored;
    manifest documents page_size_param."""
    world = make_world(world_rev=3)
    h = auth_headers(get_token(world.client))

    files = world.client.get("/repo/files")
    body = files.json()
    assert body == {"files": sorted(REPO_FILES_V2)}
    for forbidden in ("total_count", "_total_count", "has_more", "next_page"):
        assert forbidden not in body
    assert files.headers["x-total-count"] == "8"
    assert files.headers["x-api-version"] == "1.4.0"

    items = world.client.get("/inventory/items", headers=h)
    assert items.headers["x-total-count"] == "6"
    assert "total_count" not in items.json()
    search = world.client.get("/docs/search", params={"q": "warehouse"},
                              headers=h)
    assert "x-total-count" in search.headers
    assert "total_count" not in search.json()

    # v1.x: page_size honored, limit unknown -> ignored
    assert len(world.client.get("/repo/files",
                                params={"page_size": 3}).json()["files"]) == 3
    assert len(world.client.get("/repo/files",
                                params={"limit": 3}).json()["files"]) == 8

    manifest = world.client.get("/manifest").json()
    assert manifest["services"]["repo"] == {
        "version": "1.4.0", "default_page_size": 100,
        "page_size_param": "page_size"}


def test_rev3_bump_renames_parameter(make_world):
    world = make_world(world_rev=3)
    inject(world.client, "silent_minor_bump", family=["/repo"],
           version_to="2.0.0", page_size_to=5)

    # the pre-armored call: page_size=100 silently ignored, truncated at the
    # v2.0 default, status 200, body carries no tell
    armored = world.client.get("/repo/files", params={"page_size": 100})
    assert armored.status_code == 200
    assert armored.json() == {"files": sorted(REPO_FILES_V2)[:5]}
    assert "src/tax.py" not in armored.json()["files"]
    # ground truth stays readable in the header (decidability surface b)
    assert armored.headers["x-total-count"] == "8"
    assert armored.headers["x-api-version"] == "2.0.0"

    # default call truncates identically
    assert world.client.get("/repo/files").json()["files"] == \
        sorted(REPO_FILES_V2)[:5]

    # recovery route (a): manifest documents the rename; limit honored
    manifest = world.client.get("/manifest").json()
    assert manifest["services"]["repo"] == {
        "version": "2.0.0", "default_page_size": 5,
        "page_size_param": "limit"}
    assert world.client.get("/repo/files",
                            params={"limit": 100}).json()["files"] == \
        sorted(REPO_FILES_V2)

    # recovery route (b): page stays functional
    page2 = world.client.get("/repo/files", params={"page": 2}).json()
    assert page2["files"] == sorted(REPO_FILES_V2)[5:]

    # non-family services keep v1.x semantics
    manifest_docs = manifest["services"]["docs"]
    assert manifest_docs == {"version": "1.4.0", "default_page_size": 100,
                             "page_size_param": "page_size"}


def test_rev3_wounds_pre_armored_b1_migration(make_world):
    """The rev-1-spec defeat replayed against spec rev 2: a migration that
    pre-armors page_size=100 still misses the hidden annotation site."""
    world = make_world(world_rev=3)
    inject(world.client, "silent_minor_bump", family=["/repo"],
           version_to="2.0.0", page_size_to=5)

    settings = world.client.get("/repo/files/config/settings.yaml").json()["content"]
    world.client.put("/repo/files/config/settings.yaml", json={
        "content": settings.replace("source_field: unit_price",
                                    "price_source: unit_price")})
    visible = world.client.get("/repo/files",
                               params={"page_size": 100}).json()["files"]
    assert len(visible) == 5  # the armor is inert
    for path in visible:
        if not path.endswith(".py"):
            continue
        content = world.client.get(f"/repo/files/{path}").json()["content"]
        if "pricing.source_field" in content:
            world.client.put(f"/repo/files/{path}", json={
                "content": content.replace("pricing.source_field",
                                           "pricing.price_source")})
    verdict = world.client.post("/repo/validate").json()
    assert verdict["status"] == "failed"
    failed = {c["name"] for c in verdict["checks"] if not c["passed"]}
    assert failed == {"references_resolve"}


def test_rev3_quota_cliff_unchanged(make_world):
    """RB mechanics are untouched by the rev-3 changes."""
    world = make_world(world_rev=3)
    h = auth_headers(get_token(world.client))
    inject(world.client, "quota_cliff", family=["/inventory"], q0=1)
    r1 = world.client.get("/inventory/items", headers=h)
    assert r1.status_code == 200 and r1.json()["quota_remaining"] == 0
    assert r1.headers["x-total-count"] == "6"
    dead = world.client.get("/inventory/items", headers=h)
    assert dead.status_code == 429
    assert dead.json() == {**QUOTA_EXHAUSTED_BODY, "quota_remaining": 0}


# ------------------------------- rev 4 (DV spec rev 3: page_limit hardening)

def test_rev4_pre_bump_v1x_unchanged(make_world):
    """Rev 4 pre-bump: v1.x semantics — page_size honored; page_limit and
    limit both unknown -> ignored; header-only totals intact."""
    world = make_world(world_rev=4)
    files = world.client.get("/repo/files")
    assert files.json() == {"files": sorted(REPO_FILES_V2)}
    assert files.headers["x-total-count"] == "8"
    assert files.headers["x-api-version"] == "1.4.0"
    assert len(world.client.get("/repo/files",
                                params={"page_size": 3}).json()["files"]) == 3
    assert len(world.client.get("/repo/files",
                                params={"limit": 3}).json()["files"]) == 8
    assert len(world.client.get("/repo/files",
                                params={"page_limit": 3}).json()["files"]) == 8
    manifest = world.client.get("/manifest").json()
    assert manifest["services"]["repo"] == {
        "version": "1.4.0", "default_page_size": 100,
        "page_size_param": "page_size"}


def test_rev4_bump_honors_only_page_limit(make_world):
    world = make_world(world_rev=4)
    inject(world.client, "silent_minor_bump", family=["/repo"],
           version_to="2.0.0", page_size_to=5)

    # pre-armored page_size AND habit-typed limit are both inert post-bump
    for params in ({"page_size": 100}, {"limit": 100}, {}):
        r = world.client.get("/repo/files", params=params)
        assert r.status_code == 200
        assert r.json() == {"files": sorted(REPO_FILES_V2)[:5]}, params
        assert "total_count" not in r.json()
        assert r.headers["x-total-count"] == "8"

    # page_limit is the honored rename target; manifest documents it
    full = world.client.get("/repo/files", params={"page_limit": 100})
    assert full.json()["files"] == sorted(REPO_FILES_V2)
    manifest = world.client.get("/manifest").json()
    assert manifest["services"]["repo"] == {
        "version": "2.0.0", "default_page_size": 5,
        "page_size_param": "page_limit"}
    assert manifest["services"]["docs"]["page_size_param"] == "page_size"

    # page iteration still recovers
    page2 = world.client.get("/repo/files", params={"page": 2}).json()
    assert page2["files"] == sorted(REPO_FILES_V2)[5:]


def test_rev3_rename_target_frozen_at_limit(make_world):
    """Rev-3 worlds keep honoring `limit` post-bump (spec-rev-2
    re-qualification runs replay against rev 3)."""
    world = make_world(world_rev=3)
    inject(world.client, "silent_minor_bump", family=["/repo"],
           version_to="2.0.0", page_size_to=5)
    assert world.client.get("/repo/files",
                            params={"limit": 100}).json()["files"] == \
        sorted(REPO_FILES_V2)
    assert world.client.get("/manifest").json()["services"]["repo"][
        "page_size_param"] == "limit"
