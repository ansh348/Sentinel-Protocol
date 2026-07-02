"""V2nc ablation: the deterministic selector + the SAME compile_pipeline arm one
per-surface VALUE baseline-diff probe on every plan-touched /regions surface, no LLM
($0). Mirrors the V2 value-lens, by enumeration instead of compile. Deterministic; no
world-rev held-out cell, no model call.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from sentinel_v2.compile_probes import compile_pipeline
from sentinel_v2.deterministic_select import (VALUE_FIELD,
                                              region_evidence_surfaces,
                                              select_region_value_assumptions)
from sentinel_v2.probe_spec import Comparison, FaultShape, LensOp

ROOT = Path(__file__).resolve().parent.parent
TASK = yaml.safe_load((ROOT / "tasks" / "benchmark_1c.yaml").read_text(encoding="utf-8"))


def _is_value_bdiff(p):
    return (p.fault_shape == FaultShape.VALUE_CHANGED
            and p.lens.op == LensOp.FIELD_READ
            and p.comparison == Comparison.PROOF_BASELINE)


def test_selector_enumerates_n_value_assumptions():
    for n in (8, 16, 32):
        soft = select_region_value_assumptions(dict(TASK, n_regions=n))
        assert len(soft.assumptions) == n
        # every assumption is a VALUE assumption (pointer set) on the demand field
        assert all(a.pointer == VALUE_FIELD for a in soft.assumptions)
        assert all(a.recovery_hint for a in soft.assumptions)   # survives the provenance gate
        assert region_evidence_surfaces(n)[2] == "/regions/R-0003/evidence"


def test_pipeline_arms_value_probe_on_every_region_surface():
    for n in (8, 16):
        soft = select_region_value_assumptions(dict(TASK, n_regions=n))
        cr = compile_pipeline(soft, world_rev=4, n_regions=n, world=None,
                              auth_token=None, planned_write_set=set())
        value = sorted({p.target for p in cr.probes if _is_value_bdiff(p)})
        assert len(value) == n, f"N={n}: expected {n} value probes, got {len(value)}"
        # all N region surfaces present, none uncovered
        assert set(value) == set(region_evidence_surfaces(n))
        assert not [u for u in (cr.uncovered or []) if "regions" in str(u).lower()]


def test_selection_is_injection_blind_arms_all_shards():
    # the selector never reads which shard is mutated; it arms ALL n, so whichever
    # shard the injection picks is covered by construction.
    n = 8
    soft = select_region_value_assumptions(dict(TASK, n_regions=n))
    surfaces = {a.surface for a in soft.assumptions}
    assert surfaces == set(region_evidence_surfaces(n))
