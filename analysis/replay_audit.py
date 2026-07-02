"""Per-cell instrumentation-integrity replay AUDIT (standalone, READ-ONLY).

The frozen gate (`analysis/matrix_gates.py`) computes the Standing instrumentation
replay over the banked matrix and records only an aggregate verdict
(`instrumentation_replay.status == "FAIL"`, i.e. `all_pass=False`) with NO per-cell
specifics anywhere. This script re-runs that exact replay path with PER-CELL logging so
the single (or multiple) non-identical cell can be identified and explained from
evidence rather than asserted.

It does NOT modify the gate, traces, world_config, gate reports, or the deviation log.
It REUSES the gate's own primitives by import (never copies/edits them):
  - analysis.matrix_gates.replay_run_dir   (the authoritative per-cell bool oracle)
  - analysis.matrix_gates.instrumentation_replay (the aggregate oracle)
  - analysis.matrix_gates._read_trace      (identical trace parsing)
  - analysis.replay_check.strip_control, NOOP_PATH (identical control-strip + no-op path)
  - world.server.create_app, world.state.RunConfig (identical world instantiation)
The instrumented loop below is a faithful re-implementation of replay_run_dir's body
(same world instantiation, same call ordering, same 409/auth-skip/lossy rules); for
every injected-class run dir it additionally captures the first/all differing calls.

Reconciliation guards (the script STOPS / flags loudly if they break):
  (1) per-cell: instrumented byte_identical_gate == replay_run_dir(rd) for every cell;
  (2) aggregate: my (n_pass, n_fail) == instrumentation_replay(runs_root).

Determinism: the full instrumented audit runs 3x; if the set of failing cells and their
diffs is identical across runs => deterministic (NOT a race); if it varies =>
nondeterministic.

Output: runs/matrix_1b/instrumentation_replay_audit.json + a printed summary table.
No LLM calls. No matrix re-run. No edits to anything frozen.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from analysis.matrix_gates import (  # noqa: E402  (reused, never modified)
    _read_trace, instrumentation_replay, replay_run_dir,
)
from analysis.replay_check import NOOP_PATH, strip_control  # noqa: E402
from world.server import create_app  # noqa: E402
from world.state import RunConfig  # noqa: E402

RUNS_ROOT = REPO_ROOT / "runs" / "matrix_1b" / "runs"
OUT_PATH = REPO_ROOT / "runs" / "matrix_1b" / "instrumentation_replay_audit.json"

# Frozen injection -> ontology category (prereg_1b.md §3 injection set; task yamls).
CATEGORY = {
    "endpoint_404": "API_SURFACE",
    "schema_drift": "SCHEMA_DRIFT",
    "token_expiry": "PERMISSION_AUTH",
    "doc_contradiction": "RETRIEVAL_INTEGRITY",
    "gate_skip_trap": "TOOL_CONTRACT",
    "quota_cliff": "RESOURCE_BUDGET",
    "silent_minor_bump": "DEPENDENCY_VERSION",
}

# A differing body LEAF whose final key is here is treated as NON-detection: it is not a
# matcher predicate target. `quota_remaining` is the in-body informational mirror of the
# X-Quota-Remaining header (world/server.py:576); response HEADERS are not compared by the
# gate at all (it compares status + parsed body only). Everything else is conservatively
# DETECTION-relevant (the DSL can read any other body field).
NON_DETECTION_LEAVES = {"quota_remaining"}


def _short(v: Any, cap: int = 400) -> Any:
    if isinstance(v, (int, float, bool)) or v is None:
        return v
    s = json.dumps(v, ensure_ascii=False, default=str)
    return s if len(s) <= cap else s[:cap] + f"...<+{len(s) - cap}b>"


def _leaf(path: str) -> str:
    return path.replace("]", "").split("[")[0].split(".")[-1]


def deep_diff(rec: Any, rep: Any, path: str = "") -> list[dict]:
    """recorded (banked/original) vs replayed (re-run now); leaf-level diffs."""
    out: list[dict] = []
    if isinstance(rec, dict) and isinstance(rep, dict):
        for k in sorted(set(rec) | set(rep), key=str):
            cp = f"{path}.{k}" if path else str(k)
            if k not in rep:
                out.append({"path": cp, "change": "removed_in_replay",
                            "recorded": _short(rec[k]), "replayed": None})
            elif k not in rec:
                out.append({"path": cp, "change": "added_in_replay",
                            "recorded": None, "replayed": _short(rep[k])})
            else:
                out.extend(deep_diff(rec[k], rep[k], cp))
    elif isinstance(rec, list) and isinstance(rep, list):
        if len(rec) != len(rep):
            out.append({"path": path or "(root)", "change": "list_len",
                        "recorded": len(rec), "replayed": len(rep)})
        for i in range(min(len(rec), len(rep))):
            out.extend(deep_diff(rec[i], rep[i], f"{path}[{i}]"))
    else:
        if rec != rep:
            out.append({"path": path or "(root)", "change": "value",
                        "recorded": _short(rec), "replayed": _short(rep)})
    return out


def parse_cell(dir_name: str) -> dict:
    parts = dir_name.split("-")
    injection = "-".join(parts[2:-1]) if len(parts) >= 4 else None
    return {
        "dir": dir_name,
        "task": parts[0] if parts else None,
        "arm": parts[1] if len(parts) > 1 else None,
        "injection": injection,
        "category": CATEGORY.get(injection),
        "seed": parts[-1] if parts else None,
    }


def replay_instrumented(rd: Path) -> Optional[dict]:
    """Faithful re-implementation of matrix_gates.replay_run_dir, with per-call diff
    capture. Returns None for a non-injected (or non-replayable) dir, exactly as the gate
    treats it. byte_identical_gate is `mismatch == 0` — the SAME quantity the gate uses
    for pass/fail (it does NOT fold injection-counter parity into the verdict)."""
    if not (rd / "trace_world.jsonl").exists() or not (rd / "world_config.json").exists():
        return None
    events = _read_trace(rd, "trace_world.jsonl")
    calls: dict[int, dict] = {}
    actors: dict[int, str] = {}
    resps: dict[int, dict] = {}
    tripped: set[int] = set()
    for e in events:
        p = e.get("payload") or {}
        n = p.get("counter")
        if not isinstance(n, int):
            continue
        if e["event_type"] == "tool_call":
            calls[n] = p
            actors[n] = e.get("actor", "unknown")
        elif e["event_type"] == "tool_response":
            resps[n] = p
        elif e["event_type"] == "worker_noncompliance":
            tripped.add(n)

    inj_event = next((e for e in events if e["event_type"] == "injection_fired"), None)
    if inj_event is None:
        return None  # not an injected-class cell — the gate returns None here

    cfg = RunConfig.model_validate(
        json.loads((rd / "world_config.json").read_text(encoding="utf-8")))

    counts = {"match": 0, "match_control_stripped": 0, "tripped_409": 0,
              "auth_hdr": 0, "lossy_request": 0, "no_response_row": 0, "mismatch": 0}
    mismatches: list[dict] = []

    with tempfile.TemporaryDirectory() as td:
        cfg = cfg.model_copy(update={"trace_path": str(Path(td) / "r.jsonl")})
        app = create_app(cfg)
        client = TestClient(app, raise_server_exceptions=False)
        token: Optional[str] = None
        for n in sorted(calls):
            call, rec = calls[n], resps.get(n)
            if rec is None:
                counts["no_response_row"] += 1
                continue
            if n in tripped or rec.get("status") == 409:
                client.get(NOOP_PATH, headers={"X-Worker-Id": "replay-noop"})
                counts["tripped_409"] += 1
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
                r = client.request(method, path, content=body.encode("utf-8"),
                                   headers=headers)
            else:
                r = client.request(method, path, headers=headers)
            try:
                rb: Any = r.json()
            except ValueError:
                rb = r.text
            if (method == "POST" and call.get("path") == "/auth/token"
                    and r.status_code == 200 and isinstance(rb, dict)):
                token = rb.get("token", token)
            rb, _ = strip_control(rb)
            rec_status = rec.get("status")
            rec_body, _ = strip_control(rec.get("body"))

            if r.status_code == rec_status and rb == rec_body:
                counts["match"] += 1
                continue
            if 401 in (r.status_code, rec_status) and r.status_code != rec_status:
                counts["auth_hdr"] += 1
                continue
            if isinstance(call.get("body"), str) and "�" in call["body"]:
                counts["lossy_request"] += 1
                continue
            # --- genuine mismatch: capture specifics ---
            counts["mismatch"] += 1
            status_differs = (r.status_code != rec_status)
            body_diffs = deep_diff(rec_body, rb)
            detection_relevant = status_differs or any(
                _leaf(d["path"]) not in NON_DETECTION_LEAVES for d in body_diffs)
            only_quota_remaining = (not status_differs and len(body_diffs) > 0
                                    and all(_leaf(d["path"]) in NON_DETECTION_LEAVES
                                            for d in body_diffs))
            mismatches.append({
                "counter": n, "method": method, "path": path,
                "recorded_status": rec_status, "replayed_status": r.status_code,
                "status_differs": status_differs,
                "differing_fields": body_diffs,
                "detection_relevant": detection_relevant,
                "only_quota_remaining": only_quota_remaining,
            })
        st = app.state.ctx.state
        inj_parity = bool(st.injection_fired
                          and st.injection_fired_at == inj_event.get("counter"))
        app.state.ctx.trace.close()  # Windows: free handle before tempdir cleanup

    cell = parse_cell(rd.name)
    cell.update({
        "injected": True,
        "n_calls": len(calls),
        "counts": counts,
        "byte_identical_gate": counts["mismatch"] == 0,  # == replay_run_dir's verdict
        "injection_counter_parity": inj_parity,          # reported, NOT in the verdict
        "first_differing_counter": (min(m["counter"] for m in mismatches)
                                    if mismatches else None),
        "mismatches": mismatches,
    })
    return cell


def cell_signature(rec: dict) -> str:
    """Canonical signature for determinism comparison (pass/fail + exact diffs)."""
    return json.dumps({
        "dir": rec["dir"],
        "byte_identical_gate": rec["byte_identical_gate"],
        "mismatches": [
            {"counter": m["counter"], "recorded_status": m["recorded_status"],
             "replayed_status": m["replayed_status"],
             "differing_fields": m["differing_fields"]}
            for m in rec["mismatches"]
        ],
    }, sort_keys=True, ensure_ascii=False)


def run_pass(injected_dirs: list[Path]) -> dict[str, dict]:
    return {rd.name: replay_instrumented(rd) for rd in injected_dirs}


def main() -> int:
    all_dirs = sorted(p for p in RUNS_ROOT.glob("*") if p.is_dir())
    # injected-class = the gate returns non-None (injection_fired present + replayable)
    injected_dirs = [rd for rd in all_dirs if replay_instrumented(rd) is not None]
    print(f"run dirs total={len(all_dirs)}  injected-class={len(injected_dirs)}")

    # --- determinism: 3 instrumented passes ---
    passes = [run_pass(injected_dirs) for _ in range(3)]
    sigs = [{name: cell_signature(rec) for name, rec in p.items()} for p in passes]
    deterministic = (sigs[0] == sigs[1] == sigs[2])
    drift = sorted(n for n in sigs[0]
                   if not (sigs[0][n] == sigs[1][n] == sigs[2][n]))

    canon = passes[0]  # pass 1 is the recorded artifact

    # --- per-cell reconciliation vs the unmodified gate oracle replay_run_dir ---
    disagreements = []
    for rd in injected_dirs:
        gate_bool = replay_run_dir(rd)  # the frozen primitive, unmodified
        mine = canon[rd.name]["byte_identical_gate"]
        if gate_bool != mine:
            disagreements.append({"dir": rd.name, "gate": gate_bool, "audit": mine})

    # --- aggregate reconciliation vs the gate's own instrumentation_replay ---
    gate_agg = instrumentation_replay(str(RUNS_ROOT))
    n_pass = sum(1 for r in canon.values() if r["byte_identical_gate"])
    n_fail = sum(1 for r in canon.values() if not r["byte_identical_gate"])
    agg_ok = (gate_agg["n_injected_runs"] == len(injected_dirs)
              and gate_agg["n_pass"] == n_pass)

    failing = sorted(n for n, r in canon.items() if not r["byte_identical_gate"])

    # reach question: the five V2 a1+quota_cliff (RESOURCE_BUDGET) cells
    reach = [
        {"dir": r["dir"], "seed": r["seed"],
         "byte_identical_gate": r["byte_identical_gate"],
         "n_mismatch": r["counts"]["mismatch"],
         "mismatches": r["mismatches"]}
        for r in (canon[n] for n in sorted(canon))
        if r["task"] == "a1" and r["arm"] == "V2" and r["injection"] == "quota_cliff"
    ]

    artifact = {
        "meta": {
            "generated_by": "analysis/replay_audit.py",
            "read_only": True,
            "runs_root": str(RUNS_ROOT.relative_to(REPO_ROOT)),
            "primitives_reused": [
                "analysis.matrix_gates.replay_run_dir",
                "analysis.matrix_gates.instrumentation_replay",
                "analysis.matrix_gates._read_trace",
                "analysis.replay_check.strip_control",
                "analysis.replay_check.NOOP_PATH",
                "world.server.create_app", "world.state.RunConfig",
            ],
            "non_detection_leaves": sorted(NON_DETECTION_LEAVES),
            "n_determinism_passes": 3,
        },
        "summary": {
            "n_injected": len(injected_dirs),
            "n_pass": n_pass,
            "n_fail": n_fail,
            "failing_cells": failing,
            "deterministic": deterministic,
            "nondeterministic_cells_across_3_runs": drift,
            "reconciliation": {
                "gate_all_pass": gate_agg["all_pass"],
                "gate_n_injected_runs": gate_agg["n_injected_runs"],
                "gate_n_pass": gate_agg["n_pass"],
                "audit_n_injected": len(injected_dirs),
                "audit_n_pass": n_pass,
                "per_cell_agreement": (len(disagreements) == 0),
                "per_cell_disagreements": disagreements,
                "aggregate_agreement": agg_ok,
            },
        },
        "reach_question_v2_a1_quota_cliff": reach,
        "per_cell": [canon[n] for n in sorted(canon)],
    }

    OUT_PATH.write_text(json.dumps(artifact, indent=1), encoding="utf-8")

    # --- printed summary ---
    print("\n=== INSTRUMENTATION-REPLAY PER-CELL AUDIT ===")
    print(f"injected-class cells: {len(injected_dirs)}   "
          f"PASS={n_pass}  FAIL={n_fail}")
    print(f"deterministic across 3 runs: {deterministic}"
          + ("" if deterministic else f"  (varying: {drift})"))
    print(f"reconcile vs gate replay_run_dir (per-cell): "
          f"{'OK' if not disagreements else 'DISAGREE ' + str(disagreements)}")
    print(f"reconcile vs gate instrumentation_replay (aggregate): "
          f"all_pass={gate_agg['all_pass']} n_pass={gate_agg['n_pass']}/"
          f"{gate_agg['n_injected_runs']}  -> {'OK' if agg_ok else 'MISMATCH'}")
    if failing:
        print("\nFAILING CELLS:")
        for n in failing:
            r = canon[n]
            for m in r["mismatches"]:
                fields = ", ".join(
                    f"{d['path']}: {d['recorded']!r}->{d['replayed']!r}"
                    for d in m["differing_fields"]) or "(status only)"
                print(f"  {n}  @counter {m['counter']} {m['method']} {m['path']}  "
                      f"status {m['recorded_status']}->{m['replayed_status']}  "
                      f"detection_relevant={m['detection_relevant']}  "
                      f"only_quota_remaining={m['only_quota_remaining']}\n"
                      f"      diff: {fields}")
    else:
        print("\nNo failing cells.")

    print("\nREACH — five V2 a1+quota_cliff (RESOURCE_BUDGET) cells:")
    for r in reach:
        print(f"  {r['dir']:30s} byte_identical={r['byte_identical_gate']} "
              f"mismatch={r['n_mismatch']}")

    print(f"\nartifact -> {OUT_PATH}")
    if disagreements or not agg_ok:
        print("\n*** RECONCILIATION FAILED — treat per-cell findings as SUSPECT ***")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
