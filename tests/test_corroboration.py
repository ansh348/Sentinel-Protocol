"""C1 acceptance: the pure persistence decision (design v0.4 §2.2; ruling D28).
Synthetic anomaly-flag sequences only — fully deterministic, no LLM, no world.
"""
from __future__ import annotations

from conftest import auth_headers, get_token
from sentinel_v2.corroboration import (CorroboratedInvalidation, Grade,
                                       PersistenceDecision, Signal,
                                       corroborate, corroborate_signal,
                                       decide_persistence)
from sentinel_v2.probe_spec import (CadenceHint, Comparison, CostClass,
                                    EvidenceClass, FaultShape, Lens, LensOp,
                                    Probe, Provenance)
from sentinel_v2.probes import ProbeExecutor, ProbeResult
from sentinel_v2.typing_engine import BaselineObligations, Invariant

P = PersistenceDecision.PROMOTE
T = PersistenceDecision.TELEMETRY


# -- builders (seen-category surfaces; synthetic fixtures) ----------------------

def R(body, *, path="/x", status=200, headers=None) -> ProbeResult:
    return ProbeResult(method="GET", path=path, status=status,
                       headers=headers or {}, body=body)


def _prov(surface="/x") -> Provenance:
    return Provenance(plan_step="s", world_fact="f", surface=surface, read="r",
                      predicate="p", recovery_hint="h")


def _probe(fault_shape, comparison, lens, *, target="/x",
           evidence_class=EvidenceClass.CONTENT_SHAPED,
           cost_class=CostClass.LIGHT) -> Probe:
    return Probe(method="GET", target=target, lens=lens, comparison=comparison,
                 fault_shape=fault_shape, evidence_class=evidence_class,
                 cost_class=cost_class, cadence_hint=CadenceHint.EVENT_GATED,
                 provenance=_prov(target))


def _obl() -> BaselineObligations:
    return BaselineObligations(clean=True, equivalent=True, stationary=True,
                               targeted=True, frozen=True)


# -- the three ruling cases ----------------------------------------------------

def test_still_anomalous_on_relook_promotes():
    """First sighting + ONE confirming re-look that still shows the anomaly."""
    assert decide_persistence([True, True]) is P


def test_healed_by_relook_stays_telemetry():
    """A one-shot wobble that has healed by the re-look is not corroborated."""
    assert decide_persistence([True, False]) is T


def test_single_observation_only_is_telemetry_never_blind():
    """No confirming re-look yet — never promoted blind (D28)."""
    assert decide_persistence([True]) is T
    assert decide_persistence([]) is T


# -- threshold = ONE re-look (two CONSECUTIVE anomalous) ------------------------

def test_promotes_when_fault_appears_after_clean_relooks():
    # healthy re-observations, then the fault arrives and persists across a re-look
    assert decide_persistence([False, False, True, True]) is P


def test_intermittent_wobbles_never_persist():
    """Wobble / heal / wobble: no two consecutive anomalous reads — telemetry.
    This is the noise model the threshold is designed to reject."""
    assert decide_persistence([True, False, True, False, True]) is T


def test_rebreak_then_persist_promotes():
    """A wobble that heals, then a real fault that persists across its own
    re-look, still promotes (the persistence is in the later pair)."""
    assert decide_persistence([True, False, True, True]) is P


def test_persistence_then_heal_still_promoted():
    """Once a confirming re-look has shown the anomaly, later healing does not
    un-promote — the corroborated invalidation already earned its route."""
    assert decide_persistence([True, True, False]) is P


# -- adjacency, NOT a count (D28 no-raw-count prohibition) ----------------------

def test_no_raw_count_many_non_consecutive_wobbles_do_not_promote():
    """Many wobbles do not cross any 'exceeds N' threshold — there is none. Only
    consecutive persistence promotes."""
    intermittent = [True, False] * 50            # 50 wobbles, none consecutive
    assert decide_persistence(intermittent) is T
    # whereas a single consecutive pair anywhere is enough (it is persistence,
    # not volume, that promotes)
    assert decide_persistence([False] * 50 + [True, True]) is P


# == C2: the corroboration layer (routing) =====================================

# -- fast path: fire on their own, no persistence ------------------------------

def test_status_coded_signal_takes_the_fast_path_no_persistence():
    """A status-coded signal interrupts on its own from a SINGLE observation —
    no confirming re-look required (D28 status fast path)."""
    probe = _probe(FaultShape.STATUS_CLASS, Comparison.HARD_INVARIANT,
                   Lens(op=LensOp.STATUS_READ), target="/auth/validate",
                   evidence_class=EvidenceClass.STATUS_CODED)
    sig = Signal(probe=probe, observations=[R({"valid": False}, status=401)],
                 invariant=Invariant(status_in=(200,)))
    inv = corroborate_signal(sig)
    assert inv is not None and inv.grade is Grade.INTERRUPT
    assert inv.target == "/auth/validate" and inv.persistence is None


def test_typed_drift_interrupts_on_its_own():
    """A value change that instantiates a fault-shape interrupts on the first
    anomalous observation; no persistence needed."""
    probe = _probe(FaultShape.VALUE_CHANGED, Comparison.PROOF_BASELINE,
                   Lens(op=LensOp.FIELD_READ, pointer="/unit_price"),
                   target="/pricing/quote/WID-001")
    sig = Signal(probe=probe, baseline=R({"unit_price": 19.68}),
                 observations=[R({"unit_price": 25.0})], obligations=_obl())
    inv = corroborate_signal(sig)
    assert inv is not None and inv.grade is Grade.INTERRUPT and inv.persistence is None


# -- ambiguous path: shapeless drift -> persistence -> caution -----------------

def _shapeless_probe() -> Probe:
    return _probe(FaultShape.VALUE_CHANGED, Comparison.PROOF_BASELINE,
                  Lens(op=LensOp.CONTENT_HASH), target="/docs/passages/pol-returns",
                  cost_class=CostClass.MODERATE)


def test_shapeless_drift_persisting_promotes_to_caution():
    base = R({"content": "original passage"})
    changed = R({"content": "silently rewritten passage"})
    sig = Signal(probe=_shapeless_probe(), baseline=base,
                 observations=[changed, changed], obligations=_obl())  # first + re-look
    inv = corroborate_signal(sig)
    assert inv is not None
    assert inv.grade is Grade.CAUTION and inv.persistence is PersistenceDecision.PROMOTE
    assert inv.target == "/docs/passages/pol-returns"


def test_shapeless_one_shot_wobble_stays_telemetry():
    base = R({"content": "original passage"})
    changed = R({"content": "transient blip"})
    sig = Signal(probe=_shapeless_probe(), baseline=base,
                 observations=[changed, base], obligations=_obl())  # healed by re-look
    assert corroborate_signal(sig) is None


def test_shapeless_single_observation_no_relook_stays_telemetry():
    """No confirming re-look yet — never promoted blind (backstopped by the
    cadence pre-completion sweep, next session)."""
    base = R({"content": "original passage"})
    changed = R({"content": "silently rewritten passage"})
    sig = Signal(probe=_shapeless_probe(), baseline=base,
                 observations=[changed], obligations=_obl())
    assert corroborate_signal(sig) is None


def test_clean_surface_emits_nothing():
    base = R({"content": "original passage"})
    sig = Signal(probe=_shapeless_probe(), baseline=base,
                 observations=[base, base], obligations=_obl())
    assert corroborate_signal(sig) is None


# -- the multi-surface layer ---------------------------------------------------

def test_corroborate_emits_one_invalidation_per_routed_surface():
    base = R({"content": "x"})
    persist = Signal(probe=_shapeless_probe(), baseline=base,
                     observations=[R({"content": "y"}), R({"content": "y2"})],
                     obligations=_obl())
    status = Signal(
        probe=_probe(FaultShape.STATUS_CLASS, Comparison.HARD_INVARIANT,
                     Lens(op=LensOp.STATUS_READ), target="/auth/validate",
                     evidence_class=EvidenceClass.STATUS_CODED),
        observations=[R({}, status=401)], invariant=Invariant(status_in=(200,)))
    clean = Signal(probe=_shapeless_probe(), baseline=base,
                   observations=[base, base], obligations=_obl())
    out = corroborate([persist, status, clean])
    assert len(out) == 2                                   # clean emits nothing
    grades = {i.target: i.grade for i in out}
    assert grades["/docs/passages/pol-returns"] is Grade.CAUTION
    assert grades["/auth/validate"] is Grade.INTERRUPT


# -- end to end on a real seen-category world ----------------------------------

def test_end_to_end_status_fast_path_on_real_world(make_world):
    """The layer consumes real ProbeResults from a seen-category world: an
    unknown SKU returns 404 and routes as an INTERRUPT-grade fast path."""
    world = make_world(probe_channel=True, world_rev=1)
    token = get_token(world.client)
    ex = ProbeExecutor(world.client, auth_token=token)
    probe = _probe(FaultShape.STATUS_CLASS, Comparison.HARD_INVARIANT,
                   Lens(op=LensOp.STATUS_READ), target="/inventory/items/ZZZ-NOPE",
                   evidence_class=EvidenceClass.STATUS_CODED)
    obs = ex.get("/inventory/items/ZZZ-NOPE")
    assert obs.status == 404
    sig = Signal(probe=probe, observations=[obs], invariant=Invariant(status_in=(200,)))
    inv = corroborate_signal(sig)
    assert inv is not None and inv.grade is Grade.INTERRUPT


def test_end_to_end_healthy_real_surface_emits_nothing(make_world):
    world = make_world(probe_channel=True, world_rev=1)
    token = get_token(world.client)
    ex = ProbeExecutor(world.client, auth_token=token)
    probe = _probe(FaultShape.STATUS_CLASS, Comparison.HARD_INVARIANT,
                   Lens(op=LensOp.STATUS_READ), target="/inventory/items/WID-001",
                   evidence_class=EvidenceClass.STATUS_CODED)
    obs = ex.get("/inventory/items/WID-001")
    assert obs.status == 200
    sig = Signal(probe=probe, observations=[obs, obs],  # healthy + re-look
                 invariant=Invariant(status_in=(200,)))
    assert corroborate_signal(sig) is None
