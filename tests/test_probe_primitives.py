"""N5 acceptance: read-only probe executor primitives + the scheduler seam."""
from __future__ import annotations

import pytest

from conftest import auth_headers, get_token
from sentinel_v2.probes import (ProbeExecutor, content_sha256, read_field,
                                read_header, schema_fingerprint)
from sentinel_v2.scheduler import CadencePolicy, NoOpCadence, ProbeScheduler
from trace import read_trace


@pytest.fixture
def probe_world(make_world):
    world = make_world(probe_channel=True, world_rev=2)
    token = get_token(world.client)
    return world, ProbeExecutor(world.client, auth_token=token)


def test_executor_get_rides_the_side_channel(probe_world):
    world, ex = probe_world
    result = ex.get("/inventory/items")
    assert result.status == 200
    assert isinstance(result.body, dict)
    # the request rode the probe channel: no counter advance past the token
    assert world.client.get("/admin/state").json()["counter"] == 1
    events = read_trace(world.trace_path)
    assert [e["payload"]["probe_seq"] for e in events
            if e["event_type"] == "probe_call"] == [1]


def test_executor_head(probe_world):
    world, ex = probe_world
    result = ex.head("/inventory/items")
    assert result.status == 200
    assert world.client.get("/admin/state").json()["counter"] == 1


def test_executor_surface_is_read_only_by_construction():
    public = [name for name in dir(ProbeExecutor) if not name.startswith("_")]
    assert sorted(public) == ["get", "head"]


def test_read_field_supports_all_three_pointer_dialects(probe_world):
    _, ex = probe_world
    result = ex.get("/pricing/quote/WID-001")
    assert read_field(result, "/unit_price") == read_field(result, "unit_price")
    assert read_field(result, "$.unit_price") == read_field(result, "unit_price")
    assert read_field(result, "missing.key", default=None) is None
    with pytest.raises(KeyError):
        read_field(result, "missing.key")


def test_read_header_is_case_insensitive(probe_world):
    _, ex = probe_world
    result = ex.get("/inventory/items")
    assert read_header(result, "X-API-Version") == read_header(
        result, "x-api-version")
    assert read_header(result, "No-Such-Header", "absent") == "absent"


def test_content_sha256_is_deterministic_and_change_sensitive(probe_world):
    _, ex = probe_world
    a = ex.get("/docs/passages/pol-returns")
    b = ex.get("/docs/passages/pol-returns")
    other = ex.get("/docs/passages/ven-terms")
    assert content_sha256(a) == content_sha256(b)
    assert content_sha256(a) != content_sha256(other)


def test_schema_fingerprint_tracks_shape_not_values():
    fp1 = schema_fingerprint({"sku": "WID-001", "unit_price": 9.5,
                              "currency": "USD"})
    fp2 = schema_fingerprint({"sku": "GAD-002", "unit_price": 120.0,
                              "currency": "USD"})
    renamed = schema_fingerprint({"sku": "WID-001", "price": 950,
                                  "currency": "USD"})
    assert fp1 == fp2
    assert fp1 != renamed
    nested = schema_fingerprint({"items": [{"sku": "a"}], "n": 1})
    assert "items.sku:str" in nested and "n:int" in nested


def test_noop_cadence_never_sweeps():
    calls = []
    scheduler = ProbeScheduler(NoOpCadence())
    for i in range(20):
        assert scheduler.maybe_sweep({"counter": i},
                                     lambda: calls.append(1)) is None
    assert calls == []


def test_scheduler_runs_sweep_only_when_policy_says_due():
    class EveryTime(CadencePolicy):
        def due(self, context):
            return True

    scheduler = ProbeScheduler(EveryTime())
    assert scheduler.maybe_sweep({}, lambda: "swept") == "swept"


def test_cadence_policy_is_abstract():
    with pytest.raises(TypeError):
        CadencePolicy()  # the seam exists; semantics are morning work
