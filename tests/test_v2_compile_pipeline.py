"""C3 acceptance: wiring soft assumptions into the substrate.
Grounding (loud), provenance gate (→ telemetry), attachment+lens+typing, and the
§4 gate path (trapdoor / uncovered).
"""
from __future__ import annotations

import pytest

from conftest import get_token
from sentinel_v2.compile_probes import (CompileResult, GroundingError,
                                        SoftAssumption, SoftAssumptionSet,
                                        compile_pipeline)
from sentinel_v2.probe_spec import Comparison, FaultShape, LensOp


def _set(*assumptions) -> SoftAssumptionSet:
    return SoftAssumptionSet(plan_id="a1", assumptions=list(assumptions))


def _a(surface, *, plan_step="s1", world_fact="the step trusts this surface",
       pointer=None, recovery_hint="replan via this surface") -> SoftAssumption:
    return SoftAssumption(plan_step=plan_step, world_fact=world_fact,
                          surface=surface, pointer=pointer, recovery_hint=recovery_hint)


# -- grounding (loud) ----------------------------------------------------------

def test_grounding_rejects_hallucinated_surface_loudly():
    soft = _set(_a("/pricing/quote/WID-001"), _a("/pricing/totally_invented"))
    with pytest.raises(GroundingError) as err:
        compile_pipeline(soft, world_rev=4)
    assert "/pricing/totally_invented" in str(err.value)
    assert "/pricing/totally_invented" in err.value.surfaces
    assert "/pricing/quote/WID-001" not in err.value.surfaces


# -- provenance gate (→ telemetry) --------------------------------------------

def test_provenance_gate_demotes_assumption_without_recovery_hint():
    soft = _set(_a("/inventory/items", recovery_hint=None))
    result = compile_pipeline(soft, world_rev=4)
    assert result.probes == []
    assert len(result.telemetry_only) == 1
    assert "provenance" in result.telemetry_only[0]["reason"]


# -- attachment + lens selection ----------------------------------------------

def test_value_pointer_attaches_a_value_probe():
    soft = _set(_a("/docs/passages/pol-returns", pointer="/content"))
    result = compile_pipeline(soft, world_rev=4)
    assert len(result.probes) == 1
    p = result.probes[0]
    assert p.lens.op is LensOp.FIELD_READ and p.fault_shape is FaultShape.VALUE_CHANGED
    assert p.comparison is Comparison.PROOF_BASELINE


def test_bare_surface_attaches_a_structure_probe():
    soft = _set(_a("/pricing/quote/WID-001"))
    result = compile_pipeline(soft, world_rev=4)
    assert len(result.probes) == 1
    assert result.probes[0].lens.op is LensOp.SCHEMA_FINGERPRINT
    assert result.probes[0].fault_shape is FaultShape.SCHEMA_SHAPE


def test_planned_write_set_surface_is_footprint_scoped():
    # D31: a planned-write surface is footprint-scoped, not an active drift probe
    # and not silently passive.
    soft = _set(_a("/repo/files/config/settings.yaml", pointer="/content"))
    result = compile_pipeline(soft, world_rev=4,
                              planned_write_set=("/repo/files/*",))
    assert result.probes == [] and result.passive == []
    assert [f.surface for f in result.write_footprints] == \
        ["/repo/files/config/settings.yaml"]


# -- §4 gate path --------------------------------------------------------------

def test_gate_assumption_compiles_via_trapdoor_with_world(make_world):
    world = make_world(probe_channel=True, world_rev=4)
    token = get_token(world.client)
    soft = _set(_a("/repo/validate", world_fact="the repo gate actually enforces",
                   recovery_hint="replan via the gate"))
    result = compile_pipeline(soft, world_rev=4, world=world, auth_token=token)
    assert len(result.probes) == 1
    assert result.probes[0].lens.op is LensOp.GATE_SHADOW
    assert result.probes[0].target == "/repo/gate_status"
    assert result.uncovered == []


def test_gate_assumption_uncovered_without_world():
    soft = _set(_a("/docs/validate", world_fact="the docs gate enforces",
                   recovery_hint="replan via the gate"))
    result = compile_pipeline(soft, world_rev=4)  # no world → trapdoor cannot run
    assert result.probes == [] and len(result.uncovered) == 1
    assert "trapdoor cannot run" in result.uncovered[0]["reason"]


def test_tolerates_appendix_dialect_method_and_template():
    """The model copies the appendix's 'METHOD /path/{template}' form; the
    substrate normalizes it (strip method, ground a template to a concrete
    representative) instead of rejecting it as hallucinated (D5/D8-class)."""
    soft = _set(_a("GET /pricing/quote/{sku}"),       # method + template
                _a("POST /repo/validate", world_fact="gate enforces",
                   recovery_hint="replan"))           # method on a gate path
    result = compile_pipeline(soft, world_rev=4)
    targets = {p.target for p in result.probes}
    assert any(t.startswith("/pricing/quote/") for t in targets)  # instantiated
    # the gate path normalized to a §4 shadow probe (no world here → uncovered)
    assert any("/repo/validate" in u["surface"] for u in result.uncovered)


def test_grounds_an_invented_param_id_via_its_real_route():
    """The model names the right route but invents the id (/pricing/quote/SKU-001;
    real SKUs are WID-001/…). The substrate grounds it to a real representative
    instead of dropping it. A truly hallucinated surface still fails loudly."""
    ok = compile_pipeline(_set(_a("/pricing/quote/SKU-001")), world_rev=4)
    assert len(ok.probes) == 1 and ok.probes[0].target.startswith("/pricing/quote/")
    assert "SKU-001" not in ok.probes[0].target          # grounded to a real id
    with pytest.raises(GroundingError):
        compile_pipeline(_set(_a("/pricing/totally_invented")), world_rev=4)


def test_full_seen_set_compiles_a_mix():
    soft = _set(
        _a("/pricing/quote/WID-001"),                              # structure
        _a("/docs/passages/pol-returns", pointer="/content"),      # value
        _a("/auth/validate"),                                      # structure (status folds in)
        _a("/inventory/items", recovery_hint=None),                # → telemetry
    )
    result = compile_pipeline(soft, world_rev=4)
    assert len(result.probes) == 3 and len(result.telemetry_only) == 1
    assert {p.target for p in result.probes} == {
        "/pricing/quote/WID-001", "/docs/passages/pol-returns", "/auth/validate"}
