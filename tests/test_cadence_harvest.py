"""C2 acceptance: the live ReObservationSource and the six-condition harvest-
equivalence gate (decisions/cadence_semantics.md §5, §8; D29). Synthetic worker
reads + one real seen-category world for the live (header-carrying) path.
"""
from __future__ import annotations

from conftest import get_token
from sentinel_v2.cadence import (HarvestVerdict, LiveReObservationSource,
                                 WorkerRead, harvest_equivalence,
                                 is_request_side_error)
from sentinel_v2.corroboration import (Grade, Signal, corroborate_signal)
from sentinel_v2.probe_spec import Lens, LensOp
from sentinel_v2.probes import ProbeExecutor, ProbeResult
from sentinel_v2.typing_engine import Invariant


def R(body, *, path="/inventory/items/WID-001", status=200, headers=None) -> ProbeResult:
    return ProbeResult(method="GET", path=path, status=status,
                       headers=headers or {}, body=body)


def _read(**o) -> WorkerRead:
    base = dict(surface_id="/inventory/items/WID-001", method="GET",
                auth_principal="w1", cache_state="fresh",
                raw_captured_pre_transform=True,
                result=R({"sku": "WID-001", "quantity": 68}), malformed=False)
    base.update(o)
    return WorkerRead(**base)


FIELD_LENS = Lens(op=LensOp.FIELD_READ, pointer="/quantity")


# -- the six conditions: only an all-pass read is coverage ----------------------

def test_clean_equivalent_read_is_coverage():
    v = harvest_equivalence(_read(), expected_surface="/inventory/items/WID-001",
                            lens=FIELD_LENS, expected_principal="w1")
    assert v.ok


def test_write_is_telemetry_not_coverage():
    v = harvest_equivalence(_read(method="PUT"),
                            expected_surface="/inventory/items/WID-001",
                            lens=FIELD_LENS, expected_principal="w1")
    assert not v.ok and "side-effect-free" in v.reason


def test_different_auth_is_telemetry_not_coverage():
    v = harvest_equivalence(_read(auth_principal="root"),
                            expected_surface="/inventory/items/WID-001",
                            lens=FIELD_LENS, expected_principal="w1")
    assert not v.ok and "auth" in v.reason


def test_stale_cache_is_telemetry_not_coverage():
    v = harvest_equivalence(_read(cache_state="stale"),
                            expected_surface="/inventory/items/WID-001",
                            lens=FIELD_LENS, expected_principal="w1")
    assert not v.ok and "stale" in v.reason


def test_not_captured_pre_transform_is_telemetry():
    v = harvest_equivalence(_read(raw_captured_pre_transform=False),
                            expected_surface="/inventory/items/WID-001",
                            lens=FIELD_LENS, expected_principal="w1")
    assert not v.ok and "before worker transform" in v.reason


def test_partial_subset_excluding_the_region_is_telemetry():
    # a paginated/partial response missing the monitored /quantity field
    partial = _read(result=R({"sku": "WID-001"}))     # no quantity
    v = harvest_equivalence(partial, expected_surface="/inventory/items/WID-001",
                            lens=FIELD_LENS, expected_principal="w1")
    assert not v.ok and "monitored region absent" in v.reason


def test_different_surface_is_telemetry():
    v = harvest_equivalence(_read(surface_id="/pricing/quote/WID-001"),
                            expected_surface="/inventory/items/WID-001",
                            lens=FIELD_LENS, expected_principal="w1")
    assert not v.ok and "different surface" in v.reason


# -- request-side errors never trip the status fast path ------------------------

def test_malformed_worker_call_is_request_side_not_surface():
    assert is_request_side_error(_read(malformed=True, result=R({"e": "bad"}, status=400)))
    assert is_request_side_error(_read(result=R({"e": "bad"}, status=400)))   # 400 code
    assert is_request_side_error(_read(method="PUT", result=R({"e": "x"}, status=409)))
    # a well-formed read whose surface returned 401 is NOT request-side (surface anomaly)
    assert not is_request_side_error(_read(result=R({"valid": False}, status=401)))


def test_source_excludes_request_side_error_from_observations_no_fast_path():
    src = LiveReObservationSource()
    src.harvest(_read(malformed=True, result=R({"e": "bad"}, status=400)),
                lens=FIELD_LENS, expected_principal="w1")
    assert src.observations("/inventory/items/WID-001") == []        # never coverage
    assert src.telemetry("/inventory/items/WID-001")                 # recorded as telemetry
    # corroboration over the (empty) observation stream cannot fast-path-interrupt
    status_lens = Lens(op=LensOp.STATUS_READ)
    from sentinel_v2.probe_spec import (CadenceHint, Comparison, CostClass,
                                        EvidenceClass, FaultShape, Probe, Provenance)
    probe = Probe(method="GET", target="/inventory/items/WID-001", lens=status_lens,
                  comparison=Comparison.HARD_INVARIANT, fault_shape=FaultShape.STATUS_CLASS,
                  evidence_class=EvidenceClass.STATUS_CODED, cost_class=CostClass.LIGHT,
                  cadence_hint=CadenceHint.EVENT_GATED,
                  provenance=Provenance(plan_step="s", world_fact="f",
                                        surface="/inventory/items/WID-001", read="r",
                                        predicate="p", recovery_hint="h"))
    sig = Signal(probe=probe,
                 observations=src.observations("/inventory/items/WID-001"),
                 invariant=Invariant(status_in=(200,)))
    assert corroborate_signal(sig) is None     # no observation -> no fast path


def test_a_real_surface_401_is_a_coverage_observation_and_fast_paths():
    """Contrast: a well-formed read whose surface returns 401 (a surface anomaly, not
    a request error) IS credited and DOES trip the status fast path."""
    src = LiveReObservationSource()
    src.harvest(_read(result=R({"valid": False}, status=401)),
                lens=Lens(op=LensOp.STATUS_READ), expected_principal="w1")
    obs = src.observations("/inventory/items/WID-001")
    assert len(obs) == 1 and obs[0].status == 401


# -- the live source carries headers (resolves the trace-only limitation) -------

def test_live_source_carries_headers(make_world):
    world = make_world(probe_channel=True, world_rev=1)
    token = get_token(world.client)
    ex = ProbeExecutor(world.client, auth_token=token)
    src = LiveReObservationSource(executor=ex)
    obs = src.probe("/inventory/items/WID-001")
    assert obs is not None and obs.status == 200
    assert obs.headers                                   # non-empty headers, unlike trace-only
    assert src.observations("/inventory/items/WID-001")[-1].headers
