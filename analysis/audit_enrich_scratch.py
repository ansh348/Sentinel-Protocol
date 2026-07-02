"""SCRATCH read-only: enrich the 10 probe-validity worksheet rows with audit context.
NOT imported by the suite. No write, no gate recompute, nothing pushed. Held-out is spent,
so values may be shown."""
from __future__ import annotations
import json, os, sys
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO)); os.environ["TRIPWIRE_V2"] = "1"
from trace import read_trace
from conductor.escrow_loader import load_matrix_cells, load_holdout_cells
from analysis.matrix_runner import INJECTION_CATEGORY
from collections import defaultdict

RUNS = REPO / "runs" / "matrix_1b" / "runs"
FAULT = {"endpoint_404": "status->404 (API_SURFACE)", "token_expiry": "status->401 (PERMISSION_AUTH)",
         "doc_contradiction": "/content value_changed (RETRIEVAL_INTEGRITY)",
         "gate_skip_trap": "gate stops enforcing (TOOL_CONTRACT)",
         "quota_cliff": "quota_remaining < remaining required (RESOURCE_BUDGET)",
         "silent_minor_bump": "version/page drift (DEPENDENCY_VERSION)"}


def seed_map():
    mp = {}
    mc, _ = load_matrix_cells()
    for c in mc:
        kind = "matrix-injected" if c.injection else "matrix-clean"
        mp[(kind, c.task, c.injection, c.slot)] = c.launch_kwargs()["seed"]
    byp = defaultdict(list)
    for c in load_holdout_cells():
        byp[(c.task, c.injection)].append(c)
    for (t, inj), cs in byp.items():
        for i, c in enumerate(cs):
            mp[("holdout", t, inj, i)] = c.launch_kwargs()["seed"]
    return mp


def reads_of(wt_events, path):
    """clean (pre-injection) and post-injection (status, body) reads of `path` by counter."""
    inj_ctr = next((e["payload"].get("counter") for e in wt_events
                    if e["event_type"] == "injection_fired"), None)
    calls = {}
    for e in wt_events:
        p = e.get("payload") or {}; c = p.get("counter")
        if e["event_type"] == "tool_call" and p.get("path") == path:
            calls[c] = "call"
        elif e["event_type"] == "tool_response":
            calls[c] = p
    pre = post = None
    for c in sorted(k for k in calls if isinstance(k, int)):
        # find the response paired to a call on this path: tool_call then tool_response share counter
        pass
    # simpler: pair tool_call(path)->tool_response(counter)
    callctr = {e["payload"]["counter"] for e in wt_events
               if e["event_type"] == "tool_call" and (e.get("payload") or {}).get("path") == path}
    resp = {e["payload"]["counter"]: e["payload"] for e in wt_events
            if e["event_type"] == "tool_response"}
    for c in sorted(callctr):
        r = resp.get(c)
        if not r:
            continue
        rec = (c, r.get("status"))
        if inj_ctr is None or c < inj_ctr:
            pre = pre or rec
        else:
            post = rec
    return inj_ctr, pre, post


def main():
    mp = seed_map()
    ws = json.loads((REPO / "runs/matrix_1b/probe_audit_worksheet.json").read_text())
    for n, row in enumerate(ws["rows"], 1):
        kind, task, inj, slots, armj = row["interrupt"].split("|")
        slot = int(slots.replace("slot", "")); arm, j = armj.split("#"); j = int(j)
        seed = mp.get((kind, task, inj, slot))
        rd = RUNS / f"{task}-{arm}-{inj}-s{seed}"
        ev = list(read_trace(rd / "trace.jsonl"))
        esc = [e for e in ev if e["event_type"] == "escalation"]
        cap = next((e["payload"] for e in ev if e["event_type"] == "corroboration"
                    and (e.get("payload") or {}).get("layer") == "v2_arm_baseline"), {})
        probes = next((e["payload"] for e in ev if e["event_type"] == "tripwire_set"
                       and (e.get("payload") or {}).get("layer") == "v2_probes"), {})
        target = where = det_ctr = None
        if j < len(esc):
            pe = esc[j]["payload"]; target = (pe.get("evidence") or {}).get("_path")
            where = pe.get("where"); det_ctr = pe.get("counter")
        base_ctr = cap.get("capture_counter"); base_has = target in (cap.get("captured") or [])
        wt = list(read_trace(rd / "trace_world.jsonl"))
        inj_ctr, pre, post = reads_of(wt, target) if target else (None, None, None)
        print(f"[{n:2}] {row['interrupt']}")
        print(f"     category        : {INJECTION_CATEGORY.get(inj)}  (injection={inj})")
        print(f"     surface targeted: {target}   <- {'the injected load-bearing surface' if target else '?'}")
        print(f"     fault shape     : {FAULT.get(inj)}")
        print(f"     arm-time baseline: source=arm_time @counter {base_ctr} (clean, pre-injection@{inj_ctr}); "
              f"surface in baseline sweep={base_has}; clean read={pre}")
        print(f"     detection obs    : cadence={where} @counter {det_ctr}; post-injection read(status)={post}")
        print(f"     probe call       : GET {target}  via side-channel (X-Probe-Channel; read-only, counter-neutral)")
        print(f"     n_interrupts_in_run={len([e for e in ev if e['event_type']=='interrupt'])}, "
              f"armed_probes={probes.get('count')}")
        print()


if __name__ == "__main__":
    main()
