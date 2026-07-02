"""A7b runner (family close): arm (a) noiseless control, then arm (b) monitored-surface
transient-500. Foreground-chunked, resumable, HARD $8 cap on modeled total_cost_usd.

Arm (a) — V2, noise OFF, a1/b1/c1 at the A7 V2 seeds (a1 4/5/6, b1 7/8/9, c1 10/11/12):
  do A7's task-intrinsic interrupts reproduce without noise on CLI 2.1.198?
Arm (b) — V2, a1 at seeds 16-19, transient_500 placed on the frozen-rule target surface
  (/pricing/quote/* = the most-frequently-armed load-bearing surface in the A7 a1 armed-probe
  evidence): does V2's status fast path interrupt on a transient-500-that-heals on a monitored
  surface? Arm (a) runs first (cheaper, more load-bearing). v2_interrupts banked per cell.
"""
import argparse, json, os, time
from pathlib import Path

from analysis.a7_runner import load_ledger, append_ledger, read_noise_landing, PER_RUN_RESERVE_USD

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAP_USD = 8.0
DEFAULT_TIME_BUDGET_S = 300.0
TARGET_SURFACE = "/pricing/quote/*"   # A7b arm-(b) frozen selection rule (A7 armed-probe evidence)

ARM_A = [("a1", s) for s in (4, 5, 6)] + [("b1", s) for s in (7, 8, 9)] + [("c1", s) for s in (10, 11, 12)]
ARM_B = [("a1", s) for s in (16, 17, 18, 19)]


def job_list():
    return [("a", t, s) for t, s in ARM_A] + [("b", t, s) for t, s in ARM_B]


def key(job):
    return f"{job[0]}:{job[1]}:s{job[2]}"


def execute(job, runs_root):
    from conductor.run_v2_loop import run_v2_loop
    from world.state import NoiseProfile
    arm, task, seed = job
    np_ = (None if arm == "a"
           else NoiseProfile(noise_class="transient_500",
                             params={"target_surface": TARGET_SURFACE}))
    s = run_v2_loop(task_path=str(Path(REPO) / "tasks" / f"{task}.yaml"),
                    injection=None, seed=seed, runs_root=runs_root, noise_profile=np_)
    land = read_noise_landing(Path(s["run_dir"])) if arm == "b" else None
    return {"arm": arm, "task": task, "seed": seed,
            "success": bool(s.get("success")), "cost_usd": float(s.get("cost_usd", 0.0)),
            "run_dir": s.get("run_dir"), "v2_interrupts": s.get("v2_interrupts"),
            "v2_invalidations": s.get("v2_invalidations"), "reason": s.get("reason"),
            "noise_landed_on": land}


def run(ledger_path, runs_root, cap=CAP_USD, time_budget=DEFAULT_TIME_BUDGET_S,
        clock=time.monotonic):
    ledger = load_ledger(ledger_path)
    done = {e["key"] for e in ledger}
    cost = sum(float(e.get("cost_usd", 0.0)) for e in ledger)
    start, ran, reason = clock(), 0, "complete"
    for job in job_list():
        k = key(job)
        if k in done:
            continue
        if cost + PER_RUN_RESERVE_USD > cap:
            reason = "cap"; break
        if ran > 0 and clock() - start >= time_budget:
            reason = "chunk_time"; break
        r = execute(job, runs_root)
        append_ledger(ledger_path, {"key": k, **r})
        done.add(k); cost += r["cost_usd"]; ran += 1
    jl = job_list()
    return {"reason": reason, "cost_usd": round(cost, 6), "cap": cap,
            "ran_this_chunk": ran, "completed": len(done & {key(j) for j in jl}),
            "total": len(jl), "complete": all(key(j) in done for j in jl)}


def main(argv=None):
    p = argparse.ArgumentParser(description="A7b runner")
    p.add_argument("--runs-root", default="runs/a7b")
    p.add_argument("--ledger", default="runs/a7b/a7b_results.jsonl")
    p.add_argument("--cap", type=float, default=CAP_USD)
    p.add_argument("--time-budget", type=float, default=DEFAULT_TIME_BUDGET_S)
    a = p.parse_args(argv)
    print(json.dumps(run(Path(a.ledger), a.runs_root, a.cap, a.time_budget), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
