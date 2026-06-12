"""N2 acceptance: the compile-time pattern-liveness sweep (D24, #7-class fix).

Reproduces the a1+token_expiry defect class (host-qualified patterns are dead
under the D5 dialect), proves the sweep rejects whole sets loudly with every
dead pattern listed, verifies rev-aware D13 samples (rev 1 byte-identical;
rev >= 2 extends mechanically), and replays the banked-corpus dead-pattern
sweep: all 84 armed-dead patterns from archaeology_v2 must be caught.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sentinel.dsl import Tripwire, TripwireSet
from sentinel_v2.pattern_liveness import (DeadPatternError, assert_patterns_live,
                                          liveness_report, path_samples_for_rev)
from world.server import get_path_samples

REPO_ROOT = Path(__file__).resolve().parent.parent
BANKED_SWEEP = REPO_ROOT / "runs" / "archaeology_v2" / "raw_replay.json"


def _tw(tw_id: str, pattern: str) -> Tripwire:
    return Tripwire(
        id=tw_id, severity="WARNING", scope="global",
        assumption="endpoint stays available for the duration of the run",
        assumption_id="a1", category_weights={"API_SURFACE": 1.0},
        signal={"type": "http_response", "url_pattern": pattern,
                "status_in": [401, 403, 404]},
        action={"on_trigger": "ESCALATE_TO_SENTINEL",
                "hint": "re-check the service surface"},
        evidence_fields=["status"],
    )


# -- the defect class (archaeology_v2 §A.1: host-qualified -> D5-dead) --------

def test_host_qualified_pattern_is_dead():
    report = liveness_report([("tw_token_rejected_downstream",
                               "localhost:8400/inventory/items")])
    assert report[0]["mode"] == "dead"


def test_live_glob_and_regex_patterns_pass():
    report = liveness_report([("tw_glob", "/inventory/items"),
                              ("tw_glob_star", "/pricing/quote/*"),
                              ("tw_regex", r".*/pricing/quote/[^/]+$")])
    assert [r["mode"] for r in report] == ["glob", "glob", "regex"]


def test_sweep_rejects_set_listing_every_dead_pattern():
    ts = TripwireSet(plan_id="p1", tripwires=[
        _tw("tw_live", "/inventory/items"),
        _tw("tw_dead_host", "localhost:8400/inventory/items"),
        _tw("tw_dead_typo", "/inventroy/items"),
    ])
    with pytest.raises(DeadPatternError) as err:
        assert_patterns_live(ts, world_rev=1)
    msg = str(err.value)
    assert "tw_dead_host" in msg and "tw_dead_typo" in msg
    assert "tw_live" not in msg.split("must not arm")[1]
    assert len(err.value.dead) == 2


def test_sweep_passes_clean_set_and_returns_report():
    ts = TripwireSet(plan_id="p1", tripwires=[
        _tw("tw_a", "/pricing/quote/*"),
        _tw("tw_b", "/auth/token"),
    ])
    report = assert_patterns_live(ts, world_rev=1)
    assert {r["mode"] for r in report} <= {"glob", "regex"}


# -- rev-aware D13 samples (D24) ----------------------------------------------

def test_rev1_samples_byte_identical_to_phase1():
    assert path_samples_for_rev(1) == get_path_samples()


def test_rev_aware_samples_extend_at_rev2_plus():
    rev1 = set(path_samples_for_rev(1))
    rev4 = set(path_samples_for_rev(4))
    assert rev1 <= rev4
    # the exact #7 wound the build requirement names: a tripwire targeting
    # /manifest must not be classified dead on a rev >= 2 world
    assert "/manifest" not in rev1
    assert "/manifest" in rev4
    # rev >= 2 fixture-repo expansion reaches the samples mechanically
    assert "/repo/files/src/tax.py" not in rev1
    assert "/repo/files/src/tax.py" in rev4


def test_manifest_pattern_dead_at_rev1_live_at_rev4():
    report1 = liveness_report([("tw_m", "/manifest")], world_rev=1)
    report4 = liveness_report([("tw_m", "/manifest")], world_rev=4)
    assert report1[0]["mode"] == "dead"
    assert report4[0]["mode"] == "glob"


# -- banked-corpus regression (replay-based, $0) ------------------------------

@pytest.mark.skipif(not BANKED_SWEEP.exists(),
                    reason="banked corpus (runs/) is local-only")
def test_banked_corpus_all_84_dead_patterns_caught():
    sweep = json.loads(BANKED_SWEEP.read_text(encoding="utf-8"))["dead_pattern_sweep"]
    assert len(sweep) == 84
    assert sum(1 for row in sweep if row["host_qualified"]) == 61
    assert sum(1 for row in sweep if row["covers_injection_on_paper"]) == 19
    # archaeology_v2 §A.3: "across 8 cells" counts the cells whose dead
    # patterns COVER their own injection on paper
    assert len({row["cell"] for row in sweep
                if row["covers_injection_on_paper"]}) == 8

    report = liveness_report([(row["tripwire"], row["pattern"])
                              for row in sweep], world_rev=1)
    modes = {r["mode"] for r in report}
    assert modes == {"dead"}, (
        f"sweep must classify every banked armed-dead pattern dead; got {modes}")
