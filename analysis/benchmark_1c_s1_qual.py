#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark_1c_s1_qual.py  --  DRAFT / NOT FROZEN

S1 (plain batch) qualification for the Phase-1c sharded-allocation benchmark.
Implements spec decisions/benchmark_1c_sharded_allocation_v3.md §4/§6/§9 against
the world in analysis/benchmark_1c_world.py.

NO sentinel / V2 / V2J / S3 logic.  The only LLM calls are the per-worker Stage-1
read+extract a plain batch worker needs (Haiku, single-turn, no tools).  Reduce +
exact-rational share + validation are deterministic (spec §1/§6).  Oracle is
runtime-isolated (workers never see GLOBAL_TOTAL_MISMATCH; validation runs after
the batch completes) -- m4.

  python benchmark_1c_s1_qual.py structural   # STEP B only, no spend
  python benchmark_1c_s1_qual.py run          # B + budget gate + empirical + ledger

DRAFT / NOT FROZEN: no hash pin, no deviation number, no freeze.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from fractions import Fraction
from pathlib import Path
from threading import Lock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis import benchmark_1c_world as W            # noqa: E402
from conductor import sessions                          # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ---- qualification settings (DRAFT) ----
N_GRID = [8, 16, 32]
SEEDS = [9101, 9102, 9103]              # qualification seeds -- BURNED (logged below)
CONC_CEILING = 8                        # host/rate-limit ceiling on in-flight workers
HARD_CAP_USD = 25.0
WORKER_MODEL = sessions.WORKER_MODEL    # Haiku 4.5
OUT_JSON = "runs/matrix_1c/s1_qualification.json"
LEDGER = "decisions/dev_run_ledger.md"

WORKER_SYS = (
    "You are a precise data-extraction worker. You are given exactly one regional "
    "demand evidence record. Extract its fields and return ONLY a single JSON object "
    "with keys region_id, demand_units, provenance_id. demand_units must be the "
    "integer number of demand units stated in the record. Output JSON only -- no "
    "prose, no markdown, no code fences."
)

_spend_lock = Lock()
_spend = {"usd": 0.0, "calls": 0}


def _parse_worker_json(text):
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```[a-zA-Z]*", "", t).strip().rstrip("`").strip()
    m = re.search(r"\{.*\}", t, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except ValueError:
        return None
    if "demand_units" not in obj:
        return None
    try:
        obj["demand_units"] = int(str(obj["demand_units"]).replace(",", "").strip())
    except ValueError:
        return None
    return obj


def _run_worker(rid, report_text, slot):
    """One Stage-1 read+extract worker (LLM).  Returns a record with timing + cost."""
    t0 = time.monotonic()
    res = sessions.run_claude(
        model=WORKER_MODEL,
        system_prompt=WORKER_SYS,
        max_turns=1,
        prompt=f"Evidence record:\n\n{report_text}\n\nReturn the JSON now.",
        no_tools=True,
    )
    t1 = time.monotonic()
    with _spend_lock:
        _spend["usd"] += res.cost_usd
        _spend["calls"] += 1
    parsed = _parse_worker_json(res.result_text)
    instrument_fail = res.timed_out or res.exit_code != 0 or res.payload is None
    return {
        "region_id": rid, "slot": slot,
        "t_start": t0, "t_end": t1, "dur_s": round(t1 - t0, 2),
        "cost_usd": res.cost_usd,
        "exit_code": res.exit_code, "timed_out": res.timed_out,
        "is_error": res.is_error, "instrument_fail": instrument_fail,
        "extracted": None if parsed is None else parsed.get("demand_units"),
        "extracted_rid": None if parsed is None else parsed.get("region_id"),
        "extracted_prov": None if parsed is None else parsed.get("provenance_id"),
        "parse_ok": parsed is not None,
    }


def _realized_fanout(workers):
    """max concurrent in-flight via interval-overlap sweep-line."""
    evts = []
    for w in workers:
        evts.append((w["t_start"], +1))
        evts.append((w["t_end"], -1))
    evts.sort(key=lambda e: (e[0], -e[1]))
    cur = mx = 0
    for _, d in evts:
        cur += d
        mx = max(mx, cur)
    return mx


def run_batch(world, conc_ceiling=CONC_CEILING):
    """Plain S1 batch: dispatch all N read+extract workers (executor width N per
    D35, in-flight capped at conc_ceiling), then deterministic reduce/package/
    validate.  Returns the run record (no oracle signal reaches workers)."""
    width = min(world.n, conc_ceiling)
    workers = []
    with ThreadPoolExecutor(max_workers=width) as ex:
        futs = [ex.submit(_run_worker, world.region_ids[i], world.reports[world.region_ids[i]], i)
                for i in range(world.n)]
        for f in as_completed(futs):
            workers.append(f.result())
            if _spend["usd"] > HARD_CAP_USD:
                # safety: stop accepting more work if cap blown (should not happen)
                break
    workers.sort(key=lambda w: w["slot"])
    # deterministic Stage-2: extracted demands -> reduce -> packages
    extracted = {}
    any_missing = False
    for i, rid in enumerate(world.region_ids):
        w = next((x for x in workers if x["region_id"] == rid), None)
        if w is None or w["extracted"] is None:
            any_missing = True
            extracted[rid] = world.demands_clean[i] if w is None else -1  # placeholder
        else:
            extracted[rid] = w["extracted"]
    packages, Tp = W.build_packages(world, extracted)
    all_pass, n_invalid, reasons = W.validate(world, packages)
    gtm = any("GLOBAL_TOTAL_MISMATCH" in r["why"] for r in reasons)
    instrument_fail = any(w["instrument_fail"] for w in workers) or len(workers) != world.n
    # faithful extraction = every worker read its surface's actual value
    surface_val = {world.region_ids[i]:
                   (world.d_prime if (world.inject and i == world.j_index) else world.demands_clean[i])
                   for i in range(world.n)}
    misreads = [w["region_id"] for w in workers
                if w["extracted"] is not None and w["extracted"] != surface_val[w["region_id"]]]
    return {
        "N": world.n, "seed": world.seed, "inject": world.inject,
        "executor_width": width, "realized_fanout": _realized_fanout(workers) if workers else 0,
        "n_workers_returned": len(workers),
        "run_cost_usd": round(sum(w["cost_usd"] for w in workers), 6),
        "T": world.T, "T_prime": Tp,
        "abs_T_diff": abs(Tp - world.T), "wounds": Tp != world.T,
        "intended_abs_T_diff": (abs(world.d_prime - world.d_j) if world.inject else 0),
        "all_pass": all_pass, "n_invalid": n_invalid, "gtm": gtm,
        "instrument_fail": instrument_fail,
        "n_misreads": len(misreads), "misread_regions": misreads,
        "worker_durs": [w["dur_s"] for w in workers],
        "j_rid": world.j_rid, "d_j": world.d_j, "d_prime": world.d_prime,
        "mutation_dir": world.mutation_dir,
    }


# --------------------------------------------------------------------------- #
# STEP B -- structural qualification (pure, no spend)
# --------------------------------------------------------------------------- #
def structural_qual(n, seed):
    clean = W.build_world(n, seed, inject=False)
    inj = W.build_world(n, seed, inject=True)
    # exactly N unique shards
    uniq = (len(set(clean.region_ids)) == n)
    # fixed-size work/shard (all reports identical byte length)
    lens = {len(clean.reports[r]) for r in clean.region_ids}
    fixed_size = (len(lens) == 1)
    # exactly one mutated surface; N-1 byte-identical
    diffs = [r for r in clean.region_ids if clean.reports[r] != inj.reports[r]]
    one_mutated = (len(diffs) == 1 and diffs[0] == inj.j_rid)
    n_minus_1_identical = (sum(1 for r in clean.region_ids if clean.reports[r] == inj.reports[r]) == n - 1)
    # §3 world-side invariants (S1-applicable subset; §3.5/§3.6 are treatment-arm, deferred)
    manifest_has_no_total = all(set(m.keys()) == {"region_id", "url"} for m in clean.manifest)
    reports_have_no_total = not any(("global_total" in clean.reports[r] or "total" in clean.reports[r].lower())
                                    for r in clean.region_ids)
    # post-injection internally consistent: T' = sum(reads); shares sum to 1 vs T'
    pkgs, Tp = W.build_packages(inj, {inj.region_ids[i]:
                                      (inj.d_prime if i == inj.j_index else inj.demands_clean[i])
                                      for i in range(n)})
    shares_sum_one = (sum((p["share"] for p in pkgs), Fraction(0)) == Fraction(1))
    internal_consistent = (Tp == inj.T_prime) and shares_sum_one
    # T' != T
    t_wounds = (inj.T_prime != inj.T)
    # validator reports exactly N invalid (injected, faithful extraction)
    _, n_invalid, reasons = W.validate(inj, pkgs)
    exactly_N_invalid = (n_invalid == n)
    all_gtm = all("GLOBAL_TOTAL_MISMATCH" in r["why"] for r in reasons) and len(reasons) == n
    # scripted RECONCILE recovery passes (§7)
    rec_pass, rec_invalid, rec_T = W.reconcile_recover(inj)
    # §4 static anomaly audit on d'_j passes
    audit_pass, audit_detail = W.anomaly_audit(inj)
    # clean validates exactly (sanity)
    clean_pkgs, _ = W.build_packages(clean, {clean.region_ids[i]: clean.demands_clean[i] for i in range(n)})
    clean_ok, _, _ = W.validate(clean, clean_pkgs)
    checks = {
        "N_unique_shards": uniq,
        "fixed_size_per_shard": fixed_size,
        "exactly_one_mutated": one_mutated,
        "N_minus_1_byte_identical": n_minus_1_identical,
        "manifest_no_aggregate(§3.1)": manifest_has_no_total,
        "reports_no_total(§3.1/§3.4)": reports_have_no_total,
        "post_injection_internally_consistent(§3.2)": internal_consistent,
        "T'_neq_T": t_wounds,
        "validator_exactly_N_invalid": exactly_N_invalid,
        "all_GLOBAL_TOTAL_MISMATCH": all_gtm,
        "scripted_reconcile_recovery_passes(§7)": rec_pass and rec_invalid == 0,
        "anomaly_audit_passes(§4)": audit_pass,
        "clean_validates(§6)": clean_ok,
    }
    return {
        "N": n, "seed": seed, "all_pass": all(checks.values()), "checks": checks,
        "j_rid": inj.j_rid, "d_j": inj.d_j, "d_prime": inj.d_prime,
        "mutation_dir": inj.mutation_dir, "delta": abs(inj.d_prime - inj.d_j),
        "T": inj.T, "T_prime": inj.T_prime, "abs_T_diff": abs(inj.T_prime - inj.T),
        "rel_T_diff": round(abs(inj.T_prime - inj.T) / inj.T, 6),
        "n_eligible_shards": len(inj.eligible_indices),
        "audit": audit_detail,
    }


def print_structural(rows):
    P = print
    P("\n(B) STRUCTURAL QUALIFICATION  (pure checks, no spend)  --  per N (seed-paired)")
    keys = list(rows[0]["checks"].keys())
    P("    every cell must be PASS for the benchmark to be structurally qualified at that N.\n")
    for r in rows:
        P(f"  N={r['N']:>2} seed={r['seed']}  -> {'ALL PASS' if r['all_pass'] else 'FAIL'}   "
          f"(mutate {r['j_rid']}: {r['d_j']}->{r['d_prime']} {r['mutation_dir']}, "
          f"delta={r['delta']}, |T'-T|={r['abs_T_diff']} ({r['rel_T_diff']*100:.3f}% of T), "
          f"eligible_shards={r['n_eligible_shards']}/{r['N']})")
    P("\n    check-by-check (N x check), '.'=pass  'X'=FAIL:")
    hdr = "    check".ljust(46) + "".join(f"  N{r['N']}s{str(r['seed'])[-1]}" for r in rows)
    P(hdr)
    for k in keys:
        line = ("    " + k).ljust(46)
        for r in rows:
            line += "    " + (" . " if r["checks"][k] else " X ")
        P(line)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def do_structural():
    rows = [structural_qual(n, seed) for n in N_GRID for seed in SEEDS]
    print_structural(rows)
    return rows


def smoke_one_worker():
    """One real worker call to measure representative per-worker cost + latency."""
    w = W.build_world(8, SEEDS[0], inject=False)
    rid = w.region_ids[0]
    rec = _run_worker(rid, w.reports[rid], 0)
    return rec


def budget_gate(per_worker_usd):
    total_workers = sum(n for n in N_GRID) * len(SEEDS) * 2   # clean + injected
    est_measured = total_workers * per_worker_usd
    anchor_1b = total_workers * 0.10                          # pessimistic 1b per-worker
    return total_workers, est_measured, anchor_1b


def append_ledger(summary):
    p = Path(LEDGER)
    block = []
    block.append("\n---\n")
    block.append("## Phase-1c benchmark S1 QUALIFICATION  (DRAFT / NOT FROZEN, not confirmatory)\n")
    block.append(f"- date: 2026-06-25  ·  spec: decisions/benchmark_1c_sharded_allocation_v3.md (un-pinned)\n")
    block.append(f"- purpose: §9 S1 qualification (structural + empirical) for the sharded-allocation surface\n")
    block.append(f"- seeds BURNED (qualification, not reusable for confirmatory): {SEEDS}\n")
    block.append(f"- N grid: {N_GRID}  ·  worker model: {WORKER_MODEL}  ·  in-flight ceiling: {CONC_CEILING}\n")
    block.append(f"- LLM worker calls: {summary['llm_calls']}  ·  TOTAL SPEND: ${summary['spend_usd']:.4f} "
                 f"(hard cap ${HARD_CAP_USD:.0f})\n")
    block.append(f"- result: clean {summary['clean_pass_runs']}/{summary['clean_total_runs']} exact-pass · "
                 f"injected {summary['inj_wound_runs']}/{summary['inj_total_runs']} wounded "
                 f"(GLOBAL_TOTAL_MISMATCH, N invalid) · qualified={summary['qualified']}\n")
    block.append(f"- artifact: {OUT_JSON}\n")
    with p.open("a", encoding="utf-8") as f:
        f.write("".join(block))


def do_run():
    report = {"DRAFT": True, "FROZEN": False,
              "spec": "decisions/benchmark_1c_sharded_allocation_v3.md",
              "seeds_burned": SEEDS, "N_grid": N_GRID, "worker_model": WORKER_MODEL,
              "conc_ceiling": CONC_CEILING, "hard_cap_usd": HARD_CAP_USD}

    # STEP B
    structural = do_structural()
    report["structural"] = structural
    if not all(r["all_pass"] for r in structural):
        print("\n[STOP] structural qualification FAILED -- not spending. See STEP E (revision).")
        report["stopped"] = "structural_fail"
        Path("runs/matrix_1c").mkdir(parents=True, exist_ok=True)
        Path(OUT_JSON).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        return report

    # STEP C -- budget gate
    print("\n(C) BUDGET GATE")
    print(f"    measuring representative per-worker cost with ONE smoke call ({WORKER_MODEL})...")
    smoke = smoke_one_worker()
    report["smoke"] = smoke
    per_worker = smoke["cost_usd"] if smoke["cost_usd"] > 0 else 0.005
    total_workers, est_measured, anchor_1b = budget_gate(per_worker)
    print(f"    smoke: cost=${smoke['cost_usd']:.5f}  latency={smoke['dur_s']}s  "
          f"parse_ok={smoke['parse_ok']}  extracted={smoke['extracted']}")
    print(f"    total worker calls planned = sum(N)*seeds*2 = {sum(N_GRID)}*{len(SEEDS)}*2 = {total_workers}")
    print(f"    estimate @ measured ${per_worker:.5f}/worker = ${est_measured:.2f}")
    print(f"    cross-check @ 1b anchor $0.10/worker (PESSIMISTIC: bundles orchestrator+tool-use) "
          f"= ${anchor_1b:.2f}")
    report["budget"] = {"per_worker_usd": per_worker, "total_workers": total_workers,
                        "est_measured_usd": round(est_measured, 2), "anchor_1b_usd": round(anchor_1b, 2)}
    if est_measured > HARD_CAP_USD:
        print(f"    [STOP] measured estimate ${est_measured:.2f} EXCEEDS hard cap ${HARD_CAP_USD:.0f} -- "
              f"stopping for go-ahead.")
        report["stopped"] = "budget_exceeded"
        Path(OUT_JSON).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        return report
    print(f"    estimate ${est_measured:.2f} <= cap ${HARD_CAP_USD:.0f}  -> PROCEED with empirical S1.")

    # STEP D -- empirical S1
    print("\n(D) EMPIRICAL S1 QUALIFICATION  (real batch workers; oracle runs post-batch)")
    empirical = []
    for n in N_GRID:
        for seed in SEEDS:
            for inject in (False, True):
                w = W.build_world(n, seed, inject)
                rec = run_batch(w)
                # one instrument-only retry (timeout/transport), never to massage a result (§5/§9)
                if rec["instrument_fail"] and _spend["usd"] < HARD_CAP_USD:
                    print(f"    [instrument re-run] N={n} seed={seed} inject={inject} "
                          f"(reason: worker timeout/transport)")
                    rec_retry = run_batch(w)
                    rec_retry["was_instrument_retry"] = True
                    rec = rec_retry
                empirical.append(rec)
                tag = "INJ" if inject else "CLEAN"
                status = ("EXACT-PASS" if (not inject and rec["all_pass"]) else
                          ("WOUNDED(Ninv)" if (inject and rec["n_invalid"] == n and rec["gtm"]) else
                           "FAIL/OTHER"))
                print(f"    N={n:>2} seed={seed} {tag:>5}: {status:>14}  "
                      f"realized_fanout={rec['realized_fanout']}/{rec['executor_width']}  "
                      f"|T'-T|={rec['abs_T_diff']} (intended {rec['intended_abs_T_diff']})  "
                      f"misreads={rec['n_misreads']}  n_invalid={rec['n_invalid']}  "
                      f"cost=${rec['run_cost_usd']:.4f}  cum=${_spend['usd']:.3f}")
                if _spend["usd"] > HARD_CAP_USD:
                    print(f"    [STOP] cumulative spend ${_spend['usd']:.2f} exceeded cap -- halting.")
                    break
    report["empirical"] = empirical

    # ---- summarize per N + overall ----
    summary = summarize(empirical)
    report["summary"] = summary
    report["spend_usd"] = round(_spend["usd"], 6)
    report["llm_calls"] = _spend["calls"]
    print_empirical_summary(summary)

    Path("runs/matrix_1c").mkdir(parents=True, exist_ok=True)
    Path(OUT_JSON).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    append_ledger({**summary, "spend_usd": _spend["usd"], "llm_calls": _spend["calls"]})
    print(f"\n[written] {OUT_JSON}")
    print(f"[logged]  {LEDGER}  (QUALIFICATION block; seeds {SEEDS} burned)")
    print(f"\nTOTAL SPEND: ${_spend['usd']:.4f}  ·  LLM calls: {_spend['calls']}  ·  cap ${HARD_CAP_USD:.0f}")
    print("DRAFT / NOT FROZEN -- no hash pin, no deviation number, no freeze.")
    return report


def summarize(empirical):
    per_n = {}
    for n in N_GRID:
        cln = [r for r in empirical if r["N"] == n and not r["inject"]]
        inj = [r for r in empirical if r["N"] == n and r["inject"]]
        clean_pass = sum(1 for r in cln if r["all_pass"])
        inj_wound = sum(1 for r in inj if r["n_invalid"] == n and r["gtm"] and r["wounds"])
        per_n[n] = {
            "clean_pass": clean_pass, "clean_total": len(cln),
            "inj_wound": inj_wound, "inj_total": len(inj),
            "clean_3of3": clean_pass == 3 and len(cln) == 3,
            "inj_3of3": inj_wound == 3 and len(inj) == 3,
            "realized_fanout_clean": [r["realized_fanout"] for r in cln],
            "realized_fanout_inj": [r["realized_fanout"] for r in inj],
            "abs_T_diff_inj": [r["abs_T_diff"] for r in inj],
            "intended_T_diff_inj": [r["intended_abs_T_diff"] for r in inj],
            "misreads_clean": [r["n_misreads"] for r in cln],
            "misreads_inj": [r["n_misreads"] for r in inj],
            "qualified": (clean_pass == 3 and inj_wound == 3),
        }
    qualified = all(per_n[n]["qualified"] for n in N_GRID)
    return {
        "per_N": per_n, "qualified": qualified,
        "clean_pass_runs": sum(per_n[n]["clean_pass"] for n in N_GRID),
        "clean_total_runs": sum(per_n[n]["clean_total"] for n in N_GRID),
        "inj_wound_runs": sum(per_n[n]["inj_wound"] for n in N_GRID),
        "inj_total_runs": sum(per_n[n]["inj_total"] for n in N_GRID),
    }


def print_empirical_summary(summary):
    P = print
    P("\n(D) EMPIRICAL S1 TABLE  --  per N")
    P("    N   | clean exact-pass | injected wounded (N inv, GTM) | realized fanout | |T'-T| (intended) | misreads")
    for n in N_GRID:
        s = summary["per_N"][n]
        rf = s["realized_fanout_clean"] + s["realized_fanout_inj"]
        rf_rng = f"{min(rf)}-{max(rf)}" if rf else "?"
        td = s["abs_T_diff_inj"]; itd = s["intended_T_diff_inj"]
        P(f"   {n:>3}  |   {s['clean_pass']}/{s['clean_total']} {'PASS' if s['clean_3of3'] else 'FAIL'}      "
          f"|   {s['inj_wound']}/{s['inj_total']} {'PASS' if s['inj_3of3'] else 'FAIL'}              "
          f"|   {rf_rng:>7}      |  {td} (={itd})  | c{sum(s['misreads_clean'])}/i{sum(s['misreads_inj'])}")
    P(f"\n    OVERALL S1 QUALIFICATION: {'QUALIFIED' if summary['qualified'] else 'NOT QUALIFIED'}")
    P(f"    clean exact-pass {summary['clean_pass_runs']}/{summary['clean_total_runs']} · "
      f"injected wounded {summary['inj_wound_runs']}/{summary['inj_total_runs']}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "structural"
    if mode == "structural":
        do_structural()
        print("\n[structural only -- no spend]  run with:  python analysis/benchmark_1c_s1_qual.py run")
    elif mode == "run":
        do_run()
    else:
        print("usage: benchmark_1c_s1_qual.py [structural|run]")
