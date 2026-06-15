"""Phase 1b CONFIRMATORY GATE COMPUTATION — 1bKG1..1bKG4 (C2).

A POST-MATRIX scoring step over the seal-safe ledger that analysis/matrix_runner.py
produces. It is built BEFORE the run so it cannot be tuned to a result; it computes the
mechanical parts of each gate and SURFACES (never invents) every component the
pre-registration defines as a human-audit step or leaves to fire-time.

Every threshold/definition is transcribed from the FROZEN pre-registration, cited inline:
  decision_memo_phase1.md §4 (ratified gate values, e808862);
  prereg_1b.md §2 (verbatim transcription) + §3a (AUTHOR-8 recovery manifest)
    + AUTHOR-1(a) category universe + AUTHOR-9 (Wilson 95%) + AUTHOR-12 (probe-audit
    seed 1102, author auditor);
  prereg.md 6.1/6.2 (inherited operational definitions: overhead, TTD, wasted-work, FIR).

HUMAN-AUDIT / PRECONDITION inputs (passed in `audit`, never fabricated): the
instrumentation-integrity replay result (Standing), the probe-validity audit verdicts
(AUTHOR-12), the TTD-attribution manual confirmation (prereg.md 6.1), and any
escalation-cap-grind signal not present in the ledger. A gate whose required human input
is absent is reported PENDING — NOT auto-PASS and NOT auto-FAIL.

NOTHING here reads a held-out value: the ledger is seal-safe (public identity + outcome
metrics), and counting held-out cells in the recall denominator is the only held-out
touch (Rule Zero).
"""
from __future__ import annotations

import json
import math
import random
import statistics
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Original FIVE categories for the categorical clause (AUTHOR-1 ruled option (a):
# the clause ranges over the original five; held-out sit in the OVERALL recall
# denominator only, reported descriptively). prereg_1b.md §2 / §4.
ORIGINAL_CATEGORIES = ("API_SURFACE", "SCHEMA_DRIFT", "PERMISSION_AUTH",
                       "TOOL_CONTRACT", "RETRIEVAL_INTEGRITY")
HELDOUT_CATEGORIES = ("RESOURCE_BUDGET", "DEPENDENCY_VERSION")

WILSON_Z_95 = 1.959963984540054   # AUTHOR-9 ruled 95% (two-sided convention)
PROBE_AUDIT_SEED = 1102           # AUTHOR-12 ruled sampling seed
PROBE_AUDIT_FRACTION = 0.20       # 1bKG1 hard gate: "a seeded 20% audit"

PRIMARY_ARM = "V2"                # two-tier v2 is the designated primary (decision_memo §2 P3)
BATCH_ARM = "S1"                  # overhead denominator (prereg.md 6.1)
HEARTBEAT_ARM = "S3"             # 1bKG4 comparison (cost-matched heartbeat)


# -- helpers -------------------------------------------------------------------

def load_ledger(ledger_path) -> list[dict]:
    rows = []
    for line in Path(ledger_path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _by_arm(rows, arm): return [r for r in rows if r["arm"] == arm]
def _injected(rows): return [r for r in rows if r["injection"] is not None]
def _clean(rows): return [r for r in rows if r["injection"] is None]
def _median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _p95(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    # nearest-rank P95 (deterministic; no interpolation tie-break needed)
    return xs[min(len(xs) - 1, math.ceil(0.95 * len(xs)) - 1)]


def wilson_lower(k: int, n: int, z: float = WILSON_Z_95) -> Optional[float]:
    """Wilson score-interval LOWER bound at confidence z (AUTHOR-9: 95%)."""
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return center - half


# -- 1bKG1 detection -----------------------------------------------------------

def _recovery_quality(row) -> Optional[str]:
    """Classify one DETECTED injected cell's recovery (1bKG1 recovery-quality, §3a):
    RECOVERABLE + checker-success -> detect_and_recover; RETREAT_CONDITION detected ->
    detect_and_justified_abort (the §3a manifest pre-authorizes the retreat there);
    RECOVERABLE detected but not success -> detect_only (an unjustified abort on a
    recoverable cell never counts toward any gate, prereg_1b §2 / memo §3). Returns None
    for a non-detection."""
    res = row["result"]
    if not res["detected"]:
        return None
    rc = row.get("recovery_class")
    if rc == "RETREAT_CONDITION":
        return "detect_and_justified_abort"
    if rc == "RECOVERABLE":
        return "detect_and_recover" if res.get("success") else "detect_only"
    # RB_MECHANICAL_AT_LAUNCH / unknown — surfaced, not classified here
    return "unclassified_rb_mechanical"


def gate_1bKG1(rows, audit: dict) -> dict:
    """1bKG1 (detection). prereg_1b.md §2 + §3a + AUTHOR-1(a)/8/9/12; decision_memo §4."""
    v2 = _by_arm(rows, PRIMARY_ARM)
    inj = _injected(v2)
    cite = "prereg_1b.md §2 (1bKG1); decision_memo_phase1.md §4"

    # (a) overall strict recall on RECOVERABLE-CLASS cells (overall gate + kill floor only,
    #     §3a). Denominator = recoverable-class injected cells; held-out DV counted inside.
    recov = [r for r in inj if r.get("recovery_class") == "RECOVERABLE"]
    rb_mech = [r for r in inj if r.get("recovery_class") == "RB_MECHANICAL_AT_LAUNCH"]
    k = sum(1 for r in recov if r["result"]["detected"])
    n = len(recov)
    recall = (k / n) if n else None
    overall = {"k": k, "n": n, "recall": recall,
               "pass_60": (recall is not None and recall >= 0.60),
               "kill_floor_breach_lt40": (recall is not None and recall < 0.40),
               "cite": cite + " (recall ≥60% recoverable-class; kill floor <40%; §3a)"}

    # (b) categorical clause: per-category strict DETECTION over ALL injected cells of the
    #     ORIGINAL five categories (AUTHOR-1(a)), Wilson 95% LB, n<3 descriptive only.
    per_cat = {}
    for cat in ORIGINAL_CATEGORIES:
        cells = [r for r in inj if r.get("category") == cat]
        kk = sum(1 for r in cells if r["result"]["detected"])
        nn = len(cells)
        per_cat[cat] = {"k": kk, "n": nn,
                        "recall": (kk / nn) if nn else None,
                        "wilson95_lower": wilson_lower(kk, nn),
                        "descriptive_only_n_lt3": nn < 3,
                        "meets_50": (nn >= 3 and kk / nn >= 0.50)}
    gating_cats = [c for c, d in per_cat.items() if not d["descriptive_only_n_lt3"]]
    n_meet = sum(1 for c in gating_cats if per_cat[c]["meets_50"])
    categorical = {"per_category": per_cat,
                   "n_categories_meeting_50": n_meet,
                   "n_gating_categories": len(gating_cats),
                   "pass_4_of_5": n_meet >= min(4, len(gating_cats)),
                   "cite": "prereg_1b.md §2 + §4 AUTHOR-1(a) + AUTHOR-9 (Wilson 95%)"}

    # (c) probe-validity HARD gate (AUTHOR-12): deterministic 20% sample (seed 1102) of
    #     v2 probe-generated interrupts; the AUTHOR audits each (targeted/fresh/
    #     non-perturbing/independent); 100% must pass else that interrupt class is excluded
    #     from recall BEFORE the gate computes. The SAMPLE is computed here; the VERDICTS
    #     are a human input — PENDING if absent (never auto-passed).
    population = []
    for r in v2:
        for j in range(int(r["result"].get("n_interrupts") or 0)):
            population.append((f"{r['kind']}|{r['task']}|{r['injection'] or 'clean'}"
                               f"|slot{r['slot']}|{r['arm']}", j))
    n_sample = math.ceil(PROBE_AUDIT_FRACTION * len(population)) if population else 0
    rng = random.Random(PROBE_AUDIT_SEED)
    sample = sorted(rng.sample(population, n_sample)) if n_sample else []
    verdicts = (audit or {}).get("probe_validity_verdicts")  # {sample_key: bool} or None
    if not population:
        probe_validity = {"status": "PASS", "n_population": 0, "n_sample": 0,
                          "note": "no probe-generated interrupts to audit",
                          "cite": "prereg_1b.md §2 + §4 AUTHOR-12 (seed 1102)"}
    elif verdicts is None:
        probe_validity = {"status": "PENDING_AUTHOR_AUDIT", "n_population": len(population),
                          "n_sample": n_sample, "sample": sample,
                          "note": "AUTHOR-12: author audits each sampled interrupt "
                                  "(targeted/fresh/non-perturbing/independent); supply "
                                  "verdicts to compute this HARD gate",
                          "cite": "prereg_1b.md §2 + §4 AUTHOR-12 (seed 1102)"}
    else:
        all_pass = all(bool(verdicts.get(f"{key}#{j}", verdicts.get(str((key, j)), False)))
                       for (key, j) in sample)
        probe_validity = {"status": "PASS" if all_pass else "FAIL_EXCLUDE_CLASS",
                          "n_population": len(population), "n_sample": n_sample,
                          "all_pass": all_pass,
                          "cite": "prereg_1b.md §2 + §4 AUTHOR-12 (seed 1102)"}

    # (d) recovery quality: >=50% of strict detections are detect-and-recover or
    #     detect-and-justified-abort. prereg_1b.md §2 (1bKG1) + §3a.
    detected_inj = [r for r in inj if r["result"]["detected"]]
    buckets = {"detect_only": 0, "detect_and_recover": 0,
               "detect_and_justified_abort": 0, "unclassified_rb_mechanical": 0}
    for r in detected_inj:
        q = _recovery_quality(r)
        if q:
            buckets[q] += 1
    passing = buckets["detect_and_recover"] + buckets["detect_and_justified_abort"]
    nd = len(detected_inj)
    recovery_quality = {"buckets": buckets, "n_detections": nd,
                        "passing_fraction": (passing / nd) if nd else None,
                        "meets_50": (nd > 0 and passing / nd >= 0.50),
                        "rb_mechanical_unclassified": buckets["unclassified_rb_mechanical"],
                        "cite": "prereg_1b.md §2 (1bKG1) + §3a"}

    # (e) instrumentation-integrity replay (Standing precondition, 100% injected, BEFORE
    #     gates). Human/separate step — PENDING if not supplied.
    replay = (audit or {}).get("instrumentation_replay_passed")
    precondition = {"status": ("PASS" if replay is True else
                               "FAIL" if replay is False else "PENDING_REPLAY"),
                    "cite": "prereg_1b.md §2 Standing + §4 line 451 (Task-A replay, 100% injected)"}

    # Held-out denominator notes (counting allowed; values unread).
    heldout = {"dv_recoverable_cells": sum(1 for r in inj
                                           if r["injection"] == "silent_minor_bump"),
               "rb_mechanical_at_launch_cells": len(rb_mech),
               "note": "DEPENDENCY_VERSION always recoverable (DV.md §3); RESOURCE_BUDGET "
                       "recoverable-class is the mechanical REPLAN-recoverable fraction at "
                       "the drawn N/Q0 (RESOURCE_BUDGET.md §3) — labeled at launch; its "
                       "expected-remaining-required closed form is NOT pinned and must be "
                       "confirmed at fire, not invented here (SURFACED)."}

    # Gate verdict: PASS requires (a)+(b) pass AND recovery-quality AND the HARD probe gate
    # PASS AND the replay precondition PASS; any human-input pending -> PENDING.
    hard_components = [overall["pass_60"], categorical["pass_4_of_5"],
                      recovery_quality["meets_50"]]
    pending = (probe_validity["status"].startswith("PENDING")
               or precondition["status"].startswith("PENDING")
               or recovery_quality["rb_mechanical_unclassified"] > 0)
    if pending:
        status = "PENDING"
    elif (all(hard_components) and probe_validity["status"] == "PASS"
          and precondition["status"] == "PASS"):
        status = "PASS"
    else:
        status = "FAIL"
    return {"gate": "1bKG1", "status": status, "overall_recall": overall,
            "categorical": categorical, "probe_validity": probe_validity,
            "recovery_quality": recovery_quality, "instrumentation_replay": precondition,
            "heldout_denominator": heldout, "cite": cite}


# -- 1bKG2 noise / self-harm ---------------------------------------------------

def gate_1bKG2(rows, audit: dict) -> dict:
    """1bKG2 absolute caps. prereg_1b.md §2 (clean median FIR=0, P95<=1, max false <=3,
    zero escalation-cap grinds; injected pre-detection FI median <=2; clean success >=60%
    AND >= S1 clean - 10)."""
    v2 = _by_arm(rows, PRIMARY_ARM)
    cl = _clean(v2)
    # clean FIR per cell: any-interrupt rate; 0/0 = 0 (prereg.md 6.1; prereg_1b §2 FIR 0/0=0)
    clean_fir = [(r["result"]["fir"] if r["result"]["fir"] is not None else 0.0) for r in cl]
    clean_false_counts = [int(r["result"].get("false_interrupts") or
                              r["result"].get("n_interrupts") or 0) for r in cl]
    median_fir = _median(clean_fir)
    p95_fir = _p95(clean_fir)
    max_false = max(clean_false_counts) if clean_false_counts else 0
    # injected pre-detection false-interrupt budget: median <= 2 before first detection
    # (prereg_1b.md §2, 1bKG2: "Pre-detection false-interrupt budget on injected cells:
    # median <= 2 before first true detection"). PINNED DEFINITION (P2): the per-cell
    # `false_interrupts` count is the pre-detection value, used as a CONSERVATIVE UPPER
    # BOUND — every cell's full false-interrupt count is >= the count that fell strictly
    # before its first detection, so passing on this bound passes on the windowed value
    # a fortiori; it can only over-count, never let a violation through. An explicit
    # tighter trace-windowed measure may override via audit['injected_pre_detection_false'].
    override = (audit or {}).get("injected_pre_detection_false")  # optional tighter list
    inj_false = (override if override is not None
                 else [int(r["result"].get("false_interrupts") or 0) for r in _injected(v2)])
    median_pre = _median(inj_false)
    pre_detection = {"status": ("PASS" if (median_pre is not None and median_pre <= 2)
                                else "FAIL" if median_pre is not None else "PENDING"),
                     "median_false_interrupts": median_pre, "cap": 2,
                     "definition": ("audited windowed value" if override is not None else
                                    "per-cell false_interrupts (conservative upper bound, P2)"),
                     "cite": "prereg_1b.md §2 (1bKG2 pre-detection median <= 2)"}
    # escalation-cap grinds on clean cells (hard, zero). Not a ledger field — surfaced.
    grinds = (audit or {}).get("clean_escalation_cap_grinds")
    grind_component = {"status": ("PASS" if grinds == 0 else "FAIL" if isinstance(grinds, int)
                                  else "PENDING_TRACE_SIGNAL"),
                       "value": grinds,
                       "note": "zero escalation-cap grinds on clean cells (hard); supply "
                               "audit['clean_escalation_cap_grinds'] from traces"}
    # clean success
    succ = [bool(r["result"].get("success")) for r in cl]
    clean_success = (sum(succ) / len(succ)) if succ else None
    s1_cl = _clean(_by_arm(rows, BATCH_ARM))
    s1_succ = [bool(r["result"].get("success")) for r in s1_cl]
    s1_clean_success = (sum(s1_succ) / len(s1_succ)) if s1_succ else None
    success_floor = None
    if clean_success is not None and s1_clean_success is not None:
        success_floor = (clean_success >= 0.60
                         and clean_success >= (s1_clean_success - 0.10))

    caps_pass = (median_fir == 0 and (p95_fir is None or p95_fir <= 1) and max_false <= 3)
    pending = (grind_component["status"].startswith("PENDING")
               or pre_detection["status"] == "PENDING" or success_floor is None)
    status = ("PENDING" if pending else
              "PASS" if (caps_pass and grind_component["status"] == "PASS"
                         and pre_detection["status"] == "PASS" and success_floor) else "FAIL")
    return {"gate": "1bKG2", "status": status,
            "clean_median_fir": median_fir, "clean_p95_fir": p95_fir,
            "clean_max_false_interrupts": max_false, "caps_pass": caps_pass,
            "escalation_cap_grinds": grind_component, "pre_detection": pre_detection,
            "clean_success": clean_success, "s1_clean_success": s1_clean_success,
            "clean_success_floor_pass": success_floor,
            "cite": "prereg_1b.md §2 (1bKG2); prereg.md 6.1 (FIR 0/0=0)"}


# -- 1bKG3 economics -----------------------------------------------------------

def gate_1bKG3(rows, audit: dict) -> dict:
    """1bKG3 clean overhead <= 12% of S1 clean cost. Overhead = treatment clean cost minus
    S1 clean cost (prereg.md 6.1 frozen def; prereg.md 6.2 '<=12% of S1 cost'); medians
    over clean cells (Phase-1 gates written on medians). Probe cost is booked in V2's total
    cost (side-channel; ~0 in the deterministic mock)."""
    v2_clean_cost = _median([r["result"]["total_cost_usd"] for r in _clean(_by_arm(rows, PRIMARY_ARM))])
    s1_clean_cost = _median([r["result"]["total_cost_usd"] for r in _clean(_by_arm(rows, BATCH_ARM))])
    overhead_fraction = None
    if v2_clean_cost is not None and s1_clean_cost not in (None, 0):
        overhead_fraction = (v2_clean_cost - s1_clean_cost) / s1_clean_cost
    status = ("PENDING" if overhead_fraction is None else
              "PASS" if overhead_fraction <= 0.12 else "FAIL")
    return {"gate": "1bKG3", "status": status,
            "v2_clean_median_cost": v2_clean_cost, "s1_clean_median_cost": s1_clean_cost,
            "overhead_fraction": overhead_fraction, "cap": 0.12,
            "cite": "prereg_1b.md §2 (1bKG3); prereg.md 6.1 overhead def + 6.2 (<=12% of S1)"}


# -- 1bKG4 vs cost-matched heartbeat -------------------------------------------

def gate_1bKG4(rows, audit: dict) -> dict:
    """1bKG4: TTD >= 2x faster than S3 AND wasted-work parity-or-better vs S3. prereg_1b.md
    §2 + §4 (parity = (v2 post-invalidation worker tokens + v2 probe overhead) <= 1.0 x S3);
    prereg.md 6.2 (TTD >=2x, median over injected pairs). Probe overhead ~0 in the mock,
    booked in waste (never a forgivable line)."""
    v2_inj = _injected(_by_arm(rows, PRIMARY_ARM))
    s3_inj = _injected(_by_arm(rows, HEARTBEAT_ARM))
    v2_ttd = _median([r["result"]["ttd_tool_calls"] for r in v2_inj
                      if r["result"]["detected"] and r["result"]["ttd_tool_calls"] is not None])
    s3_ttd = _median([r["result"]["ttd_tool_calls"] for r in s3_inj
                      if r["result"]["detected"] and r["result"]["ttd_tool_calls"] is not None])
    ttd_ratio = (s3_ttd / v2_ttd) if (v2_ttd not in (None, 0) and s3_ttd is not None) else None
    ttd_pass = (ttd_ratio is not None and ttd_ratio >= 2.0)   # v2 >= 2x faster
    v2_waste = _median([(r["result"].get("wasted") or {}).get("tokens") for r in v2_inj])
    s3_waste = _median([(r["result"].get("wasted") or {}).get("tokens") for r in s3_inj])
    waste_ratio = (v2_waste / s3_waste) if (s3_waste not in (None, 0) and v2_waste is not None) else None
    waste_pass = (waste_ratio is not None and waste_ratio <= 1.0)
    pending = (ttd_ratio is None or waste_ratio is None)
    status = ("PENDING" if pending else "PASS" if (ttd_pass and waste_pass) else "FAIL")
    return {"gate": "1bKG4", "status": status,
            "v2_ttd_median": v2_ttd, "s3_ttd_median": s3_ttd, "ttd_ratio": ttd_ratio,
            "ttd_pass_2x": ttd_pass, "v2_wasted_tokens_median": v2_waste,
            "s3_wasted_tokens_median": s3_waste, "waste_ratio": waste_ratio,
            "waste_parity_pass": waste_pass,
            "cite": "prereg_1b.md §2 + §4 (1bKG4); prereg.md 6.1 wasted-work + 6.2 (TTD>=2x)"}


# -- P3: trace-computed gate inputs (wired from the run traces) -----------------

def _read_trace(run_dir, name="trace.jsonl"):
    from trace import read_trace
    p = Path(run_dir) / name
    return list(read_trace(p)) if p.exists() else []


def replay_run_dir(run_dir) -> Optional[bool]:
    """Instrumentation-integrity replay of ONE run (Task-A pattern, prereg_1b.md §2 Standing
    / §4 line 451; archaeology_v2.md §A): re-instantiate the world from world_config.json,
    replay the recorded tool_call sequence in counter order, and require each replayed
    response (status + body) to match the recorded tool_response byte-for-byte, with the
    SAME mechanical exclusions the banked check documents (409 tripped, auth-header, lossy
    request, control-strip). Returns True/False, or None if the run carries no replayable
    world trace. NO held-out value is surfaced — only a byte-identity verdict."""
    import json as _json
    import tempfile
    from fastapi.testclient import TestClient
    from analysis.replay_check import NOOP_PATH, strip_control
    from world.server import create_app
    from world.state import RunConfig

    rd = Path(run_dir)
    if not (rd / "trace_world.jsonl").exists() or not (rd / "world_config.json").exists():
        return None
    events = _read_trace(rd, "trace_world.jsonl")
    calls, actors, resps, tripped = {}, {}, {}, set()
    for e in events:
        p = e.get("payload") or {}
        n = p.get("counter")
        if not isinstance(n, int):
            continue
        if e["event_type"] == "tool_call":
            calls[n] = p; actors[n] = e.get("actor", "unknown")
        elif e["event_type"] == "tool_response":
            resps[n] = p
        elif e["event_type"] == "worker_noncompliance":
            tripped.add(n)
    cfg = RunConfig.model_validate(
        _json.loads((rd / "world_config.json").read_text(encoding="utf-8")))
    mismatch = 0
    with tempfile.TemporaryDirectory() as td:
        cfg = cfg.model_copy(update={"trace_path": str(Path(td) / "r.jsonl")})
        app = create_app(cfg)
        client = TestClient(app, raise_server_exceptions=False)
        token = None
        for n in sorted(calls):
            call, rec = calls[n], resps.get(n)
            if rec is None:
                continue
            if n in tripped or rec.get("status") == 409:
                client.get(NOOP_PATH, headers={"X-Worker-Id": "replay-noop"})
                continue
            method = (call.get("method") or "GET").upper()
            path = call.get("path") or "/"
            if call.get("query"):
                path = f"{path}?{call['query']}"
            headers = {"X-Worker-Id": actors.get(n, "replay")}
            if token is not None:
                headers["Authorization"] = f"Bearer {token}"
            body = call.get("body")
            if isinstance(body, (dict, list)):
                r = client.request(method, path, json=body, headers=headers)
            elif isinstance(body, str):
                headers["Content-Type"] = "application/json"
                r = client.request(method, path, content=body.encode("utf-8"), headers=headers)
            else:
                r = client.request(method, path, headers=headers)
            try:
                rb = r.json()
            except ValueError:
                rb = r.text
            if (method == "POST" and call.get("path") == "/auth/token"
                    and r.status_code == 200 and isinstance(rb, dict)):
                token = rb.get("token", token)
            rb, _ = strip_control(rb)
            rec_body, _ = strip_control(rec.get("body"))
            if r.status_code == rec.get("status") and rb == rec_body:
                continue
            if 401 in (r.status_code, rec.get("status")) and r.status_code != rec.get("status"):
                continue                                  # AUTH-HDR (unrecorded header)
            if isinstance(call.get("body"), str) and "�" in call["body"]:
                continue                                  # LOSSY-REQ
            mismatch += 1
        app.state.ctx.trace.close()
    inj = next((e for e in events if e["event_type"] == "injection_fired"), None)
    return mismatch == 0 if inj is not None else None     # only injected runs gate (Standing)


def instrumentation_replay(runs_root) -> dict:
    """Standing precondition: the Task-A replay on 100% of INJECTED 1b cells, BEFORE gates.
    Enumerates every run dir under runs_root, replays each injected run, and reports
    all_pass. prereg_1b.md §2 Standing + §4 line 451."""
    results = []
    for rd in sorted(Path(runs_root).glob("*")):
        if not rd.is_dir():
            continue
        v = replay_run_dir(rd)
        if v is not None:                                 # injected run
            results.append(v)
    n = len(results)
    return {"n_injected_runs": n, "n_pass": sum(results), "all_pass": (n > 0 and all(results)),
            "cite": "prereg_1b.md §2 Standing + §4 line 451 (Task-A replay, 100% injected)"}


def clean_cap_grinds(runs_root, arm_system: str = "V2") -> dict:
    """Zero escalation-cap grinds on clean cells (1bKG2 hard). An escalation-cap grind is a
    run that hit the escalation cap (conductor/run_one.py MAX_ESCALATIONS=52 ->
    RunAbort('escalation_loop'), recorded in the run_end event). Counts clean (no
    injection_fired) PRIMARY-arm runs whose run_end.reason == 'escalation_loop'. prereg_1b.md
    §2 (1bKG2); conductor/run_one.py:662."""
    count, n_clean = 0, 0
    for rd in sorted(Path(runs_root).glob("*")):
        if not rd.is_dir():
            continue
        events = _read_trace(rd, "trace.jsonl") or _read_trace(rd, "trace_world.jsonl")
        if any(e["event_type"] == "injection_fired" for e in events):
            continue                                      # injected run, not a clean cell
        rs = next((e for e in events if e["event_type"] == "run_start"), None)
        if rs and (rs.get("payload") or {}).get("system") not in (arm_system, None):
            continue                                      # other arm
        re = next((e for e in events if e["event_type"] == "run_end"), None)
        if re is None:
            continue
        n_clean += 1
        if (re.get("payload") or {}).get("reason") == "escalation_loop":
            count += 1
    return {"count": count, "n_clean_runs_scanned": n_clean,
            "cite": "prereg_1b.md §2 (1bKG2 zero cap-grinds); conductor/run_one.py:662 "
                    "(MAX_ESCALATIONS=52)"}


# -- top-level -----------------------------------------------------------------

def compute_gates(ledger_path, audit: Optional[dict] = None,
                  runs_root: Optional[str] = None) -> dict:
    rows = load_ledger(ledger_path)
    audit = dict(audit or {})
    # P3: wire the instrumentation-integrity replay (#3) and clean cap-grind signal (#4)
    # from the run traces when runs_root is available; an explicit audit value still wins.
    if runs_root and Path(runs_root).exists():
        rep = instrumentation_replay(runs_root)
        audit["_instrumentation_replay"] = rep
        audit.setdefault("instrumentation_replay_passed", rep["all_pass"])
        grinds = clean_cap_grinds(runs_root)
        audit["_clean_cap_grinds"] = grinds
        audit.setdefault("clean_escalation_cap_grinds", grinds["count"])
    gates = [gate_1bKG1(rows, audit), gate_1bKG2(rows, audit),
             gate_1bKG3(rows, audit), gate_1bKG4(rows, audit)]
    statuses = [g["status"] for g in gates]
    if "FAIL" in statuses:
        verdict = "FAIL"
    elif "PENDING" in statuses:
        verdict = "PENDING (human-audit / precondition inputs owed)"
    else:
        verdict = "PASS"
    return {"ledger": str(ledger_path), "n_records": len(rows),
            "gates": gates, "verdict": verdict}


def format_report(report: dict) -> str:
    lines = [f"=== 1bKG gate computation ({report['n_records']} records) ===",
             "(thresholds transcribed verbatim from the FROZEN prereg; see per-gate cites)"]
    for g in report["gates"]:
        lines.append(f"  {g['gate']}: {g['status']:8s}  [{g['cite']}]")
    lines.append(f"VERDICT: {report['verdict']}")
    return "\n".join(lines)


if __name__ == "__main__":
    from analysis.matrix_runner import LEDGER_DIR
    ledger = Path(sys.argv[1]) if len(sys.argv) > 1 else LEDGER_DIR / "results.jsonl"
    runs_root = ledger.parent / "runs"
    rep = compute_gates(ledger, runs_root=str(runs_root) if runs_root.exists() else None)
    print(format_report(rep))
    out = ledger.parent / "gate_report.json"
    out.write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(f"detail -> {out}")
    # P4: present the seed-1102 probe-validity sample as a fillable worksheet for the
    # author's post-matrix verdicts (AUTHOR-12). The gate consumes them as input.
    pv = rep["gates"][0]["probe_validity"]
    if pv.get("status") == "PENDING_AUTHOR_AUDIT":
        ws = {"audit_seed": PROBE_AUDIT_SEED, "fraction": PROBE_AUDIT_FRACTION,
              "criteria": "targeted / fresh / non-perturbing / independent (100%-or-exclude)",
              "cite": pv["cite"],
              "rows": [{"interrupt": f"{k}#{j}", "verdict": None} for (k, j) in pv["sample"]]}
        wpath = ledger.parent / "probe_audit_worksheet.json"
        wpath.write_text(json.dumps(ws, indent=1), encoding="utf-8")
        print(f"probe-validity audit worksheet ({len(ws['rows'])} rows, seed "
              f"{PROBE_AUDIT_SEED}) -> {wpath}")
