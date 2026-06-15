"""D31 C0 corpus check — CATEGORY-BLIND structural scan of the SEEN tasks.

Two questions decide whether D31's write-surface policy needs the conditional
epoch-sequence / cross-worker pieces (item 5) or stays single-epoch:

  Q1. Does any seen task write a single surface MORE THAN ONCE?
  Q2. Is any surface WRITTEN by one worker and READ by another?

The scan reads ONLY the plan declarations (subplan steps) — never any failure
category, never any injection. A "write" is a PUT/POST to a content surface
(auth issuance and the gate/packaging endpoints are excluded — they are not
written-then-read content state). Output is recorded for the C0 freeze.

Usage: python -m analysis.d31_corpus_check
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import yaml

SEEN_TASKS = ["a1", "b1", "c1", "d1"]
# Endpoints that are NOT written-then-read content surfaces (category-blind:
# auth issuance, enforcement gates, packaging — by HTTP role, not by category).
NON_CONTENT_WRITE = ("/auth/token", "/repo/validate", "/docs/validate",
                     "/docs/package")
_VERB_PATH = re.compile(r"\b(GET|PUT|POST|PATCH|DELETE)\b\s+(/[^\s,;.)]+)", re.I)
_WRITE_VERB = re.compile(r"\b(PUT|PATCH)\b", re.I)        # bare write idioms ("via PUT", "PUT it back")
_FILE_TOKEN = re.compile(r"\b([\w/*]+\.(?:py|yaml|yml|md|json|txt))\b")  # file-like targets


def _is_content_write(method: str, path: str) -> bool:
    if method.upper() not in ("PUT", "POST", "PATCH"):
        return False
    return not any(path.startswith(p) for p in NON_CONTENT_WRITE)


def _is_file_like(path: str) -> bool:
    """A specific file (has an extension or a path segment under a collection),
    not a bare collection/list endpoint."""
    return bool(_FILE_TOKEN.search(path))


def scan_task(task_id: str) -> dict:
    task = yaml.safe_load((REPO / "tasks" / f"{task_id}.yaml").read_text(encoding="utf-8"))
    writes = []   # (worker, method, path)
    reads = []    # (worker, path)
    for step in task.get("plan", []):
        worker = step.get("subplan_id")
        text = step.get("step", "")
        step_get_paths = []
        for m, p in _VERB_PATH.findall(text):
            p = p.rstrip("/")
            if m.upper() == "GET":
                reads.append((worker, p))
                step_get_paths.append(p)
            elif _is_content_write(m, p):
                writes.append((worker, m.upper(), p))
        # bare write idiom ("rename ... via PUT", "PUT it back"): attribute the
        # write to the file-like content path(s) named in the SAME step — the
        # read-then-write file, plus any file-glob token (e.g. src/*.py).
        if _WRITE_VERB.search(text):
            targets = {p for p in step_get_paths if _is_file_like(p)}
            for tok in _FILE_TOKEN.findall(text):
                if not any(tok in g for g in step_get_paths):
                    targets.add(tok)               # glob like src/*.py
            for t in sorted(targets):
                if (worker, "PUT", t) not in writes:
                    writes.append((worker, "PUT", t))
    # Q1: same path written more than once (anywhere in the plan)
    write_paths = [p for _, _, p in writes]
    multi_write = sorted({p for p in write_paths if write_paths.count(p) > 1})
    # Q2: a path written by worker X and read by worker Y != X
    cross = []
    for ww, _, wp in writes:
        for rw, rp in reads:
            if rp == wp and rw != ww:
                cross.append({"path": wp, "written_by": ww, "read_by": rw})
    return {"task": task_id, "writes": writes, "reads": reads,
            "multi_write_surfaces": multi_write, "cross_worker_write_read": cross}


def main() -> int:
    rows = [scan_task(t) for t in SEEN_TASKS]
    any_multi = sorted({p for r in rows for p in r["multi_write_surfaces"]})
    any_cross = [c for r in rows for c in r["cross_worker_write_read"]]
    print("=== D31 C0 corpus check (category-blind, plan-declaration only) ===")
    for r in rows:
        wp = sorted({f"{m} {p}" for _, m, p in r["writes"]})
        print(f"\n{r['task']}: content-writes={wp or '[]'}")
        print(f"     multi-write surfaces: {r['multi_write_surfaces'] or '[]'}")
        print(f"     cross-worker write->read: {r['cross_worker_write_read'] or '[]'}")
    print("\n--- VERDICT ---")
    print(f"Q1 any surface written > once?           {'YES: ' + str(any_multi) if any_multi else 'NO'}")
    print(f"Q2 any surface written-by-A read-by-B?   {'YES: ' + str(any_cross) if any_cross else 'NO'}")
    single_epoch = not any_multi and not any_cross
    print(f"\nPOLICY: {'SINGLE-EPOCH (item 5 conditionals -> named residuals)' if single_epoch else 'NEEDS epoch-sequence and/or cross-worker rule'}")
    out = REPO / "runs" / "d31_corpus_check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"rows": rows, "any_multi_write": any_multi,
                               "any_cross_worker": any_cross,
                               "single_epoch": single_epoch}, indent=1),
                   encoding="utf-8")
    print(f"detail -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
