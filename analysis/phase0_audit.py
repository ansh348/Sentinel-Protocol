"""Phase 0 audit tooling (deviations.md D4).

Subcommands:
  package      export runs/phase0/gpt_audit_package.md — the BLIND package for
               the external cross-vendor rater (GPT-5.5 Pro): per plan, the
               numbered plan summary with subplan ids, the assumption list,
               and the compiled tripwires as pretty-printed JSON. No scores,
               no injection specs, no KG0 thresholds.
  observable   mechanized observable bit per tripwire -> observable_mech.csv
  would-catch  empirical simulation of every planned (task, injection) pair
               against the armed compiled set -> would_catch.csv
  kg0          merge external CSV + mechanized observable + would-catch and
               print the KG0 arithmetic (thresholds live HERE, never in the
               exported package)
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PHASE0_TASKS = ("a1", "b1", "c1", "d1")
KG0_RUBRIC_THRESHOLD = 0.70      # >= 70% of tripwires score 4/4
KG0_WOULDCATCH_THRESHOLD = 0.80  # >= 80% of planned injections caught

# The mechanized url_pattern check uses the SAME classifier as the live
# matcher (deviations.md D5), so observable=1 means the matcher really can
# evaluate the gate.
from world.server import classify_url_pattern  # noqa: E402

RATER_INSTRUCTIONS = """\
# Tripwire Rating Package

You are rating compiled runtime monitors ("tripwires") for multi-agent plans.
For EACH tripwire below, output one CSV row:

    task_id,tripwire_id,parameterized,actionable,calibrated,notes

Score each property 0 or 1:

- **parameterized** — the tripwire contains concrete values, not categories.
  Example: a status list like [404, 410] is parameterized; "if the API
  changed" is not.
- **actionable** — the action hint names a specific, plan-relevant replan
  move tied to the plan's steps (not generic advice).
- **calibrated** — severity and scope are present and defensible given the
  assumption the tripwire monitors: severity reflects blast radius (CRITICAL
  only if continuing wastes the whole scope's work); scope is local with a
  subplan_id unless the assumption underpins the entire plan.

Use the plan summary and assumption list as context. Output ONLY the CSV
(with the header row above), one row per tripwire, nothing else.
"""


def load_tripwires(outdir: Path, task_id: str) -> Optional[dict]:
    path = outdir / f"tripwires_{task_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_task(task_id: str) -> dict:
    return yaml.safe_load((REPO_ROOT / "tasks" / f"{task_id}.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- package ---

def export_package(outdir: Path) -> Path:
    sections = [RATER_INSTRUCTIONS]
    authored_parts = [RATER_INSTRUCTIONS]  # blind-checked; tripwire JSON is the
    # rater's subject matter and may legitimately mention status codes etc.
    for task_id in PHASE0_TASKS:
        task = load_task(task_id)
        tripwires = load_tripwires(outdir, task_id)
        if tripwires is None:
            continue
        lines = [f"\n---\n\n## Plan {task_id}\n", "### Goal\n",
                 task["goal"].strip(), "\n### Plan steps\n"]
        for i, step in enumerate(task["plan"], start=1):
            lines.append(f"{i}. [{step['subplan_id']}] {step['step']}")
        lines.append("\n### Stated assumptions\n")
        for a in task.get("assumptions", []):
            lines.append(f"- ({a['id']}) {a['text']}")
        authored_parts.append("\n".join(lines))
        lines.append(f"\n### Compiled tripwires for plan {task_id}\n")
        lines.append("```json")
        lines.append(json.dumps(tripwires, indent=2))
        lines.append("```")
        sections.append("\n".join(lines))
    authored = "\n".join(authored_parts)
    for forbidden in ("n_inject", "endpoint_404", "schema_drift", "token_expiry",
                      "doc_contradiction", "gate_skip_trap", "KG0", "70%", "80%",
                      "injection"):
        if forbidden in authored:
            raise SystemExit(f"blind package leak: {forbidden!r} in authored text")
    package = outdir / "gpt_audit_package.md"
    package.write_text("\n".join(sections) + "\n", encoding="utf-8")
    return package


# -------------------------------------------------------------- observable --

def observable_bit(tw: dict) -> tuple[int, str]:
    sig = tw["signal"]
    reasons = []
    pattern = sig.get("url_pattern")
    if pattern:
        mode = classify_url_pattern(pattern)
        if mode is None:
            reasons.append(f"url_pattern {pattern!r} is dead "
                           "(matches no world path as glob or regex)")
    if sig.get("status_in") is not None and not sig["status_in"]:
        reasons.append("status_in empty")
    if sig.get("field_regex") is not None:
        for pointer, rx in sig["field_regex"].items():
            try:
                re.compile(rx)
            except re.error as exc:
                reasons.append(f"field_regex {pointer}: {exc}")
    if sig.get("order_violation") is not None:
        ov = sig["order_violation"]
        if not (ov.get("required_before") and ov.get("observed")):
            reasons.append("order_violation missing required_before/observed")
    return (0 if reasons else 1), "; ".join(reasons)


def export_observable(outdir: Path) -> Path:
    rows = []
    for task_id in PHASE0_TASKS:
        tripwires = load_tripwires(outdir, task_id)
        if tripwires is None:
            continue
        for tw in tripwires["tripwires"]:
            bit, reasons = observable_bit(tw)
            rows.append({"task_id": task_id, "tripwire_id": tw["id"],
                         "observable_mech": bit, "reasons": reasons})
    path = outdir / "observable_mech.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["task_id", "tripwire_id",
                                                "observable_mech", "reasons"])
        writer.writeheader()
        writer.writerows(rows)
    return path


# ------------------------------------------------------------- would-catch --

def _traffic_script(task_id: str) -> list[tuple]:
    """Canonical per-archetype traffic. Each step: (method, path, json, auth).
    Worker ids are made unique per call by the runner (avoids hard-stop)."""
    doc = {"title": "Brief", "body": "A sufficiently long body for the gate "
                                     "check to pass during simulation runs.",
           "citations": ["pol-returns"]}
    if task_id == "a1":
        return [("GET", "/inventory/items", None, True),
                ("GET", "/inventory/items/WID-001", None, True),
                ("GET", "/pricing/quote/WID-001", None, True),
                ("GET", "/shipping/rates/WID-001?dest=us-east", None, True)]
    if task_id == "b1":
        return [("GET", "/repo/files", None, False),
                ("GET", "/repo/files/config/settings.yaml", None, False),
                ("POST", "/repo/validate", None, False)]
    if task_id == "c1":
        return [("GET", "/docs/search?q=return", None, True),
                ("GET", "/docs/passages/pol-returns", None, True),
                ("POST", "/docs/validate", doc, True),
                ("POST", "/docs/package", doc, True)]
    if task_id == "d1":
        return [("GET", "/inventory/items", None, True),
                ("GET", "/docs/passages/ops-warehouses", None, True),
                ("POST", "/docs/validate", doc, True),
                ("POST", "/docs/package", doc, True)]
    raise ValueError(task_id)


def simulate_pair(task_id: str, tripwires: dict, injection: dict,
                  tmp_dir: Path) -> dict:
    """Arm the compiled set in a real world app, run canonical traffic, inject
    at the midpoint (admin path: this is tooling, not a comparative run),
    re-arm (fresh dedup/tripped state), rerun the traffic. caught == some
    tripwire's FIRST fire happens post-injection."""
    from fastapi.testclient import TestClient
    from trace import read_trace
    from world.server import create_app
    from world.state import RunConfig

    trace_path = tmp_dir / f"sim_{task_id}_{injection['type']}.jsonl"
    config = RunConfig(run_id=f"sim-{task_id}", seed=11, system="phase0-sim",
                       task_id=task_id, trace_path=str(trace_path))
    app = create_app(config)
    client = TestClient(app)
    client.post("/admin/arm_tripwires", json=tripwires)

    call_no = 0
    token = None  # shared across phases: workers reuse their run-long token,
                  # which is exactly what token_expiry invalidates

    def run_script(phase: str) -> None:
        nonlocal call_no, token
        for method, path, body, needs_auth in _traffic_script(task_id):
            call_no += 1
            headers = {"X-Worker-Id": f"sim{phase}{call_no}"}
            if needs_auth:
                if token is None:
                    token = client.post(
                        "/auth/token",
                        headers={"X-Worker-Id": f"sim{phase}{call_no}t"},
                    ).json().get("token")
                headers["Authorization"] = f"Bearer {token}"
            client.request(method, path, json=body, headers=headers)

    run_script("pre")
    pre_events = read_trace(trace_path)
    pre_fired = {e["payload"]["tripwire_id"] for e in pre_events
                 if e["event_type"] == "tripwire_fire"}

    client.post("/admin/inject", json={"type": injection["type"],
                                       "params": injection.get("params", {})})
    client.post("/admin/arm_tripwires", json=tripwires)  # reset dedup/tripped
    pre_count = len(pre_events)
    run_script("post")
    post_fires = [e["payload"] for e in read_trace(trace_path)[pre_count:]
                  if e["event_type"] == "tripwire_fire"]
    app.state.ctx.trace.close()  # Windows: tempdir cleanup needs the handle freed

    fresh = sorted({f["tripwire_id"] for f in post_fires} - pre_fired)
    caught_ids = list(fresh)
    if injection["type"] == "doc_contradiction" and not caught_ids:
        # D3: touch-triggered tripwires fire on every retrieval (also
        # pre-phase), and the JUDGE sees the contradicting content — a touch
        # fire on the injected passage IS a catch even though it is not fresh.
        passage = injection.get("params", {}).get("passage_id", "pol-returns")
        affected_path = f"/docs/passages/{passage}"
        caught_ids = [f"touch:{f['tripwire_id']}" for f in post_fires
                      if f["path"] == affected_path]
    return {"task_id": task_id, "injection": injection["type"],
            "caught": bool(caught_ids),
            "fresh_fired": ";".join(caught_ids),
            "pre_phase_fired": ";".join(sorted(pre_fired))}


def export_would_catch(outdir: Path, strict_pointers: bool = False) -> Path:
    import tempfile

    import world.server as world_server
    rows = []
    world_server.STRICT_POINTERS = strict_pointers
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for task_id in PHASE0_TASKS:
                tripwires = load_tripwires(outdir, task_id)
                if tripwires is None:
                    continue
                for injection in load_task(task_id)["injections"]:
                    rows.append(simulate_pair(task_id, tripwires, injection,
                                              Path(tmp)))
    finally:
        world_server.STRICT_POINTERS = False
    name = "would_catch_strict.csv" if strict_pointers else "would_catch.csv"
    path = outdir / name
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["task_id", "injection", "caught",
                                                "fresh_fired", "pre_phase_fired"])
        writer.writeheader()
        writer.writerows(rows)
    caught = sum(1 for r in rows if r["caught"])
    misses = [f"{r['task_id']}/{r['injection']}" for r in rows if not r["caught"]]
    print(f"{'strict' if strict_pointers else 'normalized'}: {caught}/{len(rows)}"
          f" | misses: {', '.join(misses) or 'none'}")
    return path


# ------------------------------------------------------------- audit-sample --

def export_audit_sample(outdir: Path, seed: int, n: int) -> Path:
    """Blind hand-audit export (D4): a seeded deterministic sample of the
    compiled tripwires with ALL score columns blank — first-pass scores are
    never shown to the hand auditor."""
    import random

    rows: list[dict] = []
    with open(outdir / "phase0_scoring.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    sample = random.Random(seed).sample(rows, min(n, len(rows)))
    for row in sample:
        for col in ("observable", "parameterized", "actionable", "calibrated",
                    "notes"):
            row[col] = ""
    path = outdir / f"audit_sample_seed{seed}_n{len(sample)}.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SCORING_COLUMNS)
        writer.writeheader()
        writer.writerows(sample)
    return path


# --------------------------------------------------------------------- kg0 --

def kg0(outdir: Path, external_csv: Optional[Path]) -> int:
    def read_csv(path: Path) -> list[dict]:
        with open(path, newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    observable = {(r["task_id"], r["tripwire_id"]): int(r["observable_mech"])
                  for r in read_csv(outdir / "observable_mech.csv")}
    catches = read_csv(outdir / "would_catch.csv")
    caught = sum(1 for r in catches if r["caught"] == "True")
    catch_rate = caught / len(catches) if catches else 0.0

    print(f"would-catch: {caught}/{len(catches)} planned injections "
          f"({catch_rate:.0%}); threshold >= {KG0_WOULDCATCH_THRESHOLD:.0%} "
          f"-> {'PASS' if catch_rate >= KG0_WOULDCATCH_THRESHOLD else 'FAIL'}")

    if external_csv is None or not Path(external_csv).exists():
        print("rubric 4/4 share: PENDING external rater CSV "
              "(run: kg0 --external <csv>)")
        return 1

    judged = {(r["task_id"], r["tripwire_id"]): r
              for r in read_csv(Path(external_csv))}
    total, four_of_four = 0, 0
    for key, obs in observable.items():
        total += 1
        ext = judged.get(key)
        if ext is None:
            continue
        if (obs == 1 and int(ext["parameterized"]) == 1
                and int(ext["actionable"]) == 1
                and int(ext["calibrated"]) == 1):
            four_of_four += 1
    share = four_of_four / total if total else 0.0
    print(f"rubric 4/4: {four_of_four}/{total} tripwires ({share:.0%}); "
          f"threshold >= {KG0_RUBRIC_THRESHOLD:.0%} "
          f"-> {'PASS' if share >= KG0_RUBRIC_THRESHOLD else 'FAIL'}")
    print("NOTE: external first-pass per D4; the hand audit remains "
          "authoritative before any kill decision.")
    both = (share >= KG0_RUBRIC_THRESHOLD
            and catch_rate >= KG0_WOULDCATCH_THRESHOLD)
    print(f"KG0 (both clauses): {'PASS' if both else 'FAIL'}")
    return 0 if both else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 0 audit tooling (D4)")
    parser.add_argument("command",
                        choices=["package", "observable", "would-catch", "kg0",
                                 "audit-sample"])
    parser.add_argument("--outdir", default="runs/phase0")
    parser.add_argument("--external", default=None,
                        help="external rater CSV (kg0)")
    parser.add_argument("--strict-pointers", action="store_true",
                        help="D8 ablation replay (pre-D8 pointer semantics)")
    parser.add_argument("--sample-seed", type=int, default=11)
    parser.add_argument("--sample-n", type=int, default=12)
    args = parser.parse_args(argv)
    outdir = Path(args.outdir)
    if args.command == "package":
        print(f"wrote {export_package(outdir)}")
    elif args.command == "observable":
        print(f"wrote {export_observable(outdir)}")
    elif args.command == "would-catch":
        print(f"wrote {export_would_catch(outdir, args.strict_pointers)}")
    elif args.command == "audit-sample":
        print(f"wrote {export_audit_sample(outdir, args.sample_seed, args.sample_n)}")
    elif args.command == "kg0":
        return kg0(outdir, Path(args.external) if args.external else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
