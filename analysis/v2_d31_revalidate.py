"""D31 C5: re-validate the FULL seen sweep through the real V2Conductor, for the
right reason. All five seen categories + every clean cell (incl. b1+clean). SEEN
cells only; NO held-out; the matrix is NOT run.

Per cell it reports: detected, the probe that caught it, baseline-vs-injection index
where applicable, interrupts/replans, FIR, cost — and the D31 wiring evidence
(gate_probe_armed, write_footprints, pre_completion_probes).

Usage: python -m analysis.v2_d31_revalidate [label ...]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
os.environ["TRIPWIRE_V2"] = "1"
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# (label, task, injection, n_inject) — FROZEN SEEN cells.
CELLS = [
    ("endpoint_404",     "a1", "endpoint_404", 12),    # status fast path
    ("schema_drift",     "a1", "schema_drift", 12),     # content (arm-time baseline)
    ("token_expiry",     "a1", "token_expiry", 12),     # status fast path (multi-surface)
    ("doc_contradiction", "c1", "doc_contradiction", 6),  # content (arm-time baseline)
    ("gate_skip_trap",   "b1", "gate_skip_trap", 4),    # contract (§4 gate, armed+swept+eval)
    ("a1_clean",         "a1", None, None),             # quiet
    ("c1_clean",         "c1", None, None),             # quiet
    ("b1_clean",         "b1", None, None),             # quiet (the D31 fix)
]
CONTENT = {"schema_drift", "doc_contradiction"}


def _probe_of(reason: str, fault_shape: str) -> str:
    if "status" in reason and "fast path" in reason:
        return "status_fast_path"
    if "gate stopped enforcing" in reason:
        return "gate_shadow"
    if "write-surface drift" in reason:
        return "write_footprint"
    return fault_shape or "content_drift"


def run_cell(label, task, injection, n_inject) -> dict:
    from conductor.run_v2_loop import V2Conductor
    from sentinel_v2.arms import collect_arm_result
    from trace import read_trace
    runs_root = str(REPO / "runs" / "v2_d31_revalidate")
    print(f"\n=== V2 (real path) {task}+{injection or 'clean'} (label={label}) ===")
    cond = V2Conductor(task_path=str(REPO / "tasks" / f"{task}.yaml"),
                       injection=injection, n_inject=n_inject, seed=1,
                       runs_root=runs_root, max_replans=2)
    summary = cond.run()
    res = collect_arm_result(cond.run_dir, "V2")
    invs = cond.v2_invalidations

    inj_counter = None
    wt = cond.run_dir / "trace_world.jsonl"
    if wt.exists():
        for e in read_trace(wt):
            if e["event_type"] == "injection_fired":
                inj_counter = e["payload"].get("counter")
                break
    detail = [{"target": i.target, "grade": i.grade.value, "reason": i.reason,
               "fault_shape": i.fault_shape,
               "probe": _probe_of(i.reason, i.fault_shape),
               "baseline_source": cond.v2_baseline_source.get(i.target),
               "baseline_counter": cond.v2_baseline_counter.get(i.target)} for i in invs]
    row = {
        "label": label, "task": task, "injection": injection or "clean",
        "detected": bool(invs) or bool(res.detected),
        "interrupts": res.n_interrupts,           # M6 (the matrix instrument)
        "v2_interrupts": cond.v2_interrupts,      # conductor replan-interrupts
        "replans": cond.replans_done, "coalesced": cond.v2_coalesced,
        "fir": res.fir, "ttd": res.ttd_tool_calls, "cost_usd": summary["cost_usd"],
        "gate_probe_armed": bool(cond.v2_gate_probes),
        "gate_probe_targets": [p.target for p in cond.v2_gate_probes],
        "write_footprints": [f.surface for f in cond.v2_write_footprints],
        "arm_probes": cond.v2_arm_probes,
        "pre_completion_probes": cond.v2_pre_completion_probes,
        "arm_capture_counter": cond.v2_arm_capture_counter,
        "injection_counter": inj_counter,
        "probes": sorted({d["probe"] for d in detail}),
        "invalidations": detail, "run_dir": str(cond.run_dir),
    }
    print(f"  detected={row['detected']} interrupts={row['interrupts']} "
          f"replans={row['replans']} fir={row['fir']} ttd={row['ttd']} "
          f"cost=${row['cost_usd']}")
    print(f"  gate_probe_armed={row['gate_probe_armed']} "
          f"write_footprints={row['write_footprints']} "
          f"pre_completion_probes={row['pre_completion_probes']} "
          f"inj_counter={inj_counter}")
    for d in detail:
        print(f"    {d['target']} grade={d['grade']} probe={d['probe']} "
              f"baseline={d['baseline_source']}@{d['baseline_counter']} "
              f"reason={d['reason'][:80]}")
    return row


def main(argv) -> int:
    want = set(argv) if argv else {c[0] for c in CELLS}
    rows = [run_cell(*c) for c in CELLS if c[0] in want]
    print("\n================ D31 C5 FULL SEEN SWEEP ================")
    total = 0.0
    for r in rows:
        total += r["cost_usd"] or 0.0
        rr = ""
        if r["label"] in CONTENT:
            inj = r["injection_counter"]
            pre = [d for d in r["invalidations"]
                   if d["baseline_counter"] is not None and inj is not None
                   and d["baseline_counter"] < inj]
            rr = f" right_reason={'YES' if (r['detected'] and pre) else 'NO'}(base<{inj})"
        print(f"{r['task']}+{r['injection']:16s} detected={r['detected']!s:5s} "
              f"int={r['interrupts']} replans={r['replans']} fir={r['fir']} "
              f"probe={','.join(r['probes']) or '-'} cost=${r['cost_usd']}{rr}")
    print(f"DEV_RUN_SPEND=${round(total, 6)}")
    out = REPO / "runs" / "v2_d31_revalidate" / "summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"detail -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
