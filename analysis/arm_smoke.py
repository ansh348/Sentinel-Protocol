"""Bounded SEEN-only smoke for the five matrix arms (arm-registration dev-run).

Invokes the v2 COMPILE step ONCE on a seen cell (a1), then runs the v2 detection seam
for V2/V2J on clean + injected SEEN worlds; baselines (S1/S2/S3) are collected from
banked SEEN traces. NO held-out cell is read or loaded; NO matrix run; the only LLM
spend is the single compile call. Prints a per-arm ArmResult and the compile spend.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))   # repo root first, so `import trace` is the repo's

import yaml
from fastapi.testclient import TestClient


def _plan_text(task: dict) -> str:
    lines = [f"Goal: {task['goal'].strip()}", "", "Plan:"]
    for i, step in enumerate(task.get("plan", []), start=1):
        lines.append(f"{i}. [{step.get('subplan_id')}] {step.get('step')}")
    return "\n".join(lines)


def _world(injection=None, n_inject=None, seed: int = 1) -> TestClient:
    from world.server import create_app
    from world.state import RunConfig
    cfg = RunConfig(run_id="armsmoke", seed=seed, system="V2", task_id="a1",
                    n_inject=n_inject, injection=injection,
                    trace_path=str(REPO / "runs" / "armsmoke" / "world.jsonl"),
                    world_rev=1, probe_channel=True)
    return TestClient(create_app(cfg))


def _token(client: TestClient) -> str:
    return client.post("/auth/token", headers={"X-Worker-Id": "w1"}).json()["token"]


def main() -> int:
    os.environ["TRIPWIRE_V2"] = "1"
    from trace import TraceWriter
    from world.state import InjectionSpec
    from sentinel_v2.arms import (collect_arm_result, resolve_arm,
                                  run_v2_detection, v2_result)
    from sentinel_v2.compile_probes import compile_assumptions, compile_pipeline
    from sentinel_v2.surface_appendix import surface_appendix

    for arm in ("V2", "V2J", "S1", "S2", "S3"):
        resolve_arm(arm)                       # all five resolve (v2 flag on)

    from sentinel_v2.compile_probes import SoftAssumptionSet
    from sentinel_v2.probes import ProbeExecutor
    task = yaml.safe_load((REPO / "tasks" / "a1.yaml").read_text(encoding="utf-8"))
    appendix = surface_appendix(task, world_rev=1)

    # --- the v2 COMPILE step (the dev-run; the only LLM spend). Cached so re-runs
    #     replay the recorded soft set at $0 (record/replay determinism, D4 C4). ---
    (REPO / "runs" / "armsmoke").mkdir(parents=True, exist_ok=True)
    soft_path = REPO / "runs" / "armsmoke" / "soft.json"
    if soft_path.exists():
        soft = SoftAssumptionSet.model_validate_json(soft_path.read_text(encoding="utf-8"))
        compile_cost = 0.0
        print(f"compile: REPLAYED recorded soft set ($0)")
    else:
        tw = TraceWriter(REPO / "runs" / "armsmoke" / "compile.jsonl",
                         run_id="armsmoke", seed=1, system="V2", task_id="a1")
        soft, sessions = compile_assumptions(_plan_text(task), appendix, tw)
        tw.close()
        compile_cost = round(sum(s.cost_usd for s in sessions), 6)
        if soft is None:
            print(f"COMPILE FAILED after {len(sessions)} attempts; spend ${compile_cost}")
            return 1
        soft_path.write_text(soft.model_dump_json(), encoding="utf-8")
    probes = compile_pipeline(soft, world_rev=1).probes
    print(f"compile: {len(soft.assumptions)} soft assumptions -> {len(probes)} probes; "
          f"spend ${compile_cost}")

    def _auth(tok):
        return {"Authorization": f"Bearer {tok}", "X-Worker-Id": "w1"}

    # --- CLEAN seen world: harvest baselines and detect on the SAME instance + token
    #     (harvest equivalence §8) -> correctly quiet, no cross-instance false positives.
    clean = _world()
    ctok = _token(clean)
    cex = ProbeExecutor(clean, auth_token=ctok)
    clean_base = {p.target: cex.get(p.target) for p in probes}
    det_clean = run_v2_detection(probes, clean, auth_token=ctok, baselines=clean_base)

    # --- INJECTED seen world (endpoint_404): harvest clean baselines PRE-injection on
    #     the same world (probe-channel reads are counter-neutral), fire the injection
    #     with one worker call, then detect on the same instance + token.
    inj_entry = next(i for i in task["injections"] if i["type"] == "endpoint_404")
    inj = InjectionSpec(type="endpoint_404", params=inj_entry.get("params", {}))
    injw = _world(injection=inj, n_inject=2)
    itok = _token(injw)                                  # main counter 1 (clean)
    iex = ProbeExecutor(injw, auth_token=itok)
    inj_base = {p.target: iex.get(p.target) for p in probes}      # pre-injection (probe channel)
    injw.get("/inventory/items", headers=_auth(itok))   # main counter 2 -> injection fires
    det_inj = run_v2_detection(probes, injw, auth_token=itok, baselines=inj_base)

    results = {
        "V2": v2_result("V2", det_inj, total_cost_usd=compile_cost),
        "V2J": v2_result("V2J", run_v2_detection(probes, injw, auth_token=itok,
                                                 baselines=inj_base, judge=True),
                         total_cost_usd=compile_cost),
    }
    for arm, rd in (("S1", "a1-S1-endpoint_404-s1"),
                    ("S2", "a1-S2-endpoint_404-s1"),
                    ("S3", "a1-S3-endpoint_404-s1")):
        p = REPO / "runs" / rd
        if p.is_dir():
            results[arm] = collect_arm_result(str(p), arm)

    print(f"v2 clean seen world (expect quiet): detected={det_clean['detected']}")
    print(f"v2 injected seen world (endpoint_404): detected={det_inj['detected']} "
          f"interrupts={det_inj['n_interrupts']} grades={det_inj['grades']}")
    print("--- per-arm ArmResult (seen cells only) ---")
    for arm in ("V2", "V2J", "S1", "S2", "S3"):
        r = results.get(arm)
        if r is None:
            print(f"{arm}: (no banked seen trace present)")
            continue
        print(f"{arm:4s} detected={r.detected!s:5s} interrupts={r.n_interrupts} "
              f"ttd={r.ttd_tool_calls} fir={r.fir} cost=${r.total_cost_usd} "
              f"src={r.source} well_formed={r.well_formed()}")
    print(f"COMPILE_SPEND=${compile_cost}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
