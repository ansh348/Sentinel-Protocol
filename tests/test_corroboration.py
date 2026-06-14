"""C1 acceptance: the pure persistence decision (design v0.4 §2.2; ruling D28).
Synthetic anomaly-flag sequences only — fully deterministic, no LLM, no world.
"""
from __future__ import annotations

from sentinel_v2.corroboration import PersistenceDecision, decide_persistence

P = PersistenceDecision.PROMOTE
T = PersistenceDecision.TELEMETRY


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
