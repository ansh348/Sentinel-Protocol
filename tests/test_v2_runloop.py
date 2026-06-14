"""Deterministic acceptance for the V2 run-loop barrier helpers: §8 harvest from the
world trace, token re-use, and per-worker surfaces (the REAL path's building blocks,
exercised without a live subprocess run). The full loop is validated by the live
seen-cell dev-run (analysis/v2_runloop_smoke.py). $0 LLM, no world started.
"""
from __future__ import annotations

import json

from conductor.run_v2_loop import V2_SYSTEM, V2J_SYSTEM, V2Conductor
from sentinel_v2.probe_spec import (CadenceHint, Comparison, CostClass,
                                    EvidenceClass, FaultShape, Lens, LensOp, Probe,
                                    Provenance)

PRICING = "/pricing/quote/WID-001"


def _probe(target=PRICING, lens=None, comparison=Comparison.PROOF_BASELINE,
           shape=FaultShape.SCHEMA_SHAPE):
    lens = lens or Lens(op=LensOp.SCHEMA_FINGERPRINT)
    return Probe(method="GET", target=target, lens=lens, comparison=comparison,
                 fault_shape=shape, evidence_class=EvidenceClass.CONTENT_SHAPED,
                 cost_class=CostClass.MODERATE, cadence_hint=CadenceHint.EVENT_GATED,
                 provenance=Provenance(plan_step="s", world_fact="f", surface=target,
                                       read="r", predicate="p", recovery_hint="h"))


def _cond(tmp_path, **kw):
    return V2Conductor(task_path="tasks/a1.yaml", runs_root=str(tmp_path), **kw)


def _write_world_trace(cond, events):
    path = cond.run_dir / "trace_world.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")


def _call(counter, path, actor="w1", method="GET"):
    return {"event_type": "tool_call", "actor": actor,
            "payload": {"counter": counter, "method": method, "path": path}}


def _resp(counter, status, body):
    return {"event_type": "tool_response", "actor": "world",
            "payload": {"counter": counter, "status": status, "body": body}}


# -- the v2 system configs are NOT v1 SYSTEMS entries --------------------------

def test_v2_systems_are_local_not_in_v1_registry():
    from conductor.systems import SYSTEMS
    assert V2_SYSTEM.id == "V2" and V2J_SYSTEM.id == "V2J"
    assert "V2" not in SYSTEMS and "V2J" not in SYSTEMS
    assert V2_SYSTEM.tripwires_enabled and not V2_SYSTEM.judge_enabled


# -- token re-use from the trace (same-instance/token discipline) --------------

def test_last_observed_token_from_trace(tmp_path):
    cond = _cond(tmp_path)
    try:
        _write_world_trace(cond, [
            _call(1, "/auth/token", method="POST"),
            _resp(1, 200, {"token": "tok_abc123"}),
            _call(2, PRICING), _resp(2, 200, {"sku": "WID-001"}),
            _call(3, "/auth/token", method="POST"),
            _resp(3, 200, {"token": "tok_def456"}),   # the most recent
        ])
        assert cond._last_observed_token() == "tok_def456"
    finally:
        cond.trace.close()


def test_no_token_yet_is_none(tmp_path):
    cond = _cond(tmp_path)
    try:
        assert cond._last_observed_token() is None     # no trace yet
    finally:
        cond.trace.close()


# -- §8 harvest from the trace: clean read = baseline, 404 is not --------------

def test_harvest_captures_clean_baseline_and_skips_404(tmp_path):
    cond = _cond(tmp_path)
    cond.v2_probes = [_probe(PRICING)]
    try:
        _write_world_trace(cond, [
            _call(1, PRICING), _resp(1, 200, {"sku": "WID-001", "unit_price": 19.68}),
            _call(2, PRICING), _resp(2, 404, {"detail": "deprecated"}),   # post-injection
        ])
        cond._harvest_into_baselines()
        assert PRICING in cond.v2_baselines                  # the clean 200 read is the baseline
        assert cond.v2_baselines[PRICING].status == 200
        assert cond.v2_baselines[PRICING].body["unit_price"] == 19.68
    finally:
        cond.trace.close()


def test_harvest_skips_write_and_unwatched_surface(tmp_path):
    cond = _cond(tmp_path)
    cond.v2_probes = [_probe(PRICING)]
    try:
        _write_world_trace(cond, [
            _call(1, PRICING, method="PUT"), _resp(1, 200, {"sku": "WID-001"}),  # a write
            _call(2, "/inventory/items"), _resp(2, 200, {"items": []}),          # unwatched
        ])
        cond._harvest_into_baselines()
        assert cond.v2_baselines == {}     # neither qualifies as coverage
    finally:
        cond.trace.close()


def test_only_earliest_clean_read_is_the_baseline(tmp_path):
    cond = _cond(tmp_path)
    cond.v2_probes = [_probe(PRICING)]
    try:
        _write_world_trace(cond, [
            _call(1, PRICING), _resp(1, 200, {"sku": "WID-001", "unit_price": 19.68}),
            _call(2, PRICING), _resp(2, 200, {"sku": "WID-001", "unit_price": 25.00}),
        ])
        cond._harvest_into_baselines()
        assert cond.v2_baselines[PRICING].body["unit_price"] == 19.68   # earliest, not latest
    finally:
        cond.trace.close()


# -- per-worker surfaces ------------------------------------------------------

def test_worker_surfaces_from_trace(tmp_path):
    cond = _cond(tmp_path)
    cond.v2_probes = [_probe(PRICING), _probe("/inventory/items/WID-001")]

    class _O:
        instance_id = "w2"
        subplan_id = "s3"

    try:
        _write_world_trace(cond, [
            _call(1, PRICING, actor="w2"), _resp(1, 200, {"sku": "WID-001"}),
            _call(2, "/inventory/items/WID-001", actor="w1"), _resp(2, 200, {"sku": "x"}),
        ])
        # w2 touched only the pricing surface
        assert cond._worker_surfaces(_O()) == {PRICING}
    finally:
        cond.trace.close()
