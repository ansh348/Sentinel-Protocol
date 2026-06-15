"""Acceptance for the 1b confirmatory matrix runner + 1bKG gate computation (C1/C2).

Wiring + scoring only, on SYNTHETIC data: like the escrow loader's tests, these NEVER read
the real escrow/*.json and dispatch NO cell (no LLM). They prove the glue enumerates,
labels, and stays seal-safe, and that the gates compute every component to its frozen
prereg definition and emit a verdict (PENDING where a human-audit input is owed, never
auto-passed).
"""
from __future__ import annotations

import hashlib
import json

from conductor.escrow_loader import (D23_SKIPPED_PAIRS, SealedCell,
                                     load_holdout_cells, load_matrix_cells)
from analysis import matrix_runner as MR
from analysis import matrix_gates as MG

FAKE_SEED = 91827           # distinctive: must never appear in any ledger/identity output
FAKE_N = 47
FAKE_PARAM = 73313


# -- runner: enumeration, labels, arm scope, seal-safety -----------------------

def _write(path, payload) -> str:
    raw = json.dumps(payload, indent=1, sort_keys=True).encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_fire_arms_exclude_v2j():
    assert MR.FIRE_ARMS == ("V2", "S1", "S2", "S3")
    assert "V2J" not in MR.FIRE_ARMS


def test_recovery_class_matches_3a_manifest():
    # original nine pairs — prereg_1b §3a (AUTHOR-8), verbatim
    def cell(task, inj):
        return SealedCell(kind="matrix-injected", task=task, injection=inj, slot=1,
                          category=None, _seed=FAKE_SEED, _n_inject=FAKE_N, _params={})
    assert MR.recovery_class(cell("a1", "endpoint_404")) == "RECOVERABLE"        # pair 1
    assert MR.recovery_class(cell("a1", "token_expiry")) == "RETREAT_CONDITION"  # pair 3
    assert MR.recovery_class(cell("c1", "doc_contradiction")) == "RECOVERABLE"   # pair 6
    assert MR.recovery_class(cell("d1", "endpoint_404")) == "RETREAT_CONDITION"  # pair 9
    # held-out: DV always recoverable; RB surfaced (mechanical at launch, not invented)
    assert MR.recovery_class(cell("b1", "silent_minor_bump")) == "RECOVERABLE"
    assert MR.recovery_class(cell("a1", "quota_cliff")) == "RB_MECHANICAL_AT_LAUNCH"
    # clean
    clean = SealedCell(kind="matrix-clean", task="a1", injection=None, slot=1,
                       category=None, _seed=FAKE_SEED, _n_inject=None, _params={})
    assert MR.recovery_class(clean) is None


def test_cell_identity_is_seal_safe():
    cell = SealedCell(kind="holdout", task="a1", injection="quota_cliff", slot=None,
                      category="RESOURCE_BUDGET", _seed=FAKE_SEED, _n_inject=FAKE_N,
                      _params={"q0": FAKE_PARAM})
    ident = MR.cell_identity(cell, slot_index=3)
    blob = json.dumps(ident)
    # NO drawn value (seed / n_inject / param) may appear in the public identity
    for secret in (str(FAKE_SEED), str(FAKE_N), str(FAKE_PARAM)):
        assert secret not in blob
    assert ident["slot"] == 3                      # positional index stands in (public)
    assert ident["category"] == "RESOURCE_BUDGET"
    assert ident["recovery_class"] == "RB_MECHANICAL_AT_LAUNCH"


def test_enumerate_honors_d23_skips_synthetic(tmp_path):
    # synthetic matrix fixture (9 pairs x 3 slots injected + 12 clean); load via the loader
    pairs = [("a1", "endpoint_404"), ("a1", "schema_drift"), ("a1", "token_expiry"),
             ("b1", "schema_drift"), ("b1", "gate_skip_trap"), ("c1", "doc_contradiction"),
             ("c1", "token_expiry"), ("d1", "gate_skip_trap"), ("d1", "endpoint_404")]
    injected = [{"task": t, "injection": i, "slot": s, "seed": FAKE_SEED + n, "n_inject": FAKE_N}
                for n, (t, i) in enumerate(pairs) for s in (1, 2, 3)]
    clean = [{"task": t, "slot": s, "seed": FAKE_SEED + 900 + j}
             for j, (t, s) in enumerate((t, s) for t in ("a1", "b1", "c1", "d1") for s in (1, 2, 3))]
    p = tmp_path / "m.json"
    digest = _write(p, {"injected_cells": injected, "clean_cells": clean})
    cells, skipped = load_matrix_cells(p, digest)
    assert skipped == len(D23_SKIPPED_PAIRS) * 3           # 2 retired pairs x 3 slots = 6
    inj = [c for c in cells if c.kind == "matrix-injected"]
    assert len(inj) == 27 - 6 and len([c for c in cells if c.kind == "matrix-clean"]) == 12
    # no retired pair survives
    assert not any((c.task, c.injection) in D23_SKIPPED_PAIRS for c in inj)


# -- gates: compute every component + verdict ----------------------------------

def _rec(arm, *, kind="matrix-injected", task="a1", inj="endpoint_404",
         cat="API_SURFACE", rc="RECOVERABLE", detected=True, ttd=5, fir=0.0,
         cost=0.40, success=True, fi=0, nint=0, waste=100, slot=0):
    return {"kind": kind, "task": task, "injection": inj, "category": cat,
            "slot": slot, "recovery_class": rc, "arm": arm,
            "result": {"arm_id": arm, "detected": detected, "n_interrupts": nint,
                       "total_cost_usd": cost, "ttd_tool_calls": ttd,
                       "false_interrupts": fi, "fir": fir, "replans": 0,
                       "success": success, "grades": [], "source": "x",
                       "wasted": {"tool_calls": 0, "tokens": waste, "usd": 0.0}}}


def _ledger(tmp_path, rows):
    p = tmp_path / "results.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return p


def test_wilson_lower_known_values():
    assert abs(MG.wilson_lower(1, 1) - 0.2065) < 1e-3      # 1/1 at 95%
    assert abs(MG.wilson_lower(10, 10) - 0.7225) < 1e-2
    assert MG.wilson_lower(0, 0) is None


def test_recovery_quality_classification():
    rec = MG._recovery_quality(_rec("V2", rc="RECOVERABLE", detected=True, success=True))
    abrt = MG._recovery_quality(_rec("V2", rc="RETREAT_CONDITION", detected=True, success=False))
    only = MG._recovery_quality(_rec("V2", rc="RECOVERABLE", detected=True, success=False))
    miss = MG._recovery_quality(_rec("V2", detected=False))
    assert rec == "detect_and_recover"
    assert abrt == "detect_and_justified_abort"
    assert only == "detect_only"
    assert miss is None


def test_gates_compute_and_emit_verdict(tmp_path):
    rows = []
    for arm, det, ttd, cost, waste in [("V2", True, 5, 0.40, 100), ("S1", False, None, 0.32, 300),
                                       ("S2", True, 9, 0.35, 250), ("S3", True, 11, 0.50, 260)]:
        rows.append(_rec(arm, detected=det, ttd=ttd, cost=cost, waste=waste, nint=1 if det else 0))
        rows.append(_rec(arm, kind="matrix-clean", inj=None, cat=None, rc=None,
                         detected=False, ttd=None, fir=None, cost=cost * 0.9, nint=0))
    rep = MG.compute_gates(_ledger(tmp_path, rows))
    assert [g["gate"] for g in rep["gates"]] == ["1bKG1", "1bKG2", "1bKG3", "1bKG4"]
    assert all(g["status"] in ("PASS", "FAIL", "PENDING") for g in rep["gates"])
    assert rep["verdict"] in ("PASS", "FAIL", "PENDING (human-audit / precondition inputs owed)")
    # 1bKG3 overhead computes: (0.40-0.32)/0.32 = 0.25 -> FAIL
    assert abs(rep["gates"][2]["overhead_fraction"] - 0.25) < 1e-9
    assert rep["gates"][2]["status"] == "FAIL"
    # 1bKG4: ttd 11/5 = 2.2x (>=2) and waste 100/260 <=1 -> PASS
    assert rep["gates"][3]["ttd_ratio"] == 2.2 and rep["gates"][3]["status"] == "PASS"


def test_probe_validity_pending_without_audit_then_consumes_verdicts(tmp_path):
    rows = [_rec("V2", nint=5, detected=True)]
    g = MG.gate_1bKG1(MG.load_ledger(_ledger(tmp_path, rows)), audit={})
    assert g["probe_validity"]["status"] == "PENDING_AUTHOR_AUDIT"
    sample = g["probe_validity"]["sample"]
    assert g["probe_validity"]["n_sample"] == 1            # ceil(0.20 * 5)
    # supply ALL-PASS verdicts -> the HARD gate computes PASS (deterministic seed 1102)
    verdicts = {f"{k}#{j}": True for (k, j) in sample}
    g2 = MG.gate_1bKG1(MG.load_ledger(_ledger(tmp_path, rows)),
                       audit={"probe_validity_verdicts": verdicts})
    assert g2["probe_validity"]["status"] == "PASS"
    # one failing verdict -> class-exclusion FAIL
    bad = dict(verdicts); bad[list(bad)[0]] = False
    g3 = MG.gate_1bKG1(MG.load_ledger(_ledger(tmp_path, rows)),
                       audit={"probe_validity_verdicts": bad})
    assert g3["probe_validity"]["status"] == "FAIL_EXCLUDE_CLASS"


def test_probe_audit_sample_is_deterministic(tmp_path):
    rows = [_rec("V2", nint=10, detected=True)]
    a = MG.gate_1bKG1(MG.load_ledger(_ledger(tmp_path, rows)), audit={})["probe_validity"]["sample"]
    b = MG.gate_1bKG1(MG.load_ledger(_ledger(tmp_path, rows)), audit={})["probe_validity"]["sample"]
    assert a == b and len(a) == 2                          # ceil(0.20 * 10), seed 1102 fixed


# -- P2/P3: pinned pre-detection + trace-computed replay / cap-grind ------------

def test_pre_detection_pinned_not_pending(tmp_path):
    # P2: pre-detection is a PINNED definition (per-cell false_interrupts, conservative
    # upper bound), never PENDING. Low -> PASS; high -> FAIL.
    lo = MG.gate_1bKG2(MG.load_ledger(_ledger(tmp_path, [_rec("V2", fi=1)])), audit={})
    hi = MG.gate_1bKG2(MG.load_ledger(_ledger(tmp_path, [_rec("V2", fi=5)])), audit={})
    assert lo["pre_detection"]["status"] == "PASS"
    assert hi["pre_detection"]["status"] == "FAIL"
    assert "false_interrupts" in lo["pre_detection"]["definition"]


def _synth_run(dirp, *, system, injected, reason):
    dirp.mkdir(parents=True, exist_ok=True)
    ev = [{"event_type": "run_start", "actor": "conductor", "payload": {"system": system}}]
    if injected:
        ev.append({"event_type": "injection_fired", "actor": "world", "payload": {"counter": 6}})
    ev.append({"event_type": "run_end", "actor": "conductor", "payload": {"reason": reason}})
    (dirp / "trace.jsonl").write_text("\n".join(json.dumps(e) for e in ev), encoding="utf-8")


def test_clean_cap_grinds_counts_escalation_loop(tmp_path):
    # #4 wired from traces: a clean V2 run that hit the escalation cap counts; a healthy
    # clean run does not; an injected run is skipped (not a clean cell).
    _synth_run(tmp_path / "a1-V2-clean-s1", system="V2", injected=False, reason="escalation_loop")
    _synth_run(tmp_path / "a1-V2-clean-s2", system="V2", injected=False, reason="aggregated")
    _synth_run(tmp_path / "a1-V2-endpoint_404-s1", system="V2", injected=True, reason="escalation_loop")
    g = MG.clean_cap_grinds(tmp_path)
    assert g["count"] == 1 and g["n_clean_runs_scanned"] == 2
    assert "MAX_ESCALATIONS" in g["cite"]


def test_replay_run_dir_none_without_world_trace(tmp_path):
    d = tmp_path / "r"; d.mkdir()
    (d / "trace.jsonl").write_text("", encoding="utf-8")
    assert MG.replay_run_dir(d) is None                    # no replayable world trace


def test_compute_gates_accepts_runs_root_and_survives_empty(tmp_path):
    rows = [_rec("V2", detected=True), _rec("V2", kind="matrix-clean", inj=None,
                                            cat=None, rc=None, detected=False, ttd=None)]
    rep = MG.compute_gates(_ledger(tmp_path, rows), runs_root=str(tmp_path / "no_runs"))
    assert rep["verdict"] in ("PASS", "FAIL", "PENDING (human-audit / precondition inputs owed)")
