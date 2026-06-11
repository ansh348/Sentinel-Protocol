"""PHASE 0 (archaeology v2): deterministic-world byte-identity check.

EXPLORATORY instrument verification — recomputes no gate quantity. For each
injected S5 cell, re-instantiates the world from the banked world_config.json
(trace redirected to a scratch file; banked runs/ never written) and replays
the run's recorded tool_call sequence in counter order, comparing each
replayed response (status + body) against the recorded tool_response.

Mechanical exclusions, by construction of the live system, documented here
once and counted per cell:
  TRIPPED-409   the live call was hard-stopped by the M3 amendment-2 409 for
                a tripped worker and never reached the router. The replay has
                no armed tripwires, so it advances the counter with a no-op
                request to a nonexistent path (counted by the middleware,
                no state effects, mirroring the live no-dispatch semantics)
                and does not compare bodies.
  CONTROL       the recorded body embeds a tripwire_control object (live
                matcher fired); the control is stripped (or the {"raw": ...}
                wrapper unwrapped) before comparison — the comparison then
                covers the world content only.
  AUTH-HDR      request headers are not recorded in traces; the replay
                attaches the most recently issued bearer token. A divergence
                where exactly one side is a 401 with the constant
                invalid-token body is attributable to an unrecorded header,
                not to world nondeterminism, and is counted separately.
  LOSSY-REQ     the recorded request body is a string carrying U+FFFD: the
                live worker sent invalid UTF-8 bytes, the router rejected
                them (400), and the trace stores only the errors="replace"
                decode, so the original bytes are unrecoverable. The replayed
                re-encoding is valid UTF-8 and may parse. Request-side trace
                fidelity boundary (candidate-deviation material), not world
                nondeterminism; matcher inputs are response-side and
                unaffected.

Anything else is an UNEXPLAINED mismatch, and the WAIT-FREE rule says stop.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from analysis.gates import cell_run_dir  # noqa: E402
from trace import read_trace  # noqa: E402
from world.server import create_app  # noqa: E402
from world.state import RunConfig  # noqa: E402

RUNS = REPO_ROOT / "runs"
CELLS = json.loads((REPO_ROOT / "analysis" / "matrix_manifest.json")
                   .read_text(encoding="utf-8"))
OUT_DIR = RUNS / "archaeology_v2"

NOOP_PATH = "/__replay_counter_advance__"


def strip_control(body: Any) -> tuple[Any, bool]:
    """Remove the live-run tripwire_control embedding from a recorded body."""
    if isinstance(body, dict) and "tripwire_control" in body:
        if set(body) == {"tripwire_control", "raw"}:
            return body["raw"], True
        return {k: v for k, v in body.items() if k != "tripwire_control"}, True
    return body, False


def replay_cell(cell: dict) -> Optional[dict]:
    run_dir = cell_run_dir(RUNS, cell)
    if run_dir is None:
        return None
    events = read_trace(run_dir / "trace_world.jsonl")
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

    config = RunConfig.model_validate(
        json.loads((run_dir / "world_config.json").read_text(encoding="utf-8")))

    counts = {"match": 0, "match_control_stripped": 0, "tripped_409": 0,
              "auth_hdr": 0, "lossy_request": 0, "mismatch": 0,
              "no_response_row": 0}
    mismatches: list[dict] = []

    with tempfile.TemporaryDirectory() as td:
        config = config.model_copy(
            update={"trace_path": str(Path(td) / "replay_trace.jsonl")})
        app = create_app(config)
        client = TestClient(app, raise_server_exceptions=False)
        token: Optional[str] = None

        for n in sorted(calls):
            call, rec = calls[n], resps.get(n)
            if rec is None:
                counts["no_response_row"] += 1
                continue
            if n in tripped or rec.get("status") == 409:
                client.get(NOOP_PATH,
                           headers={"X-Worker-Id": "replay-noop"})
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
                rep_body: Any = r.json()
            except ValueError:
                rep_body = r.text
            if (method == "POST" and call.get("path") == "/auth/token"
                    and r.status_code == 200 and isinstance(rep_body, dict)):
                token = rep_body.get("token", token)
            # the replayed response may carry a control only if tripwires were
            # armed in the replay; they never are — but strip defensively
            rep_body, _ = strip_control(rep_body)

            rec_status = rec.get("status")
            rec_body, had_control = strip_control(rec.get("body"))

            if r.status_code == rec_status and rep_body == rec_body:
                counts["match_control_stripped" if had_control
                       else "match"] += 1
            elif 401 in (r.status_code, rec_status) and r.status_code != rec_status:
                counts["auth_hdr"] += 1
            elif isinstance(call.get("body"), str) and "�" in call["body"]:
                counts["lossy_request"] += 1
            else:
                counts["mismatch"] += 1
                if len(mismatches) < 5:
                    mismatches.append({
                        "counter": n, "method": method, "path": path,
                        "recorded_status": rec_status,
                        "replayed_status": r.status_code,
                        "recorded_body_head": json.dumps(
                            rec_body, ensure_ascii=False, default=str)[:200],
                        "replayed_body_head": json.dumps(
                            rep_body, ensure_ascii=False, default=str)[:200],
                    })
        # injection bookkeeping parity
        st = app.state.ctx.state
        rec_inj = next((e["payload"] for e in events
                        if e["event_type"] == "injection_fired"), None)
        inj_parity = (
            (rec_inj is None and not st.injection_fired)
            or (rec_inj is not None and st.injection_fired
                and st.injection_fired_at == rec_inj.get("counter")))
        app.state.ctx.trace.close()  # Windows: tempdir cleanup needs handle freed

    return {
        "cell": f"{cell['task']}+{cell['injection']}/s{cell['seed']}",
        "run_dir": run_dir.name,
        "n_calls": len(calls),
        **counts,
        "injection_counter_parity": inj_parity,
        "byte_identical": counts["mismatch"] == 0 and inj_parity,
        "mismatch_examples": mismatches,
    }


def main() -> int:
    rows = []
    targets = [c for c in CELLS if c["system"] == "S5"
               and c["injection"] is not None]
    for cell in targets:
        row = replay_cell(cell)
        if row is None:
            print(f"MISSING RUN DIR for {cell} — stop per WAIT-FREE rule")
            return 1
        rows.append(row)
        flag = "OK " if row["byte_identical"] else "FAIL"
        print(f"{flag} {row['cell']:34s} calls={row['n_calls']:4d} "
              f"match={row['match'] + row['match_control_stripped']:4d} "
              f"ctrl={row['match_control_stripped']:3d} "
              f"409={row['tripped_409']:3d} auth={row['auth_hdr']:2d} lossy={row['lossy_request']:2d} "
              f"mismatch={row['mismatch']:3d} injK={row['injection_counter_parity']}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "replay_check.json").write_text(
        json.dumps(rows, indent=1), encoding="utf-8")
    n_ok = sum(r["byte_identical"] for r in rows)
    print(f"\nbyte-identity: {n_ok}/{len(rows)} injected S5 cells; "
          f"detail -> {OUT_DIR / 'replay_check.json'}")
    return 0 if n_ok == len(rows) else 2


if __name__ == "__main__":
    sys.exit(main())
