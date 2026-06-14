"""Seen-category extraction-recall measurement for the v2 compile prompt (D4).

Rule Zero: SEEN injections ONLY. The surface appendix is derived SEEN-ONLY (rev 1 —
no /manifest, no rev-2 held-out surface), and recall is measured against the nine
seen (task, injection) cells. The prompt is category-blind. This is NOT evaluated
against the held-out two categories or any real benchmark cell; generalization to
the held-out categories is measured only at matrix launch.

Extraction recall = of the seen cells whose injection targets a surface the plan
trusts, the fraction where the compile prompt emitted an assumption bound to that
surface. The injection defines the load-bearing surface (compiler-independent).

    python -m analysis.v2_extraction_recall          # live (sonnet) compiles
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from sentinel.compile import plan_text_from_task  # noqa: E402
from sentinel_v2.compile_probes import compile_assumptions, ground_surface  # noqa: E402
from sentinel_v2.pattern_liveness import path_samples_for_rev  # noqa: E402
from sentinel_v2.surface_appendix import (openapi_paths_for_rev,  # noqa: E402
                                          surface_appendix)
from trace import TraceWriter  # noqa: E402

# SEEN ground truth: (task, seen-injection) -> the injected surface FAMILY.
# Held-out injections (quota_cliff, silent_minor_bump) are deliberately ABSENT.
# Recall is measured on GROUNDED surfaces (dialect-normalized + instantiated), at
# the family level: did the model extract a dependency on the injected surface?
SEEN_CELLS = [
    ("a1", "endpoint_404", "/pricing/quote"),
    ("a1", "schema_drift", "/pricing/quote"),
    ("a1", "token_expiry", "/auth"),
    ("b1", "schema_drift", "/repo/files/config/settings"),
    ("b1", "gate_skip_trap", "/repo/validate"),
    ("c1", "doc_contradiction", "/docs/passages"),
    ("c1", "token_expiry", "/auth"),
    ("d1", "gate_skip_trap", "/docs/validate"),
    ("d1", "endpoint_404", "/docs/package"),
]
TASKS = ["a1", "b1", "c1", "d1"]
SAMPLES = path_samples_for_rev(1)  # SEEN-ONLY world (no held-out surface)
ROUTES = tuple(openapi_paths_for_rev(1).keys())  # real route templates (rev 1)


def compile_task(task_id: str, trace: TraceWriter) -> tuple[list, float]:
    task = yaml.safe_load((REPO_ROOT / "tasks" / f"{task_id}.yaml").read_text(
        encoding="utf-8"))
    plan = plan_text_from_task(task)
    appendix = surface_appendix(task, world_rev=1)  # SEEN-ONLY appendix (Rule Zero)
    soft, results = compile_assumptions(plan, appendix, trace)
    raw = [a.surface for a in soft.assumptions] if soft else []
    grounded = sorted({g for g in (ground_surface(s, SAMPLES, ROUTES) for s in raw) if g})
    return grounded, round(sum(r.cost_usd for r in results), 6)


def main() -> int:
    samples = int(sys.argv[sys.argv.index("--samples") + 1]) \
        if "--samples" in sys.argv else 3
    out_dir = REPO_ROOT / "runs" / "v2_d4"
    out_dir.mkdir(parents=True, exist_ok=True)
    trace = TraceWriter(out_dir / "extraction_recall_trace.jsonl",
                        run_id="v2-d4-recall", seed=0, system="v2_compile",
                        task_id="seen")

    total_cost = 0.0
    per_sample_recall = []          # recall per sample (covered cells / 9)
    cell_hits = {(t, i): 0 for t, i, _ in SEEN_CELLS}   # hits across samples
    for n in range(1, samples + 1):
        by_task = {}
        for tid in TASKS:
            surfaces, cost = compile_task(tid, trace)
            by_task[tid] = surfaces
            total_cost += cost
        covered = 0
        for tid, inj, family in SEEN_CELLS:
            hit = any(family in g for g in by_task.get(tid, []))
            cell_hits[(tid, inj)] += int(hit)
            covered += int(hit)
        per_sample_recall.append(covered / len(SEEN_CELLS))
        print(f"sample {n}: {covered}/{len(SEEN_CELLS)} = {covered/len(SEEN_CELLS):.0%}")

    cells = [{"task": t, "injection": i, "family": f,
              "hit_rate": cell_hits[(t, i)] / samples}
             for t, i, f in SEEN_CELLS]
    for c in cells:
        print(f"  {c['hit_rate']:.0%}  {c['task']}+{c['injection']} ({c['family']})")
    mean_recall = sum(per_sample_recall) / len(per_sample_recall)
    summary = {"samples": samples, "seen_cells": len(SEEN_CELLS),
               "mean_extraction_recall": round(mean_recall, 4),
               "per_sample_recall": [round(r, 4) for r in per_sample_recall],
               "cost_usd": round(total_cost, 6), "cells": cells}
    (out_dir / "extraction_recall.json").write_text(
        json.dumps(summary, indent=1), encoding="utf-8")
    trace.close()
    print(f"\nseen-category extraction recall: mean {mean_recall:.0%} over {samples} "
          f"samples (per-sample {[f'{r:.0%}' for r in per_sample_recall]}); "
          f"spend ${total_cost:.4f}; -> {out_dir/'extraction_recall.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
