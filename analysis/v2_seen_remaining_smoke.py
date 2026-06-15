"""REMAINING-CATEGORY SEEN CHECK: exercise the two untested seen mechanisms on the
REAL V2Conductor path before the one-shot matrix. SEEN cells only; NO held-out; the
matrix is NOT run.

Two remaining seen categories ride DIFFERENT probe mechanisms than D30's content diff:
  - PERMISSION_AUTH = token_expiry (a1)  -> the STATUS FAST PATH (401 on a trusted
    surface), like endpoint_404. Expect: detect, 1 interrupt / 1 replan.
  - TOOL_CONTRACT   = gate_skip_trap (b1) -> the §4 GATE-SHADOW / premise re-read
    probe (GET /repo/gate_status, enforcing==True hard invariant), the "validation
    machinery silently stopped checking" case. This is the probe under test.

Part A runs each cell (+ a matched clean) through the actual V2Conductor (cadence
barriers, §8 harvest, arm-time baseline) and reports detected / probe-that-caught /
interrupts / replans / FIR / cost, plus the ARMED probe targets and baseline sources.

Part B (gate diagnosis) is category-blind: it shows, on the b1 soft set, whether the
§4 gate probe arms when compile_pipeline is called WITHOUT a world (the real loop's
call) vs WITH a live world (what the §4 trapdoor needs). It never tunes toward the
category — it only measures where the gate-enforcement assumption lands.

Usage: python -m analysis.v2_seen_remaining_smoke [gate|clean|token|diagnose ...]
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
try:                                    # Windows console is cp1252; emit UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# (label, task, injection, n_inject) — FROZEN SEEN cells (manipulation-table values:
# a1+token_expiry seed1 = 12; b1+gate_skip_trap seed1 = 4). SEEN; n_inject is the
# frozen seen value read from the banked S5 configs.
CELLS = [
    ("gate",  "b1", "gate_skip_trap", 4),    # TOOL_CONTRACT  (§4 gate-shadow probe)
    ("clean", "b1", None, None),             # matched clean -> must stay quiet
    ("token", "a1", "token_expiry", 12),     # PERMISSION_AUTH (status fast path)
]
STATUS_PATH = {"token"}      # expected to fire via the status fast path
GATE_SHADOWS = {"/repo/gate_status", "/docs/gate_status"}


def _armed_targets(run_dir: Path) -> list:
    """The probe targets the conductor armed at compile time (the last v2_probes
    tripwire_set event in the run trace)."""
    from trace import read_trace
    t = run_dir / "trace.jsonl"
    if not t.exists():
        return []
    armed = []
    for e in read_trace(t):
        if (e["event_type"] == "tripwire_set"
                and (e.get("payload") or {}).get("layer") == "v2_probes"):
            armed = e["payload"].get("targets", [])
    return armed


def run_cell(label: str, task: str, injection, n_inject) -> dict:
    from conductor.run_v2_loop import V2Conductor
    from sentinel_v2.arms import collect_arm_result
    runs_root = str(REPO / "runs" / "v2_seen_remaining")
    print(f"\n=== V2 (real path) on {task}+{injection or 'clean'} (label={label}) ===")
    cond = V2Conductor(task_path=str(REPO / "tasks" / f"{task}.yaml"),
                       injection=injection, n_inject=n_inject, seed=1,
                       runs_root=runs_root, max_replans=2)
    summary = cond.run()
    res = collect_arm_result(cond.run_dir, "V2")        # M6 metrics (fir/ttd parity)

    invs = cond.v2_invalidations
    armed = _armed_targets(cond.run_dir)
    gate_probe_armed = any(t in GATE_SHADOWS for t in armed)
    # injection counter (None on clean)
    inj_counter = None
    from trace import read_trace
    wt = cond.run_dir / "trace_world.jsonl"
    if wt.exists():
        for e in read_trace(wt):
            if e["event_type"] == "injection_fired":
                inj_counter = e["payload"].get("counter")
                break

    row = {
        "label": label, "task": task, "injection": injection or "clean",
        "detected": bool(invs), "n_invalidations": len(invs),
        "v2_interrupts": cond.v2_interrupts, "replans": cond.replans_done,
        "coalesced": cond.v2_coalesced,
        "grades": [i.grade.value for i in invs],
        "targets": [i.target for i in invs],
        "reasons": [i.reason for i in invs],
        "fault_shapes": [i.fault_shape for i in invs],
        "fir": res.fir, "ttd": res.ttd_tool_calls,
        "cost_usd": summary["cost_usd"],
        "arm_probes": cond.v2_arm_probes,
        "arm_capture_counter": cond.v2_arm_capture_counter,
        "injection_counter": inj_counter,
        "armed_targets": armed, "gate_probe_armed": gate_probe_armed,
        "baseline_source": dict(cond.v2_baseline_source),
        "run_dir": str(cond.run_dir),
    }
    print(f"  detected={row['detected']} invalidations={row['n_invalidations']} "
          f"interrupts={row['v2_interrupts']} replans={row['replans']} "
          f"coalesced={row['coalesced']} grades={row['grades']}")
    print(f"  fir={row['fir']} ttd={row['ttd']} cost=${row['cost_usd']} "
          f"arm_probes={row['arm_probes']} inj_counter={inj_counter}")
    print(f"  gate_probe_armed={gate_probe_armed}  armed_targets={armed}")
    for g, t, r in zip(row["grades"], row["targets"], row["reasons"]):
        print(f"    invalidation: target={t} grade={g} reason={r[:90]}")
    return row


# ---------------------------------------------------------------------------
# Part B: gate-miss diagnosis (category-blind; measures where the §4 gate
# assumption lands, world present vs absent — never tunes toward the category).
# ---------------------------------------------------------------------------

def _b1_soft_set():
    """Compile (or replay-cached) the b1 soft assumption set. One bounded compile
    call, cached so re-runs are $0."""
    import yaml
    from trace import TraceWriter
    from sentinel_v2.compile_probes import (SoftAssumptionSet, compile_assumptions)
    from sentinel_v2.surface_appendix import surface_appendix
    cache = REPO / "runs" / "v2_seen_remaining" / "b1_soft.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists():
        print("diagnose: REPLAYED cached b1 soft set ($0)")
        return SoftAssumptionSet.model_validate_json(cache.read_text(encoding="utf-8")), 0.0
    task = yaml.safe_load((REPO / "tasks" / "b1.yaml").read_text(encoding="utf-8"))
    lines = [f"Goal: {task['goal'].strip()}", "", "Plan:"]
    for i, step in enumerate(task.get("plan", []), start=1):
        lines.append(f"{i}. [{step.get('subplan_id')}] {step.get('step')}")
    plan_text = "\n".join(lines)
    appendix = surface_appendix(task, world_rev=int(task.get("world_rev", 1)))
    tw = TraceWriter(REPO / "runs" / "v2_seen_remaining" / "b1_compile.jsonl",
                     run_id="b1diag", seed=1, system="V2", task_id="b1")
    soft, sessions = compile_assumptions(plan_text, appendix, tw)
    tw.close()
    cost = round(sum(s.cost_usd for s in sessions), 6)
    if soft is None:
        raise RuntimeError(f"b1 compile failed; spend ${cost}")
    cache.write_text(soft.model_dump_json(), encoding="utf-8")
    print(f"diagnose: compiled b1 soft set ({len(soft.assumptions)} assumptions); ${cost}")
    return soft, cost


class _WorldAdapter:
    """Minimal `world` for compile_gate_probe: exposes `.client` (a live world
    client). The §4 non-perturbation trapdoor reads /admin/state and posts a
    sentinel canary through it."""
    def __init__(self, client):
        self.client = client


def diagnose_gate() -> dict:
    """Show whether the §4 gate probe arms with NO world (the real V2Conductor
    call) vs WITH a live world (what the trapdoor needs). Category-blind."""
    from fastapi.testclient import TestClient
    from world.server import create_app
    from world.state import RunConfig
    from sentinel_v2.compile_probes import compile_pipeline, GATE_SHADOWS as GS_MAP

    soft, cost = _b1_soft_set()
    rev = 4
    gate_surfaces = [s.surface for s in soft.assumptions
                     if any(g in (s.surface or "") for g in ("/repo/validate", "validate"))]
    print(f"\ndiagnose: b1 soft surfaces naming a gate: {gate_surfaces}")
    print(f"diagnose: GATE_SHADOWS map = {GS_MAP}")

    # (1) the REAL loop's call: compile_pipeline WITHOUT a world
    cr_noworld = compile_pipeline(soft, world_rev=rev)
    armed_noworld = [p.target for p in cr_noworld.probes]
    gate_uncovered = [u for u in cr_noworld.uncovered
                      if u["surface"] in GS_MAP]
    print(f"\n  [world=None  (the real V2Conductor call, run_v2_loop.py:68)]")
    print(f"    probes armed:        {len(cr_noworld.probes)}")
    print(f"    /…/gate_status probe armed? {any(p.target in GATE_SHADOWS for p in cr_noworld.probes)}")
    print(f"    gate assumption -> UNCOVERED: {gate_uncovered}")

    # (2) WITH a live world (what the §4 trapdoor needs to run)
    cfg = RunConfig(run_id="b1diag", seed=1, system="V2", task_id="b1",
                    trace_path=str(REPO / "runs" / "v2_seen_remaining" / "b1_diag_world.jsonl"),
                    world_rev=rev, probe_channel=True)
    client = TestClient(create_app(cfg))
    token = client.post("/auth/token", headers={"X-Worker-Id": "w1"}).json().get("token")
    cr_world = compile_pipeline(soft, world_rev=rev, world=_WorldAdapter(client),
                                auth_token=token)
    gate_probes = [p.target for p in cr_world.probes if p.target in GATE_SHADOWS]
    print(f"\n  [world=live (what compile_gate_probe's non-perturbation trapdoor needs)]")
    print(f"    probes armed:        {len(cr_world.probes)}")
    print(f"    /…/gate_status probe armed? {bool(gate_probes)}  ({gate_probes})")
    if gate_probes:
        gp = next(p for p in cr_world.probes if p.target in GATE_SHADOWS)
        print(f"    gate probe: target={gp.target} lens.op={gp.lens.op} "
              f"comparison={gp.comparison} predicate=enforcing==True")
    return {"gate_surfaces": gate_surfaces, "armed_noworld": armed_noworld,
            "gate_armed_noworld": any(p.target in GATE_SHADOWS for p in cr_noworld.probes),
            "gate_uncovered_noworld": gate_uncovered,
            "gate_armed_with_world": [p.target for p in cr_world.probes if p.target in GATE_SHADOWS],
            "compile_cost": cost}


def main(argv: list[str]) -> int:
    want = set(argv) if argv else {c[0] for c in CELLS} | {"diagnose"}
    rows = []
    for label, task, injection, n_inject in CELLS:
        if label in want:
            rows.append(run_cell(label, task, injection, n_inject))

    diag = diagnose_gate() if "diagnose" in want else None

    print("\n================ REMAINING-CATEGORY SEEN SUMMARY ================")
    total = 0.0
    for r in rows:
        total += r["cost_usd"] or 0.0
        probe = ("status_fast_path" if any(f == "status_class" for f in r["fault_shapes"])
                 else (",".join(sorted(set(r["fault_shapes"]))) or "—"))
        print(f"{r['task']}+{r['injection']:16s} detected={r['detected']!s:5s} "
              f"int={r['v2_interrupts']} replans={r['replans']} fir={r['fir']} "
              f"ttd={r['ttd']} cost=${r['cost_usd']} probe={probe} "
              f"gate_armed={r['gate_probe_armed']}")
    print(f"DEV_RUN_SPEND=${round(total + (diag['compile_cost'] if diag else 0.0), 6)}")
    out = REPO / "runs" / "v2_seen_remaining" / "summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"cells": rows, "diagnosis": diag}, indent=1),
                   encoding="utf-8")
    print(f"detail -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
