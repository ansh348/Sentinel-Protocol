"""D31 C4: the write-surface footprint policy.

A planned-write surface is footprint-scoped, not an active drift probe (a legitimate
write would false-positive — the b1+clean FIR 1.0) and not silently passive:
off-footprint change -> DRIFT; in-footprint -> verify-or-UNCOVERED_CAUTION;
persistence runs only after the footprint check, so a legitimate permanent write is
never promoted as drift.
"""
from __future__ import annotations

from sentinel_v2.compile_probes import (SoftAssumption, SoftAssumptionSet,
                                        compile_pipeline)
from sentinel_v2.write_surface import (FootprintVerdict, WriteFootprint,
                                       evaluate_write_footprint)

_BASE = {"pricing": {"source_field": "unit_price"}, "report": {"format": "json"}}


def test_whole_surface_legit_rewrite_is_uncovered_caution_not_drift():
    """b1+clean: a legitimate whole-file migration rewrite with no checkable expected
    post-state -> UNCOVERED_CAUTION (loud, scored), NOT a drift interrupt and NOT
    silently clean."""
    fp = WriteFootprint(surface="/repo/files/config/settings.yaml")  # whole-surface
    migrated = {"pricing": {"price_source": "unit_price"}, "report": {"format": "json"}}
    ev = evaluate_write_footprint(fp, _BASE, migrated)
    assert ev.verdict is FootprintVerdict.UNCOVERED_CAUTION


def test_off_footprint_change_is_drift():
    fp = WriteFootprint(surface="/s", fields=("pricing.source_field",))
    obs = {"pricing": {"source_field": "unit_price"}, "report": {"format": "csv"}}
    ev = evaluate_write_footprint(fp, _BASE, obs)        # report.format changed off-footprint
    assert ev.verdict is FootprintVerdict.DRIFT and "report.format" in (ev.witness or [])


def test_in_footprint_change_without_expected_is_uncovered():
    fp = WriteFootprint(surface="/s", fields=("pricing.source_field",))
    obs = {"pricing": {"source_field": "changed"}, "report": {"format": "json"}}
    ev = evaluate_write_footprint(fp, _BASE, obs)        # only the footprint field moved
    assert ev.verdict is FootprintVerdict.UNCOVERED_CAUTION


def test_in_footprint_verify_clean_then_drift():
    # a rename footprint covers BOTH the old and new key; the expected post-state is
    # the new key carrying the preserved value.
    fp = WriteFootprint(surface="/s",
                        fields=("pricing.source_field", "pricing.price_source"),
                        expected={"pricing.price_source": "unit_price"})
    legit = {"pricing": {"price_source": "unit_price"}, "report": {"format": "json"}}
    assert evaluate_write_footprint(fp, _BASE, legit).verdict is FootprintVerdict.CLEAN
    # the injected schema_drift renames to price_FIELD, not price_source: the new key
    # appears OFF the authorized footprint -> DRIFT (detected for the right reason)
    injected = {"pricing": {"price_field": "unit_price"}, "report": {"format": "json"}}
    assert evaluate_write_footprint(fp, _BASE, injected).verdict is FootprintVerdict.DRIFT


def test_compile_routes_write_surface_to_footprints_not_probes_not_passive():
    soft = SoftAssumptionSet(plan_id="b1", assumptions=[
        SoftAssumption(plan_step="GET then PUT config/settings.yaml",
                       world_fact="settings.yaml carries the pricing key",
                       surface="/repo/files/config/settings.yaml",
                       recovery_hint="re-read settings on drift")])
    cr = compile_pipeline(soft, world_rev=2, planned_write_set=("/repo/files/*",))
    # NOT an active drift probe (would false-positive on the legit write) ...
    assert not any(p.target == "/repo/files/config/settings.yaml" for p in cr.probes)
    # ... and NOT silently passive — it is a tracked, footprint-scoped surface
    assert [f.surface for f in cr.write_footprints] == ["/repo/files/config/settings.yaml"]
    assert not cr.passive


def test_legit_write_not_promoted_by_persistence():
    """The write surface is evaluated by the footprint predicate, not the ordinary
    drift+D28-persistence path (it is never compiled as an active probe), so a
    legitimate permanent write (CLEAN/UNCOVERED) never self-corroborates as drift."""
    fp = WriteFootprint(surface="/s")                    # whole-surface, unverifiable
    migrated = {"pricing": {"price_source": "unit_price"}}
    # re-observing the same legitimate post-state any number of times never escalates
    for _ in range(5):
        ev = evaluate_write_footprint(fp, _BASE, migrated)
        assert ev.verdict is not FootprintVerdict.DRIFT
