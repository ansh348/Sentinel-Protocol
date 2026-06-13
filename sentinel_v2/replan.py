"""Replan behavior (B6; probe_compiler_design_v0.4.md §6, author ruling D2).

Ruling D2 replaces v0.3's flush-and-recompile with KEEP-NOT-FLUSH:
  1. KEEP the prior probe inventory (no flush; no probe-to-context re-mapping loss).
  2. RECOMPILE-ADD probes for the revised plan.
  3. PRUNE only probes the N2 pattern-liveness sweep proves DEAD against the
     revised rev (reusing sentinel_v2.pattern_liveness / the D5 classifier).
  4. Run the §6 coverage/liveness check: every assumption still live for
     in-flight or downstream work must have a covering probe — a live assumption
     left UNCOVERED is flagged loudly (the v1 death-specimen detector).
  5. Every post-replan fire is instrumented (instrument_fire) so a kept-but-now-
     irrelevant probe firing is observable, not silent.

Named residual (§8): the IN-FLIGHT-DROPPED probe — a probe whose assumption the
revised plan drops while work is still in flight — is kept (still watching) and
LOGGED (in_flight_dropped), observable, not architected away this phase.

Pure and deterministic; no runtime-execution-state architecture change this phase.
The N2 sweep is reused unchanged; §4 GATE_SHADOW probes are exempt from the path
sweep (their liveness was established by the §4 non-perturbation trapdoor, not the
path space). Rule Zero: nothing here names a holdout category.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sentinel_v2.pattern_liveness import path_samples_for_rev
from sentinel_v2.probe_spec import LensOp, Probe
from world.server import classify_url_pattern


def _is_dead(probe: Probe, world_rev: int) -> bool:
    """N2 dead-pattern test for a probe's target. §4 gate-shadow probes are
    exempt — their liveness is governed by the §4 trapdoor, and their shadow
    paths deliberately live outside the probe_channel-off path samples."""
    if probe.lens.op is LensOp.GATE_SHADOW:
        return False
    samples = path_samples_for_rev(world_rev)
    return classify_url_pattern(probe.target, samples) is None


@dataclass
class ReplanReport:
    epoch: int
    kept: list                  # prior assumption_ids retained after the replan
    added: list                 # newly recompiled assumption_ids added
    pruned_dead: list           # probes pruned because their target is N2-dead
    uncovered: list             # LIVE assumptions with no covering probe (death-specimen)
    in_flight_dropped: list     # dropped-but-in-flight assumptions (named residual)
    inventory: dict             # assumption_id -> Probe, the resulting inventory
    live: set = field(default_factory=set)

    @property
    def death_specimen_detected(self) -> bool:
        return bool(self.uncovered)


def replan(prior_inventory: dict, *, live_assumptions, recompiled: dict,
           in_flight=frozenset(), world_rev: int = 1, epoch: int = 1) -> ReplanReport:
    """Apply ruling D2 to the probe inventory and return the audit report."""
    live = set(live_assumptions)
    in_flight = set(in_flight)

    # 1. KEEP prior (no flush)  +  2. RECOMPILE-ADD
    inventory = dict(prior_inventory)
    added = []
    for aid, probe in recompiled.items():
        if aid not in prior_inventory:
            added.append(aid)
        inventory[aid] = probe  # a recompiled probe refreshes its slot

    # 3. PRUNE-DEAD (N2): ONLY probes whose target is dead under the revised rev
    pruned_dead = [aid for aid, p in list(inventory.items())
                   if _is_dead(p, world_rev)]
    for aid in pruned_dead:
        del inventory[aid]

    # 4. COVERAGE / LIVENESS CHECK: every live assumption must be covered, else
    #    it is flagged loudly (the death-specimen detector)
    uncovered = sorted(aid for aid in live if aid not in inventory)

    # 5. IN-FLIGHT-DROPPED residual: dropped from the revised plan (not live) but
    #    still has in-flight work and a kept probe — logged, observable
    in_flight_dropped = sorted(aid for aid in in_flight
                               if aid not in live and aid in inventory)

    kept = sorted(aid for aid in prior_inventory if aid in inventory)
    return ReplanReport(epoch=epoch, kept=kept, added=sorted(added),
                        pruned_dead=sorted(pruned_dead), uncovered=uncovered,
                        in_flight_dropped=in_flight_dropped, inventory=inventory,
                        live=live)


def instrument_fire(report: ReplanReport, assumption_id: str) -> dict:
    """Instrument a post-replan probe fire (D2). Surfaces whether the firing
    probe was kept across the replan while its assumption is no longer live
    (kept-but-irrelevant) or is an in-flight-dropped residual — observable, never
    silent."""
    in_inventory = assumption_id in report.inventory
    is_live = assumption_id in report.live
    return {
        "assumption_id": assumption_id,
        "epoch": report.epoch,
        "post_replan": True,
        "in_inventory": in_inventory,
        "live": is_live,
        "kept_but_irrelevant": in_inventory and not is_live,
        "in_flight_dropped": assumption_id in report.in_flight_dropped,
    }
