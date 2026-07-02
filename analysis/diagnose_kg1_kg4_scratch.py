"""SCRATCH read-only diagnosis of the two PENDING 1bKG inputs (D1 replay, D2 TTD).
NOT imported by the suite/world. No fix, no re-run, no ledger/verdict/harness change.
Prints field NAMES + counts only — never a held-out instance value."""
from __future__ import annotations
import json, sys, tempfile
from pathlib import Path
from collections import Counter

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import os; os.environ["TRIPWIRE_V2"] = "1"
from trace import read_trace
from fastapi.testclient import TestClient
from world.server import create_app
from world.state import RunConfig
from analysis.replay_check import NOOP_PATH, strip_control

RUNS = REPO / "runs" / "matrix_1b" / "runs"
HOLDOUT = {"quota_cliff", "silent_minor_bump"}


def classify(rd: Path):
    # injection name from dir: a1-V2-<injection>-s<seed>  (clean has 'clean')
    parts = rd.name.split("-")
    inj = parts[2] if len(parts) >= 3 else "?"
    return inj


def world_config_has_injection(rd: Path):
    cfg = json.loads((rd / "world_config.json").read_text(encoding="utf-8"))
    injc = cfg.get("injection")
    return injc is not None, (sorted((injc or {}).get("params", {}).keys()) if injc else [])


def replay_diff(rd: Path):
    """Replay one run; return (verdict, first_mismatch_dict_or_None, n_calls)."""
    events = list(read_trace(rd / "trace_world.jsonl"))
    calls, actors, resps, tripped = {}, {}, {}, set()
    for e in events:
        p = e.get("payload") or {}; n = p.get("counter")
        if not isinstance(n, int): continue
        if e["event_type"] == "tool_call": calls[n] = p; actors[n] = e.get("actor", "?")
        elif e["event_type"] == "tool_response": resps[n] = p
        elif e["event_type"] == "worker_noncompliance": tripped.add(n)
    cfg = RunConfig.model_validate(json.loads((rd / "world_config.json").read_text(encoding="utf-8")))
    inj = next((e for e in events if e["event_type"] == "injection_fired"), None)
    first = None
    with tempfile.TemporaryDirectory() as td:
        cfg = cfg.model_copy(update={"trace_path": str(Path(td) / "r.jsonl")})
        app = create_app(cfg); client = TestClient(app, raise_server_exceptions=False); token = None
        rep_inj = None
        for n in sorted(calls):
            call, rec = calls[n], resps.get(n)
            if rec is None: continue
            if n in tripped or rec.get("status") == 409:
                client.get(NOOP_PATH, headers={"X-Worker-Id": "replay-noop"}); continue
            method = (call.get("method") or "GET").upper(); path = call.get("path") or "/"
            if call.get("query"): path = f"{path}?{call['query']}"
            h = {"X-Worker-Id": actors.get(n, "replay")}
            if token is not None: h["Authorization"] = f"Bearer {token}"
            body = call.get("body")
            if isinstance(body, (dict, list)): r = client.request(method, path, json=body, headers=h)
            elif isinstance(body, str):
                h["Content-Type"] = "application/json"; r = client.request(method, path, content=body.encode(), headers=h)
            else: r = client.request(method, path, headers=h)
            try: rb = r.json()
            except ValueError: rb = r.text
            if method == "POST" and call.get("path") == "/auth/token" and r.status_code == 200 and isinstance(rb, dict):
                token = rb.get("token", token)
            rb, _ = strip_control(rb); rec_body, _ = strip_control(rec.get("body"))
            if r.status_code == rec.get("status") and rb == rec_body: continue
            if 401 in (r.status_code, rec.get("status")) and r.status_code != rec.get("status"): continue
            if isinstance(call.get("body"), str) and "�" in call["body"]: continue
            if first is None:
                # field NAMES that differ (no values)
                diff_keys = []
                if isinstance(rb, dict) and isinstance(rec_body, dict):
                    diff_keys = sorted(k for k in set(rb) | set(rec_body) if rb.get(k) != rec_body.get(k))
                first = {"counter": n, "method": method, "path": call.get("path"),
                         "status_replayed": r.status_code, "status_recorded": rec.get("status"),
                         "status_match": r.status_code == rec.get("status"),
                         "body_diff_keys": diff_keys,
                         "both_dict": isinstance(rb, dict) and isinstance(rec_body, dict)}
        # injection-counter parity
        st = app.state.ctx.state
        rep_parity = ((inj is None and not st.injection_fired)
                      or (inj is not None and st.injection_fired and st.injection_fired_at == inj["payload"].get("counter")))
        app.state.ctx.trace.close()
    verdict = "PASS" if (first is None and rep_parity) else "FAIL"
    return verdict, first, rep_parity, len(calls)


def d1():
    print("==== D1: instrumentation-integrity replay over matrix INJECTED runs ====")
    rows = []
    for rd in sorted(RUNS.glob("*")):
        if not rd.is_dir(): continue
        if not (rd / "trace_world.jsonl").exists() or not (rd / "world_config.json").exists(): continue
        inj_name = classify(rd)
        if inj_name == "clean": continue
        kind = "HOLDOUT" if inj_name in HOLDOUT else "SEEN-INJ"
        has_inj, pkeys = world_config_has_injection(rd)
        v, first, parity, ncalls = replay_diff(rd)
        rows.append((kind, inj_name, v, first, has_inj, pkeys, parity, ncalls))
    byk = Counter((k, v) for k, _, v, *_ in rows)
    print("counts by (kind, verdict):", dict(byk))
    print(f"world_config has injection spec: {sum(1 for r in rows if r[4])}/{len(rows)} injected runs; "
          f"all carry param keys: {Counter(tuple(r[5]) for r in rows)}")
    print("\n-- first mismatch per FAILED run (field NAMES + counts only) --")
    fails = [r for r in rows if r[2] == "FAIL"]
    for kind, inj, v, first, has_inj, pkeys, parity, ncalls in fails[:12]:
        print(f"  [{kind} {inj}] calls={ncalls} parity={parity} first={first}")
    # aggregate the mismatch signature
    sig = Counter()
    for *_, in []: pass
    msig = Counter((tuple(f[3]["body_diff_keys"]) if f[3] else ("<parity-only>",)) for f in fails)
    print("\n-- mismatch signature (body diff key-sets) across failed runs --")
    for keys, c in msig.most_common():
        print(f"  x{c}: differing keys = {list(keys)}")
    return rows


if __name__ == "__main__":
    d1()
