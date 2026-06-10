"""Phase 0 (protocol Section 6.4): run the sentinel compiler on the designated
task plans, emit the tripwires plus a hand-scoring sheet.

Outputs into --outdir:
  phase0_scoring.csv  one row per compiled tripwire; the four rubric columns
                      (observable, parameterized, actionable, calibrated) are
                      BLANK for hand-scoring, per the pre-registered design
  phase0_plans.csv    per-plan stats: tripwire count, compile tokens, cost,
                      latency, attempts, fence rate (descriptive
                      format-compliance statistic per deviations.md D2), and a
                      blank assumptions-covered column for hand-mapping against
                      the task's ground-truth assumption list
  tripwires_<task>.json + trace.jsonl per task
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Optional

import yaml

from conductor.sessions import get_cli_version
from sentinel.compile import compile_tripwires, plan_text_from_task
from trace import TraceWriter

PHASE0_TASKS = ("a1", "b1", "c1", "d1")

SCORING_COLUMNS = [
    "task_id", "tripwire_id", "severity", "scope", "subplan_id",
    "assumption_id", "assumption", "category_weights", "signal", "action",
    "hint", "evidence_fields",
    # rubric, blank for hand-scoring (protocol 6.4: 0/1 per property)
    "observable", "parameterized", "actionable", "calibrated", "notes",
]

PLAN_COLUMNS = [
    "task_id", "tripwire_count", "attempts", "fences_stripped_rate",
    "input_tokens", "output_tokens", "cost_usd", "latency_s",
    "assumptions_in_spec", "distinct_assumption_ids_compiled",
    "assumptions_covered_hand_scored",
]


def run_phase0(task_ids: list[str], tasks_dir: Path, outdir: Path,
               enrich: bool = False) -> bool:
    outdir.mkdir(parents=True, exist_ok=True)
    cli_version = get_cli_version()
    scoring_rows: list[dict] = []
    plan_rows: list[dict] = []
    all_ok = True

    for task_id in task_ids:
        task = yaml.safe_load((tasks_dir / f"{task_id}.yaml").read_text(encoding="utf-8"))
        plan = plan_text_from_task(task)
        if enrich:
            # D6: mechanical, blind, identical rule for all plans; the plan
            # text and the lean yaml stay byte-identical
            from world.surface import enriched_context
            task_context = enriched_context(task)
        else:
            task_context = task["task_context"].strip()
        trace = TraceWriter(outdir / f"trace_{task_id}.jsonl",
                            run_id=f"phase0-{task_id}", seed=0,
                            system="phase0", task_id=task_id)
        trace.emit(actor="conductor", event_type="run_start",
                   payload={"mode": "phase0", "cli_version": cli_version,
                            "context": "rich" if enrich else "lean"})
        started = time.monotonic()
        tripwire_set, results = compile_tripwires(plan, task_context, trace)
        latency = time.monotonic() - started
        cost = sum(r.cost_usd for r in results)
        usage_in = sum((r.usage or {}).get("input_tokens", 0)
                       + (r.usage or {}).get("cache_creation_input_tokens", 0)
                       + (r.usage or {}).get("cache_read_input_tokens", 0)
                       for r in results)
        usage_out = sum((r.usage or {}).get("output_tokens", 0) for r in results)
        fence_count = 0

        if tripwire_set is None:
            all_ok = False
            print(f"{task_id}: COMPILE FAILED after {len(results)} attempts",
                  file=sys.stderr)
            trace.emit(actor="conductor", event_type="run_end",
                       payload={"success": False, "attempts": len(results)})
            trace.close()
            tripwire_count = 0
        else:
            set_json = tripwire_set.model_dump_json(indent=2)
            (outdir / f"tripwires_{task_id}.json").write_text(set_json,
                                                              encoding="utf-8")
            trace.emit(actor="sentinel", event_type="tripwire_set",
                       payload={"plan_id": tripwire_set.plan_id,
                                "count": len(tripwire_set.tripwires)})
            trace.emit(actor="conductor", event_type="run_end",
                       payload={"success": True, "attempts": len(results),
                                "cost_usd": round(cost, 6),
                                "latency_s": round(latency, 1)})
            trace.close()
            tripwire_count = len(tripwire_set.tripwires)
            for tw in tripwire_set.tripwires:
                signal = {k: v for k, v in tw.signal.model_dump().items()
                          if v is not None}
                scoring_rows.append({
                    "task_id": task_id,
                    "tripwire_id": tw.id,
                    "severity": tw.severity.value,
                    "scope": tw.scope.value,
                    "subplan_id": tw.subplan_id or "",
                    "assumption_id": tw.assumption_id,
                    "assumption": tw.assumption,
                    "category_weights": json.dumps(
                        {k.value: v for k, v in tw.category_weights.items()}),
                    "signal": json.dumps(signal),
                    "action": tw.action.on_trigger,
                    "hint": tw.action.hint,
                    "evidence_fields": json.dumps(tw.evidence_fields),
                    "observable": "", "parameterized": "", "actionable": "",
                    "calibrated": "", "notes": "",
                })

        # fence rate from the trace we just wrote (per-attempt flags)
        from trace import read_trace
        events = read_trace(outdir / f"trace_{task_id}.jsonl")
        compile_events = [e for e in events if e["event_type"] == "compile"]
        fence_count = sum(1 for e in compile_events
                          if e["payload"].get("fences_stripped"))
        distinct_ids = ({tw.assumption_id for tw in tripwire_set.tripwires}
                        if tripwire_set else set())
        plan_rows.append({
            "task_id": task_id,
            "tripwire_count": tripwire_count,
            "attempts": len(results),
            "fences_stripped_rate": f"{fence_count}/{len(compile_events)}",
            "input_tokens": usage_in,
            "output_tokens": usage_out,
            "cost_usd": round(cost, 6),
            "latency_s": round(latency, 1),
            "assumptions_in_spec": len(task.get("assumptions", [])),
            "distinct_assumption_ids_compiled": len(distinct_ids),
            "assumptions_covered_hand_scored": "",
        })
        print(f"{task_id}: {tripwire_count} tripwires, {len(results)} attempt(s), "
              f"${cost:.4f}, {latency:.1f}s, fences {fence_count}/{len(compile_events)}")

    with open(outdir / "phase0_scoring.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SCORING_COLUMNS)
        writer.writeheader()
        writer.writerows(scoring_rows)
    with open(outdir / "phase0_plans.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=PLAN_COLUMNS)
        writer.writeheader()
        writer.writerows(plan_rows)
    print(f"scoring sheet: {outdir / 'phase0_scoring.csv'} "
          f"({len(scoring_rows)} tripwires)")
    return all_ok


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 0 compile + scoring sheet")
    parser.add_argument("--tasks", nargs="*", default=list(PHASE0_TASKS))
    parser.add_argument("--tasks-dir", default="tasks")
    parser.add_argument("--outdir", default="runs/phase0")
    parser.add_argument("--enrich", action="store_true",
                        help="D6 production-fidelity context (mechanical, blind)")
    args = parser.parse_args(argv)
    ok = run_phase0(args.tasks, Path(args.tasks_dir), Path(args.outdir),
                    enrich=args.enrich)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
