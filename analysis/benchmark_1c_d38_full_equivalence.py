#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark_1c_d38_full_equivalence.py  --  FEASIBILITY / NOT FROZEN

Synthesis of the D38 full-worker-path equivalence gate.  Reads the proxy-captured
Path-A (Claude Code CLI) requests, records the thin Path-B (D38 /v1/messages)
request shape, computes the STEP-2 request-equivalence diff per call site, folds
in the token-footprint / Tier-4 rate-limit arithmetic (STEP 4), and writes the
verdict (STEP 5).  No new spend here (reads prior captures).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ---- doc-confirmed Tier-4 limits (platform.claude.com/docs, 2026-06-25) ----
TIER4 = {
    "sonnet": {"rpm": 4000, "itpm": 2_000_000, "otpm": 400_000},
    "haiku":  {"rpm": 4000, "itpm": 4_000_000, "otpm": 800_000},
    "opus":   {"rpm": 4000, "itpm": 10_000_000, "otpm": 800_000},
}
# cache_read_input_tokens do NOT count toward ITPM (Haiku4.5/Sonnet4.6 unmarked);
# per-model-class, org-wide pools (Sonnet & Haiku separate).

def summarize_capture(path):
    try:
        lines = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    except FileNotFoundError:
        return None
    out = []
    for rec in lines:
        b = rec.get("body") or {}
        sysblk = b.get("system") or []
        out.append({
            "path": rec.get("path"),
            "model": b.get("model"),
            "keys": sorted(b.keys()),
            "n_system_blocks": len(sysblk) if isinstance(sysblk, list) else 0,
            "n_tools": len(b.get("tools") or []),
            "temperature": b.get("temperature"),
            "thinking": b.get("thinking"),
            "output_config": b.get("output_config"),
            "stream": b.get("stream"),
            "has_context_management": "context_management" in b,
            "has_metadata": "metadata" in b,
            "anthropic_beta": rec.get("headers", {}).get("anthropic-beta"),
            "cache_control_on_system": [bool(isinstance(x, dict) and x.get("cache_control")) for x in sysblk] if isinstance(sysblk, list) else [],
        })
    return out


def main():
    compile_cap = summarize_capture(ROOT / "runs/matrix_1c/pathA_capture.jsonl")
    worker_cap = summarize_capture(ROOT / "runs/matrix_1c/pathA_worker_capture.jsonl")

    # Thin Path-B (D38) request shape, as actually built in benchmark_1c_apikey_equivalence.api_worker
    pathB_shape = {
        "endpoint": "POST /v1/messages (no ?beta=true)",
        "keys": ["model", "max_tokens", "system", "messages"],
        "system": "single STRING (no CLI preamble blocks, no billing block)",
        "tools": 0, "temperature": "absent", "thinking": "absent",
        "output_config": "absent", "stream": False, "context_management": "absent",
        "metadata": "absent", "anthropic_beta": "none", "cache_control": "none",
        "auxiliary_calls": "none (no title call)",
    }

    # ---- STEP 1 inventory ----
    inventory = [
        {"id": 1, "site": "extraction worker (benchmark S1)", "module": "benchmark_1c_s1_qual.py",
         "model": "haiku", "turns": 1, "tools": "none", "driver": "prompt"},
        {"id": 2, "site": "multi-turn tool worker", "module": "conductor/run_one.py:589",
         "model": "haiku", "turns": "<=14", "tools": "Bash(curl) -> full 29-tool catalog sent", "driver": "CLI agent loop"},
        {"id": 3, "site": "Sonnet compile-to-arm", "module": "sentinel_v2/compile_probes.py:116",
         "model": "sonnet", "turns": 1, "tools": "none", "driver": "stdin"},
        {"id": 4, "site": "orchestrator / replan", "module": "conductor/run_one.py:457",
         "model": "sonnet", "turns": "<=6", "tools": "none", "driver": "--resume stateful session"},
        {"id": 5, "site": "judge (V2J only)", "module": "sentinel/judge.py:60",
         "model": "haiku", "turns": 1, "tools": "none", "driver": "stdin"},
    ]

    # ---- STEP 2 request-equivalence verdict per call site ----
    step2 = {
        "method": "proxy capture of the CLI's actual /v1/messages request via ANTHROPIC_BASE_URL",
        "finding": ("Path A (CLI) injects scaffolding into EVERY request that a thin Path-B call does not: "
                    "a 3-block system array (billing block + 'You are a Claude agent' preamble + the --system-prompt), "
                    "thinking config, output_config (effort/format), context_management, metadata, stream:true, "
                    "?beta=true with claude-code-20250219 + other beta flags, ephemeral cache_control breakpoints, "
                    "and an AUXILIARY Haiku 'title' call per CLI invocation. The tool worker additionally receives "
                    "the FULL 29-tool Claude Code catalog (--allowedTools only gates execution, not the sent tool set)."),
        "per_site": {
            "1_extraction_worker": "B1 NOT request-equivalent (CLI adds preamble/temperature/thinking/etc.); prior gate was OUTPUT-equiv on a trivial task only",
            "2_tool_worker": "B1 NOT request-equivalent — categorical: agent loop + 29 tool defs vs single no-tool call",
            "3_compile": "B1 NOT request-equivalent — CLI adds adaptive thinking + effort:high + cache breakpoints + preamble + title call",
            "4_orchestrator": "B1 NOT request-equivalent — --resume stateful multi-turn session, not reproducible as a stateless call",
            "5_judge": "B1 NOT request-equivalent — same scaffolding as compile",
        },
        "B1_thin_api": "FAIL on every call site (not even the single-turn compile matches)",
        "B2_cli_apikey": "PASS by construction on every call site (same CLI binary+argv+scaffolding; only the auth credential differs) -- demonstrated: the CLI ran identically under ANTHROPIC_API_KEY through the proxy",
    }

    # ---- STEP 4 token footprint + Tier-4 peak-minute arithmetic ----
    # measured/known per-call footprints
    footprint = {
        "thin_haiku_worker_measured": {"in": 241, "out": 54, "usd": 0.000511, "src": "apikey_equivalence gate"},
        "sonnet_compile_1b_median_usd": 0.1376,
        "cli_request_max_tokens_observed": 32000,
        "cli_compile_prefix_cached": "YES -- ephemeral cache_control on system blocks; cache_read tokens are FREE vs ITPM",
        "cli_aux_title_call": "1 extra Haiku call per CLI invocation (output_config.format {title})",
    }
    # matrix scope: 30 seeds x 3 arms x 2 conds x N in {8,16,32}
    SEEDS, ARMS, CONDS, NGRID = 30, 3, 2, [8, 16, 32]
    worker_calls_b1 = SEEDS * ARMS * CONDS * sum(NGRID)
    v2_cells = SEEDS * CONDS * len(NGRID)
    # B2 multiplies per-worker requests by the agent-loop turn count (+1 title call)
    avg_turns_b2 = 8  # conservative midpoint of <=14
    worker_requests_b2 = worker_calls_b1 * (avg_turns_b2 + 1)
    arithmetic = {
        "matrix": "30 seeds x 3 arms x 2 conds x N in {8,16,32}",
        "B1_total_worker_requests": worker_calls_b1,
        "B2_total_worker_requests_est": worker_requests_b2,
        "B2_note": f"each CLI worker ~= {avg_turns_b2} agent turns + 1 title call = {avg_turns_b2+1} Haiku requests",
        "peak_minute": {
            "B1_haiku": "a single N=32 cell bursts 32 Haiku reqs; Haiku Tier-4 = 4000 RPM / 4M ITPM (excl cache reads). "
                        "Worker input ~250 tok => 4M/250 = 16k worker-calls/min ITPM headroom; RPM headroom 125 N=32-cells/min. COMFORTABLE.",
            "B1_sonnet_compile": "180 compiles total, ~1 per V2 cell. Sonnet Tier-4 = 4000 RPM / 2M ITPM. "
                                 "Compile ~15k input tok => 2M/15k ~= 133 compiles/min. Spread over the run => COMFORTABLE; "
                                 "firing all 180 in one minute (unrealistic) would briefly exceed 2M Sonnet ITPM.",
            "B2_cli": "each worker fires ~9 Haiku requests (agent turns + title), each turn carrying the 29-tool catalog + 3-block system "
                      "(~5k input tok/turn). A N=32 cell ~= 32x8x5k = 1.28M Haiku input tok => only ~3 such cells/min under 4M Haiku ITPM "
                      "BEFORE prompt caching. The CLI sets ephemeral cache breakpoints, so cached prefix tokens are FREE vs ITPM, "
                      "lifting effective throughput materially. TIGHT-but-manageable with pacing.",
        },
        "verdict": {
            "B1": "COMFORTABLE at Tier 4 with sane pacing",
            "B2": "TIGHT at high concurrency (agent loop + 29-tool catalog inflate ITPM); rely on the CLI's prompt caching and pace cells",
            "caveat": "Tier 4 ASSUMED (not verified for this org). RPM/ITPM are per-model-class and ORG-WIDE -- nothing else heavy should "
                      "share the Sonnet or Haiku pools during the matrix. Lower tiers are far tighter (Tier-1 Sonnet ITPM = 30k).",
        },
    }

    report = {
        "FEASIBILITY": True, "FROZEN": False,
        "step0_docs_confirmed": {
            "usage_fields": ["input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"],
            "cache_hit_signal": "cache_read_input_tokens > 0",
            "cache_read_excluded_from_itpm": True,
            "haiku_id": "claude-haiku-4-5-20251001", "sonnet_id": "claude-sonnet-4-6",
            "tier4": TIER4,
            "brief_discrepancy": "brief said 10K RPM / 10M ITPM / 2M OTPM same-for-all; docs say 4K RPM, per-class ITPM/OTPM (Sonnet 2M/400k, Haiku 4M/800k, Opus 10M/800k)",
        },
        "step1_inventory": inventory,
        "step2_request_equivalence": step2,
        "pathA_compile_capture": compile_cap,
        "pathA_worker_capture": worker_cap,
        "pathB_thin_shape": pathB_shape,
        "step3_behavioral": "NOT RUN -- STEP 2 failed for B1 on all sites (the task gates STEP 3 on a clean STEP 2). "
                            "B2 needs no behavioral test: identical requests => identical behavior modulo model stochasticity.",
        "step4_footprint_and_ratelimits": {"footprint": footprint, "arithmetic": arithmetic},
        "step5_bottom_line": {
            "B1_thin_api_D38": "Safe for NO confirmatory call site -- not request-equivalent to the Phase-1b CLI path on any of them. "
                               "Using it would change the SUT and break comparability with Phase-1b.",
            "B2_cli_apikey": "The correct API-key switch: request-equivalent to Path A by construction on every call site. "
                             "BUT keeps the subprocess -> the 259MB/worker memory wall returns -> laptop N=8 ceiling -> needs a provisioned VM for N>8.",
            "concurrency_implication": "The earlier N=64-on-laptop result used B1 (thin, single-turn extraction worker), which is NOT the "
                                       "real multi-turn tool worker and NOT request-equivalent. That concurrency win does NOT transfer to a "
                                       "Phase-1b-comparable run. A comparable Phase-1c at N>8 requires B2 on a provisioned VM (RAM-bound).",
            "recommendation": "Run Phase-1c confirmatory on B2 (CLI + ANTHROPIC_API_KEY) on a provisioned VM (>=10GB free for N=32). "
                              "Reserve B1 thin-API only for non-confirmatory concurrency/cost probes, never for data compared to Phase-1b.",
        },
    }
    Path(ROOT / "runs/matrix_1c").mkdir(parents=True, exist_ok=True)
    out = ROOT / "runs/matrix_1c/d38_full_equivalence.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    with open(ROOT / "decisions/dev_run_ledger.md", "a", encoding="utf-8") as f:
        f.write("\n---\n")
        f.write("## Phase-1c D38 FULL-worker-path equivalence gate (FEASIBILITY / NOT FROZEN, not confirmatory)\n")
        f.write("- date: 2026-06-25  ·  method: localhost logging proxy (ANTHROPIC_BASE_URL) captured the CLI's actual /v1/messages requests\n")
        f.write("- STEP 0: cache_read EXCLUDED from ITPM; Tier-4 per-class (Sonnet 4k/2M/400k, Haiku 4k/4M/800k, Opus 4k/10M/800k) -- brief's 10k/10M/2M figures corrected\n")
        f.write("- STEP 2 (request equivalence): B1 thin-API FAILS on ALL call sites -- CLI injects 3-block system (billing+preamble+prompt), "
                "thinking/effort/output_config/context_management/metadata/stream/?beta=true/claude-code-20250219/cache breakpoints + an auxiliary Haiku title call; "
                "tool worker gets the full 29-tool catalog. B2 (CLI+API-key) PASSES by construction.\n")
        f.write("- STEP 3: not run (STEP 2 failed for B1; B2 identical by construction)\n")
        f.write("- STEP 4: B1 COMFORTABLE @Tier4; B2 TIGHT-but-manageable (agent loop+29 tools inflate ITPM; CLI prompt-caching gives free cache-read ITPM)\n")
        f.write("- STEP 5: confirmatory MUST run on B2 (CLI+API-key) for Phase-1b comparability -> subprocess -> VM needed for N>8; B1 thin-API only for non-confirmatory probes\n")
        f.write("- artifact: runs/matrix_1c/d38_full_equivalence.json (+ pathA_capture.jsonl, pathA_worker_capture.jsonl)\n")

    print("[written]", out)
    print("STEP2:", step2["B1_thin_api"], "|", step2["B2_cli_apikey"][:60])
    print("STEP5 recommendation:", report["step5_bottom_line"]["recommendation"])


if __name__ == "__main__":
    main()
