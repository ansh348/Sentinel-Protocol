"""B6 acceptance: replan behavior (probe_compiler_design_v0.4.md §6, ruling D2).
keep-not-flush + recompile-add + N2-prune-dead + coverage/liveness (death-specimen
detector) + post-replan fire instrumentation + the in-flight-dropped residual.
"""
from __future__ import annotations

from sentinel_v2.probe_spec import (CadenceHint, Comparison, CostClass,
                                    EvidenceClass, FaultShape, Lens, LensOp,
                                    Probe, Provenance)
from sentinel_v2.replan import ReplanReport, instrument_fire, replan


def _prov() -> Provenance:
    return Provenance(plan_step="s", world_fact="f", surface="/x", read="r",
                      predicate="p", recovery_hint="h")


def _p(target: str, *, lens_op=LensOp.STATUS_READ,
       fault_shape=FaultShape.STATUS_CLASS, comparison=Comparison.HARD_INVARIANT,
       pointer=None) -> Probe:
    return Probe(method="GET", target=target, lens=Lens(op=lens_op, pointer=pointer),
                 comparison=comparison, fault_shape=fault_shape,
                 evidence_class=EvidenceClass.STATUS_CODED, cost_class=CostClass.LIGHT,
                 cadence_hint=CadenceHint.EVENT_GATED, provenance=_prov())


def _gate(target="/repo/gate_status") -> Probe:
    return _p(target, lens_op=LensOp.GATE_SHADOW, fault_shape=FaultShape.VALUE_CHANGED,
              comparison=Comparison.HARD_INVARIANT, pointer="/enforcing")


# -- keep-not-flush + recompile-add --------------------------------------------

def test_keep_not_flush_and_recompile_add():
    prior = {"a1": _p("/inventory/items"), "a2": _p("/pricing/quote/WID-001"),
             "a3": _p("/docs/passages/pol-returns")}
    report = replan(prior, live_assumptions={"a1", "a2", "a3", "a4"},
                    recompiled={"a4": _p("/shipping/destinations")}, world_rev=2)
    assert set(report.inventory) == {"a1", "a2", "a3", "a4"}
    assert report.added == ["a4"] and report.kept == ["a1", "a2", "a3"]
    assert report.uncovered == [] and report.pruned_dead == []


# -- death-specimen: averted by keep-not-flush, detected when truly uncovered ---

def test_death_specimen_averted_by_keep_not_flush():
    """v1's death specimen: replan -> recompiled set covers NONE of the original
    armed surfaces -> injection fires unwatched. Keep-not-flush keeps them
    covered, so nothing is left uncovered."""
    prior = {"a1": _p("/inventory/items"), "a2": _p("/pricing/quote/WID-001")}
    report = replan(prior, live_assumptions={"a1", "a2"}, recompiled={}, world_rev=2)
    assert set(report.inventory) == {"a1", "a2"}        # still watched
    assert report.uncovered == [] and report.death_specimen_detected is False


def test_death_specimen_detected_when_a_live_assumption_is_uncovered():
    # recompile covers none AND nothing prior covers the live assumption
    bare = replan({}, live_assumptions={"aX"}, recompiled={}, world_rev=2)
    assert bare.uncovered == ["aX"] and bare.death_specimen_detected is True

    # the original armed surface went dead under the revised rev, was pruned, and
    # is left uncovered -> flagged LOUDLY instead of firing into an unwatched world
    pruned = replan({"a1": _p("/manifest")}, live_assumptions={"a1"},
                    recompiled={}, world_rev=1)
    assert pruned.pruned_dead == ["a1"] and pruned.uncovered == ["a1"]
    assert pruned.death_specimen_detected is True


# -- N2 prune-dead -------------------------------------------------------------

def test_n2_prune_only_dead_probes():
    prior = {"live": _p("/inventory/items"), "dead": _p("/manifest")}
    at_rev1 = replan(prior, live_assumptions={"live"}, recompiled={}, world_rev=1)
    assert at_rev1.pruned_dead == ["dead"] and set(at_rev1.inventory) == {"live"}
    # /manifest is live at rev 4: not pruned
    at_rev4 = replan(prior, live_assumptions={"live", "dead"}, recompiled={},
                     world_rev=4)
    assert at_rev4.pruned_dead == [] and set(at_rev4.inventory) == {"live", "dead"}


def test_gate_shadow_probe_is_exempt_from_dead_prune():
    """§4 probe targets live outside the path samples; their liveness is the
    trapdoor's job, so the path sweep must not prune them."""
    report = replan({"g": _gate()}, live_assumptions={"g"}, recompiled={}, world_rev=2)
    assert report.pruned_dead == [] and "g" in report.inventory
    assert report.uncovered == []


# -- in-flight-dropped residual (observable, not silent) -----------------------

def test_in_flight_dropped_residual_is_logged():
    prior = {"a1": _p("/inventory/items"), "a2": _p("/pricing/quote/WID-001")}
    # the revised plan drops a2, but work is still in flight against it
    report = replan(prior, live_assumptions={"a1"}, recompiled={},
                    in_flight={"a2"}, world_rev=2)
    assert "a2" in report.inventory               # kept (still watching)
    assert report.in_flight_dropped == ["a2"]      # named residual, observable
    assert report.uncovered == []                  # a1 stays covered


# -- post-replan fire instrumentation ------------------------------------------

def test_post_replan_fire_is_instrumented():
    prior = {"a1": _p("/inventory/items"), "a2": _p("/pricing/quote/WID-001")}
    report = replan(prior, live_assumptions={"a1"}, recompiled={},
                    in_flight={"a2"}, world_rev=2, epoch=3)

    live_fire = instrument_fire(report, "a1")
    assert live_fire["post_replan"] and live_fire["live"]
    assert live_fire["kept_but_irrelevant"] is False and live_fire["epoch"] == 3

    dropped_fire = instrument_fire(report, "a2")
    assert dropped_fire["kept_but_irrelevant"] is True       # kept but no longer live
    assert dropped_fire["in_flight_dropped"] is True
    assert dropped_fire["post_replan"] and dropped_fire["epoch"] == 3
