#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark_1c_railway_b2_status.py  --  FEASIBILITY / NOT FROZEN

Status + cost synthesis for the attempted Railway B2 run.  The live deploy is
BLOCKED in this environment (railway CLI unauthenticated; Docker daemon down --
both need interactive user action), so this records the blockers, the CLI-version
drift finding, and computes the full-matrix B2 cost (the 'Eray number') from
banked 1b worker footprints + last task's Sonnet compile figure.  No infra, no
new spend.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ---- grounded inputs ----
WORKER_USD = 0.0193          # 1b banked median per multi-turn worker (cache-effective); 2079 worker_end events
WORKER_OUT_TOK = 1015        # median output tokens / worker
COMPILE_USD = 0.1376         # 1b Sonnet compile median (cost_autopsy_v3.json), cache breakpoints set
ORCH_USD = 0.12              # est. Sonnet orchestrator/plan per cell (run_one.py make_plan, max_turns 6)
REPLAN_FRAC = 0.6            # ~detected injected V2 cell -> 1 recompile

SEEDS, ARMS, CONDS, NGRID = 30, 3, 2, [8, 16, 32]
# user's console Tier-4 (per instruction); doc-standard differs (noted)
TIER4_CONSOLE = {"rpm": 10000, "itpm": 10_000_000, "otpm": 2_000_000, "note": "4.x classes, per MY console"}
TIER4_DOCS = {"sonnet_itpm": 2_000_000, "haiku_itpm": 4_000_000, "rpm": 4000,
              "note": "platform.claude.com/docs standard Tier-4 (lower than console; per-class)"}


def main():
    worker_calls = SEEDS * ARMS * CONDS * sum(NGRID)        # all arms run N workers/cell
    cells_total = SEEDS * ARMS * CONDS * len(NGRID)
    v2_cells = SEEDS * CONDS * len(NGRID)
    v2_injected = SEEDS * 1 * len(NGRID)

    worker_cost = worker_calls * WORKER_USD
    compile_cost = v2_cells * COMPILE_USD + v2_injected * REPLAN_FRAC * COMPILE_USD
    orch_cost = cells_total * ORCH_USD
    core = worker_cost + compile_cost                       # per user's STEP-6 formula (worker + compile)
    full = core + orch_cost

    # peak-minute sanity (B2 = real CLI worker = multi-turn agent loop ~15 Haiku reqs/worker)
    REQ_PER_WORKER = 15
    n32_cell_haiku_reqs = 32 * REQ_PER_WORKER
    cells_per_min_rpm = TIER4_CONSOLE["rpm"] / n32_cell_haiku_reqs
    # OTPM: ~1015 out tok/worker; how many workers/min under console OTPM
    workers_per_min_otpm = TIER4_CONSOLE["otpm"] / WORKER_OUT_TOK

    report = {
        "FEASIBILITY": True, "FROZEN": False, "live_run": False,
        "blockers": {
            "railway_cli": "installed 4.58.0 but UNAUTHENTICATED (railway whoami -> Unauthorized; OAuth refresh invalid_grant). "
                           "railway login is interactive (browser) -- cannot run headless. UNBLOCK: user runs `railway login` "
                           "OR provides a RAILWAY_TOKEN/RAILWAY_API_TOKEN service token for headless use.",
            "docker_daemon": "docker CLI present but daemon DOWN (Docker Desktop not started; dockerDesktopLinuxEngine pipe missing). "
                             "Cannot build the image. UNBLOCK: user starts Docker Desktop (or build on Railway via Nixpacks/remote build).",
        },
        "cli_version_finding": {
            "phase1b_pinned_SUT": "2.1.170 (prereg.md)",
            "last_task_capture_and_current": "2.1.193",
            "both_installable_from_npm": True,
            "problem": "Phase-1b ran on 2.1.170; last task proved B2 equivalence on 2.1.193, NOT on 2.1.170. "
                       "23-patch drift (2.1.170->2.1.193) can silently change the request shape (the exact risk the brief names). "
                       "Equivalence-to-the-real-1b-SUT is therefore NOT established.",
            "resolution": "Pin the image to 2.1.170 to match the 1b SUT AND re-run the in-container proxy capture against pathA_capture "
                          "(which is 2.1.193) to MEASURE the 2.1.170-vs-2.1.193 request diff; if they differ, 1c-on-2.1.193 is a documented "
                          "deviation, not a silent one. Do NOT assume 2.1.193 == 1b.",
        },
        "cost_eray_number": {
            "inputs": {"worker_usd_per_call_1b_median": WORKER_USD, "compile_usd": COMPILE_USD,
                       "orchestrator_usd_per_cell_est": ORCH_USD, "replan_frac": REPLAN_FRAC},
            "matrix": "30 seeds x 3 arms x 2 conds x N in {8,16,32}",
            "worker_calls": worker_calls, "worker_cost_usd": round(worker_cost, 0),
            "compile_cost_usd": round(compile_cost, 0), "orchestrator_cost_usd": round(orch_cost, 0),
            "CORE_worker_plus_compile_usd": round(core, 0),
            "FULL_incl_orchestrator_usd": round(full, 0),
            "vs_thin_api_estimate": "thin-API D38 was ~$37 (worker $5 + compile $32); B2 is ~6-8x higher because the "
                                    "request-equivalent path runs the REAL multi-turn tool worker ($0.0193 vs $0.0005/worker)",
        },
        "tier4_peak_minute": {
            "limits_used": TIER4_CONSOLE, "docs_standard_for_comparison": TIER4_DOCS,
            "b2_reqs_per_worker_est": REQ_PER_WORKER,
            "n32_cell_haiku_requests": n32_cell_haiku_reqs,
            "rpm_headroom_cells_per_min": round(cells_per_min_rpm, 1),
            "otpm_headroom_workers_per_min": round(workers_per_min_otpm, 0),
            "verdict": "COMFORTABLE on the console numbers at sane pacing (cache reads free vs ITPM; Sonnet & Haiku separate pools). "
                       "On the lower DOC-standard Tier-4 (4k RPM / Sonnet 2M ITPM) it is TIGHTER -- verify which your console actually "
                       "enforces. RPM is per-class & ORG-WIDE: nothing else heavy should share the key during the matrix.",
        },
        "prepared_artifacts": {
            "Dockerfile": "deploy/railway/Dockerfile (PREPARED, UNTESTED -- daemon down)",
            "railway_toml": "deploy/railway/railway.toml (restartPolicyType=NEVER)",
            "entrypoint": "deploy/railway/entrypoint.sh (persistence-proof HARD GATE + probe hook)",
            "equiv_recheck": "analysis/_capture_proxy.py + _capture_pathA.py (reused in-container for STEP 4)",
        },
        "not_run_pending_unblock": ["STEP2 persistence proof", "STEP4 in-container equivalence",
                                    "STEP5 concurrency probe (real multi-turn worker)", "STEP7 pull", "STEP8 teardown"],
    }
    out = ROOT / "runs/matrix_1c/railway_b2_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    with open(ROOT / "decisions/dev_run_ledger.md", "a", encoding="utf-8") as f:
        f.write("\n---\n")
        f.write("## Phase-1c RAILWAY B2 run -- ATTEMPTED, BLOCKED (FEASIBILITY / NOT FROZEN, not confirmatory)\n")
        f.write("- date: 2026-06-25  ·  NO live deploy: railway CLI UNAUTHENTICATED (needs `railway login`) + Docker daemon DOWN (Docker Desktop not started)\n")
        f.write("- CLI DRIFT FINDING: Phase-1b SUT = 2.1.170; last-task equivalence + current = 2.1.193 (both on npm). "
                "Equivalence to the real 1b SUT (2.1.170) NOT established -- pin 2.1.170 + re-capture before claiming 1c<->1b comparability.\n")
        f.write(f"- COST (Eray number, B2 real multi-turn worker @ ${WORKER_USD}/worker from 1b banked + compile ${COMPILE_USD}): "
                f"core(worker+compile) ~${round(core,0):.0f}, full(+orchestrator) ~${round(full,0):.0f} "
                f"for 30s x 3 arms x 2 cond x N{{8,16,32}} ({worker_calls} workers). ~6-8x the thin-API ~$37.\n")
        f.write("- Tier-4 peak-minute: COMFORTABLE on console limits (10k/10M/2M) at sane pacing; TIGHTER on doc-standard (4k/2M Sonnet).\n")
        f.write("- prepared (UNTESTED): deploy/railway/{Dockerfile,railway.toml,entrypoint.sh}; equiv recheck reuses _capture_proxy/_capture_pathA\n")
        f.write("- spend this step: $0 (no calls; cost computed from banked data). artifact: runs/matrix_1c/railway_b2_status.json\n")

    P = print
    P("="*92); P("RAILWAY B2 RUN -- STATUS  (FEASIBILITY / NOT FROZEN)"); P("="*92)
    P("LIVE DEPLOY: BLOCKED  (railway unauthenticated + Docker daemon down -- both need interactive user action)")
    P(f"\nCOST (Eray number), B2 real multi-turn worker:")
    P(f"  worker ${WORKER_USD}/call x {worker_calls} = ${worker_cost:,.0f}")
    P(f"  Sonnet compile (+replan) = ${compile_cost:,.0f}")
    P(f"  CORE (worker+compile, per your formula) = ${core:,.0f}")
    P(f"  + orchestrator/plan (~${ORCH_USD}/cell x {cells_total}) = ${orch_cost:,.0f}  ->  FULL ~${full:,.0f}")
    P(f"  (vs thin-API D38 ~$37 -- B2 is the request-equivalent path, ~6-8x)")
    P(f"\nTier-4 peak-minute (console 10k/10M/2M): RPM allows ~{cells_per_min_rpm:.0f} N=32-cells/min, "
      f"OTPM allows ~{workers_per_min_otpm:.0f} workers/min -> COMFORTABLE at sane pacing")
    P(f"\nCLI DRIFT: 1b=2.1.170 vs current/last-task=2.1.193 -- equivalence to real 1b SUT NOT proven (pin 2.1.170 + re-capture)")
    P(f"\n[written] {out}")


if __name__ == "__main__":
    main()
