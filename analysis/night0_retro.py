"""Retroactive checker evaluation over night-0's preserved runs (D16).

Author rulings 2026-06-10: after checker review, retroactive evaluation over
night-0's preserved final aggregates is ADMISSIBLE — checkers are
deterministic functions of outputs already on disk. The retroactive checker
must consume what a live checker would have: the end-of-run ground-truth
snapshot. For b1 (workers mutate repo_files) the snapshot is reconstructed
by replaying the trace — every successful PUT /repo/files/{path} in counter
order, plus the injection mutation at its recorded counter (the injected
call is the first to observe the broken world) — and the reconstruction is
validated against every successful GET /repo/files response in the same
trace (content and listing). Any b1 run whose replay fails this parity
check stays UNRESOLVED: no substitute inputs.

Reads traces only; never writes into run dirs. Verdicts are recorded in
decisions/night0_retroactive_verdicts.md by the operator.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from trace import read_run  # noqa: E402
from world.injections import apply_injection  # noqa: E402
from world.state import InjectionSpec, RunConfig, WorldState  # noqa: E402

REPO_PREFIX = "/repo/files"

# (job id, task, injection, run dir) — night-0 rows 5-13, from queue.sqlite.
NIGHT0_RUNS = [
    (5, "b1", None, "b1-S1-clean-s1"),
    (6, "b1", "schema_drift", "b1-S1-schema_drift-s1"),
    (7, "b1", "gate_skip_trap", "b1-S1-gate_skip_trap-s1"),
    (8, "c1", None, "c1-S1-clean-s1"),
    (9, "c1", "doc_contradiction", "c1-S1-doc_contradiction-s1"),
    (10, "c1", "token_expiry", "c1-S1-token_expiry-s1"),
    (11, "d1", None, "d1-S1-clean-s1"),
    (12, "d1", "gate_skip_trap", "d1-S1-gate_skip_trap-s1"),
    (13, "d1", "endpoint_404", "d1-S1-endpoint_404-s1"),
]


def load_checker(task: str):
    path = REPO_ROOT / "tasks" / "checkers" / f"{task}.py"
    spec = importlib.util.spec_from_file_location(f"checker_{task}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _as_dict(body: Any) -> Optional[dict]:
    if isinstance(body, dict):
        return body
    if isinstance(body, str):
        try:
            return json.loads(body)
        except ValueError:
            return None
    return None


def replay(task: str, events: list[dict]) -> dict:
    """Reconstruct the end-of-run world state and validate it against every
    successful repo GET in the trace. Returns the parity/replay record."""
    ws = WorldState(RunConfig(run_id="retro", seed=1, system="S1",
                              task_id=task, trace_path="retro"))
    calls: dict[int, dict] = {}
    resps: dict[int, dict] = {}
    fired: Optional[dict] = None
    for event in events:
        payload = event.get("payload") or {}
        etype = event.get("event_type")
        if etype == "tool_call" and isinstance(payload.get("counter"), int):
            calls[payload["counter"]] = payload
        elif etype == "tool_response" and isinstance(payload.get("counter"), int):
            resps[payload["counter"]] = payload
        elif etype == "injection_fired":
            fired = payload

    puts_applied = 0
    gets_validated = 0
    mismatches: list[str] = []
    injection_applied = False
    for counter in sorted(calls):
        if (fired and not injection_applied
                and fired.get("counter") == counter):
            # The injected call is the first to observe the broken world.
            apply_injection(ws, InjectionSpec(**fired["injection"]))
            injection_applied = True
        call = calls[counter]
        resp = resps.get(counter)
        if resp is None or resp.get("status") != 200:
            continue
        method, path = call.get("method"), call.get("path") or ""
        if method == "PUT" and path.startswith(REPO_PREFIX + "/"):
            body = _as_dict(call.get("body"))
            if body is not None and "content" in body:
                ws.repo_files[path[len(REPO_PREFIX) + 1:]] = body["content"]
                puts_applied += 1
        elif method == "GET" and path == REPO_PREFIX:
            body = _as_dict(resp.get("body")) or {}
            if body.get("files") != sorted(ws.repo_files):
                mismatches.append(f"counter {counter}: listing mismatch")
            gets_validated += 1
        elif method == "GET" and path.startswith(REPO_PREFIX + "/"):
            rel = path[len(REPO_PREFIX) + 1:]
            body = _as_dict(resp.get("body")) or {}
            if body.get("content") != ws.repo_files.get(rel):
                mismatches.append(f"counter {counter}: content mismatch {rel}")
            gets_validated += 1
    if fired and not injection_applied:
        # Fired after the last recorded call (tail injection) — apply so the
        # end-state matches what the live admin snapshot would have shown.
        apply_injection(ws, InjectionSpec(**fired["injection"]))
        injection_applied = True

    shipping_nested: dict[str, dict[str, Any]] = {}
    for (sku, dest), entry in ws.shipping.items():
        shipping_nested.setdefault(sku, {})[dest] = entry
    ground_truth = {
        "prices": ws.prices,
        "inventory": ws.inventory,
        "shipping": shipping_nested,
        "passages": {pid: {"title": p["title"], "content": p["content"]}
                     for pid, p in ws.passages.items()},
        "repo_files": ws.repo_files,
    }
    return {"ground_truth": ground_truth, "puts_applied": puts_applied,
            "gets_validated": gets_validated, "mismatches": mismatches,
            "injection_replayed": bool(fired)}


def final_report_of(events: list[dict]) -> tuple[bool, Any]:
    finals = [e for e in events if e.get("event_type") == "aggregate"
              and "final_report" in (e.get("payload") or {})]
    if not finals:
        return False, None
    return True, finals[-1]["payload"]["final_report"]


def evaluate() -> list[dict]:
    results = []
    for job_id, task, injection, run_dir in NIGHT0_RUNS:
        events = read_run(REPO_ROOT / "runs" / run_dir)
        rep = replay(task, events)
        has_final, final_report = final_report_of(events)
        redispatches = sum(1 for e in events
                           if e.get("event_type") == "redispatch")
        record = {
            "job": job_id, "task": task, "injection": injection,
            "run_dir": run_dir, "has_final_aggregate": has_final,
            "redispatches": redispatches,
            "puts_applied": rep["puts_applied"],
            "gets_validated": rep["gets_validated"],
            "parity_mismatches": rep["mismatches"],
            "injection_replayed": rep["injection_replayed"],
        }
        parity_ok = not rep["mismatches"]
        if task == "b1" and not parity_ok:
            record.update(verdict="UNRESOLVED",
                          detail="b1 parity not demonstrated (ruling 2)")
        elif not has_final:
            record.update(verdict=False,
                          detail="no final aggregate event in trace")
        else:
            ok, detail = load_checker(task).check(final_report,
                                                  rep["ground_truth"])
            record.update(verdict=ok, detail=detail)
        results.append(record)
    return results


def main() -> int:
    for record in evaluate():
        print(json.dumps(record))
    return 0


if __name__ == "__main__":
    sys.exit(main())
