#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark_1c_apikey_equivalence.py  --  FEASIBILITY / NOT FROZEN

STEP 2 (auth switch) + STEP 3 (equivalence gate) + STEP 5 (cost) for the Phase-1c
concurrency re-probe.  The VM ramp (STEP 1/4) is BLOCKED in this environment (no
cloud credential / no provisioning CLI), so this does everything that does NOT
need the VM:

  STEP 2  build an ANTHROPIC_API_KEY worker path (direct Messages API, stdlib
          urllib) -- the harness change is named D38 (D21-adjacent: D21 governs the
          sub-CLI invocation; D38 adds an API-key direct-HTTP worker invocation).
  STEP 3  EQUIVALENCE GATE: one extraction-worker call via the NEW api-key path and
          one via the EXISTING sub-CLI path, on the SAME fixed shard. Confirm
          success + same model string + structurally equivalent output (same parse,
          same extracted values). HARD STOP semantics: prints PASS/FAIL.
  STEP 5  measured API cost/call (token usage x published rates) + full-matrix
          extrapolation for the funder note.

Auth/version/base-URL/model-IDs taken from platform.claude.com/docs (read 2026-06-25):
  base https://api.anthropic.com ; POST /v1/messages ; header x-api-key ;
  anthropic-version 2023-06-01 ; content-type application/json ;
  Haiku id claude-haiku-4-5-20251001 ($1/$5 MTok) ; Sonnet id claude-sonnet-4-6 ($3/$15 MTok).

FEASIBILITY, burned, no confirmatory artifact touched.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from analysis import benchmark_1c_world as W                 # noqa: E402
from analysis.benchmark_1c_s1_qual import WORKER_SYS, _parse_worker_json  # noqa: E402
from conductor import sessions                               # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

API_BASE = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"
# published list prices (USD per MTok) -- src: platform.claude.com/docs models overview, 2026-06-25
PRICES = {HAIKU: {"in": 1.00, "out": 5.00}, SONNET: {"in": 3.00, "out": 15.00}}
ENV_CANDIDATES = [ROOT / ".env", ROOT.parent / ".env"]   # tripwire-pilot/.env or aSizableLeapForward/.env
OUT_JSON = "runs/matrix_1c/apikey_equivalence.json"
LEDGER = "decisions/dev_run_ledger.md"
TEST_SEED = 7701      # burned feasibility seed


def load_api_key():
    import os
    k = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if k:
        return k, "env"
    for env_path in ENV_CANDIDATES:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY="):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if v:
                        return v, str(env_path)
    return None, None


def _mask(k):
    if not k:
        return "<none>"
    return f"{k[:7]}...{k[-4:]} (len={len(k)})"


def api_worker(api_key, model, system, user, max_tokens=64):
    """STEP 2: one worker call via the ANTHROPIC_API_KEY direct Messages-API path."""
    body = json.dumps({
        "model": model, "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }).encode("utf-8")
    req = urllib.request.Request(
        API_BASE, data=body, method="POST",
        headers={"x-api-key": api_key, "anthropic-version": ANTHROPIC_VERSION,
                 "content-type": "application/json"})
    t0 = time.monotonic()
    rate_limited = False
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            payload = json.loads(r.read().decode("utf-8"))
        status = 200
    except urllib.error.HTTPError as e:
        status = e.code
        rate_limited = (e.code == 429)
        payload = {"error": e.read().decode("utf-8", "replace")[:300]}
    except Exception as e:
        status = -1
        payload = {"error": str(e)[:300]}
    t1 = time.monotonic()
    text = None
    usage = {}
    resolved_model = None
    if status == 200:
        parts = [c.get("text", "") for c in payload.get("content", []) if c.get("type") == "text"]
        text = "".join(parts)
        usage = payload.get("usage", {}) or {}
        resolved_model = payload.get("model")
    cost = None
    if usage:
        pr = PRICES.get(model, {"in": 1.0, "out": 5.0})
        cost = round((usage.get("input_tokens", 0) * pr["in"]
                      + usage.get("output_tokens", 0) * pr["out"]) / 1e6, 6)
    return {"status": status, "rate_limited": rate_limited, "dur_s": round(t1 - t0, 2),
            "text": text, "resolved_model": resolved_model, "usage": usage, "cost_usd": cost,
            "error": payload.get("error")}


def subcli_worker(model, system, user):
    """The EXISTING sub-CLI path (D21), for the equivalence comparison."""
    t0 = time.monotonic()
    res = sessions.run_claude(model=model, system_prompt=system, max_turns=1,
                              prompt=user, no_tools=True, timeout_s=90)
    t1 = time.monotonic()
    return {"status": (0 if res.exit_code == 0 else res.exit_code),
            "dur_s": round(t1 - t0, 2), "text": res.result_text,
            "model_arg": res.model, "usage": res.usage or {}, "cost_usd": res.cost_usd,
            "is_error": res.is_error, "timed_out": res.timed_out}


def main():
    api_key, src = load_api_key()
    print("=" * 92)
    print("PHASE-1c API-KEY AUTH SWITCH + EQUIVALENCE GATE + COST  --  FEASIBILITY / NOT FROZEN")
    print("=" * 92)
    if not api_key:
        print("[STOP] ANTHROPIC_API_KEY not found in env or .env -- cannot build the api-key path.")
        return
    print(f"ANTHROPIC_API_KEY loaded from {src}: {_mask(api_key)}  (value never printed/traced)")
    print(f"api path -> POST {API_BASE} | x-api-key | anthropic-version {ANTHROPIC_VERSION} | model {HAIKU}")

    # fixed test shard (deterministic; clean)
    world = W.build_world(8, TEST_SEED, inject=False)
    rid = world.region_ids[0]
    canonical_demand = world.demands_clean[0]
    canonical_prov = world.provs[0]
    report = world.reports[rid]
    user_prompt = f"Evidence record:\n\n{report}\n\nReturn the JSON now."

    print(f"\n--- STEP 3: EQUIVALENCE GATE on fixed shard {rid} (true demand={canonical_demand}) ---")
    print("    [api-key path] calling...", flush=True)
    a = api_worker(api_key, HAIKU, WORKER_SYS, user_prompt)
    print(f"      status={a['status']} dur={a['dur_s']}s resolved_model={a['resolved_model']} "
          f"cost=${a['cost_usd']} usage={a['usage']}")
    print("    [sub-CLI path] calling...", flush=True)
    s = subcli_worker(HAIKU, WORKER_SYS, user_prompt)
    print(f"      status={s['status']} dur={s['dur_s']}s model_arg={s['model_arg']} cost=${s['cost_usd']}")

    a_parsed = _parse_worker_json(a["text"]) if a["status"] == 200 else None
    s_parsed = _parse_worker_json(s["text"]) if s["status"] == 0 else None

    # gate checks
    a_ok = a["status"] == 200 and a_parsed is not None
    s_ok = s["status"] == 0 and s_parsed is not None
    model_match = (a["resolved_model"] == HAIKU == s["model_arg"])
    a_extract_ok = bool(a_parsed) and a_parsed.get("demand_units") == canonical_demand
    s_extract_ok = bool(s_parsed) and s_parsed.get("demand_units") == canonical_demand
    output_shape_match = bool(a_parsed) and bool(s_parsed) and (
        set(["demand_units"]).issubset(a_parsed) and set(["demand_units"]).issubset(s_parsed) and
        a_parsed.get("demand_units") == s_parsed.get("demand_units"))
    gate_pass = a_ok and s_ok and model_match and a_extract_ok and s_extract_ok and output_shape_match

    print("\n    GATE CHECKS:")
    print(f"      (a) api-key call succeeds + parses ............ {'PASS' if a_ok else 'FAIL'}  "
          f"(api parsed={a_parsed})")
    print(f"          sub-CLI call succeeds + parses ........... {'PASS' if s_ok else 'FAIL'}  "
          f"(sub parsed={s_parsed})")
    print(f"      (b) resolved model string == sub-CLI Haiku ... {'PASS' if model_match else 'FAIL'}  "
          f"(api={a['resolved_model']} sub={s['model_arg']} expect={HAIKU})")
    print(f"      (c) output structurally equivalent ........... {'PASS' if output_shape_match else 'FAIL'}")
    print(f"          both extract the true demand {canonical_demand} ..... "
          f"api={'Y' if a_extract_ok else 'N'} sub={'Y' if s_extract_ok else 'N'}")
    print(f"\n    EQUIVALENCE GATE: {'PASS' if gate_pass else 'FAIL'}")
    if not gate_pass:
        print("    [HARD STOP] api-key path is NOT behavior-equivalent -- must not feed anything")
        print("    compared to Phase-1b/sub data until reconciled. (Ramp would be blocked even with a VM.)")

    # ---- STEP 5: cost measurement + extrapolation ----
    per_call_api = a["cost_usd"] if a["cost_usd"] else None
    in_tok = a["usage"].get("input_tokens"); out_tok = a["usage"].get("output_tokens")
    # full confirmatory matrix (user's scope): 30 seeds x 3 arms x 2 conditions x N in {8,16,32}
    SEEDS, ARMS, CONDS, NGRID = 30, 3, 2, [8, 16, 32]
    worker_calls = SEEDS * ARMS * CONDS * sum(NGRID)
    worker_cost = (per_call_api or 0.0017) * worker_calls
    # V2 (sentinel) arm Sonnet overhead: 1 compile per cell + replans; cells = seeds x conds x |Ngrid|
    v2_cells = SEEDS * CONDS * len(NGRID)
    sonnet_compile_per_cell = 0.1376   # 1b v2 compile median (src: cost_autopsy_v3.json)
    v2_injected_cells = SEEDS * 1 * len(NGRID)   # injected condition only
    replan_frac = 0.6                  # ~detected->1 replan (recompile) on injected; conservative
    sonnet_cost = (v2_cells * sonnet_compile_per_cell
                   + v2_injected_cells * replan_frac * sonnet_compile_per_cell)
    # also flag the N=64 inclusion delta (worker side scales with sum(N))
    worker_calls_with64 = SEEDS * ARMS * CONDS * sum([8, 16, 32, 64])
    worker_cost_with64 = (per_call_api or 0.0017) * worker_calls_with64
    total_8_16_32 = worker_cost + sonnet_cost
    total_with64 = worker_cost_with64 + sonnet_cost

    print("\n--- STEP 5: COST (measured api-path call x published rates) ---")
    print(f"    measured api worker call: in={in_tok} out={out_tok} tok -> ${per_call_api} "
          f"(Haiku $1/$5 per MTok; src platform.claude.com/docs)")
    print(f"    sub-CLI worker call cost (same input) = ${s['cost_usd']} (cross-check)")
    print(f"\n    FULL-MATRIX EXTRAPOLATION (30 seeds x 3 arms x 2 conds x N in {{8,16,32}}):")
    print(f"      Haiku worker calls = {worker_calls:,}  ->  ${worker_cost:,.2f}")
    print(f"      V2 Sonnet (compile {v2_cells} cells @ ${sonnet_compile_per_cell} + "
          f"~{replan_frac} replan on {v2_injected_cells} injected) -> ${sonnet_cost:,.2f}")
    print(f"      ──────────────────────────────────────────────")
    print(f"      BALLPARK TOTAL (N in 8,16,32) ≈ ${total_8_16_32:,.0f}")
    print(f"      (if N=64 added: workers {worker_calls_with64:,} -> ${worker_cost_with64:,.2f}; "
          f"total ≈ ${total_with64:,.0f})")
    print(f"      NOTE: Sonnet is 3x Haiku per-token at list; the big multiple is token VOLUME "
          f"(compile reads whole plan + emits structured probes ≈ ${sonnet_compile_per_cell}/call "
          f"vs ≈ ${per_call_api}/Haiku-call).")

    report_obj = {
        "FEASIBILITY": True, "FROZEN": False,
        "step0_docs": {"base_url": "https://api.anthropic.com", "endpoint": "POST /v1/messages",
                       "auth_header": "x-api-key", "version_header": ANTHROPIC_VERSION,
                       "haiku_id": HAIKU, "sonnet_id": SONNET,
                       "prices_usd_per_mtok": PRICES, "src": "platform.claude.com/docs 2026-06-25"},
        "step2_harness_change": "D38 (D21-adjacent): added ANTHROPIC_API_KEY direct Messages-API "
                                "worker path (urllib POST /v1/messages, x-api-key) alongside the "
                                "sub-CLI/OAuth path; selectable per worker.",
        "step3_equivalence_gate": {
            "test_shard": rid, "true_demand": canonical_demand,
            "api": {k: a[k] for k in ("status", "resolved_model", "cost_usd", "usage", "dur_s")},
            "subcli": {k: s[k] for k in ("status", "model_arg", "cost_usd", "dur_s")},
            "api_parsed": a_parsed, "subcli_parsed": s_parsed,
            "model_match": model_match, "output_shape_match": output_shape_match,
            "api_extract_ok": a_extract_ok, "subcli_extract_ok": s_extract_ok,
            "gate_pass": gate_pass},
        "step5_cost": {"per_call_api_usd": per_call_api, "per_call_subcli_usd": s["cost_usd"],
                       "matrix_8_16_32": {"worker_calls": worker_calls, "worker_cost": round(worker_cost, 2),
                                          "v2_sonnet_cost": round(sonnet_cost, 2),
                                          "ballpark_total_usd": round(total_8_16_32, 0)},
                       "matrix_with_64": {"worker_calls": worker_calls_with64,
                                          "ballpark_total_usd": round(total_with64, 0)}},
        "vm_ramp": "BLOCKED in this environment (no cloud credential / provisioning CLI); STEP 1/4 not run.",
        "spend_usd": round((per_call_api or 0) + (s["cost_usd"] or 0), 6),
    }
    Path("runs/matrix_1c").mkdir(parents=True, exist_ok=True)
    Path(OUT_JSON).write_text(json.dumps(report_obj, indent=2, default=str), encoding="utf-8")

    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write("\n---\n")
        f.write("## Phase-1c API-KEY auth switch + EQUIVALENCE GATE  (FEASIBILITY / NOT FROZEN, not confirmatory)\n")
        f.write(f"- date: 2026-06-25  ·  STEP-0 docs read from platform.claude.com (base api.anthropic.com, "
                f"x-api-key, anthropic-version {ANTHROPIC_VERSION}, Haiku {HAIKU}, Sonnet {SONNET})\n")
        f.write(f"- harness change D38 (D21-adjacent): ANTHROPIC_API_KEY direct Messages-API worker path "
                f"(urllib POST /v1/messages)\n")
        f.write(f"- EQUIVALENCE GATE on shard {rid}: model_match={model_match}, output_shape_match="
                f"{output_shape_match}, gate_pass={gate_pass}  (api ${a['cost_usd']} / sub ${s['cost_usd']})\n")
        f.write(f"- VM ramp (STEP 1/4, N=16/32/64): BLOCKED -- no cloud credential / provisioning CLI in env\n")
        f.write(f"- cost extrapolation (30s x 3 arms x 2 cond x N{{8,16,32}}): ~${total_8_16_32:,.0f} "
                f"(+N64 ~${total_with64:,.0f}); spend this step ${report_obj['spend_usd']:.4f}\n")
        f.write(f"- artifact: {OUT_JSON}\n")

    print(f"\n[written] {OUT_JSON}")
    print(f"[logged]  {LEDGER}")
    print(f"spend this step: ${report_obj['spend_usd']:.4f}")
    print("FEASIBILITY / NOT FROZEN -- no freeze/pin; confirmatory artifacts untouched. VM ramp BLOCKED (reported).")


if __name__ == "__main__":
    main()
