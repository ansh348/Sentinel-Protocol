"""Arm registration acceptance: the five matrix arms register, resolve, dispatch,
and collect a well-formed result (decision_memo_phase1.md §2,§4; prereg_1b P3).
Deterministic: baselines over BANKED SEEN traces; the v2 detection seam against a
real seen-category world. No held-out cell, no matrix run, $0 LLM.
"""
from __future__ import annotations

import os

import pytest

from conftest import get_token
from sentinel_v2 import arms, flags
from sentinel_v2.arms import (ArmResult, collect_arm_result, resolve_arm,
                              run_v2_detection, v2_result)
from sentinel_v2.probe_spec import (CadenceHint, Comparison, CostClass,
                                    EvidenceClass, FaultShape, Lens, LensOp, Probe,
                                    Provenance)
from sentinel_v2.probes import ProbeExecutor

RUNS = "runs"


def _status_probe(target):
    return Probe(method="GET", target=target, lens=Lens(op=LensOp.STATUS_READ),
                 comparison=Comparison.HARD_INVARIANT, fault_shape=FaultShape.STATUS_CLASS,
                 evidence_class=EvidenceClass.STATUS_CODED, cost_class=CostClass.LIGHT,
                 cadence_hint=CadenceHint.EVENT_GATED,
                 provenance=Provenance(plan_step="s", world_fact="f", surface=target,
                                       read="r", predicate="p", recovery_hint="h"))


# -- the registry: five arms, roles, reporting flags ---------------------------

def test_five_arms_registered_with_roles():
    assert set(arms.ARMS) == {"V2", "V2J", "S1", "S2", "S3"}
    assert arms.PRIMARY_ARM == "V2" and arms.ARMS["V2"].role == "primary"
    assert arms.ARMS["V2J"].role == "exploratory" and arms.ARMS["V2J"].judge is True
    assert arms.EXPLORATORY_ARMS == ("V2J",)
    assert all(arms.ARMS[b].kind == "baseline" for b in ("S1", "S2", "S3"))


def test_s2_carries_the_honesty_clause_and_s3_the_heartbeat():
    assert arms.ARMS["S2"].honesty_clause is True       # mandatory head-to-head
    assert arms.ARMS["S3"].heartbeat is True            # cost-matched periodic revalidation
    assert arms.ARMS["S1"].honesty_clause is False


def test_v2_is_primary_not_exploratory():
    assert arms.PRIMARY_ARM not in arms.EXPLORATORY_ARMS


def test_resolve_flag_gating(monkeypatch):
    monkeypatch.delenv(flags.ENV_VAR, raising=False)
    with pytest.raises(RuntimeError, match="flagged off"):
        resolve_arm("V2")
    assert resolve_arm("S1").id == "S1"                 # baselines resolve flag-off
    monkeypatch.setenv(flags.ENV_VAR, "1")
    assert resolve_arm("V2").is_v2 and resolve_arm("V2J").is_v2
    with pytest.raises(KeyError):
        resolve_arm("nope")


# -- baseline result collection over BANKED SEEN traces ($0) -------------------

def _have(run_dir):
    return os.path.isdir(os.path.join(RUNS, run_dir))


def test_collect_baseline_result_on_a_banked_clean_seen_cell():
    if not _have("a1-S1-clean-s1"):
        pytest.skip("banked seen baseline run not present")
    res = collect_arm_result(os.path.join(RUNS, "a1-S1-clean-s1"), "S1")
    assert isinstance(res, ArmResult) and res.well_formed()
    assert res.detected is False and res.source == "conductor"
    assert res.total_cost_usd > 0


def test_collect_baseline_result_on_a_banked_injected_seen_cell():
    if not _have("a1-S2-endpoint_404-s1"):
        pytest.skip("banked seen injected baseline run not present")
    res = collect_arm_result(os.path.join(RUNS, "a1-S2-endpoint_404-s1"), "S2")
    assert res.well_formed() and res.detected is True
    assert res.ttd_tool_calls is not None and res.n_interrupts >= 1
    assert res.fir is not None                          # the S2 honesty-clause metric


# -- the v2 detection seam against a real seen-category world ($0 LLM) ----------

def test_v2_detection_fires_on_a_real_anomaly(make_world):
    world = make_world(probe_channel=True, world_rev=1)
    token = get_token(world.client)
    # a 404 surface (unknown SKU) is a status anomaly -> the status fast path interrupts
    det = run_v2_detection([_status_probe("/inventory/items/ZZZ-NOPE")], world.client,
                           auth_token=token)
    assert det["detected"] is True and det["n_interrupts"] == 1
    assert det["grades"] == ["interrupt"]
    res = v2_result("V2", det, total_cost_usd=0.0)
    assert res.well_formed() and res.source == "v2_detection"


def test_v2_detection_quiet_on_a_healthy_surface(make_world):
    world = make_world(probe_channel=True, world_rev=1)
    token = get_token(world.client)
    det = run_v2_detection([_status_probe("/inventory/items/WID-001")], world.client,
                           auth_token=token)
    assert det["detected"] is False and det["n_interrupts"] == 0


def test_v2j_judge_seam_is_pass_through_exploratory(make_world):
    world = make_world(probe_channel=True, world_rev=1)
    token = get_token(world.client)
    # V2J routes through the exploratory judge seam; here it does not filter
    det = run_v2_detection([_status_probe("/inventory/items/ZZZ-NOPE")], world.client,
                           auth_token=token, judge=True)
    assert det["detected"] is True
    res = v2_result("V2J", det)
    assert res.arm_id == "V2J"
