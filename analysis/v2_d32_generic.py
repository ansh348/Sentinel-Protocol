"""D32 C2(b): the DECISIVE generic-naming-plan variant of c1+doc_contradiction.

The grounding-rate diagnosis flagged — and did not spend — the decisive test: under a
plan that names the document-passage retrieval at the FAMILY level with NO concrete
passage id bound, does the family get fully armed so the (injection-blind) substrate
covers pol-returns as a family member, and does detection follow?

This runs the REAL V2Conductor path (real compile + workers + cadence + arm-time
baseline + pre-completion sweep), overriding ONLY the orchestrator plan with a FIXED
generic plan (planner variance controlled out, exactly as the diagnosis controlled it).
The plan is constructed SEEN-ONLY and CATEGORY-BLIND: it names the family-level
retrieval `/docs/passages/{passage_id}` and the `/docs/passages` index, binds NO
concrete passage id, and never references the injection. Both an injected and a clean
generic cell are run.

Reports per cell: detected, the probe that caught it, the ARMED PASSAGE FAMILY (the
member set the contradiction surface grounds to), baseline-vs-injection index,
interrupts/replans, FIR, cost.

Usage: ../.venv/Scripts/python.exe -m analysis.v2_d32_generic
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

from conductor.run_one import Plan, PlanStep, REPO_ROOT  # noqa: E402
from conductor.run_v2_loop import V2Conductor  # noqa: E402

TASK = "c1"
INJECTED_PASSAGE = "/docs/passages/pol-returns"
N_INJECT = 6                      # the SEEN c1+doc_contradiction cell
RUNS_ROOT = str(REPO / "runs" / "v2_d32_generic")

# A GENERIC-naming plan: names the FAMILY-level passage retrieval with NO concrete
# passage id bound (the worker discovers the ids from the index at run time). Category-
# blind, injection-blind, seen-only. The `{passage_id}` literal names the family-level
# retrieval; the index `/docs/passages` lists the members.
_LIST_AND_FETCH = (
    "1. Obtain a bearer token: run `curl http://localhost:8400/auth/token -s -X POST "
    "-H \"X-Worker-Id: <your_worker_id>\"`. Parse the JSON and extract the 'token' field "
    "as TOKEN.\n"
    "2. List the available document passages: run `curl \"http://localhost:8400/docs/"
    "passages\" -s -H \"Authorization: Bearer $TOKEN\" -H \"X-Worker-Id: <your_worker_id>\"`. "
    "This returns the set of passage ids available in the corpus.\n"
    "3. For EACH passage id the list returned, fetch that passage from the passage store "
    "via the GET /docs/passages/{passage_id} endpoint: run `curl \"http://localhost:8400/"
    "docs/passages/<id>\" -s -H \"Authorization: Bearer $TOKEN\" -H \"X-Worker-Id: "
    "<your_worker_id>\"` (substitute each id). Capture each full JSON response.\n")

GENERIC_PLAN = Plan(
    plan_id="c1-generic-d32", revision=0,
    aggregation="Combine the retrieved passages into one operations policy brief.",
    steps=[
        PlanStep(subplan_id="s1", worker_id="w1", subtask=(
            "Retrieve the company document passages from the passage store and return "
            "them. Follow these steps in order:\n" + _LIST_AND_FETCH +
            "4. Output exactly this JSON object: {\"passages\": [<each passage response "
            "object you fetched>]}.")),
        PlanStep(subplan_id="s2", worker_id="w2", subtask=(
            "Compose, validate, and package an operations policy brief from the document "
            "passages. Follow these steps in order:\n" + _LIST_AND_FETCH +
            "4. Compose a JSON brief payload: {\"title\": \"Operations Policy Brief\", "
            "\"body\": a single string of at least 50 characters concatenating the text "
            "fields of the passages you fetched, \"citations\": the list of passage ids "
            "you fetched}.\n"
            "5. Validate the brief: run `curl http://localhost:8400/docs/validate -s -X "
            "POST -H \"Authorization: Bearer $TOKEN\" -H \"Content-Type: application/json\" "
            "-H \"X-Worker-Id: <your_worker_id>\" -d \"$PAYLOAD\"`. Record VALIDATE_RESP.\n"
            "6. Package the brief with the IDENTICAL payload: run `curl http://localhost:"
            "8400/docs/package -s -X POST -H \"Authorization: Bearer $TOKEN\" -H "
            "\"Content-Type: application/json\" -H \"X-Worker-Id: <your_worker_id>\" -d "
            "\"$PAYLOAD\"`. Record PACKAGE_RESP.\n"
            "7. Output exactly this JSON object: {\"validate_response\": <VALIDATE_RESP "
            "object>, \"package_response\": <PACKAGE_RESP object>}.")),
    ])


class GenericPlanV2Conductor(V2Conductor):
    """Real V2Conductor, but the orchestrator PLAN is fixed to GENERIC_PLAN (planner
    variance controlled out). Everything downstream — the real compile, workers,
    cadence, arm-time baseline, and pre-completion sweep — runs unchanged."""

    def make_plan(self) -> Plan:
        # replicate make_plan's orch_system_prompt setup (replan/aggregate need it),
        # but install the fixed generic plan instead of calling the orchestrator LLM.
        template = (REPO_ROOT / "prompts" / "orchestrator.md").read_text(encoding="utf-8")
        self.orch_system_prompt = (template
                                   .replace("{world_base_url}", self.base_url)
                                   .replace("{task_goal}", self.task["goal"].strip())
                                   .replace("{task_context}", self.task_context)
                                   .replace("{fan_out}", str(self.task.get("fan_out", 4))))
        self.plan = GENERIC_PLAN
        self.trace.emit(actor="orchestrator", event_type="plan",
                        payload={"reply": self.plan.model_dump(),
                                 "note": "D32 generic-plan override (planner controlled out)"})
        return self.plan


def _probe_of(reason: str, fault_shape: str) -> str:
    if "status" in reason and "fast path" in reason:
        return "status_fast_path"
    if "gate stopped enforcing" in reason:
        return "gate_shadow"
    if "write-surface drift" in reason:
        return "write_footprint"
    return fault_shape or "content_drift"


def run_generic(label: str, injection) -> dict:
    from trace import read_trace
    print(f"\n=== V2 GENERIC-plan {TASK}+{injection or 'clean'} (label={label}) ===")
    cond = GenericPlanV2Conductor(
        task_path=str(REPO / "tasks" / f"{TASK}.yaml"), injection=injection,
        n_inject=(N_INJECT if injection else None), seed=1, runs_root=RUNS_ROOT,
        max_replans=2)
    summary = cond.run()
    invs = cond.v2_invalidations

    # the armed PASSAGE FAMILY (the member set the contradiction surface grounds to)
    armed_family = sorted({p.target for p in cond.v2_probes
                           if p.target.startswith("/docs/passages/")})
    inj_counter = None
    wt = cond.run_dir / "trace_world.jsonl"
    if wt.exists():
        for e in read_trace(wt):
            if e["event_type"] == "injection_fired":
                inj_counter = e["payload"].get("counter")
                break
    detail = [{"target": i.target, "grade": i.grade.value,
               "probe": _probe_of(i.reason, i.fault_shape),
               "baseline_source": cond.v2_baseline_source.get(i.target),
               "baseline_counter": cond.v2_baseline_counter.get(i.target),
               "reason": i.reason} for i in invs]
    row = {
        "label": label, "task": TASK, "injection": injection or "clean",
        "detected": bool(invs),
        "interrupts": cond.v2_interrupts, "replans": cond.replans_done,
        "coalesced": cond.v2_coalesced,
        "cost_usd": summary["cost_usd"],
        "armed_passage_family": armed_family,
        "pol_returns_armed": INJECTED_PASSAGE in armed_family,
        "arm_capture_counter": cond.v2_arm_capture_counter,
        "injection_counter": inj_counter,
        "arm_probes": cond.v2_arm_probes,
        "pre_completion_probes": cond.v2_pre_completion_probes,
        "probes": sorted({d["probe"] for d in detail}),
        "invalidations": detail, "run_dir": str(cond.run_dir),
    }
    print(f"  detected={row['detected']} interrupts={row['interrupts']} "
          f"replans={row['replans']} cost=${row['cost_usd']}")
    print(f"  armed passage family ({len(armed_family)}): {armed_family}")
    print(f"  pol_returns_armed={row['pol_returns_armed']} "
          f"arm_capture_counter={row['arm_capture_counter']} "
          f"injection_counter={inj_counter}")
    for d in detail:
        print(f"    {d['target']} grade={d['grade']} probe={d['probe']} "
              f"baseline={d['baseline_source']}@{d['baseline_counter']} "
              f"reason={d['reason'][:80]}")
    return row


def main(argv) -> int:
    rows = [run_generic("generic_doc_contradiction", "doc_contradiction"),
            run_generic("generic_clean", None)]
    print("\n================ D32 C2(b) GENERIC-PLAN VARIANT ================")
    total = 0.0
    for r in rows:
        total += r["cost_usd"] or 0.0
        inj = r["injection_counter"]
        pre = [d for d in r["invalidations"]
               if d["baseline_counter"] is not None and inj is not None
               and d["baseline_counter"] < inj]
        rr = (f" right_reason={'YES' if (r['detected'] and pre) else 'NO'}(base<{inj})"
              if r["injection"] != "clean" else "")
        print(f"{r['task']}+{r['injection']:16s} detected={r['detected']!s:5s} "
              f"int={r['interrupts']} replans={r['replans']} "
              f"pol_returns_armed={r['pol_returns_armed']} family={len(r['armed_passage_family'])} "
              f"probe={','.join(r['probes']) or '-'} cost=${r['cost_usd']}{rr}")
    print(f"DEV_RUN_SPEND=${round(total, 6)}")
    out = REPO / "runs" / "v2_d32_generic" / "summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"detail -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
