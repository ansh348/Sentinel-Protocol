"""GROUNDING-RATE DIAGNOSIS — doc_contradiction passage grounding (MEASUREMENT ONLY).

Measures the doc_contradiction (RETRIEVAL_INTEGRITY) passage-grounding rate on the
SEEN cell c1+doc_contradiction (injected passage = pol-returns) and LOCALIZES where the
passage-selection non-determinism lives:
  (a) the LLM compile naming a specific passage / set (variance in the model output), vs
  (b) the substrate template-instantiation picking a representative (the wrong pick being
      deterministic substrate logic over a possibly-varying model-named set).

Design — ISOLATE the compile (the one LLM step), per the dev-run budget:
  * The plan is held FIXED to the REAL recorded c1+doc_contradiction orchestrator plan
    (runs/v2_d31_revalidate/c1-V2-doc_contradiction-s1), reconstructed exactly as
    Conductor.plan_text() builds it. This controls planner variance OUT, so any residual
    variance is purely the compile step.
  * Each iteration is an INDEPENDENT compile: fresh isolated home, no soft-set caching,
    one bounded compile_assumptions() call (with its own one-retry-on-schema, faithful to
    one matrix compile) + the deterministic compile_pipeline() grounding.
  * For each compile it records the RAW soft surfaces the model emits for /docs/passages
    AND the GROUNDED probe targets the substrate produces, so (a) vs (b) is decidable.

NO production/test code is touched: this is a standalone analysis script, not imported by
the suite or the world. compile_pipeline is run with world=None (the §4 gate shadow then
routes to 'uncovered' — irrelevant to passage grounding, which is static over the rev-4
fixture samples). Scoring uses the SEEN cell's KNOWN injected passage (pol-returns).

Usage: ../.venv/Scripts/python.exe -m analysis.v2_doc_grounding_rate [N] [concurrency]
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
os.environ["TRIPWIRE_V2"] = "1"
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import yaml

from conductor.sessions import COMPILE_MODEL, default_scratch_root
from sentinel_v2.compile_probes import (compile_assumptions, compile_pipeline,
                                        ground_surface, _normalize_surface,
                                        GroundingError)
from sentinel_v2.pattern_liveness import path_samples_for_rev
from sentinel_v2.surface_appendix import openapi_paths_for_rev
from sentinel_v2.write_footprint import planned_write_patterns
from world.surface import enriched_context
from trace import TraceWriter, read_trace

TASK = "c1"
INJECTION = "doc_contradiction"
INJECTED_PASSAGE = "/docs/passages/pol-returns"   # SEEN-cell known truth
WORLD_REV = 4                                     # c1.yaml world_rev
RECORDED_RUN = (REPO / "runs" / "v2_d31_revalidate"
                / "c1-V2-doc_contradiction-s1" / "trace.jsonl")
PASSAGE_RE = re.compile(r"^/docs/passages/[^/]+$")   # a concrete passage (not the list)

OUT_DIR = REPO / "runs" / "v2_doc_grounding_rate"


def build_fixed_plan_text() -> str:
    """Reconstruct Conductor.plan_text() from the REAL recorded c1+doc_contradiction
    orchestrator plan (held fixed across all compiles)."""
    task = yaml.safe_load((REPO / "tasks" / f"{TASK}.yaml").read_text(encoding="utf-8"))
    events = list(read_trace(RECORDED_RUN))
    plan = [e for e in events if e["event_type"] == "plan"][0]["payload"]["reply"]
    lines = [f"Goal: {task['goal'].strip()}", "", "Plan:"]
    for i, step in enumerate(plan["steps"], start=1):
        lines.append(f"{i}. [{step['subplan_id']}] ({step['worker_id']}) {step['subtask']}")
    return "\n".join(lines), task


def _passage_probe_targets(probes) -> list[str]:
    """The concrete passage surfaces the substrate actually armed (the 'passages the
    contradiction probe grounds to')."""
    return sorted({p.target for p in probes if PASSAGE_RE.match(p.target)})


def run_one_compile(idx: int, plan_text: str, task_context: str, task: dict,
                    samples: tuple, routes: tuple, write_set: tuple) -> dict:
    """One INDEPENDENT compile: own isolated home, own throwaway trace, no caching."""
    scratch = default_scratch_root()
    home = Path(tempfile.mkdtemp(prefix=f"grnd_home_{idx}_", dir=str(scratch)))
    tfd, tpath = tempfile.mkstemp(prefix=f"grnd_trace_{idx}_", suffix=".jsonl",
                                  dir=str(scratch))
    os.close(tfd)
    trace = TraceWriter(tpath, run_id=f"grounding-{idx}", seed=1,
                        system="V2", task_id=TASK)
    rec: dict = {"i": idx}
    try:
        soft, results = compile_assumptions(plan_text, task_context, trace,
                                            isolated_home=home)
        rec["cost_usd"] = round(sum(s.cost_usd for s in results), 6)
        rec["attempts"] = len(results)
        if soft is None:
            rec.update(valid=False, n_assumptions=0, error="compile produced no soft set")
            return rec
        rec["valid"] = True
        rec["n_assumptions"] = len(soft.assumptions)
        # RAW soft surfaces (model output) paired with their substrate grounding, for
        # every assumption that concerns a passage either before or after grounding.
        passage_soft = []
        for a in soft.assumptions:
            norm = _normalize_surface(a.surface)
            # D32: ground_surface returns a SurfaceGrounding (members may be a family).
            g = ground_surface(a.surface, samples, routes)
            members = list(g.members)
            touches = norm.startswith("/docs/passages/") or norm == "/docs/passages" or (
                any(m.startswith("/docs/passages") for m in members))
            if touches:
                passage_soft.append({
                    "raw_surface": a.surface,
                    "normalized": norm,
                    "is_template": "{" in norm,
                    "pointer": a.pointer,
                    "grounded": members,
                    "world_fact": (a.world_fact or "")[:90],
                })
        rec["passage_soft"] = passage_soft
        rec["raw_passage_surfaces"] = sorted({p["raw_surface"] for p in passage_soft})
        # substrate output: the actually-compiled probe set
        try:
            cr = compile_pipeline(soft, world_rev=WORLD_REV, world=None,
                                  auth_token=None, planned_write_set=write_set)
            armed = _passage_probe_targets(cr.probes)
            rec["grounded_passage_probes"] = armed
            rec["all_probe_targets"] = [p.target for p in cr.probes]
            rec["pol_returns_covered"] = INJECTED_PASSAGE in armed
            rec["grounding_error"] = None
        except GroundingError as exc:
            rec["grounded_passage_probes"] = []
            rec["pol_returns_covered"] = False
            rec["grounding_error"] = str(exc)[:200]
        return rec
    except Exception as exc:  # never let one compile crash the sweep
        rec.setdefault("valid", False)
        rec["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        return rec
    finally:
        trace.close()
        import shutil
        shutil.rmtree(home, ignore_errors=True)
        try:
            os.unlink(tpath)
        except OSError:
            pass


def main(argv) -> int:
    n = int(argv[0]) if argv else 10
    concurrency = int(argv[1]) if len(argv) > 1 else 5
    plan_text, task = build_fixed_plan_text()
    task_context = enriched_context(task)
    samples = path_samples_for_rev(WORLD_REV)
    routes = tuple(openapi_paths_for_rev(WORLD_REV).keys())
    write_set = planned_write_patterns(task.get("plan", []))

    print(f"GROUNDING-RATE DIAGNOSIS  cell={TASK}+{INJECTION}  model={COMPILE_MODEL}")
    print(f"injected passage (truth) = {INJECTED_PASSAGE}  world_rev={WORLD_REV}")
    print(f"plan held FIXED (recorded orchestrator plan); N={n} independent compiles, "
          f"concurrency={concurrency}\n")

    rows: list[dict] = [None] * n
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = {ex.submit(run_one_compile, i, plan_text, task_context, task,
                          samples, routes, write_set): i for i in range(n)}
        for fut in as_completed(futs):
            r = fut.result()
            rows[r["i"]] = r
            ok = r.get("pol_returns_covered")
            print(f"  compile #{r['i']:2d}: valid={r.get('valid')} "
                  f"n_assump={r.get('n_assumptions')} "
                  f"pol_returns_covered={ok} "
                  f"grounded={r.get('grounded_passage_probes')} "
                  f"cost=${r.get('cost_usd')}")

    valid = [r for r in rows if r and r.get("valid")]
    k = sum(1 for r in valid if r.get("pol_returns_covered"))
    nv = len(valid)
    total_cost = round(sum(r.get("cost_usd", 0.0) or 0.0 for r in rows if r), 6)

    print("\n================ GROUNDING RATE ================")
    print(f"correct-grounding rate k/N = {k}/{nv}"
          + (f"  ({100*k/nv:.0f}%)" if nv else ""))

    # full distribution of passage-probe SETS grounded to across runs
    print("\n--- distribution of grounded passage-probe SETS (per compile) ---")
    set_dist = Counter(tuple(r["grounded_passage_probes"]) for r in valid
                       if "grounded_passage_probes" in r)
    for combo, cnt in set_dist.most_common():
        flag = "CORRECT" if INJECTED_PASSAGE in combo else "MISS   "
        print(f"  [{flag}] x{cnt}: {list(combo)}")

    # per-passage coverage frequency
    print("\n--- per-passage coverage frequency (across N compiles) ---")
    pass_freq = Counter()
    for r in valid:
        for t in r.get("grounded_passage_probes", []):
            pass_freq[t] += 1
    for t, cnt in sorted(pass_freq.items(), key=lambda kv: (-kv[1], kv[0])):
        mark = "  <-- INJECTED" if t == INJECTED_PASSAGE else ""
        print(f"  {t}: {cnt}/{nv}{mark}")

    # RAW model-named passage surfaces distribution (localization (a) vs (b))
    print("\n--- distribution of RAW model-named passage surfaces ---")
    raw_dist = Counter()
    for r in valid:
        for ps in r.get("passage_soft", []):
            raw_dist[ps["raw_surface"]] += 1
    for surf, cnt in raw_dist.most_common():
        print(f"  {cnt:3d}x  {surf!r}")

    print(f"\nDEV_RUN_SPEND=${total_cost}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {"cell": f"{TASK}+{INJECTION}", "model": COMPILE_MODEL,
               "injected_passage": INJECTED_PASSAGE, "world_rev": WORLD_REV,
               "N": n, "valid": nv, "k_correct": k,
               "dev_run_spend_usd": total_cost,
               "fixed_plan": True, "rows": rows}
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=1),
                                          encoding="utf-8")
    print(f"detail -> {OUT_DIR / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
