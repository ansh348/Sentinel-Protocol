"""TASK E (archaeology v2): zero-LLM shadow replay of v2-style probes +
offline corroboration policy. EXPLORATORY — recomputes no gate quantity; the
projected-recall preview is an assumption-laden projection, never a gate.

Executes per decisions/phase1b_precommitments.md §E.1–E.3:
- probes derived MECHANICALLY from each run's armed tripwires (union over
  arming epochs) + seed-matched clean-world baselines; the injection identity
  is never an input to probe construction;
- probes are read-only (GET / auth-validate / gate re-read with an invalid
  synthetic sentinel); every world instantiation is in the dev-run ledger;
- interrupts disabled: probes run against snapshot worlds (clean, then
  /admin/inject-mutated — the sanctioned tests/manual path), never inside a
  live agent run;
- cadence = the task's committed heartbeat-k; per-cell probe-overhead column;
- PROBE-UNCOVERED cells reported, never skipped (probes inherit Law 1);
- corroboration policy (full and probe-primary variants) replayed offline
  over the actual Phase 1 S5 escalation/interrupt stream.

Stated assumptions for the projection (also restated in archaeology_v2.md):
A1. Probe url_pattern targets are extracted with the v2 §11.9 #7 dialect fix
    applied (scheme/host:port prefixes stripped before D5 classification),
    since that instrument-class fix is part of the v2 the probes belong to.
    A strict variant (no normalization) is reported alongside.
A2. Trajectories are held fixed: probes neither extend nor shorten the
    recorded run; a probe can only detect at a sweep counter that the run
    actually reached.
A3. A decisive anomalous probe on the injected surface at a reached sweep is
    counted as a detection under v2 mechanics (probe evidence rides the
    fast path); blocked interrupts produce no pause.
A4. Probe verdicts on healthy surfaces are NOMINAL (justified by the Phase 0
    byte-identity result: the deterministic world gives stable baselines).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from analysis.gates import cell_run_dir  # noqa: E402
from analysis.metrics import (_attributable, _counter_at,  # noqa: E402
                              first_attributable_pause, injection_info,
                              surface_predicate)
from trace import read_run, read_trace  # noqa: E402
from world.server import create_app, classify_url_pattern, get_path_samples  # noqa: E402
from world.state import RunConfig  # noqa: E402

RUNS = REPO_ROOT / "runs"
OUT_DIR = RUNS / "archaeology_v2"
CELLS = json.loads((REPO_ROOT / "analysis" / "matrix_manifest.json")
                   .read_text(encoding="utf-8"))

HEARTBEAT_K = {"a1": 2, "b1": 21, "c1": 4, "d1": 5}  # committed fd21d9a
GATE_PATHS = ("/repo/validate", "/docs/validate")
AUTH_FREE_PREFIXES = ("/repo",)  # repo service has no require_token
INVALID_SENTINEL_DOC = {"title": "", "body": "x", "citations": []}
W_WINDOW = 10  # pre-committed second-signal window (counters)


def normalize_pattern(pattern: str) -> str:
    """A1: strip scheme/host:port prefixes (the v2 #7 dialect fix)."""
    p = re.sub(r"^[a-z]+://", "", pattern)
    p = re.sub(r"^localhost(:\d+)?", "", p)
    p = re.sub(r"^127\.0\.0\.1(:\d+)?", "", p)
    # regex-dialect patterns (start with . ^ ( [ or end-anchored wildcards)
    # must not gain a path prefix; only bare host-less paths do
    if not p.startswith(("/", "*", ".", "^", "(", "[")):
        p = "/" + p
    return p


def concrete_targets(pattern: str) -> list[str]:
    samples = get_path_samples()
    mode = classify_url_pattern(pattern)
    if mode == "glob":
        return sorted(s for s in samples if fnmatchcase(s, pattern))
    if mode == "regex":
        rx = re.compile(pattern)
        return sorted(s for s in samples if rx.search(s))
    return []


def derive_probes(tripwires: list[dict], fixed_dialect: bool) -> list[dict]:
    probes: dict[tuple, dict] = {}
    for tw in tripwires:
        sig = tw.get("signal") or {}
        pattern = sig.get("url_pattern") or ""
        if pattern and fixed_dialect:
            pattern = normalize_pattern(pattern)
        targets = concrete_targets(pattern) if pattern else []
        if sig.get("type") == "auth_state":
            targets = ["/auth/validate"]
        elif not targets:
            continue  # dead/absent pattern: no mechanical probe target (Law 1)
        for target in targets:  # one probe per concrete target (D13 spirit)
            if target.startswith("/auth"):
                kind, target = "auth-validate", "/auth/validate"
            elif target in GATE_PATHS:
                kind = "gate-reread"
            elif target.startswith("/docs/passages/"):
                kind = "content-fingerprint"
            elif sig.get("field_absent") or sig.get("field_regex") \
                    or sig.get("contradicts_assumption"):
                kind = "schema-fingerprint"
            else:
                kind = "status-probe"
            probes.setdefault((kind, target), {
                "kind": kind, "target": target,
                "tripwire_ids": [], "requires_auth":
                    not target.startswith(AUTH_FREE_PREFIXES)})
            probes[(kind, target)]["tripwire_ids"].append(tw.get("id"))
    return list(probes.values())


def execute_probe(client: TestClient, probe: dict,
                  token: Optional[str]) -> dict:
    headers = {"X-Worker-Id": "probe-replay"}
    if token and probe["requires_auth"]:
        headers["Authorization"] = f"Bearer {token}"
    kind, target = probe["kind"], probe["target"]
    if kind == "gate-reread":
        if target == "/docs/validate":
            r = client.post(target, json=INVALID_SENTINEL_DOC, headers=headers)
        else:
            r = client.post(target, headers=headers)
        try:
            b = r.json()
        except ValueError:
            b = r.text
        extract = {"status_field": b.get("status") if isinstance(b, dict) else None,
                   "checks_run": b.get("checks_run") if isinstance(b, dict) else None}
        return {"http_status": r.status_code, "extract": extract}
    r = client.get(target, headers=headers)
    try:
        b = r.json()
    except ValueError:
        b = r.text
    if kind == "auth-validate" or kind == "status-probe":
        return {"http_status": r.status_code, "extract": None}
    if kind == "content-fingerprint":
        content = b.get("content") if isinstance(b, dict) else str(b)
        return {"http_status": r.status_code,
                "extract": hashlib.sha256(str(content).encode()).hexdigest()[:16]}
    # schema-fingerprint
    if isinstance(b, dict) and isinstance(b.get("content"), str):
        extract = "sha:" + hashlib.sha256(b["content"].encode()).hexdigest()[:16]
    elif isinstance(b, dict):
        node = b
        for v in b.values():  # descend into a single list payload
            if isinstance(v, list) and v and isinstance(v[0], dict):
                node = v[0]
                break
        extract = sorted((k, type(v).__name__) for k, v in node.items())
    elif isinstance(b, list) and b and isinstance(b[0], dict):
        extract = sorted((k, type(v).__name__) for k, v in b[0].items())
    else:
        extract = str(b)[:120]
    return {"http_status": r.status_code, "extract": extract}


def probe_covers(probe: dict, inj: dict) -> bool:
    t, params = inj["type"], inj["params"]
    target = probe["target"]
    if t == "token_expiry":
        return probe["kind"] == "auth-validate" or probe["requires_auth"]
    if t in ("endpoint_404", "gate_skip_trap"):
        return fnmatchcase(target, params.get("path", "*"))
    if t == "schema_drift":
        if params.get("target") == "repo_config":
            return target.endswith("config/settings.yaml")
        return target.startswith("/pricing")
    if t == "doc_contradiction":
        return target == f"/docs/passages/{params.get('passage_id', 'pol-returns')}"
    return False


def run_worlds(task: str, seed: int, injection: dict,
               probes: list[dict]) -> list[dict]:
    """Execute every probe against the clean and mutated snapshot worlds."""
    results = []
    with tempfile.TemporaryDirectory() as td:
        config = RunConfig(run_id=f"probe-{task}-s{seed}", seed=seed,
                           system="probe-replay", task_id=task,
                           trace_path=str(Path(td) / "trace.jsonl"))
        app = create_app(config)
        client = TestClient(app, raise_server_exceptions=False)
        token = client.post("/auth/token",
                            headers={"X-Worker-Id": "probe-replay"}
                            ).json().get("token")
        clean = [execute_probe(client, p, token) for p in probes]
        client.post("/admin/inject", json=injection)
        mutated = [execute_probe(client, p, token) for p in probes]
        app.state.ctx.trace.close()
    for p, c, m in zip(probes, clean, mutated):
        results.append({**{k: p[k] for k in ("kind", "target", "requires_auth")},
                        "tripwire_ids": p["tripwire_ids"],
                        "clean": c, "mutated": m,
                        "anomalous": c != m})
    return results


def union_tripwires(events) -> list[dict]:
    tws, seen = [], set()
    for e in events:
        if e["event_type"] != "tripwire_set":
            continue
        for tw in e["payload"]["tripwires"]:
            key = json.dumps(tw.get("signal"), sort_keys=True) + str(tw.get("id"))
            if key not in seen:
                seen.add(key)
                tws.append(tw)
    return tws


def sweep_counters(arm_counter: int, last_counter: int, k: int) -> list[int]:
    return [n for n in range(k, last_counter + 1, k) if n > arm_counter]


def cell_record(cell: dict, fixed_dialect: bool) -> dict:
    run_dir = cell_run_dir(RUNS, cell)
    events = read_run(run_dir)
    inj = injection_info(events)
    task, seed = cell["task"], cell["seed"]
    k = HEARTBEAT_K[task]

    counters = [e["payload"]["counter"] for e in events
                if e["event_type"] == "tool_call"
                and isinstance(e["payload"].get("counter"), int)]
    last_counter = max(counters, default=0)
    first_set_ts = next((e["ts"] for e in events
                         if e["event_type"] == "tripwire_set"), None)
    arm_counter = 0
    if first_set_ts:
        after = [e["payload"]["counter"] for e in events
                 if e["event_type"] == "tool_call" and e["ts"] >= first_set_ts
                 and isinstance(e["payload"].get("counter"), int)]
        arm_counter = min(after) - 1 if after else last_counter

    tws = union_tripwires(events)
    probes = derive_probes(tws, fixed_dialect)
    injection = json.loads((run_dir / "world_config.json")
                           .read_text(encoding="utf-8"))["injection"]
    probe_results = run_worlds(task, seed, injection, probes) if probes else []

    covered = [r for r in probe_results if probe_covers(r, inj)] \
        if inj else []
    decisive = [r for r in covered if r["anomalous"]]

    sweeps = sweep_counters(arm_counter, last_counter, k)
    n_inj = inj["counter"] if inj else None
    post_sweeps = [s for s in sweeps if n_inj is not None and s >= n_inj]
    probe_ttd = None
    if decisive and post_sweeps:
        probe_ttd = post_sweeps[0] - n_inj

    detected_v1 = (first_attributable_pause(events, inj) is not None
                   if inj else False)
    return {
        "cell": f"{task}+{cell['injection']}/s{seed}",
        "run_dir": run_dir.name,
        "n_inject": n_inj, "arm_counter": arm_counter,
        "last_counter": last_counter, "heartbeat_k": k,
        "n_probes": len(probes),
        "probes": probe_results,
        "probe_coverage": ("L0-NO-INJECTION" if inj is None else
                           "PROBE-UNCOVERED" if not covered else
                           ("COVERED-DECISIVE" if decisive
                            else "COVERED-INDECISIVE")),
        "decisive_probe_targets": [r["target"] for r in decisive],
        "n_sweeps_total": len(sweeps),
        "n_sweeps_post_injection": len(post_sweeps),
        "probe_calls_total": len(sweeps) * len(probes),
        "probe_calls_post_injection": len(post_sweeps) * len(probes),
        "probe_ttd": probe_ttd,
        "first_post_sweep_reached": bool(post_sweeps),
        "v1_detected_strict": detected_v1,
    }


def policy_replay(cell: dict, probe_row: dict) -> list[dict]:
    """Pre-committed corroboration policy over the cell's actual interrupts."""
    run_dir = cell_run_dir(RUNS, cell)
    events = read_run(run_dir)
    inj = injection_info(events)

    escalations = []
    for e in events:
        if e["event_type"] == "escalation":
            p = e["payload"] or {}
            ev = p.get("evidence") or {}
            tw = (p.get("tripwire") or {})
            escalations.append({
                "ts": e["ts"], "counter": _counter_at(events, e["ts"]),
                "tripwire_id": tw.get("id") or p.get("tripwire_id"),
                "path": ev.get("_path") or ev.get("path") or ""})

    rows = []
    for e in events:
        if e["event_type"] != "interrupt":
            continue
        p = e["payload"] or {}
        ev = p.get("evidence") or {}
        tw = (p.get("tripwire") or {})
        tw_id = tw.get("id") or p.get("tripwire_id") or "(raw)"
        counter = _counter_at(events, e["ts"])
        status = ev.get("_status") if ev.get("_status") is not None \
            else ev.get("status")
        fast = isinstance(status, int) and status >= 400
        path = ev.get("_path") or ev.get("path") or ""

        second = any(
            esc["tripwire_id"] and esc["tripwire_id"] != tw_id
            and esc["path"] != path
            and abs(esc["counter"] - counter) <= W_WINDOW
            for esc in escalations)

        # offline probe confirmation (A4: healthy surfaces -> NOMINAL)
        probe_confirms = False
        if inj is not None and probe_row["decisive_probe_targets"]:
            on_injected_surface = surface_predicate(
                inj["type"], inj["params"])(path, status)
            post = counter >= inj["counter"]
            sweep_reachable = any(
                s >= counter for s in range(
                    probe_row["heartbeat_k"],
                    probe_row["last_counter"] + 1,
                    probe_row["heartbeat_k"]))
            probe_confirms = on_injected_surface and post and sweep_reachable

        attributable = _attributable(events, inj, e)
        rows.append({
            "cell": probe_row["cell"], "counter": counter,
            "tripwire": tw_id, "evidence_status": status, "path": path,
            "fast_path": fast, "second_signal": second,
            "probe_confirms": probe_confirms,
            "attributable": attributable,
            "allowed_full": fast or second or probe_confirms,
            "allowed_probe_primary": fast or probe_confirms,
        })
    return rows


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    s5_injected = [c for c in CELLS if c["system"] == "S5"
                   and c["injection"] is not None]

    s5_clean = [c for c in CELLS if c["system"] == "S5"
                and c["injection"] is None]

    records, interrupts = {}, []
    for variant in (True, False):
        key = "fixed_dialect" if variant else "strict_dialect"
        records[key] = [cell_record(c, variant) for c in s5_injected]
    for cell, row in zip(s5_injected, records["fixed_dialect"]):
        interrupts.extend(policy_replay(cell, row))
    # clean-cell interrupts complete the false denominator (3 in v1 anatomy);
    # no injection -> probes NOMINAL (A4) -> probe_confirms always False
    for cell in s5_clean:
        run_dir = cell_run_dir(RUNS, cell)
        events = read_run(run_dir)
        counters = [e["payload"]["counter"] for e in events
                    if e["event_type"] == "tool_call"
                    and isinstance(e["payload"].get("counter"), int)]
        stub = {"cell": f"{cell['task']}+clean/s{cell['seed']}",
                "decisive_probe_targets": [],
                "heartbeat_k": HEARTBEAT_K[cell["task"]],
                "last_counter": max(counters, default=0)}
        interrupts.extend(policy_replay(cell, stub))

    # ---- confusion-matrix preview (fixed-dialect primary) ----
    false_ints = [r for r in interrupts if not r["attributable"]]
    true_ints = [r for r in interrupts if r["attributable"]]

    def project(allow_key: str) -> dict:
        detected = []
        for cell, row in zip(s5_injected, records["fixed_dialect"]):
            cell_ints = [r for r in interrupts if r["cell"] == row["cell"]]
            v1_path = row["v1_detected_strict"] and any(
                r["attributable"] and r[allow_key] for r in cell_ints)
            probe_path = (row["probe_coverage"] == "COVERED-DECISIVE"
                          and row["first_post_sweep_reached"])
            detected.append({"cell": row["cell"], "v1_path": v1_path,
                             "probe_path": probe_path,
                             "detected": v1_path or probe_path})
        n = sum(d["detected"] for d in detected)
        n_excl_l0 = sum(d["detected"] for d in detected
                        if not d["cell"].startswith("b1+gate_skip_trap/s1"))
        return {"per_cell": detected, "recall": f"{n}/{len(detected)}",
                "recall_gate_denominator": f"{n_excl_l0}/{len(detected) - 1}"}

    summary = {
        "n_interrupts": len(interrupts),
        "false_interrupts": {
            "n": len(false_ints),
            "blocked_full": sum(1 for r in false_ints if not r["allowed_full"]),
            "blocked_probe_primary": sum(
                1 for r in false_ints if not r["allowed_probe_primary"]),
        },
        "true_attributable_interrupts": {
            "n": len(true_ints),
            "suppressed_full": sum(1 for r in true_ints
                                   if not r["allowed_full"]),
            "suppressed_probe_primary": sum(
                1 for r in true_ints if not r["allowed_probe_primary"]),
        },
        "projection_full": project("allowed_full"),
        "projection_probe_primary": project("allowed_probe_primary"),
    }

    (OUT_DIR / "probe_replay.json").write_text(
        json.dumps({"records": records, "interrupts": interrupts,
                    "summary": summary}, indent=1), encoding="utf-8")

    print("TASK E — probe shadow replay (fixed-dialect primary)")
    print(f"{'cell':28s} {'cov':22s} {'pTTD':>5s} {'swPost':>6s} "
          f"{'ovTot':>5s} {'ovPost':>6s} {'v1':>3s}")
    for r in records["fixed_dialect"]:
        print(f"{r['cell']:28s} {r['probe_coverage']:22s} "
              f"{str(r['probe_ttd']) if r['probe_ttd'] is not None else '-':>5s} "
              f"{r['n_sweeps_post_injection']:6d} {r['probe_calls_total']:5d} "
              f"{r['probe_calls_post_injection']:6d} "
              f"{'Y' if r['v1_detected_strict'] else 'n':>3s}")
    cov = [r["probe_coverage"] for r in records["fixed_dialect"]]
    cov_strict = [r["probe_coverage"] for r in records["strict_dialect"]]
    print(f"\ncoverage (fixed dialect): DECISIVE="
          f"{cov.count('COVERED-DECISIVE')} INDECISIVE="
          f"{cov.count('COVERED-INDECISIVE')} UNCOVERED="
          f"{cov.count('PROBE-UNCOVERED')}")
    print(f"coverage (strict dialect): DECISIVE="
          f"{cov_strict.count('COVERED-DECISIVE')} INDECISIVE="
          f"{cov_strict.count('COVERED-INDECISIVE')} UNCOVERED="
          f"{cov_strict.count('PROBE-UNCOVERED')}")
    print(json.dumps({k: v for k, v in summary.items()
                      if k != "projection_full"
                      and k != "projection_probe_primary"}, indent=1))
    print("projected strict recall (full policy):",
          summary["projection_full"]["recall"])
    print("projected strict recall (probe-primary):",
          summary["projection_probe_primary"]["recall"])
    print(f"detail -> {OUT_DIR / 'probe_replay.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
