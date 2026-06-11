"""TASK A (archaeology v2): raw-event replay of the 12 L2 cells.

EXPLORATORY — adjudicates Rival Story A (GPT-5.5 + Gemini): that "L2
starvation" is actually telemetry/normalization loss, i.e. the injected
surface WAS observed in raw traffic but the evidence never produced a matcher
fire. For every L2 cell, the recorded raw tool/HTTP stream (trace_world.jsonl
— the same (method, path, status, body) tuples the live matcher consumed) is
piped through a freshly-armed TripwireMatcher per arming epoch, bypassing all
worker context. Reading discipline per decisions/phase1b_precommitments.md
§A.1: epoch-faithful replay (full epoch from its start so touch-dedup and
call-history state match live first-fire semantics; verdict rows reported
post-injection), live D11 suppression cross-referenced from suppressed_refire
events, L2<->L3 flips are FINDINGS never corrections, both pointer dialects.

Recomputes no gate quantity. Verdict (kill_gates_final.md) untouched.
"""
from __future__ import annotations

import json
import sys
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import world.server as world_server  # noqa: E402
from analysis.archaeology import covers_on_paper  # noqa: E402
from analysis.gates import cell_run_dir  # noqa: E402
from analysis.metrics import injection_info, surface_predicate  # noqa: E402
from sentinel.dsl import TripwireSet  # noqa: E402
from trace import read_run, read_trace  # noqa: E402
from world.server import (TripwireMatcher, _MISSING, _pointer_lookup,  # noqa: E402
                          classify_url_pattern)

RUNS = REPO_ROOT / "runs"
OUT_DIR = RUNS / "archaeology_v2"
CELLS = json.loads((REPO_ROOT / "analysis" / "matrix_manifest.json")
                   .read_text(encoding="utf-8"))

L2_CELLS = [  # archaeology_v1.md chain-of-death table, the 12 L2 rows
    ("a1", "endpoint_404", 1), ("a1", "endpoint_404", 2),
    ("a1", "schema_drift", 1), ("a1", "schema_drift", 3),
    ("a1", "token_expiry", 1),
    ("b1", "schema_drift", 2),
    ("b1", "gate_skip_trap", 2), ("b1", "gate_skip_trap", 3),
    ("c1", "doc_contradiction", 2),
    ("d1", "gate_skip_trap", 1),
    ("d1", "endpoint_404", 1), ("d1", "endpoint_404", 2),
]


def strip_control(body: Any) -> Any:
    if isinstance(body, dict) and "tripwire_control" in body:
        if set(body) == {"tripwire_control", "raw"}:
            return body["raw"]
        return {k: v for k, v in body.items() if k != "tripwire_control"}
    return body


def explain_no_match(tw, method: str, path: str, status: int, body: Any,
                     mode: Optional[str]) -> str:
    """Mirror TripwireMatcher._matches stepwise; first failing gate/predicate."""
    sig = tw.signal
    if sig.type == "retrieval_content" and not path.startswith("/docs"):
        return "type-gate: retrieval_content requires /docs path"
    if sig.type == "auth_state" and not (status == 401
                                         or path.startswith("/auth")):
        return "type-gate: auth_state requires 401 or /auth path"
    if sig.method and sig.method.upper() != method.upper():
        return f"method-gate: wants {sig.method}, saw {method}"
    if sig.url_pattern:
        if mode is None:
            return (f"url_pattern DEAD (D5): {sig.url_pattern!r} matches no "
                    "world path under glob or regex")
        if mode == "glob" and not fnmatchcase(path, sig.url_pattern):
            return f"url-gate(glob): {sig.url_pattern!r} !~ {path}"
        if mode == "regex":
            import re
            if not re.search(sig.url_pattern, path):
                return f"url-gate(regex): {sig.url_pattern!r} !~ {path}"
    fails = []
    if sig.status_in is not None and status not in sig.status_in:
        fails.append(f"status {status} not in {sig.status_in}")
    if sig.field_absent is not None:
        if _pointer_lookup(body, sig.field_absent) is not _MISSING:
            fails.append(f"field_absent {sig.field_absent!r} present")
    if sig.field_regex is not None:
        import re
        hit = False
        for pointer, pattern in sig.field_regex.items():
            value = _pointer_lookup(body, pointer)
            try:
                if value is not _MISSING and re.search(pattern, str(value)):
                    hit = True
            except re.error:
                pass
        if not hit:
            fails.append("field_regex no-hit")
    if fails:
        return "; ".join(fails)
    if sig.contradicts_assumption is not None:
        return "touch-dedup: already fired once for this (tripwire, path)"
    if sig.order_violation is not None:
        return "order_violation predicate not satisfied"
    return "matched (no failure)"


def replay_cell(task: str, injection: str, seed: int,
                strict_pointers: bool) -> dict:
    world_server.STRICT_POINTERS = strict_pointers
    cell = {"task": task, "system": "S5", "injection": injection, "seed": seed}
    run_dir = cell_run_dir(RUNS, cell)
    merged = read_run(run_dir)
    inj = injection_info(merged)
    pred = surface_predicate(inj["type"], inj["params"])

    sets = [e for e in merged if e["event_type"] == "tripwire_set"]
    epochs = []
    for i, e in enumerate(sets):
        end_ts = sets[i + 1]["ts"] if i + 1 < len(sets) else "9999"
        ts_obj = TripwireSet.model_validate(
            {"plan_id": e["payload"].get("plan_id", "replay"),
             "tripwires": e["payload"]["tripwires"]})
        epochs.append({"start": e["ts"], "end": end_ts, "set": ts_obj,
                       "recorded_modes": e["payload"].get("url_match_modes")})

    wevents = read_trace(run_dir / "trace_world.jsonl")
    calls: dict[int, dict] = {}
    resps: dict[int, dict] = {}
    resp_ts: dict[int, str] = {}
    tripped: set[int] = set()
    for e in wevents:
        p = e.get("payload") or {}
        n = p.get("counter")
        if not isinstance(n, int):
            continue
        if e["event_type"] == "tool_call":
            calls[n] = p
        elif e["event_type"] == "tool_response":
            resps[n] = p
            resp_ts[n] = e["ts"]
        elif e["event_type"] == "worker_noncompliance":
            tripped.add(n)

    live_surface_fires = [
        e["payload"] for e in wevents if e["event_type"] == "tripwire_fire"
        and e["payload"].get("counter", -1) >= inj["counter"]
        and pred(e["payload"].get("path", ""), e["payload"].get("status"))]
    live_suppressed_surface = [
        e["payload"] for e in wevents if e["event_type"] == "suppressed_refire"
        and e["payload"].get("counter", -1) >= inj["counter"]
        and pred(e["payload"].get("path", ""), e["payload"].get("status"))]

    rows = []
    replay_surface_fires = []
    replay_all_fires = []
    hardstop_surface_attempts = 0

    for ep in epochs:
        matcher = TripwireMatcher()
        matcher.arm(ep["set"])
        tw_by_id = {tw.id: tw for tw in ep["set"].tripwires}
        covering_ids = [tw_d.get("id") for tw_d in
                        json.loads(ep["set"].model_dump_json())["tripwires"]
                        if covers_on_paper(tw_d, inj)]
        for n in sorted(calls):
            ts = resp_ts.get(n)
            if ts is None or not (ep["start"] <= ts < ep["end"]):
                continue
            call, rec = calls[n], resps[n]
            status = rec.get("status")
            path = call.get("path") or ""
            method = (call.get("method") or "GET").upper()
            post = n >= inj["counter"]
            if n in tripped or status == 409:
                if post and pred(path, None):  # attempted surface re-touch,
                    hardstop_surface_attempts += 1  # refused by the hard-stop
                continue  # live matcher never evaluated these
            body = strip_control(rec.get("body"))
            matched = matcher.evaluate(method=method, path=path,
                                       status=status, body=body)
            if not post:
                continue
            raw_obs = pred(path, status)
            matched_ids = [tw.id for tw in matched]
            replay_all_fires.extend(matched_ids)
            if raw_obs and matched_ids:
                replay_surface_fires.append(
                    {"counter": n, "path": path, "status": status,
                     "tripwires": matched_ids})
            why = ""
            if raw_obs and not matched_ids and covering_ids:
                whys = []
                for cid in covering_ids:
                    tw = tw_by_id.get(cid)
                    if tw is None:
                        continue
                    whys.append(f"{cid}: " + explain_no_match(
                        tw, method, path, status, body,
                        matcher.pattern_mode(cid)))
                why = " | ".join(whys)
            if raw_obs:
                rows.append({
                    "counter": n, "method": method, "path": path,
                    "status": status,
                    "raw_surface_obs": True,
                    "normalized_present": True,
                    "applicable_covering": covering_ids,
                    "replay_matched": matched_ids,
                    "why_no_match": why,
                })

    # Generous union variant (pre-commitments A.1): would ANY compiled set
    # from this run have fired on the recorded post-injection raw stream?
    union_fires = []
    for ep in epochs:
        matcher = TripwireMatcher()
        matcher.arm(ep["set"])
        first_fire: dict[str, int] = {}
        ep_rows = []
        for n in sorted(calls):
            if n in tripped or resps[n].get("status") == 409:
                continue
            call, rec = calls[n], resps[n]
            matched = matcher.evaluate(
                method=(call.get("method") or "GET").upper(),
                path=call.get("path") or "",
                status=rec.get("status"),
                body=strip_control(rec.get("body")))
            for tw in matched:
                first_fire.setdefault(tw.id, n)
            if (n >= inj["counter"]
                    and pred(call.get("path") or "", rec.get("status"))
                    and matched):
                ep_rows.append(
                    {"set_armed_at": ep["start"], "counter": n,
                     "path": call.get("path"),
                     "tripwires": [tw.id for tw in matched]})
        for row in ep_rows:  # KG0 freshness: first fire must be post-injection
            row["fresh_tripwires"] = [
                t for t in row["tripwires"]
                if first_fire.get(t, 0) >= inj["counter"]]
        union_fires.extend(ep_rows)

    surface_obs = len(rows)
    if surface_obs == 0 and hardstop_surface_attempts == 0:
        ruling = "TRUE-STARVATION (zero post-injection surface observations)"
    elif replay_surface_fires and not live_surface_fires:
        ruling = ("RAW-EVIDENCE-MATCHABLE — misclassified starvation: fresh "
                  "matcher fires on recorded raw traffic where live had zero")
    elif replay_surface_fires and live_surface_fires:
        ruling = ("FIRED-LIVE-TOO (live surface fires exist; see L3 "
                  "cross-reference)")
    elif surface_obs > 0:
        ruling = ("OBSERVED-BUT-UNMATCHABLE (surface observed; no armed "
                  "predicate can express it)")
    else:
        ruling = ("HARD-STOP-STARVED (only surface re-touches were 409 "
                  "hard-stops; matcher never saw them)")

    return {
        "cell": f"{task}+{injection}/s{seed}",
        "run_dir": run_dir.name,
        "strict_pointers": strict_pointers,
        "injection_counter": inj["counter"],
        "epochs": len(epochs),
        "post_inj_surface_observations": surface_obs,
        "hardstop_surface_attempts_409": hardstop_surface_attempts,
        "replay_surface_fires": replay_surface_fires,
        "union_variant_surface_fires": union_fires,
        "replay_total_fire_events": len(replay_all_fires),
        "live_surface_fires": [
            {"counter": f.get("counter"), "tripwire_id": f.get("tripwire_id"),
             "path": f.get("path")} for f in live_surface_fires],
        "live_suppressed_surface_refires": [
            {"counter": f.get("counter"), "tripwire_id": f.get("tripwire_id"),
             "where": f.get("where")} for f in live_suppressed_surface],
        "ruling": ruling,
        "rows": rows,
    }


def dead_pattern_sweep() -> list[dict]:
    """Singleton-or-class ruling input: every armed set across all 27 injected
    S5 cells, per-tripwire D5 pattern mode, flagged when a dead/mismatched
    pattern belongs to a tripwire that covers the cell's injection on paper."""
    out = []
    for cell in CELLS:
        if cell["system"] != "S5" or cell["injection"] is None:
            continue
        run_dir = cell_run_dir(RUNS, cell)
        merged = read_run(run_dir)
        inj = injection_info(merged)
        for e in merged:
            if e["event_type"] != "tripwire_set":
                continue
            for tw in e["payload"]["tripwires"]:
                pattern = (tw.get("signal") or {}).get("url_pattern")
                if not pattern:
                    continue
                mode = classify_url_pattern(pattern)
                covering = (covers_on_paper(tw, inj) if inj else False)
                if mode is None:
                    out.append({
                        "cell": f"{cell['task']}+{cell['injection']}/s{cell['seed']}",
                        "revision": e["payload"].get("revision"),
                        "tripwire": tw.get("id"), "pattern": pattern,
                        "mode": "dead", "covers_injection_on_paper": covering,
                        "host_qualified": pattern.startswith("localhost")
                                          or "://" in pattern,
                    })
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {"lenient": [], "strict": []}
    for strict in (False, True):
        key = "strict" if strict else "lenient"
        for task, injection, seed in L2_CELLS:
            results[key].append(replay_cell(task, injection, seed, strict))
    world_server.STRICT_POINTERS = False

    dead = dead_pattern_sweep()
    results["dead_pattern_sweep"] = dead

    (OUT_DIR / "raw_replay.json").write_text(
        json.dumps(results, indent=1), encoding="utf-8")

    print(f"{'cell':28s} {'surfObs':>7s} {'409att':>6s} {'replayFire':>10s} "
          f"{'unionFire':>9s} {'liveFire':>8s} {'liveSupp':>8s}  ruling")
    for r in results["lenient"]:
        print(f"{r['cell']:28s} {r['post_inj_surface_observations']:7d} "
              f"{r['hardstop_surface_attempts_409']:6d} "
              f"{len(r['replay_surface_fires']):10d} "
              f"{len(r['union_variant_surface_fires']):9d} "
              f"{len(r['live_surface_fires']):8d} "
              f"{len(r['live_suppressed_surface_refires']):8d}  {r['ruling']}")
    delta = [
        (a["cell"], len(a["replay_surface_fires"]),
         len(b["replay_surface_fires"]))
        for a, b in zip(results["lenient"], results["strict"])
        if len(a["replay_surface_fires"]) != len(b["replay_surface_fires"])]
    print(f"\nD8 ablation (strict pointers) changes surface fires in "
          f"{len(delta)} cells: {delta}")
    n_dead = len(dead)
    n_dead_cov = sum(1 for d in dead if d["covers_injection_on_paper"])
    n_host = sum(1 for d in dead if d["host_qualified"])
    cells_dead_cov = sorted({d['cell'] for d in dead
                             if d['covers_injection_on_paper']})
    print(f"\ndead-pattern sweep over 27 injected S5 cells: {n_dead} dead "
          f"armed patterns ({n_host} host-qualified); {n_dead_cov} of them on "
          f"tripwires covering their cell's injection on paper, in cells: "
          f"{cells_dead_cov}")
    print(f"detail -> {OUT_DIR / 'raw_replay.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
