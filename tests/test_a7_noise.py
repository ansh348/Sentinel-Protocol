"""A7 benign-noise unit tests (D36): flag-on mechanisms + flag-off inertness.

Byte-identity of the flag-OFF path against banked traces is the separate admissibility
gate (`analysis/replay_check.py`, verified before these count). These tests exercise the
flag-ON behaviour: each class fires at its seed-derived schedule and heals / stays benign,
and `elapsed_ms` is a constant envelope present across ALL classes (D36).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from world.server import create_app
from world.state import NoiseProfile, RunConfig, WorldState

WID = "WID-001"
HDR = {"X-Worker-Id": "w1"}


def _config(noise_class=None, seed=4):
    return RunConfig(
        run_id=f"a7-{noise_class or 'off'}-s{seed}", seed=seed, system="S1",
        task_id="a1", trace_path="unused.jsonl",
        noise_profile=NoiseProfile(noise_class=noise_class) if noise_class else None,
    )


def _client(config, tmp_path, name="t"):
    config = config.model_copy(update={"trace_path": str(tmp_path / f"{name}.jsonl")})
    return TestClient(create_app(config), raise_server_exceptions=False)


def _token(client):
    r = client.post("/auth/token", headers=HDR)
    if r.status_code == 500:  # transient_500 may 500 the first call; the retry heals
        r = client.post("/auth/token", headers=HDR)
    return r.json()["token"]


def _authed(client):
    return {**HDR, "Authorization": f"Bearer {_token(client)}"}


def _get_healed(client, path, headers):
    """GET that tolerates the one transient_500 (it may land on any early call); the
    retry heals, per the benign-noise contract."""
    r = client.get(path, headers=headers)
    if r.status_code == 500:
        r = client.get(path, headers=headers)
    return r


# -- flag-off inertness (unit-level; the banked-trace byte-identity is the real gate) ------

def test_flag_off_state_is_inert():
    s = WorldState(_config(None))
    assert s.noise_rng is None
    assert s.noise_500_trigger is None
    assert s.noise_latency_trigger is None
    assert s.noise_elapsed_base_ms is None
    assert s.noise_additive_value is None


def test_flag_off_responses_carry_no_noise_fields(tmp_path):
    client = _client(_config(None), tmp_path)
    body = client.get(f"/pricing/quote/{WID}", headers=_authed(client)).json()
    assert "elapsed_ms" not in body
    assert "advisory" not in body


# -- elapsed_ms is a constant envelope on EVERY A7 class (D36) -----------------------------

@pytest.mark.parametrize("nc", ["transient_500", "latency_spike", "additive_field"])
def test_elapsed_ms_present_in_all_classes(nc, tmp_path):
    client = _client(_config(nc), tmp_path)
    r = _get_healed(client, f"/pricing/quote/{WID}", _authed(client))
    assert r.status_code == 200
    assert "elapsed_ms" in r.json()


# -- transient_500: fires exactly once at the seed-derived call, then heals ----------------

def test_transient_500_fires_once_and_heals(tmp_path):
    client = _client(_config("transient_500"), tmp_path)
    statuses = [client.post("/auth/token", headers=HDR).status_code for _ in range(6)]
    assert statuses.count(500) == 1, statuses          # exactly one transient
    assert statuses[-1] == 200                          # healed by the retry


def test_transient_500_body_is_benign_transient(tmp_path):
    client = _client(_config("transient_500"), tmp_path)
    seen_500 = None
    for _ in range(4):
        r = client.post("/auth/token", headers=HDR)
        if r.status_code == 500:
            seen_500 = r.json()
    assert seen_500 is not None
    assert seen_500["error"] == "internal_error"


# -- latency_spike: exactly one elevated elapsed_ms; baseline otherwise --------------------

def test_latency_spike_single_elevated_value(tmp_path):
    client = _client(_config("latency_spike"), tmp_path)
    r0 = client.post("/auth/token", headers=HDR)
    tok = r0.json()["token"]
    hdr = {**HDR, "Authorization": f"Bearer {tok}"}
    elapsed = [r0.json()["elapsed_ms"]]
    for _ in range(6):
        elapsed.append(client.get(f"/pricing/quote/{WID}", headers=hdr).json()["elapsed_ms"])
    spikes = [e for e in elapsed if e >= 1000]
    baseline = [e for e in elapsed if e < 1000]
    assert len(spikes) == 1, elapsed                    # one spike only
    assert all(e < 100 for e in baseline), elapsed      # baseline stays small


# -- additive_field: one extra unused field; every original field preserved (benign) -------

def test_additive_field_is_purely_additive(tmp_path):
    off = _client(_config(None), tmp_path, name="off")
    b_off = off.get(f"/pricing/quote/{WID}", headers=_authed(off)).json()

    on = _client(_config("additive_field"), tmp_path, name="on")
    b_on = on.get(f"/pricing/quote/{WID}", headers=_authed(on)).json()

    for k, v in b_off.items():                          # nothing removed or changed
        assert b_on[k] == v
    assert set(b_on) - set(b_off) == {"elapsed_ms", "advisory"}
    assert b_on["advisory"].startswith("a7-")


# -- determinism: same seed -> same schedule (byte-replayable) -----------------------------

def test_same_seed_same_schedule():
    a = WorldState(_config("latency_spike", seed=7))
    b = WorldState(_config("latency_spike", seed=7))
    assert a.noise_latency_trigger == b.noise_latency_trigger
    assert a.noise_elapsed_base_ms == b.noise_elapsed_base_ms
    assert a.noise_elapsed_spike_ms == b.noise_elapsed_spike_ms


# -- A7b: transient_500 monitored-surface placement (target_surface param) -----------------

def test_transient_500_target_surface_lands_on_that_surface(tmp_path):
    cfg = RunConfig(
        run_id="a7b", seed=16, system="V2", task_id="a1",
        trace_path=str(tmp_path / "t.jsonl"),
        noise_profile=NoiseProfile(noise_class="transient_500",
                                   params={"target_surface": "/pricing/quote/*"}))
    client = TestClient(create_app(cfg), raise_server_exceptions=False)
    tok = client.post("/auth/token", headers=HDR).json()["token"]   # token != target -> 200
    hdr = {**HDR, "Authorization": f"Bearer {tok}"}
    assert client.get("/inventory/items", headers=hdr).status_code == 200   # non-target -> 200
    r1 = client.get("/pricing/quote/WID-001", headers=hdr)          # first target hit -> 500
    assert r1.status_code == 500
    assert r1.json()["error"] == "internal_error"
    r2 = client.get("/pricing/quote/WID-001", headers=hdr)          # retry heals
    assert r2.status_code == 200
    # only one 500 total
    assert all(client.get("/pricing/quote/GAD-001", headers=hdr).status_code == 200
               for _ in range(3))
