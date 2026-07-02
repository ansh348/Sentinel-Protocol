#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark_1c_phase2_validate.py  --  BUILD / NOT FROZEN / NOT CONFIRMATORY

Local validation of the phase-2 world/task build (5 components) + structural
qualification (N in {8,16,32}) + the SUT-neutrality diff. No Railway, no detection
run, no spend. Treatment code untouched (verified here).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402
from world.state import RunConfig, InjectionSpec, WorldState                # noqa: E402
from world.injections import apply_injection, INJECTION_TYPES               # noqa: E402
from world.server import create_app                                         # noqa: E402
from analysis import benchmark_1c_world as BW                               # noqa: E402
from checkers import benchmark_1c as CHK                                    # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

P = print


def _cfg(n_regions, seed, inject=False):
    return RunConfig(run_id="v", seed=seed, system="manual", task_id="benchmark_1c",
                     trace_path=str(ROOT / "scratch_trace.jsonl"), world_rev=4,
                     n_regions=n_regions,
                     n_inject=(1 if inject else None),
                     injection=(InjectionSpec(type="single_shard_value_mutation", params={}) if inject else None))


def _served(state):
    """The evidence value the regions service would serve per region (mutated shard -> d')."""
    mut = state.regions_mutation
    out = {}
    for rid in state.region_order:
        v = state.regions[rid]
        if mut and mut.get("region_id") == rid:
            v = int(mut["d_prime"])
        out[rid] = int(v)
    return out


def comp1_regions_service():
    P("\n[1] world/services/regions.py + registration")
    app = create_app(_cfg(32, 9101))
    paths = {r.path for r in app.routes}
    has = "/regions" in paths and "/regions/{region_id}/evidence" in paths
    # existing-task byte-identity: n_regions=None -> NO /regions routes
    app_a1 = create_app(_cfg(None, 9101))
    a1_paths = {r.path for r in app_a1.routes}
    absent = "/regions" not in a1_paths and "/regions/{region_id}/evidence" not in a1_paths
    # responses via the route functions (in-process)
    from world.services.regions import list_regions, region_evidence
    class Req:
        def __init__(self, app): self.app = app
    req = Req(app)
    listing = list_regions(req)
    ev = [region_evidence(rid, req) for rid in (r["region_id"] for r in listing["regions"])]
    n_distinct = len({e["region_id"] for e in ev})
    widths = {len(str(e["normalized_verified_demand"])) for e in ev}
    ok = has and absent and n_distinct == 32 and widths == {4} and all(1000 <= e["normalized_verified_demand"] <= 9999 for e in ev)
    P(f"    /regions routes present (n_regions set): {has}  | absent on a1-style world (byte-identical): {absent}")
    P(f"    distinct region ids: {n_distinct}/32  | demand digit-widths: {widths} (fixed 4)  -> {'PASS' if ok else 'FAIL'}")
    return ok


def comp2_fixtures():
    P("\n[2] world/state.py region fixtures")
    s1 = WorldState(_cfg(32, 9101)); s2 = WorldState(_cfg(32, 9101))
    deterministic = (s1.regions == s2.regions and s1.region_order == s2.region_order)
    # clean vs injected: N-1 byte-identical, only target differs
    sc = WorldState(_cfg(32, 9101))
    si = WorldState(_cfg(32, 9101, inject=True)); apply_injection(si, si.config.injection)
    served_c, served_i = _served(sc), _served(si)
    diffs = [r for r in served_c if served_c[r] != served_i[r]]
    ok = deterministic and len(diffs) == 1
    P(f"    deterministic under fixed seed: {deterministic}  | clean-vs-injected differing shards: {len(diffs)} (==1)  -> {'PASS' if ok else 'FAIL'}")
    return ok


def comp3_injection():
    P("\n[3] world/injections.py single_shard_value_mutation")
    P(f"    registered injection types: {'single_shard_value_mutation' in INJECTION_TYPES}")
    si = WorldState(_cfg(32, 9101, inject=True)); detail = apply_injection(si, si.config.injection)
    served_c = _served(WorldState(_cfg(32, 9101)))
    served_i = _served(si)
    diffs = [r for r in served_c if served_c[r] != served_i[r]]
    one_mutated = len(diffs) == 1
    n_minus_1 = sum(1 for r in served_c if served_c[r] == served_i[r]) == 31
    # §4 anomaly audit on d'_j (reuse benchmark_1c_world, same seed/world)
    inj_world = BW.build_world(32, 9101, inject=True)
    audit_pass, audit = BW.anomaly_audit(inj_world)
    T = sum(served_c.values()); Tp = sum(served_i.values())
    wounds = Tp != T
    ok = one_mutated and n_minus_1 and audit_pass and wounds
    P(f"    exactly one surface mutated: {one_mutated}  | N-1 byte-identical: {n_minus_1}")
    P(f"    mutated {detail['region_id']}: {detail['d_orig']}->{detail['d_prime']} ({detail['dir']}, delta={detail['delta']})")
    P(f"    §4 anomaly audit passes (non-outlying): {audit_pass}  | T'!=T (real wound): {wounds} (|T'-T|={abs(Tp-T)})  -> {'PASS' if ok else 'FAIL'}")
    return ok


def comp4_task():
    P("\n[4] tasks/benchmark_1c.yaml")
    task = yaml.safe_load((ROOT / "tasks" / "benchmark_1c.yaml").read_text(encoding="utf-8"))
    plan_text = " ".join(s["step"] for s in task["plan"])
    named = sum(1 for i in range(1, 33) if f"/regions/R-{i:04d}/evidence" in plan_text)
    ok = (task["id"] == "benchmark_1c" and task["injections"][0]["type"] == "single_shard_value_mutation"
          and named == 32 and task["checker"] == "checkers/benchmark_1c.py")
    P(f"    loads via yaml: yes  | plan names all 32 region ids: {named}/32  | injection={task['injections'][0]['type']}  -> {'PASS' if ok else 'FAIL'}")
    return ok


def comp5_checker():
    P("\n[5] checkers/benchmark_1c.py reducer + §6 validator")
    n, seed = 32, 9101
    _w = BW.build_world(n, seed, False)
    clean = {_w.region_ids[i]: _w.demands_clean[i] for i in range(n)}
    pk_c, Tc = CHK.reduce_and_package(n, seed, clean)
    allc, ninvc, _ = CHK.validate_against_canonical(n, seed, pk_c)
    # injected served demands
    si = WorldState(_cfg(n, seed, inject=True)); apply_injection(si, si.config.injection)
    served_i = _served(si)
    pk_i, Ti = CHK.reduce_and_package(n, seed, served_i)
    alli, ninvi, reasons = CHK.validate_against_canonical(n, seed, pk_i)
    gtm = all("GLOBAL_TOTAL_MISMATCH" in r["why"] for r in reasons) and len(reasons) == n
    rec_ok, rec_inv, _ = CHK.reconcile(n, seed)
    ok = allc and (not alli) and ninvi == n and gtm and rec_ok
    P(f"    clean validator PASS: {allc} (invalid {ninvc})  | injected FAIL with N invalid: {not alli} (invalid {ninvi}/{n}, all GLOBAL_TOTAL_MISMATCH {gtm})")
    P(f"    RECONCILE recovery passes: {rec_ok}  -> {'PASS' if ok else 'FAIL'}")
    return ok


def structural_qual():
    P("\n=== STRUCTURAL QUALIFICATION (pure checks, no detection, no spend) ===")
    rows = []
    for n in (8, 16, 32):
        seed = 9100 + n
        sc = WorldState(_cfg(n, seed)); si = WorldState(_cfg(n, seed, inject=True))
        apply_injection(si, si.config.injection)
        served_c, served_i = _served(sc), _served(si)
        inj_world = BW.build_world(n, seed, inject=True)
        clean = {sc.region_order[i]: served_c[sc.region_order[i]] for i in range(n)}
        # checker on served
        pk_i, Ti = CHK.reduce_and_package(n, seed, served_i)
        all_i, ninv_i, reasons = CHK.validate_against_canonical(n, seed, pk_i)
        audit_pass, _ = BW.anomaly_audit(inj_world)
        rec_ok, _, _ = CHK.reconcile(n, seed)
        man = create_app(_cfg(n, seed))  # manifest has no aggregate
        from world.services.regions import list_regions
        listing = list_regions(type("R", (), {"app": man})())
        manifest_no_total = all(set(m.keys()) == {"region_id", "url"} for m in listing["regions"])
        # post-injection internally consistent: shares sum to 1 vs T'
        from fractions import Fraction
        shares_sum_one = sum((p["share"] for p in pk_i), Fraction(0)) == Fraction(1)
        T = sum(served_c.values()); Tp = sum(served_i.values())
        checks = {
            "N_unique_shards": len(set(sc.region_order)) == n,
            "fixed_work_per_shard": len({len(str(v)) for v in served_c.values()}) == 1,
            "exactly_one_mutated": sum(1 for r in served_c if served_c[r] != served_i[r]) == 1,
            "N_minus_1_byte_identical": sum(1 for r in served_c if served_c[r] == served_i[r]) == n - 1,
            "manifest_no_aggregate(§3.1)": manifest_no_total,
            "post_injection_consistent(§3.2)": shares_sum_one and Ti == Tp,
            "opaque_provenance(§4)": all(len(p) == 16 for p in sc.region_provs.values()),
            "T'_neq_T": Tp != T,
            "validator_exactly_N_invalid": ninv_i == n,
            "all_GLOBAL_TOTAL_MISMATCH": all("GLOBAL_TOTAL_MISMATCH" in r["why"] for r in reasons) and len(reasons) == n,
            "reconcile_passes(§7)": rec_ok,
            "anomaly_audit_passes(§4)": audit_pass,
        }
        rows.append((n, seed, checks))
    keys = list(rows[0][2].keys())
    P("    check".ljust(40) + "".join(f"  N={n}" for n, _, _ in rows))
    for k in keys:
        line = ("    " + k).ljust(40)
        for _, _, ch in rows:
            line += "    " + (" . " if ch[k] else " X ")
        P(line)
    allpass = all(all(ch.values()) for _, _, ch in rows)
    P(f"    -> ALL N STRUCTURALLY {'QUALIFIED' if allpass else 'FAILED'}")
    return allpass, [(n, all(ch.values())) for n, _, ch in rows]


def sut_neutrality_diff():
    P("\n=== SUT-NEUTRALITY DIFF (HARD GATE) — treatment/detection code byte-identical? ===")
    def changed(paths):
        out = subprocess.run(["git", "-C", str(ROOT), "diff", "--name-only", "--", *paths],
                             capture_output=True, text=True)
        return [l for l in out.stdout.splitlines() if l.strip()]
    treatment = ["sentinel_v2", "conductor/run_v2_loop.py", "conductor/run_one.py",
                 "conductor/sessions.py", "sentinel"]
    tr_changed = changed(treatment)
    world_changed = changed(["world/server.py", "world/state.py", "world/injections.py"])
    verdict = "PASS (byte-neutral)" if not tr_changed else "FAIL — §3.6 surgery"
    rec = {"BUILD": True, "FROZEN": False,
           "treatment_scope": treatment,
           "treatment_code_changed": tr_changed,
           "treatment_byte_identical": not tr_changed,
           "world_files_changed_additive_only": world_changed,
           "D35_executor_knob": "NOT implemented this phase (conductor/run_one.py byte-identical) — deferred to phase 3 forced-width runs",
           "D36_plan": "tasks/benchmark_1c.yaml (task INPUT, no code change) — SUT-neutral by construction",
           "regions_registration": "conditional on config.n_regions (existing tasks' OpenAPI/path-samples byte-identical, like the rev-2 meta router)",
           "verdict": verdict}
    (ROOT / "runs" / "matrix_1c").mkdir(parents=True, exist_ok=True)
    (ROOT / "runs" / "matrix_1c" / "sut_neutrality_diff.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    P(f"    treatment code (sentinel_v2/, conductor run loops, sessions) changed files: {tr_changed or 'NONE'}")
    P(f"    world files changed (ADDITIVE benchmark hunks only): {world_changed}")
    P(f"    D35 executor knob: NOT touched (deferred); D36 plan: task-YAML input")
    P(f"    VERDICT: {verdict}")
    return not tr_changed


def main():
    P("=" * 92)
    P("BENCHMARK_1c PHASE-2 BUILD VALIDATION  --  BUILD / NOT FROZEN / NOT CONFIRMATORY  --  $0")
    P("=" * 92)
    results = {
        "comp1_regions_service": comp1_regions_service(),
        "comp2_fixtures": comp2_fixtures(),
        "comp3_injection": comp3_injection(),
        "comp4_task": comp4_task(),
        "comp5_checker": comp5_checker(),
    }
    sq_pass, sq_rows = structural_qual()
    sut_pass = sut_neutrality_diff()
    P("\n" + "=" * 92)
    P("SUMMARY")
    for k, v in results.items():
        P(f"  {k}: {'PASS' if v else 'FAIL'}")
    P(f"  structural_qualification (N in 8,16,32): {'PASS' if sq_pass else 'FAIL'}  {sq_rows}")
    P(f"  SUT-neutrality (treatment byte-identical): {'PASS' if sut_pass else 'FAIL'}")
    P("BUILD / NOT FROZEN / NOT CONFIRMATORY — no Railway, no detection run, no spend.")


if __name__ == "__main__":
    main()
