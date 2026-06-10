"""Heartbeat k calibration (protocol Section 5.1): k is set per task so the
heartbeat's expected overhead equals the sentinel's MEASURED compile+judge
overhead from the S5 seed-1 run.

    python -m conductor.calibrate_k --s5-run runs/a1-S5-endpoint_404-s1

The record explicitly notes when the measured overhead included a replan
(two compiles): in that case heartbeat's budget is conservative in the
baseline's favor (M4 condition 2).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Optional

from trace import read_run

ORCH_TURN_EVENTS = ("plan", "replan", "aggregate")


def calibrate(s5_run_dir: str, reval_cost: Optional[float] = None) -> dict:
    events = read_run(s5_run_dir)

    def cost(event: dict) -> float:
        return (event.get("usage") or {}).get("cost_usd") or 0.0

    compiles = [e for e in events if e["event_type"] == "compile"]
    judges = [e for e in events if e["event_type"] == "judge_verdict"]
    compile_cost = sum(cost(e) for e in compiles)
    judge_cost = sum(cost(e) for e in judges)
    sentinel_overhead = compile_cost + judge_cost

    if reval_cost is None:
        orch_costs = [cost(e) for e in events
                      if e["event_type"] in ORCH_TURN_EVENTS and cost(e) > 0]
        reval_cost = (sum(orch_costs) / len(orch_costs)) if orch_costs else 0.05

    worker_calls = sum(1 for e in events if e["event_type"] == "tool_call")
    n_revals = max(1, round(sentinel_overhead / reval_cost))
    k = max(1, math.ceil(worker_calls / n_revals))

    record = {
        "source_run": s5_run_dir,
        "compile_cost_usd": round(compile_cost, 6),
        "compile_calls": len(compiles),
        "judge_cost_usd": round(judge_cost, 6),
        "judge_calls": len(judges),
        "sentinel_overhead_usd": round(sentinel_overhead, 6),
        "revalidation_turn_cost_usd": round(reval_cost, 6),
        "worker_tool_calls": worker_calls,
        "target_revalidations": n_revals,
        "k": k,
    }
    if len(compiles) > 1:
        record["note"] = (
            "seed-1 sentinel overhead INCLUDED a replan (multiple compiles); "
            "heartbeat's matched budget is therefore conservative in the "
            "baseline's favor (M4 condition 2)")
    return record


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="heartbeat k calibration")
    parser.add_argument("--s5-run", required=True)
    parser.add_argument("--reval-cost", type=float, default=None,
                        help="override measured per-revalidation cost (USD)")
    args = parser.parse_args(argv)
    print(json.dumps(calibrate(args.s5_run, args.reval_cost), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
